import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import type { GroupMemberInfo } from "@/api";
import type { Message } from "@/types";
import { extractEntityUid, formatCompactTokenCount } from "@/lib/utils";

interface PixelRoomSeat {
  member: GroupMemberInfo;
  left: number;
  top: number;
}

interface PixelOfficeRoomProps {
  roomName?: string | null;
  seats: PixelRoomSeat[];
  latestMessage?: Message;
  recentByMember: Map<string, Message>;
  activeSpeakerUid: string;
  avatarByUid: Map<string, string | undefined>;
  providerByUid: Map<string, string | undefined>;
  tokenLabel: string;
  turnCount: number;
  tokenCount: number;
}

interface SeatPose {
  member: GroupMemberInfo;
  x: number;
  z: number;
  angle: number;
  miniX: number;
  miniY: number;
}

interface ProjectedLabel {
  uid: string;
  name: string;
  provider?: string;
  active: boolean;
  x: number;
  y: number;
}

interface ProjectedSpeaker {
  name: string;
  text: string;
  x: number;
  y: number;
  align: "left" | "center" | "right";
}

type Vec3Tuple = [number, number, number];
type CharacterArchetype =
  | "architect"
  | "assistant"
  | "coder"
  | "data"
  | "designer"
  | "finance"
  | "leader"
  | "legal"
  | "market"
  | "mediator"
  | "ops"
  | "planner"
  | "product"
  | "researcher"
  | "reviewer"
  | "security";

interface CharacterProfile {
  archetype: CharacterArchetype;
  accent: number;
  animationPhase: number;
  animationSpeed: number;
  base: number;
  cloth: number;
  hair: number;
  seed: string;
  skin: number;
  variant: number;
  machine: boolean;
}

interface MeshOptions {
  castShadow?: boolean;
  name?: string;
  outline?: boolean;
  receiveShadow?: boolean;
  rotation?: Vec3Tuple;
}

const CENTER = new THREE.Vector3(0, 0.72, 0);
const HUMAN_SKIN = [0xf0c08a, 0xd79a67, 0xae7049, 0xf3d2a4, 0xc8875b];
const HUMAN_HAIR = [0x2a1a12, 0x59321f, 0x151923, 0x6e3a94, 0x25466d, 0x8a5a2e];
const HUMAN_CLOTHES = [0x2f6fd6, 0x2fa56f, 0xbe6a42, 0x8b57d1, 0xd2a33e, 0x2a9ea1, 0x1f2f46];
const ROBOT_BASE = [0xd7e2e6, 0x9caeba, 0x1f2a36, 0x526579, 0xe8edf0];

function shortText(message?: Message): string {
  const text = String(message?.payload.text ?? "");
  return text.length > 92 ? `${text.slice(0, 92)}...` : text;
}

function hashText(text: string): number {
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function pickColor(values: number[], seed: string, offset = 0): number {
  const hash = hashText(seed);
  return values[(hash + offset) % values.length];
}

function isMachine(member: GroupMemberInfo): boolean {
  return ["agent", "tool", "service", "resource", "bot"].includes(member.kind.toLowerCase());
}

function roleLabel(member: GroupMemberInfo, provider?: string): string {
  return provider || member.kind || member.role;
}

function seatRotationToCenter(x: number, z: number): number {
  return Math.atan2(x, z);
}

function computeSeatPoses(seats: PixelRoomSeat[]): SeatPose[] {
  const count = Math.max(seats.length, 1);
  const fixedSeats: Vec3Tuple[] =
    count === 1
      ? [[0, 0, 2.45]]
      : count === 2
        ? [[-2.65, 0, 2.05], [2.65, 0, 2.05]]
        : count === 3
          ? [[0, 0, 2.55], [-4.15, 0, 0.1], [4.15, 0, 0.1]]
          : [];
  if (fixedSeats.length > 0) {
    return seats.map(({ member }, index) => {
      const [x, , z] = fixedSeats[index];
      return {
        member,
        x,
        z,
        angle: seatRotationToCenter(x, z),
        miniX: 50 + (x / 4.8) * 34,
        miniY: 50 + (z / 3.2) * 28,
      };
    });
  }

  const xRadius = count <= 3 ? 4.35 : count <= 6 ? 4.65 : 4.95;
  const zRadius = count <= 3 ? 2.5 : count <= 6 ? 2.72 : 2.92;
  const start = Math.PI / 2;

  return seats.map(({ member }, index) => {
    const angle = start + (index * Math.PI * 2) / count;
    const x = Math.cos(angle) * xRadius;
    const z = Math.sin(angle) * zRadius;
    return {
      member,
      x,
      z,
      angle: seatRotationToCenter(x, z),
      miniX: 50 + Math.cos(angle) * 36,
      miniY: 50 + Math.sin(angle) * 30,
    };
  });
}

function projectPoint(
  point: THREE.Vector3,
  camera: THREE.Camera,
  width: number,
  height: number,
): { x: number; y: number } {
  const projected = point.clone().project(camera);
  return {
    x: (projected.x * 0.5 + 0.5) * width,
    y: (-projected.y * 0.5 + 0.5) * height,
  };
}

function frameRoom(camera: THREE.OrthographicCamera, width: number, height: number) {
  const aspect = width / Math.max(height, 1);
  const halfHeight = aspect < 0.74 ? 4.35 / Math.max(aspect, 0.52) : aspect > 1.2 ? 5.35 : 5.75;
  const halfWidth = halfHeight * aspect;

  camera.left = -halfWidth;
  camera.right = halfWidth;
  camera.top = halfHeight;
  camera.bottom = -halfHeight;
  camera.position.set(6.9, 7.35, 7.0);
  camera.lookAt(CENTER);
  camera.updateProjectionMatrix();
}

function createTextTexture(title: string, subtitle?: string): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 256;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "#172333";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#6fb7ff";
    ctx.lineWidth = 10;
    ctx.strokeRect(18, 18, canvas.width - 36, canvas.height - 36);
    ctx.fillStyle = "#edf4ff";
    ctx.font = "700 44px system-ui, sans-serif";
    ctx.fillText(title.slice(0, 18), 44, 92);
    ctx.fillStyle = "#9aaac0";
    ctx.font = "500 26px system-ui, sans-serif";
    ctx.fillText(subtitle ?? "shared context room", 44, 142);
    ctx.fillStyle = "#f0bf57";
    ctx.fillRect(44, 176, 82, 10);
    ctx.fillStyle = "#55d687";
    ctx.fillRect(144, 176, 142, 10);
    ctx.fillStyle = "#55d9ff";
    ctx.fillRect(304, 176, 98, 10);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.needsUpdate = true;
  return texture;
}

function createPatternTexture(
  base: string,
  line: string,
  accent: string,
  size = 256,
): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = base;
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = line;
    ctx.lineWidth = 2;
    for (let x = 0; x <= size; x += 32) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, size);
      ctx.stroke();
    }
    for (let y = 0; y <= size; y += 32) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(size, y);
      ctx.stroke();
    }
    ctx.fillStyle = accent;
    for (let index = 0; index < 42; index += 1) {
      const x = (index * 47) % size;
      const y = (index * 83) % size;
      ctx.globalAlpha = 0.12;
      ctx.fillRect(x, y, 8, 2);
    }
    ctx.globalAlpha = 1;
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function createWoodTexture(seed: string, base = "#7b4a2b", dark = "#4b2f24", light = "#b87945"): THREE.CanvasTexture {
  const size = 512;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  const hash = hashText(seed);
  if (ctx) {
    const gradient = ctx.createLinearGradient(0, 0, size, size);
    gradient.addColorStop(0, light);
    gradient.addColorStop(0.38, base);
    gradient.addColorStop(1, dark);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);

    for (let y = 0; y < size; y += 42) {
      ctx.fillStyle = y % 84 === 0 ? "rgba(70, 35, 20, 0.24)" : "rgba(255, 225, 180, 0.1)";
      ctx.fillRect(0, y + ((hash + y) % 7), size, 5);
    }
    for (let index = 0; index < 90; index += 1) {
      const y = (hash + index * 37) % size;
      const x = (hash * 3 + index * 53) % size;
      ctx.strokeStyle = index % 3 === 0 ? "rgba(44, 24, 16, 0.35)" : "rgba(255, 218, 170, 0.18)";
      ctx.lineWidth = 1 + (index % 2);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.bezierCurveTo(size * 0.28, y + ((index % 5) - 2) * 10, size * 0.64, y - ((index % 7) - 3) * 8, size, y + ((index % 3) - 1) * 12);
      ctx.stroke();

      if (index % 13 === 0) {
        ctx.strokeStyle = "rgba(38, 19, 12, 0.38)";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.ellipse(x, y, 18 + (index % 4) * 3, 7 + (index % 3) * 2, 0.2, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function createFabricTexture(base: string, thread: string, stitch: string): THREE.CanvasTexture {
  const size = 256;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = base;
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = thread;
    ctx.lineWidth = 1;
    for (let index = 0; index < size; index += 8) {
      ctx.globalAlpha = index % 16 === 0 ? 0.32 : 0.16;
      ctx.beginPath();
      ctx.moveTo(index, 0);
      ctx.lineTo(index, size);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, index);
      ctx.lineTo(size, index);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.strokeStyle = stitch;
    ctx.setLineDash([4, 5]);
    for (let y = 16; y < size; y += 48) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(size, y);
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function createWallTexture(): THREE.CanvasTexture {
  const size = 512;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "#b7ad9e";
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = "rgba(105, 92, 80, 0.2)";
    for (let x = 0; x < size; x += 64) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, size);
      ctx.stroke();
    }
    ctx.fillStyle = "rgba(255, 255, 255, 0.12)";
    for (let index = 0; index < 120; index += 1) {
      ctx.fillRect((index * 37) % size, (index * 71) % size, 2, 2);
    }
    ctx.fillStyle = "rgba(72, 60, 50, 0.08)";
    for (let index = 0; index < 34; index += 1) {
      ctx.fillRect((index * 97) % size, (index * 43) % size, 18, 2);
    }
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function createMetalTexture(base: string, accent: string): THREE.CanvasTexture {
  const size = 256;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = base;
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.16)";
    for (let y = 0; y < size; y += 16) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(size, y + 4);
      ctx.stroke();
    }
    ctx.fillStyle = accent;
    for (let index = 0; index < 12; index += 1) {
      ctx.globalAlpha = 0.18;
      ctx.fillRect((index * 43) % size, (index * 67) % size, 48, 5);
    }
    ctx.globalAlpha = 1;
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function createScreenTexture(accent: string, label: string): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "#0b1220";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = accent;
    ctx.lineWidth = 4;
    ctx.strokeRect(10, 10, canvas.width - 20, canvas.height - 20);
    ctx.fillStyle = accent;
    for (let index = 0; index < 6; index += 1) {
      ctx.globalAlpha = 0.25 + index * 0.08;
      ctx.fillRect(28 + index * 32, 70 - index * 7, 18, 26 + index * 7);
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#edf4ff";
    ctx.font = "700 20px system-ui, sans-serif";
    ctx.fillText(label.slice(0, 12), 28, 38);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

class MaterialLibrary {
  private readonly materials: THREE.Material[] = [];
  private readonly textures: THREE.Texture[] = [];
  readonly outline = new THREE.LineBasicMaterial({ color: 0x06101d, transparent: true, opacity: 0.62 });

  constructor() {
    this.materials.push(this.outline);
  }

  standard(color: number, roughness = 0.78, metalness = 0.02): THREE.MeshStandardMaterial {
    const material = new THREE.MeshStandardMaterial({ color, roughness, metalness });
    this.materials.push(material);
    return material;
  }

  basic(color: number, opacity = 1): THREE.MeshBasicMaterial {
    const material = new THREE.MeshBasicMaterial({
      color,
      opacity,
      transparent: opacity < 1,
    });
    this.materials.push(material);
    return material;
  }

  emissive(color: number, intensity = 0.5): THREE.MeshStandardMaterial {
    const material = new THREE.MeshStandardMaterial({
      color,
      emissive: new THREE.Color(color),
      emissiveIntensity: intensity,
      metalness: 0.08,
      roughness: 0.48,
    });
    this.materials.push(material);
    return material;
  }

  textured(texture: THREE.Texture, roughness = 0.86): THREE.MeshStandardMaterial {
    this.textures.push(texture);
    const material = new THREE.MeshStandardMaterial({ map: texture, roughness, metalness: 0.02 });
    this.materials.push(material);
    return material;
  }

  dispose() {
    for (const material of this.materials) material.dispose();
    for (const texture of this.textures) texture.dispose();
  }
}

class MeshKit {
  private readonly materials: MaterialLibrary;

  constructor(materials: MaterialLibrary) {
    this.materials = materials;
  }

  box(
    parent: THREE.Object3D,
    size: Vec3Tuple,
    position: Vec3Tuple,
    color: number,
    options: MeshOptions = {},
  ): THREE.Mesh {
    return this.mesh(parent, new THREE.BoxGeometry(...size), this.materials.standard(color), position, options);
  }

  boxWithMaterial(
    parent: THREE.Object3D,
    size: Vec3Tuple,
    position: Vec3Tuple,
    material: THREE.Material,
    options: MeshOptions = {},
  ): THREE.Mesh {
    return this.mesh(parent, new THREE.BoxGeometry(...size), material, position, options);
  }

  cylinder(
    parent: THREE.Object3D,
    radius: number,
    height: number,
    position: Vec3Tuple,
    color: number,
    radialSegments = 24,
    options: MeshOptions = {},
  ): THREE.Mesh {
    return this.mesh(
      parent,
      new THREE.CylinderGeometry(radius, radius, height, radialSegments),
      this.materials.standard(color),
      position,
      options,
    );
  }

  capsule(
    parent: THREE.Object3D,
    radius: number,
    length: number,
    position: Vec3Tuple,
    color: number,
    options: MeshOptions = {},
  ): THREE.Mesh {
    return this.mesh(parent, new THREE.CapsuleGeometry(radius, length, 6, 14), this.materials.standard(color), position, options);
  }

  sphere(
    parent: THREE.Object3D,
    radius: number,
    position: Vec3Tuple,
    color: number,
    options: MeshOptions = {},
  ): THREE.Mesh {
    return this.mesh(
      parent,
      new THREE.SphereGeometry(radius, 22, 16),
      this.materials.standard(color, 0.82, 0.01),
      position,
      { outline: false, ...options },
    );
  }

  plane(
    parent: THREE.Object3D,
    size: [number, number],
    position: Vec3Tuple,
    material: THREE.Material,
    options: MeshOptions = {},
  ): THREE.Mesh {
    return this.mesh(parent, new THREE.PlaneGeometry(...size), material, position, { outline: false, ...options });
  }

  limb(
    parent: THREE.Object3D,
    from: THREE.Vector3,
    to: THREE.Vector3,
    radius: number,
    color: number,
    name?: string,
  ) {
    const direction = to.clone().sub(from);
    const length = direction.length();
    const midpoint = from.clone().add(to).multiplyScalar(0.5);
    const mesh = this.cylinder(parent, radius, length, [midpoint.x, midpoint.y, midpoint.z], color, 14, { name, outline: false });
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
    return mesh;
  }

  mesh(
    parent: THREE.Object3D,
    geometry: THREE.BufferGeometry,
    material: THREE.Material,
    position: Vec3Tuple,
    options: MeshOptions = {},
  ): THREE.Mesh {
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(...position);
    mesh.castShadow = options.castShadow ?? true;
    mesh.receiveShadow = options.receiveShadow ?? true;
    if (options.rotation) mesh.rotation.set(...options.rotation);
    if (options.name) mesh.name = options.name;
    if (options.outline ?? true) {
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), this.materials.outline);
      mesh.add(edges);
    }
    parent.add(mesh);
    return mesh;
  }

  shadow(parent: THREE.Object3D, position: Vec3Tuple, scale: [number, number], opacity = 0.22) {
    const material = this.materials.basic(0x000000, opacity);
    const mesh = this.plane(parent, scale, position, material, { receiveShadow: false, rotation: [-Math.PI / 2, 0, 0] });
    mesh.renderOrder = 1;
  }

  transparentMaterial(color: number, opacity: number): THREE.MeshBasicMaterial {
    return this.materials.basic(color, opacity);
  }

  texturedMaterial(texture: THREE.Texture, roughness = 0.86): THREE.MeshStandardMaterial {
    return this.materials.textured(texture, roughness);
  }
}

class OfficeEnvironment {
  private readonly kit: MeshKit;
  private readonly materials: MaterialLibrary;
  private readonly roomName: string;

  constructor(
    kit: MeshKit,
    materials: MaterialLibrary,
    roomName: string,
  ) {
    this.kit = kit;
    this.materials = materials;
    this.roomName = roomName;
  }

  build(scene: THREE.Scene) {
    this.shell(scene);
    this.wallFixtures(scene);
    this.furniture(scene);
    this.table(scene);
  }

  private shell(scene: THREE.Scene) {
    const stageTexture = createPatternTexture("#7d6d5a", "#5f5144", "#c7b59c");
    stageTexture.repeat.set(8.5, 6.4);
    this.kit.mesh(
      scene,
      new THREE.BoxGeometry(28, 0.08, 22),
      this.materials.textured(stageTexture),
      [0, -0.18, 3.8],
      { name: "extended-floor", outline: false, receiveShadow: true },
    );

    const floorTexture = createPatternTexture("#927f69", "#6b5a48", "#e3d2b8");
    floorTexture.repeat.set(5.2, 3.4);
    this.kit.mesh(
      scene,
      new THREE.BoxGeometry(13.2, 0.18, 8.8),
      this.materials.textured(floorTexture),
      [0, -0.09, 0],
      { name: "floor", outline: false },
    );

    const wallTexture = createWallTexture();
    wallTexture.repeat.set(3, 1.4);
    const wallMaterial = this.materials.textured(wallTexture, 0.92);
    this.kit.boxWithMaterial(scene, [13.25, 3.0, 0.2], [0, 1.45, -4.36], wallMaterial, { name: "back-wall", receiveShadow: true });
    this.kit.boxWithMaterial(scene, [0.22, 3.0, 8.8], [-6.62, 1.45, 0], wallMaterial, { name: "left-wall", receiveShadow: true });
    this.kit.box(scene, [13.25, 0.16, 0.2], [0, 0.78, -4.24], 0x776a5d, { outline: false });
    this.kit.box(scene, [0.2, 0.16, 8.8], [-6.5, 0.78, 0], 0x776a5d, { outline: false });
    this.kit.box(scene, [13.35, 0.08, 0.28], [0, 2.95, -4.22], 0xd7c9b8, { outline: false });
    this.kit.box(scene, [0.28, 0.08, 8.9], [-6.5, 2.95, 0], 0xd0c0ad, { outline: false });

    const rugTexture = createFabricTexture("#27384c", "rgba(130, 170, 210, 0.42)", "rgba(255, 255, 255, 0.18)");
    rugTexture.repeat.set(2.8, 1.4);
    const rug = this.kit.mesh(
      scene,
      new THREE.BoxGeometry(8.9, 0.035, 4.35),
      this.materials.textured(rugTexture, 0.96),
      [0, 0.015, 0.12],
      { outline: false, receiveShadow: true },
    );
    rug.scale.z = 0.92;
    this.kit.box(scene, [8.5, 0.02, 0.05], [0, 0.055, 1.92], 0x4d6c8f, { outline: false });
    this.kit.box(scene, [8.5, 0.02, 0.05], [0, 0.055, -1.68], 0x4d6c8f, { outline: false });
  }

  private wallFixtures(scene: THREE.Scene) {
    const signTexture = createTextTexture(this.roomName || "AI Office", "multi-agent team room");
    const sign = this.kit.plane(
      scene,
      [2.3, 1.15],
      [-0.55, 1.86, -4.235],
      this.materials.textured(signTexture, 0.62),
      { name: "room-status-display", rotation: [0, 0, 0] },
    );
    sign.castShadow = false;

    this.door(scene, [-5.3, 0, -4.18]);
    this.kit.box(scene, [0.92, 0.86, 0.12], [3.92, 1.68, -4.2], 0xd4ccc2, { name: "chart-frame" });
    this.kit.box(scene, [0.1, 0.45, 0.08], [3.66, 1.44, -4.11], 0xf0bf57, { outline: false });
    this.kit.box(scene, [0.1, 0.68, 0.08], [3.89, 1.56, -4.11], 0x55d687, { outline: false });
    this.kit.box(scene, [0.1, 0.55, 0.08], [4.12, 1.49, -4.11], 0x6fb7ff, { outline: false });

    this.kit.box(scene, [0.62, 0.78, 0.08], [5.16, 1.56, -4.19], 0x8b785f, { name: "small-art" });
    this.kit.box(scene, [0.42, 0.58, 0.05], [5.16, 1.56, -4.12], 0x28384d, { outline: false });
    this.kit.box(scene, [0.08, 0.28, 0.04], [5.07, 1.5, -4.08], 0xf0bf57, { outline: false });
    this.kit.box(scene, [0.08, 0.38, 0.04], [5.21, 1.55, -4.08], 0x55d9ff, { outline: false });
  }

  private door(scene: THREE.Scene, position: Vec3Tuple) {
    const group = new THREE.Group();
    group.position.set(...position);
    this.kit.box(group, [0.98, 2.18, 0.18], [0, 1.1, 0], 0x5d3825, { name: "door" });
    this.kit.box(group, [0.76, 0.74, 0.08], [0, 1.46, 0.11], 0x7da6b2, { outline: false });
    this.kit.box(group, [0.08, 0.12, 0.05], [0.34, 1.0, 0.13], 0xf0bf57, { outline: false });
    this.kit.box(group, [1.16, 2.34, 0.11], [0, 1.1, -0.08], 0x34251e, { outline: false });
    scene.add(group);
  }

  private furniture(scene: THREE.Scene) {
    this.bookshelf(scene, [-5.92, 0, -2.52]);
    this.credenza(scene, [5.52, 0, 2.78]);
    this.waterCooler(scene, [5.42, 0, -2.2]);
    this.plant(scene, [-5.72, 0, 2.72], 0.78);
    this.plant(scene, [4.78, 0, -3.15], 0.66);
    this.printer(scene, [5.15, 0.9, 2.78]);
  }

  private bookshelf(scene: THREE.Scene, position: Vec3Tuple) {
    const shelf = new THREE.Group();
    shelf.position.set(...position);
    shelf.rotation.y = Math.PI / 2;
    const wood = createWoodTexture("bookshelf", "#5a3926", "#2c1d18", "#8a5632");
    wood.repeat.set(1.2, 2.2);
    this.kit.boxWithMaterial(shelf, [1.16, 2.1, 0.52], [0, 1.05, 0], this.materials.textured(wood, 0.84), { name: "bookshelf" });
    for (let row = 0; row < 4; row += 1) {
      this.kit.box(shelf, [1.06, 0.06, 0.56], [0, 0.38 + row * 0.45, 0], 0x2c1d18, { outline: false });
      for (let book = 0; book < 5; book += 1) {
        const color = [0xb87938, 0x4f8f57, 0x526fa3, 0xd0a33f, 0x7b466b][(row + book) % 5];
        this.kit.box(shelf, [0.09, 0.24 + (book % 2) * 0.07, 0.18], [-0.4 + book * 0.18, 0.53 + row * 0.45, -0.18], color, { outline: false });
      }
    }
    scene.add(shelf);
  }

  private credenza(scene: THREE.Scene, position: Vec3Tuple) {
    const cabinet = new THREE.Group();
    cabinet.position.set(...position);
    const cabinetWood = createWoodTexture("cabinet", "#6b422d", "#3a241b", "#98603b");
    cabinetWood.repeat.set(1.4, 0.8);
    this.kit.boxWithMaterial(cabinet, [1.42, 0.78, 0.76], [0, 0.39, 0], this.materials.textured(cabinetWood, 0.82), { name: "cabinet" });
    this.kit.boxWithMaterial(cabinet, [1.32, 0.08, 0.82], [0, 0.82, 0], this.materials.textured(createWoodTexture("cabinet-top", "#8a5632", "#4f2f20", "#bd7744"), 0.78), { outline: false });
    this.kit.box(cabinet, [0.06, 0.32, 0.06], [-0.28, 0.42, -0.41], 0xf0bf57, { outline: false });
    this.kit.box(cabinet, [0.06, 0.32, 0.06], [0.28, 0.42, -0.41], 0xf0bf57, { outline: false });
    scene.add(cabinet);
  }

  private printer(scene: THREE.Scene, position: Vec3Tuple) {
    const printer = new THREE.Group();
    printer.position.set(...position);
    this.kit.box(printer, [0.72, 0.32, 0.48], [0, 0.16, 0], 0xaeb8bf, { name: "printer" });
    this.kit.box(printer, [0.62, 0.06, 0.36], [0, 0.35, -0.02], 0x2d3a45, { outline: false });
    this.kit.box(printer, [0.48, 0.02, 0.26], [0, 0.45, -0.12], 0xe9edf0, { outline: false });
    scene.add(printer);
  }

  private waterCooler(scene: THREE.Scene, position: Vec3Tuple) {
    const cooler = new THREE.Group();
    cooler.position.set(...position);
    this.kit.box(cooler, [0.58, 0.92, 0.46], [0, 0.54, 0], 0xc5cdd0, { name: "water-cooler" });
    this.kit.cylinder(cooler, 0.26, 0.54, [0, 1.28, 0], 0x8ed1ef, 24, { outline: false });
    this.kit.cylinder(cooler, 0.2, 0.22, [0, 1.65, 0], 0x69bde3, 24, { outline: false });
    this.kit.box(cooler, [0.32, 0.08, 0.07], [0, 0.7, -0.26], 0x5d6b75, { outline: false });
    scene.add(cooler);
  }

  private plant(parent: THREE.Object3D, position: Vec3Tuple, scale: number) {
    const plant = new THREE.Group();
    plant.position.set(...position);
    plant.scale.setScalar(scale);
    this.kit.cylinder(plant, 0.22, 0.45, [0, 0.23, 0], 0x704327, 12);
    for (let index = 0; index < 9; index += 1) {
      const angle = (index * Math.PI * 2) / 9;
      const leaf = this.kit.sphere(plant, 0.24, [Math.cos(angle) * 0.24, 0.62 + (index % 3) * 0.08, Math.sin(angle) * 0.2], 0x2f7a45 + (index % 2) * 0x0b2106);
      leaf.scale.set(1.25, 0.55, 0.84);
    }
    parent.add(plant);
  }

  private table(scene: THREE.Scene) {
    const table = new THREE.Group();
    table.position.set(0, 0, 0.12);
    const tableWood = createWoodTexture("conference-table", "#7b4a2b", "#472916", "#b87945");
    tableWood.repeat.set(3.2, 1.15);
    const tableMaterial = this.materials.textured(tableWood, 0.66);

    this.kit.shadow(table, [0, 0.02, 0], [8.6, 3.8], 0.18);
    this.kit.boxWithMaterial(table, [6.95, 0.34, 2.72], [0, 0.72, 0], tableMaterial, { name: "table-center" });
    const leftCap = this.kit.mesh(table, new THREE.CylinderGeometry(1.36, 1.36, 0.34, 48), tableMaterial, [-3.48, 0.72, 0]);
    leftCap.scale.x = 0.76;
    const rightCap = this.kit.mesh(table, new THREE.CylinderGeometry(1.36, 1.36, 0.34, 48), tableMaterial, [3.48, 0.72, 0]);
    rightCap.scale.x = 0.76;

    for (let index = 0; index < 6; index += 1) {
      this.kit.box(table, [6.65, 0.035, 0.045], [0, 0.93, -1.0 + index * 0.38], index % 2 ? 0x6a3f28 : 0x9b6137, { outline: false });
    }
    this.kit.box(table, [6.55, 0.035, 0.04], [0, 0.97, -1.24], 0xc08149, { outline: false });
    for (const x of [-2.55, 0, 2.55]) {
      this.kit.cylinder(table, 0.11, 0.72, [x, 0.34, -0.86], 0x3d291d, 14);
      this.kit.cylinder(table, 0.11, 0.72, [x, 0.34, 0.86], 0x3d291d, 14);
    }

    this.tableProp(table, [-1.35, 0.99, -0.72], "document");
    this.tableProp(table, [1.78, 0.99, -0.58], "document");
    this.tableProp(table, [-2.38, 0.99, 0.48], "laptop");
    this.tableProp(table, [2.55, 0.99, 0.42], "laptop");
    this.tableProp(table, [-0.36, 0.99, 0.82], "mug");
    this.tableProp(table, [1.0, 0.99, -0.92], "mug");
    this.plant(table, [0, 0.96, 0.02], 0.42);
    this.tableHologram(table);

    scene.add(table);
  }

  private tableHologram(parent: THREE.Group) {
    const plateMaterial = this.materials.basic(0x55d9ff, 0.16);
    const ringMaterial = this.materials.basic(0x69f2b4, 0.34);
    const plate = this.kit.mesh(
      parent,
      new THREE.CylinderGeometry(0.82, 0.82, 0.018, 48),
      plateMaterial,
      [0, 1.045, 0.02],
      { name: "anim-hologram", outline: false },
    );
    plate.userData.anim = "hologram";
    plate.userData.baseY = plate.position.y;
    const ring = this.kit.mesh(
      parent,
      new THREE.RingGeometry(0.9, 1.02, 48),
      ringMaterial,
      [0, 1.08, 0.02],
      { name: "anim-hologram-ring", outline: false, rotation: [-Math.PI / 2, 0, 0] },
    );
    ring.userData.anim = "hologram-ring";
    for (let index = 0; index < 5; index += 1) {
      const angle = (index * Math.PI * 2) / 5;
      const bar = this.kit.box(
        parent,
        [0.08, 0.12 + index * 0.045, 0.08],
        [Math.cos(angle) * 0.45, 1.16 + index * 0.015, Math.sin(angle) * 0.28],
        index % 2 ? 0x69f2b4 : 0x55d9ff,
        { name: "anim-hologram-bar", outline: false },
      );
      bar.userData.anim = "hologram-bar";
      bar.userData.phase = index * 0.7;
      bar.userData.baseY = bar.position.y;
    }
  }

  private tableProp(parent: THREE.Group, position: Vec3Tuple, kind: "document" | "laptop" | "mug") {
    if (kind === "document") {
      const paper = this.kit.box(parent, [0.48, 0.025, 0.34], position, 0xe8ded0, { outline: true });
      paper.rotation.y = position[0] > 0 ? -0.22 : 0.18;
      this.kit.box(parent, [0.32, 0.01, 0.025], [position[0], position[1] + 0.02, position[2] - 0.07], 0x8da0b0, { outline: false });
      return;
    }
    if (kind === "laptop") {
      const laptop = this.kit.box(parent, [0.58, 0.06, 0.38], position, 0x344554, { outline: true });
      laptop.rotation.y = position[0] > 0 ? -0.26 : 0.26;
      this.kit.box(parent, [0.46, 0.03, 0.03], [position[0], position[1] + 0.06, position[2] - 0.18], 0x55d9ff, { outline: false });
      return;
    }
    this.kit.cylinder(parent, 0.13, 0.22, position, 0xe3d5c5, 16);
  }
}

class CharacterDesigner {
  private readonly kit: MeshKit;

  constructor(kit: MeshKit) {
    this.kit = kit;
  }

  create(scene: THREE.Scene, pose: SeatPose, provider?: string, active = false): THREE.Group {
    const profile = this.profile(pose.member, provider);
    const seat = new THREE.Group();
    seat.position.set(pose.x, 0, pose.z);
    seat.rotation.y = pose.angle;
    seat.name = `seat-${pose.member.entity_uid}`;
    seat.userData.baseY = 0;
    seat.userData.phase = profile.animationPhase;
    seat.userData.speed = profile.animationSpeed;

    this.chair(seat, profile, active);
    if (profile.machine) this.robot(seat, profile, active);
    else this.human(seat, profile, active);
    this.roleProp(seat, profile);
    if (active) this.activeRing(seat, profile.accent);

    scene.add(seat);
    return seat;
  }

  private profile(member: GroupMemberInfo, provider?: string): CharacterProfile {
    const seed = `${member.name}:${member.entity_uid}:${provider ?? ""}`;
    const name = member.name.toLowerCase();
    const service = (provider ?? "").toLowerCase();
    const machine = isMachine(member);
    let archetype: CharacterArchetype = machine ? "assistant" : "leader";

    if (name.includes("codey") || name.includes("coder") || name.includes("engineer") || service.includes("codex")) archetype = "coder";
    if (name.includes("planner")) archetype = "planner";
    if (name.includes("review") || name.includes("qa") || name.includes("test")) archetype = "reviewer";
    if (name.includes("data") || name.includes("analyst")) archetype = "data";
    if (name.includes("design") || name.includes("wizard")) archetype = "designer";
    if (name.includes("ops") || name.includes("devops")) archetype = "ops";
    if (name.includes("product") || name.includes("pm")) archetype = "product";
    if (name.includes("research")) archetype = "researcher";
    if (name.includes("architect")) archetype = "architect";
    if (name.includes("hr") || name.includes("people")) archetype = "mediator";
    if (name.includes("market")) archetype = "market";
    if (name.includes("legal")) archetype = "legal";
    if (name.includes("finance")) archetype = "finance";
    if (name.includes("security") || name.includes("hack") || name.includes("defense")) archetype = "security";
    if (!machine && member.role === "owner") archetype = "leader";

    const archetypeColors: Record<CharacterArchetype, [number, number]> = {
      architect: [0x344554, 0x73c6ff],
      assistant: [0xe8edf0, 0x55d9ff],
      coder: [0x2fa56f, 0x69f2b4],
      data: [0xd7e2e6, 0x55d9ff],
      designer: [0x8b57d1, 0xff8fd7],
      finance: [0x2f6fd6, 0xf0bf57],
      leader: [0x25466d, 0xf0bf57],
      legal: [0x1f2f46, 0xa9b6c4],
      market: [0x2fa56f, 0xf3cf5a],
      mediator: [0x8a5a2e, 0x69d5ff],
      ops: [0x244c82, 0x69f2b4],
      planner: [0x2fa56f, 0x69f2b4],
      product: [0x2a9ea1, 0xf0bf57],
      researcher: [0xf4efe4, 0x8f8cff],
      reviewer: [0x5967d8, 0xf0bf57],
      security: [0x1b1f2a, 0xff735c],
    };

    const [base, accent] = archetypeColors[archetype];
    const variant = hashText(seed) % 5;
    return {
      archetype,
      accent,
      animationPhase: (hashText(seed) % 628) / 100,
      animationSpeed: 0.85 + (hashText(`${seed}:speed`) % 40) / 100,
      base: machine ? pickColor(ROBOT_BASE, seed, 1) : base,
      cloth: machine ? base : pickColor(HUMAN_CLOTHES, seed, 11),
      hair: pickColor(HUMAN_HAIR, seed, 5),
      seed,
      skin: pickColor(HUMAN_SKIN, seed, 2),
      variant,
      machine,
    };
  }

  private chair(parent: THREE.Group, profile: CharacterProfile, active: boolean) {
    const fabricBase = active ? "#35679b" : profile.archetype === "security" ? "#222938" : "#27415f";
    const fabric = createFabricTexture(fabricBase, "rgba(160, 200, 240, 0.28)", "rgba(255, 255, 255, 0.18)");
    fabric.repeat.set(1.4, 1.0);
    const fabricMaterial = this.kit.texturedMaterial(fabric, 0.96);
    this.kit.shadow(parent, [0, 0.025, 0.08], [1.2, 1.15], active ? 0.25 : 0.18);
    this.kit.boxWithMaterial(parent, [0.94, 0.22, 0.78], [0, 0.36, 0.02], fabricMaterial, { name: "chair-seat" });
    this.kit.boxWithMaterial(parent, [0.96, 0.92, 0.18], [0, 0.86, 0.42], fabricMaterial, { name: "chair-back" });
    this.kit.box(parent, [0.12, 0.52, 0.12], [-0.36, 0.08, -0.25], 0x172235);
    this.kit.box(parent, [0.12, 0.52, 0.12], [0.36, 0.08, -0.25], 0x172235);
    this.kit.box(parent, [0.88, 0.12, 0.12], [0, 0.62, -0.34], 0x172235, { outline: false });
    this.kit.cylinder(parent, 0.12, 0.52, [0, 0.1, 0.04], 0x172235, 12);
    for (const x of [-0.34, 0.34]) {
      for (const z of [-0.26, 0.34]) {
        this.kit.sphere(parent, 0.08, [x, 0.03, z], 0x101823);
      }
    }
  }

  private human(parent: THREE.Group, profile: CharacterProfile, active: boolean) {
    const cloth = active ? profile.accent : profile.cloth;
    const clothTexture = createFabricTexture(`#${cloth.toString(16).padStart(6, "0")}`, "rgba(255, 255, 255, 0.18)", "rgba(0, 0, 0, 0.12)");
    clothTexture.repeat.set(0.7, 1.2);
    this.kit.mesh(
      parent,
      new THREE.CapsuleGeometry(0.22, 0.46, 6, 14),
      this.kit.texturedMaterial(clothTexture, 0.92),
      [0, 1.02, -0.12],
      { name: "human-torso" },
    );
    const head = this.kit.sphere(parent, 0.29, [0, 1.5, -0.14], profile.skin, { name: "anim-head" });
    head.userData.anim = "head-breathe";
    head.userData.baseY = head.position.y;
    head.userData.phase = profile.animationPhase;
    this.hair(parent, profile);
    this.kit.limb(parent, new THREE.Vector3(-0.22, 1.16, -0.15), new THREE.Vector3(-0.54, 0.88, -0.5), 0.055, profile.skin);
    this.kit.limb(parent, new THREE.Vector3(0.22, 1.16, -0.15), new THREE.Vector3(0.5, 0.9, -0.5), 0.055, profile.skin);
    this.kit.limb(parent, new THREE.Vector3(-0.11, 0.78, -0.18), new THREE.Vector3(-0.28, 0.42, -0.46), 0.07, 0x1a2533);
    this.kit.limb(parent, new THREE.Vector3(0.11, 0.78, -0.18), new THREE.Vector3(0.28, 0.42, -0.46), 0.07, 0x1a2533);

    if (profile.archetype === "leader") {
      this.kit.box(parent, [0.08, 0.34, 0.035], [0, 1.07, -0.35], 0xf0bf57, { outline: false });
      this.kit.box(parent, [0.34, 0.05, 0.05], [0, 1.31, -0.34], 0xf4efe4, { outline: false });
    }
    if (profile.archetype === "designer") {
      this.kit.box(parent, [0.62, 0.08, 0.08], [0, 1.29, -0.2], 0xff8fd7, { outline: false });
      this.kit.sphere(parent, 0.09, [-0.35, 1.44, -0.1], 0x8b57d1);
    }
    if (profile.archetype === "ops") {
      this.kit.cylinder(parent, 0.31, 0.1, [0, 1.74, -0.14], 0x244c82, 24);
      this.kit.box(parent, [0.24, 0.05, 0.18], [0, 1.73, -0.42], 0x244c82, { outline: false });
    }
    if (profile.archetype === "architect") {
      this.kit.box(parent, [0.5, 0.025, 0.36], [0.22, 0.91, -0.62], 0xd8eef6, { name: "architect-blueprint" });
      this.kit.box(parent, [0.38, 0.01, 0.025], [0.22, 0.93, -0.7], 0x55d9ff, { outline: false });
      this.kit.cylinder(parent, 0.04, 0.48, [-0.42, 1.12, -0.28], 0x73c6ff, 10, { rotation: [0.7, 0, 0.4] });
    }
    if (profile.archetype === "researcher") {
      this.kit.box(parent, [0.42, 0.5, 0.035], [0.44, 0.98, -0.46], 0xf4efe4, { name: "research-notebook" });
      this.kit.box(parent, [0.22, 0.035, 0.02], [0.44, 1.1, -0.49], 0x8f8cff, { outline: false });
      this.glasses(parent, 0x202a34);
    }
    if (profile.archetype === "product") {
      this.kit.box(parent, [0.11, 0.11, 0.025], [-0.22, 1.16, -0.36], 0xf0bf57, { outline: false });
      this.kit.box(parent, [0.11, 0.11, 0.025], [0, 1.18, -0.36], 0x55d687, { outline: false });
      this.kit.box(parent, [0.11, 0.11, 0.025], [0.22, 1.15, -0.36], 0x55d9ff, { outline: false });
    }
    if (profile.archetype === "mediator") {
      this.headset(parent, profile.accent);
    }
  }

  private hair(parent: THREE.Group, profile: CharacterProfile) {
    if (profile.archetype === "designer") {
      const hair = this.kit.sphere(parent, 0.31, [0, 1.58, -0.12], 0x6e3a94);
      hair.scale.set(1.05, 0.65, 1.0);
      this.kit.limb(parent, new THREE.Vector3(-0.23, 1.55, -0.1), new THREE.Vector3(-0.38, 1.1, -0.2), 0.08, 0x6e3a94);
      return;
    }
    const cap = this.kit.sphere(parent, 0.305, [0, 1.6, -0.14], profile.hair);
    cap.scale.set(1.04, 0.48, 1);
    this.kit.box(parent, [0.42, 0.12, 0.16], [0, 1.54, -0.35], profile.hair, { outline: false });
  }

  private glasses(parent: THREE.Group, color: number) {
    this.kit.box(parent, [0.16, 0.07, 0.025], [-0.11, 1.5, -0.405], color, { outline: false });
    this.kit.box(parent, [0.16, 0.07, 0.025], [0.11, 1.5, -0.405], color, { outline: false });
    this.kit.box(parent, [0.06, 0.025, 0.025], [0, 1.5, -0.407], color, { outline: false });
  }

  private headset(parent: THREE.Group, accent: number) {
    this.kit.cylinder(parent, 0.018, 0.58, [0, 1.66, -0.14], 0x101722, 8, { rotation: [0, 0, Math.PI / 2] });
    this.kit.sphere(parent, 0.075, [-0.31, 1.54, -0.14], accent);
    this.kit.sphere(parent, 0.075, [0.31, 1.54, -0.14], accent);
    this.kit.limb(parent, new THREE.Vector3(0.24, 1.47, -0.23), new THREE.Vector3(0.46, 1.32, -0.42), 0.018, accent);
  }

  private robot(parent: THREE.Group, profile: CharacterProfile, active: boolean) {
    if (profile.archetype === "security") {
      this.securityBot(parent, profile, active);
      return;
    }
    if (profile.archetype === "reviewer") {
      this.reviewerBot(parent, profile, active);
      return;
    }
    if (profile.archetype === "planner") {
      this.plannerBot(parent, profile, active);
      return;
    }
    if (profile.archetype === "coder") {
      this.coderBot(parent, profile, active);
      return;
    }
    if (profile.archetype === "data") {
      this.dataBot(parent, profile, active);
      return;
    }
    if (profile.archetype === "ops") {
      this.opsBot(parent, profile, active);
      return;
    }
    if (profile.archetype === "finance" || profile.archetype === "legal" || profile.archetype === "market") {
      this.domainBot(parent, profile, active);
      return;
    }
    this.assistantBot(parent, profile, active);
  }

  private assistantBot(parent: THREE.Group, profile: CharacterProfile, active: boolean) {
    const accent = active ? 0xf0bf57 : profile.accent;
    this.kit.capsule(parent, 0.24, 0.42, [0, 1.0, -0.12], 0xe8edf0, { name: "assistant-body" });
    this.kit.box(parent, [0.62, 0.48, 0.46], [0, 1.43, -0.12], 0xd7e2e6, { name: "assistant-head" });
    this.kit.box(parent, [0.44, 0.18, 0.05], [0, 1.45, -0.37], 0x16202d, { outline: false });
    this.kit.box(parent, [0.13, 0.1, 0.04], [-0.12, 1.46, -0.41], accent, { outline: false });
    this.kit.box(parent, [0.13, 0.1, 0.04], [0.12, 1.46, -0.41], accent, { outline: false });
    this.kit.limb(parent, new THREE.Vector3(-0.34, 1.04, -0.12), new THREE.Vector3(-0.52, 0.86, -0.48), 0.055, 0x8796a3);
    this.kit.limb(parent, new THREE.Vector3(0.34, 1.04, -0.12), new THREE.Vector3(0.52, 0.86, -0.48), 0.055, 0x8796a3);
  }

  private plannerBot(parent: THREE.Group, profile: CharacterProfile, active: boolean) {
    const accent = active ? 0xf0bf57 : profile.accent;
    this.kit.capsule(parent, 0.23, 0.44, [0, 1.0, -0.12], 0x2f6f56, { name: "planner-body" });
    this.kit.box(parent, [0.6, 0.48, 0.42], [0, 1.42, -0.12], 0xd8e6dc, { name: "planner-head" });
    this.kit.cylinder(parent, 0.31, 0.12, [0, 1.7, -0.12], 0x2fa56f, 24);
    this.kit.box(parent, [0.28, 0.05, 0.16], [0, 1.68, -0.41], 0x2fa56f, { outline: false });
    this.kit.box(parent, [0.38, 0.14, 0.05], [0, 1.43, -0.35], 0x16202d, { outline: false });
    this.kit.box(parent, [0.12, 0.08, 0.04], [-0.11, 1.44, -0.39], accent, { outline: false });
    this.kit.box(parent, [0.12, 0.08, 0.04], [0.11, 1.44, -0.39], accent, { outline: false });
    this.kit.box(parent, [0.46, 0.03, 0.32], [0.2, 0.9, -0.62], 0x1d3f42, { outline: true });
    this.kit.box(parent, [0.32, 0.02, 0.2], [0.2, 0.93, -0.63], accent, { outline: false });
  }

  private coderBot(parent: THREE.Group, profile: CharacterProfile, active: boolean) {
    const accent = active ? 0xf0bf57 : profile.accent;
    this.kit.capsule(parent, 0.22, 0.44, [0, 1.0, -0.12], 0x27384c, { name: "coder-body" });
    this.kit.box(parent, [0.62, 0.46, 0.44], [0, 1.42, -0.12], 0xd8e6dc, { name: "coder-head" });
    const visor = this.kit.box(parent, [0.46, 0.18, 0.05], [0, 1.43, -0.38], 0x0b1220, { name: "anim-screen" });
    visor.material = this.kit.texturedMaterial(createScreenTexture("#69f2b4", "CODE"), 0.42);
    visor.userData.anim = "screen-pulse";
    visor.userData.phase = profile.animationPhase;
    this.kit.box(parent, [0.42, 0.035, 0.26], [0.32, 0.9, -0.62], 0x18242e, { name: "coder-keyboard" });
    for (let index = 0; index < 5; index += 1) {
      this.kit.box(parent, [0.04, 0.012, 0.03], [0.16 + index * 0.07, 0.93, -0.72], accent, { outline: false });
    }
    this.kit.limb(parent, new THREE.Vector3(-0.34, 1.04, -0.12), new THREE.Vector3(-0.52, 0.88, -0.55), 0.055, 0x8796a3);
    this.kit.limb(parent, new THREE.Vector3(0.34, 1.04, -0.12), new THREE.Vector3(0.52, 0.88, -0.55), 0.055, 0x8796a3);
  }

  private reviewerBot(parent: THREE.Group, profile: CharacterProfile, active: boolean) {
    const accent = active ? 0xf0bf57 : profile.accent;
    this.kit.box(parent, [0.52, 0.62, 0.36], [0, 0.98, -0.12], 0x5967d8, { name: "reviewer-body" });
    this.kit.box(parent, [0.64, 0.5, 0.46], [0, 1.43, -0.12], 0xcfd8f3, { name: "reviewer-head" });
    this.kit.box(parent, [0.5, 0.05, 0.06], [0, 1.47, -0.4], 0x171b28, { outline: false });
    this.kit.box(parent, [0.14, 0.1, 0.04], [-0.13, 1.47, -0.43], accent, { outline: false });
    this.kit.box(parent, [0.14, 0.1, 0.04], [0.13, 1.47, -0.43], accent, { outline: false });
    this.kit.box(parent, [0.32, 0.44, 0.04], [-0.52, 0.92, -0.44], 0xe8ded0, { name: "reviewer-clipboard" });
    this.kit.box(parent, [0.22, 0.035, 0.03], [-0.52, 1.08, -0.47], 0xf0bf57, { outline: false });
    this.kit.limb(parent, new THREE.Vector3(0.32, 1.05, -0.12), new THREE.Vector3(0.52, 0.9, -0.45), 0.055, 0x8796a3);
  }

  private dataBot(parent: THREE.Group, profile: CharacterProfile, active: boolean) {
    const accent = active ? 0xf0bf57 : profile.accent;
    this.kit.box(parent, [0.56, 0.58, 0.34], [0, 0.98, -0.12], 0x334f66, { name: "data-body" });
    this.kit.box(parent, [0.62, 0.42, 0.5], [0, 1.43, -0.12], 0xd7e2e6, { name: "data-head" });
    const screen = this.kit.box(parent, [0.42, 0.18, 0.05], [0, 1.44, -0.4], 0x101722, { name: "anim-screen", outline: false });
    screen.material = this.kit.texturedMaterial(createScreenTexture("#55d9ff", "DATA"), 0.42);
    screen.userData.anim = "screen-pulse";
    screen.userData.phase = profile.animationPhase;
    for (let index = 0; index < 3; index += 1) {
      this.kit.box(parent, [0.06, 0.06 + index * 0.035, 0.04], [-0.12 + index * 0.12, 1.41 + index * 0.018, -0.44], accent, { outline: false });
    }
    this.kit.cylinder(parent, 0.035, 0.28, [0, 1.76, -0.12], 0x202a34, 10);
    this.kit.sphere(parent, 0.07, [0, 1.94, -0.12], accent);
  }

  private opsBot(parent: THREE.Group, profile: CharacterProfile, active: boolean) {
    const accent = active ? 0xf0bf57 : profile.accent;
    this.kit.box(parent, [0.58, 0.58, 0.36], [0, 0.98, -0.12], 0x244c82, { name: "ops-body" });
    this.kit.box(parent, [0.64, 0.46, 0.44], [0, 1.42, -0.12], 0xd7e2e6, { name: "ops-head" });
    this.kit.cylinder(parent, 0.34, 0.12, [0, 1.72, -0.12], 0xf0bf57, 24);
    this.kit.box(parent, [0.28, 0.05, 0.18], [0, 1.7, -0.42], 0xf0bf57, { outline: false });
    const wrench = this.kit.limb(parent, new THREE.Vector3(0.42, 1.0, -0.42), new THREE.Vector3(0.66, 1.28, -0.58), 0.035, accent);
    wrench.name = "anim-prop";
    wrench.userData.anim = "prop-wiggle";
    wrench.userData.phase = profile.animationPhase;
    this.kit.sphere(parent, 0.08, [0.7, 1.32, -0.62], accent);
  }

  private domainBot(parent: THREE.Group, profile: CharacterProfile, active: boolean) {
    const accent = active ? 0xf0bf57 : profile.accent;
    const metal = createMetalTexture("#4d5b69", `#${accent.toString(16).padStart(6, "0")}`);
    metal.repeat.set(1.2, 1.2);
    this.kit.mesh(
      parent,
      new THREE.BoxGeometry(0.58, 0.58, 0.36),
      this.kit.texturedMaterial(metal, 0.52),
      [0, 0.98, -0.12],
      { name: `${profile.archetype}-body` },
    );
    this.kit.box(parent, [0.62, 0.46, 0.44], [0, 1.42, -0.12], 0xe8edf0, { name: `${profile.archetype}-head` });
    const screen = this.kit.box(parent, [0.42, 0.16, 0.05], [0, 1.43, -0.39], 0x0b1220, { name: "anim-screen", outline: false });
    screen.material = this.kit.texturedMaterial(createScreenTexture(`#${accent.toString(16).padStart(6, "0")}`, profile.archetype.toUpperCase()), 0.42);
    screen.userData.anim = "screen-pulse";
    screen.userData.phase = profile.animationPhase;
  }

  private securityBot(parent: THREE.Group, profile: CharacterProfile, active: boolean) {
    const accent = active ? 0xf0bf57 : profile.accent;
    this.kit.box(parent, [0.56, 0.6, 0.36], [0, 0.98, -0.12], 0x1b1f2a, { name: "security-body" });
    this.kit.box(parent, [0.62, 0.48, 0.46], [0, 1.42, -0.12], 0x202634, { name: "security-head" });
    this.kit.box(parent, [0.46, 0.16, 0.05], [0, 1.45, -0.4], 0x0d1118, { outline: false });
    this.kit.box(parent, [0.12, 0.08, 0.04], [-0.12, 1.45, -0.44], accent, { outline: false });
    this.kit.box(parent, [0.12, 0.08, 0.04], [0.12, 1.45, -0.44], accent, { outline: false });
    this.kit.limb(parent, new THREE.Vector3(-0.2, 1.66, -0.12), new THREE.Vector3(-0.38, 1.92, -0.12), 0.035, accent);
    this.kit.limb(parent, new THREE.Vector3(0.2, 1.66, -0.12), new THREE.Vector3(0.38, 1.92, -0.12), 0.035, accent);
    this.kit.box(parent, [0.38, 0.42, 0.04], [0.48, 0.96, -0.46], 0x4c1f24, { name: "security-shield" });
  }

  private roleProp(parent: THREE.Group, profile: CharacterProfile) {
    if (profile.archetype === "market") {
      this.kit.box(parent, [0.44, 0.02, 0.26], [0.26, 0.92, -0.62], 0x2fa56f, { outline: true });
      this.kit.box(parent, [0.06, 0.08, 0.04], [0.12, 0.96, -0.66], 0xf0bf57, { outline: false });
      this.kit.box(parent, [0.06, 0.14, 0.04], [0.24, 0.99, -0.66], 0x55d687, { outline: false });
      this.kit.box(parent, [0.06, 0.2, 0.04], [0.36, 1.02, -0.66], 0x55d9ff, { outline: false });
    }
    if (profile.archetype === "finance") {
      this.kit.cylinder(parent, 0.12, 0.05, [-0.28, 0.92, -0.58], 0xf0bf57, 18);
      this.kit.cylinder(parent, 0.12, 0.05, [-0.22, 0.99, -0.58], 0xf0bf57, 18);
    }
    if (profile.archetype === "legal") {
      this.kit.box(parent, [0.42, 0.06, 0.3], [0.28, 0.9, -0.62], 0x1f2f46, { outline: true });
      this.kit.box(parent, [0.32, 0.02, 0.22], [0.28, 0.95, -0.62], 0xe8ded0, { outline: false });
    }
  }

  private activeRing(parent: THREE.Group, accent: number) {
    const material = this.kit.transparentMaterial(accent, 0.28);
    const ring = this.kit.mesh(
      parent,
      new THREE.RingGeometry(0.72, 0.92, 42),
      material,
      [0, 0.045, 0.02],
      { name: "speaker-ring", outline: false, rotation: [-Math.PI / 2, 0, 0] },
    );
    ring.renderOrder = 2;
  }
}

function disposeScene(scene: THREE.Scene, materials: MaterialLibrary) {
  const geometries = new Set<THREE.BufferGeometry>();
  scene.traverse((object) => {
    if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) {
      if (object.geometry) geometries.add(object.geometry);
    }
  });
  for (const geometry of geometries) geometry.dispose();
  materials.dispose();
}

export function PixelOfficeRoom({
  roomName,
  seats,
  latestMessage,
  activeSpeakerUid,
  providerByUid,
  tokenLabel,
  turnCount,
  tokenCount,
}: PixelOfficeRoomProps) {
  const canvasHostRef = useRef<HTMLDivElement>(null);
  const [labels, setLabels] = useState<ProjectedLabel[]>([]);
  const [speaker, setSpeaker] = useState<ProjectedSpeaker | null>(null);

  const poses = useMemo(() => computeSeatPoses(seats), [seats]);
  const speakerMember = poses.find((pose) => pose.member.entity_uid === activeSpeakerUid)?.member;
  const bubbleText = shortText(latestMessage);

  useEffect(() => {
    const host = canvasHostRef.current;
    if (!host) return;

    const materials = new MaterialLibrary();
    const kit = new MeshKit(materials);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x101722);
    scene.fog = new THREE.Fog(0x101722, 14, 25);

    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100);
    frameRoom(camera, 1200, 760);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xf8efe0, 0x34445a, 2.15));

    const keyLight = new THREE.DirectionalLight(0xfff5e3, 2.7);
    keyLight.position.set(2.8, 8.6, 4.8);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(2048, 2048);
    keyLight.shadow.camera.near = 0.5;
    keyLight.shadow.camera.far = 24;
    keyLight.shadow.camera.left = -9;
    keyLight.shadow.camera.right = 9;
    keyLight.shadow.camera.top = 8;
    keyLight.shadow.camera.bottom = -8;
    scene.add(keyLight);

    const fillLight = new THREE.PointLight(0x6fb7ff, 1.15, 9);
    fillLight.position.set(-3.2, 3.5, 2.6);
    scene.add(fillLight);

    new OfficeEnvironment(kit, materials, roomName ?? "AI Office").build(scene);
    const designer = new CharacterDesigner(kit);

    const labelPoints = new Map<string, THREE.Vector3>();
    let speakerPoint: THREE.Vector3 | null = null;
    for (const pose of poses) {
      const provider = providerByUid.get(pose.member.entity_uid);
      const active = pose.member.entity_uid === activeSpeakerUid;
      designer.create(scene, pose, provider, active);
      labelPoints.set(pose.member.entity_uid, new THREE.Vector3(pose.x, 1.92, pose.z));
      if (active) speakerPoint = new THREE.Vector3(pose.x, 2.36, pose.z);
    }

    const updateSizeAndOverlay = () => {
      const rect = host.getBoundingClientRect();
      const width = Math.max(1, Math.floor(rect.width));
      const height = Math.max(1, Math.floor(rect.height));
      renderer.setSize(width, height, false);
      frameRoom(camera, width, height);

      setLabels(poses.map((pose) => {
        const point = labelPoints.get(pose.member.entity_uid) ?? new THREE.Vector3(pose.x, 1.8, pose.z);
        const projected = projectPoint(point, camera, width, height);
        return {
          uid: pose.member.entity_uid,
          name: pose.member.name,
          provider: roleLabel(pose.member, providerByUid.get(pose.member.entity_uid)),
          active: pose.member.entity_uid === activeSpeakerUid,
          x: Math.min(width - 76, Math.max(76, projected.x)),
          y: Math.min(height - 28, Math.max(58, projected.y + 10)),
        };
      }));

      if (latestMessage && speakerPoint) {
        const projected = projectPoint(speakerPoint, camera, width, height);
        const sideMargin = Math.min(205, Math.max(24, width * 0.18));
        const clampedX = Math.min(width - sideMargin, Math.max(sideMargin, projected.x));
        const clampedY = Math.min(height - 186, Math.max(18, projected.y - 168));
        setSpeaker({
          name: speakerMember?.name ?? extractEntityUid(latestMessage.sender),
          text: bubbleText,
          x: clampedX,
          y: clampedY,
          align: clampedX < width * 0.36 ? "left" : clampedX > width * 0.64 ? "right" : "center",
        });
      } else {
        setSpeaker(null);
      }
    };

    const resizeObserver = new ResizeObserver(updateSizeAndOverlay);
    resizeObserver.observe(host);
    updateSizeAndOverlay();

    let frame = 0;
    renderer.setAnimationLoop(() => {
      frame += 1;
      const time = frame * 0.032;
      fillLight.intensity = 1.04 + Math.sin(time * 0.8) * 0.1;
      scene.traverse((object) => {
        if (activeSpeakerUid && object.name === `seat-${activeSpeakerUid}`) {
          const baseY = typeof object.userData.baseY === "number" ? object.userData.baseY : 0;
          const phase = typeof object.userData.phase === "number" ? object.userData.phase : 0;
          const speed = typeof object.userData.speed === "number" ? object.userData.speed : 1;
          object.position.y = baseY + Math.sin(time * 2.8 * speed + phase) * 0.03;
          object.rotation.z = Math.sin(time * 1.7 * speed + phase) * 0.012;
        }
        if (object.name === "speaker-ring") {
          object.scale.setScalar(1 + Math.sin(time * 3.2) * 0.035);
        }
        if (object.userData.anim === "head-breathe") {
          const baseY = typeof object.userData.baseY === "number" ? object.userData.baseY : object.position.y;
          const phase = typeof object.userData.phase === "number" ? object.userData.phase : 0;
          object.position.y = baseY + Math.sin(time * 1.4 + phase) * 0.012;
        }
        if (object.userData.anim === "prop-wiggle") {
          const phase = typeof object.userData.phase === "number" ? object.userData.phase : 0;
          object.rotation.z = Math.sin(time * 2.1 + phase) * 0.08;
        }
        if (object.userData.anim === "hologram" || object.userData.anim === "hologram-bar") {
          const baseY = typeof object.userData.baseY === "number" ? object.userData.baseY : object.position.y;
          const phase = typeof object.userData.phase === "number" ? object.userData.phase : 0;
          object.position.y = baseY + Math.sin(time * 2.2 + phase) * 0.025;
        }
        if (object.userData.anim === "hologram-ring") {
          object.rotation.z += 0.006;
        }
        if (object.userData.anim === "screen-pulse" && object instanceof THREE.Mesh) {
          const phase = typeof object.userData.phase === "number" ? object.userData.phase : 0;
          object.scale.setScalar(1 + Math.sin(time * 2.5 + phase) * 0.018);
          if (!Array.isArray(object.material) && object.material instanceof THREE.MeshStandardMaterial) {
            object.material.emissive = new THREE.Color(0x55d9ff);
            object.material.emissiveIntensity = 0.12 + Math.sin(time * 3 + phase) * 0.04;
          }
        }
      });
      renderer.render(scene, camera);
    });

    return () => {
      resizeObserver.disconnect();
      renderer.setAnimationLoop(null);
      renderer.dispose();
      host.removeChild(renderer.domElement);
      disposeScene(scene, materials);
    };
  }, [
    activeSpeakerUid,
    bubbleText,
    latestMessage,
    poses,
    providerByUid,
    roomName,
    speakerMember?.name,
  ]);

  return (
    <div className="office3d">
      <div ref={canvasHostRef} className="office3d__canvas" />

      {speaker && (
        <div
          className={`office3d__speech office3d__speech--${speaker.align}`}
          style={{ left: speaker.x, top: speaker.y }}
        >
          <p className="office3d__speech-name">{speaker.name}</p>
          <p>{speaker.text}</p>
        </div>
      )}

      {labels.map((label) => (
        <div
          key={label.uid}
          className={`office3d__label ${label.active ? "is-active" : ""}`}
          style={{ left: label.x, top: label.y }}
        >
          <span>{label.name}</span>
          <small>{label.provider}</small>
        </div>
      ))}

      <div className="office3d__status">
        <span>{turnCount} turns</span>
        <span>{formatCompactTokenCount(tokenCount)} {tokenLabel}</span>
      </div>

      <div className="office3d__minimap">
        <p>Office Room</p>
        <div>
          {poses.slice(0, 12).map((pose) => (
            <span
              key={pose.member.address}
              style={{ left: `${pose.miniX}%`, top: `${pose.miniY}%` }}
              className={pose.member.entity_uid === activeSpeakerUid ? "is-active" : ""}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
