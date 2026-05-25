/* Network graph for host hierarchy + entity mount relationships. */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, Loader2, Server, User, UserPlus, X } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, kindAvatarClass } from "@/lib/utils";
import { useAppStore } from "@/stores/app";
import { useThemeStore } from "@/stores/theme";
import type { Contact, DiscoverHost, HostRelation, HostTopologyEdge } from "@/types";

interface GraphBaseNode {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  anchorX: number;
  anchorY: number;
  pulsePhase: number;
}

interface HostGraphNode extends GraphBaseNode {
  kind: "host";
  host: DiscoverHost;
  childCount: number;
}

interface EntityGraphNode extends GraphBaseNode {
  kind: "entity";
  entity: Contact;
  hostUid: string;
  isMe: boolean;
  isFriend: boolean;
}

type GraphNode = HostGraphNode | EntityGraphNode;

interface GraphEdge {
  source: string;
  target: string;
  kind: "host" | "mount" | "friend";
  strength: number;
}

interface NetworkGraphProps {
  hosts: DiscoverHost[];
  hostEdges: HostTopologyEdge[];
  entities: Contact[];
  friends: Contact[];
  currentEntityUid: string;
  onAddFriend: (entity: Contact) => void;
  addingUid: string | null;
  className?: string;
}

const REPULSION = 2200;
const DAMPING = 0.9;
const HOST_SPRING = 0.016;
const ENTITY_SPRING = 0.018;
const HOST_LAYOUT_PADDING = 84;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

const HOST_LAYOUT_PRIORITY: Record<HostRelation, number> = {
  parent: 0,
  self: 1,
  child: 2,
  remote: 3,
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function uidPhase(uid: string): number {
  const seed = Array.from(uid).reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return ((seed % 360) * Math.PI) / 180;
}

function parseHostUidFromAddress(address: string | undefined): string | null {
  if (!address) return null;
  const [hostUid] = address.split(":");
  return hostUid || null;
}

function resolveEntityHostUid(entity: Contact): string {
  return parseHostUidFromAddress(entity.address?.address) ?? entity.host_uid;
}

function hostNodeId(uid: string): string {
  return `host:${uid}`;
}

function entityNodeId(entity: Contact): string {
  return `entity:${resolveEntityHostUid(entity)}:${entity.entity_uid}`;
}

function relationColor(relation: HostRelation, dark: boolean): string {
  switch (relation) {
    case "self":
      return dark ? "76,160,224" : "35,131,226";
    case "parent":
      return dark ? "211,163,88" : "199,124,20";
    case "child":
      return dark ? "64,177,155" : "15,123,108";
    default:
      return dark ? "180,180,180" : "100,100,100";
  }
}

function buildNodeMap(nodes: GraphNode[]): Map<string, GraphNode> {
  return new Map(nodes.map((node) => [node.id, node]));
}

function trunc(text: string, maxLen: number): string {
  return text.length > maxLen ? `${text.slice(0, maxLen - 1)}…` : text;
}

export function NetworkGraph({
  hosts,
  hostEdges,
  entities,
  friends,
  currentEntityUid,
  onAddFriend,
  addingUid,
  className,
}: NetworkGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodesRef = useRef<GraphNode[]>([]);
  const edgesRef = useRef<GraphEdge[]>([]);
  const animFrameRef = useRef(0);
  const mouseRef = useRef({ x: -9999, y: -9999 });
  const hoveredNodeRef = useRef<string | null>(null);
  const containerSizeRef = useRef({ w: 600, h: 400 });

  const avatarCache = useAppStore((state) => state.avatarCache);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [detailPos, setDetailPos] = useState({ x: 0, y: 0 });

  const theme = useThemeStore((state) => state.theme);
  const isDarkRef = useRef(theme === "dark");
  useEffect(() => {
    isDarkRef.current = theme === "dark";
  }, [theme]);

  const friendUidSet = useMemo(
    () => new Set(friends.map((friend) => friend.entity_uid)),
    [friends],
  );

  const buildGraph = useCallback(
    (width: number, height: number) => {
      const hostMap = new Map<string, DiscoverHost>(hosts.map((host) => [host.uid, host]));
      const groupedEntities = new Map<string, Contact[]>();

      for (const entity of entities) {
        const hostUid = resolveEntityHostUid(entity);
        if (!hostMap.has(hostUid)) {
          hostMap.set(hostUid, {
            uid: hostUid,
            name: `Host ${hostUid.slice(0, 8)}`,
            url: "",
            relation: "remote",
          });
        }
        const list = groupedEntities.get(hostUid) ?? [];
        list.push(entity);
        groupedEntities.set(hostUid, list);
      }

      for (const list of groupedEntities.values()) {
        list.sort((a, b) => a.name.localeCompare(b.name));
      }

      const childCount = new Map<string, number>();
      for (const edge of hostEdges) {
        childCount.set(edge.parentUid, (childCount.get(edge.parentUid) ?? 0) + 1);
      }

      const allHosts = Array.from(hostMap.values());
      const nodes: GraphNode[] = [];
      const edges: GraphEdge[] = [];
      const hostPositionMap = new Map<string, { x: number; y: number }>();

      const adjacency = new Map<string, Set<string>>();
      for (const host of allHosts) {
        adjacency.set(host.uid, new Set<string>());
      }

      for (const edge of hostEdges) {
        const parentNeighbors = adjacency.get(edge.parentUid);
        const childNeighbors = adjacency.get(edge.childUid);
        if (!parentNeighbors || !childNeighbors) continue;
        parentNeighbors.add(edge.childUid);
        childNeighbors.add(edge.parentUid);
      }

      const centerHost =
        allHosts.find((host) => host.relation === "parent") ??
        allHosts.find((host) => host.relation === "self") ??
        allHosts[0];

      const depthByUid = new Map<string, number>();
      if (centerHost) {
        const queue: Array<{ uid: string; depth: number }> = [{ uid: centerHost.uid, depth: 0 }];
        while (queue.length > 0) {
          const current = queue.shift();
          if (!current) continue;
          const existing = depthByUid.get(current.uid);
          if (existing !== undefined && existing <= current.depth) continue;
          depthByUid.set(current.uid, current.depth);

          const neighbors = adjacency.get(current.uid) ?? new Set<string>();
          for (const neighborUid of neighbors) {
            queue.push({ uid: neighborUid, depth: current.depth + 1 });
          }
        }
      }

      let maxDepth = Math.max(...depthByUid.values(), 0);
      for (const host of allHosts) {
        if (!depthByUid.has(host.uid)) {
          depthByUid.set(host.uid, maxDepth + 1);
        }
      }
      maxDepth = Math.max(...depthByUid.values(), 0);

      const hostsByDepth = new Map<number, DiscoverHost[]>();
      for (const host of allHosts) {
        const depth = depthByUid.get(host.uid) ?? 0;
        const list = hostsByDepth.get(depth) ?? [];
        list.push(host);
        hostsByDepth.set(depth, list);
      }

      for (const list of hostsByDepth.values()) {
        list.sort((a, b) => {
          const relationDiff = HOST_LAYOUT_PRIORITY[a.relation] - HOST_LAYOUT_PRIORITY[b.relation];
          if (relationDiff !== 0) return relationDiff;
          return a.name.localeCompare(b.name);
        });
      }

      const centerX = width * 0.5;
      const centerY = height * 0.5;
      const maxRadius = Math.max(Math.min(width, height) * 0.5 - HOST_LAYOUT_PADDING, 80);
      const baseRadius = Math.min(170, Math.max(120, maxRadius * 0.42));
      const ringStep = maxDepth <= 1
        ? 0
        : Math.max(90, Math.min(145, (maxRadius - baseRadius) / (maxDepth - 1)));
      const hostBoundaryPadding = 42;

      for (let depth = 0; depth <= maxDepth; depth += 1) {
        const ringHosts = hostsByDepth.get(depth) ?? [];
        if (ringHosts.length === 0) continue;

        if (depth === 0) {
          const host = ringHosts[0];
          hostPositionMap.set(host.uid, { x: centerX, y: centerY });
          continue;
        }

        const ringRadius = Math.min(baseRadius + (depth - 1) * ringStep, maxRadius);
        const count = ringHosts.length;
        const angleStep = (2 * Math.PI) / count;

        const selfIndex = ringHosts.findIndex((host) => host.relation === "self");
        const startAngle = selfIndex >= 0 && depth === 1
          ? -Math.PI / 2 - selfIndex * angleStep
          : uidPhase(centerHost?.uid ?? "center") - Math.PI / 2 + depth * 0.24;

        ringHosts.forEach((host, index) => {
          const angle = startAngle + index * angleStep;
          const x = clamp(
            centerX + Math.cos(angle) * ringRadius,
            hostBoundaryPadding,
            width - hostBoundaryPadding,
          );
          const y = clamp(
            centerY + Math.sin(angle) * ringRadius,
            hostBoundaryPadding,
            height - hostBoundaryPadding,
          );
          hostPositionMap.set(host.uid, { x, y });
        });
      }

      for (const host of allHosts) {
        const pos = hostPositionMap.get(host.uid);
        if (!pos) continue;
        nodes.push({
          id: hostNodeId(host.uid),
          kind: "host",
          host,
          childCount: childCount.get(host.uid) ?? 0,
          x: pos.x,
          y: pos.y,
          vx: 0,
          vy: 0,
          radius: host.relation === "self" ? 22 : 18,
          anchorX: pos.x,
          anchorY: pos.y,
          pulsePhase: Math.random() * Math.PI * 2,
        });
      }

      const edgeSet = new Set<string>();
      const addEdge = (source: string, target: string, kind: GraphEdge["kind"], strength: number) => {
        const key = `${source}->${target}:${kind}`;
        if (edgeSet.has(key)) return;
        edgeSet.add(key);
        edges.push({ source, target, kind, strength });
      };

      for (const edge of hostEdges) {
        const sourceId = hostNodeId(edge.parentUid);
        const targetId = hostNodeId(edge.childUid);
        if (!hostPositionMap.has(edge.parentUid) || !hostPositionMap.has(edge.childUid)) continue;
        addEdge(sourceId, targetId, "host", 0.85);
      }

      for (const host of allHosts) {
        const center = hostPositionMap.get(host.uid);
        if (!center) continue;

        const hostEntities = groupedEntities.get(host.uid) ?? [];
        const phase = uidPhase(host.uid);
        hostEntities.forEach((entity, index) => {
          const spiralIndex = index + 1;
          const radius = 56 + Math.sqrt(spiralIndex) * 18;
          const angle = phase + spiralIndex * GOLDEN_ANGLE;
          const offset = spiralIndex % 2 === 0 ? 4 : -4;
          const x = center.x + Math.cos(angle) * (radius + offset);
          const y = center.y + Math.sin(angle) * (radius - offset);

          nodes.push({
            id: entityNodeId(entity),
            kind: "entity",
            entity,
            hostUid: host.uid,
            isMe: entity.entity_uid === currentEntityUid,
            isFriend: friendUidSet.has(entity.entity_uid),
            x,
            y,
            vx: 0,
            vy: 0,
            radius: entity.entity_uid === currentEntityUid ? 12 : 10,
            anchorX: x,
            anchorY: y,
            pulsePhase: Math.random() * Math.PI * 2,
          });

          addEdge(hostNodeId(host.uid), entityNodeId(entity), "mount", 0.72);
        });
      }

      const meNodeId = nodes.find(
        (node): node is EntityGraphNode => node.kind === "entity" && node.isMe,
      )?.id;
      if (meNodeId) {
        for (const node of nodes) {
          if (node.kind !== "entity" || !node.isFriend || node.isMe) continue;
          addEdge(meNodeId, node.id, "friend", 0.35);
        }
      }

      nodesRef.current = nodes;
      edgesRef.current = edges;
    },
    [currentEntityUid, entities, friendUidSet, hostEdges, hosts],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const maybeContext = canvas.getContext("2d");
    if (!maybeContext) return;
    const context: CanvasRenderingContext2D = maybeContext;

    let alive = true;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const parent = canvas.parentElement;
      const width = parent?.clientWidth ?? window.innerWidth;
      const height = parent?.clientHeight ?? window.innerHeight;

      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);

      containerSizeRef.current = { w: width, h: height };
      buildGraph(width, height);
    };

    const handleMouseMove = (event: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current = {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      };
    };

    const handleClick = (event: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const mx = event.clientX - rect.left;
      const my = event.clientY - rect.top;

      for (const node of nodesRef.current) {
        const dx = mx - node.x;
        const dy = my - node.y;
        if (dx * dx + dy * dy <= (node.radius + 8) * (node.radius + 8)) {
          setSelectedNode(node);
          setDetailPos({ x: mx, y: my });
          return;
        }
      }

      setSelectedNode(null);
    };

    function simulate(nodeMap: Map<string, GraphNode>) {
      const nodes = nodesRef.current;
      const edges = edgesRef.current;

      for (let i = 0; i < nodes.length; i += 1) {
        for (let j = i + 1; j < nodes.length; j += 1) {
          const a = nodes[i];
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const repulsionScale =
            a.kind === "host" && b.kind === "host"
              ? 1.3
              : a.kind === "entity" && b.kind === "entity"
                ? a.hostUid === b.hostUid
                  ? 0.42
                  : 0.75
                : 0.9;
          const force = (REPULSION * repulsionScale) / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          a.vx += fx;
          a.vy += fy;
          b.vx -= fx;
          b.vy -= fy;
        }
      }

      for (const edge of edges) {
        const source = nodeMap.get(edge.source);
        const target = nodeMap.get(edge.target);
        if (!source || !target) continue;

        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const desired = edge.kind === "host" ? 162 : edge.kind === "mount" ? 88 : 170;
        const displacement = dist - desired;
        const force = 0.0045 * displacement * edge.strength;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        source.vx += fx;
        source.vy += fy;
        target.vx -= fx;
        target.vy -= fy;
      }

      const { w, h } = containerSizeRef.current;
      const padding = 34;
      const centerX = w * 0.5;
      const centerY = h * 0.5;

      for (const node of nodes) {
        const centerGravity = node.kind === "host" ? 0.0009 : 0.00035;
        node.vx += (centerX - node.x) * centerGravity;
        node.vy += (centerY - node.y) * centerGravity;

        const spring = node.kind === "host" ? HOST_SPRING : ENTITY_SPRING;
        node.vx += (node.anchorX - node.x) * spring;
        node.vy += (node.anchorY - node.y) * spring;

        node.vx *= DAMPING;
        node.vy *= DAMPING;

        node.x += node.vx;
        node.y += node.vy;
        node.pulsePhase += 0.03;

        if (node.x < padding) {
          node.x = padding;
          node.vx *= -0.4;
        }
        if (node.x > w - padding) {
          node.x = w - padding;
          node.vx *= -0.4;
        }
        if (node.y < padding) {
          node.y = padding;
          node.vy *= -0.4;
        }
        if (node.y > h - padding) {
          node.y = h - padding;
          node.vy *= -0.4;
        }
      }
    }

    function draw() {
      if (!alive) return;

      const { w, h } = containerSizeRef.current;
      context.clearRect(0, 0, w, h);

      const nodes = nodesRef.current;
      const edges = edgesRef.current;
      const nodeMap = buildNodeMap(nodes);
      const hovered = hoveredNodeRef.current;
      const mouse = mouseRef.current;
      const dark = isDarkRef.current;

      const bgTextColor = dark ? "245,245,245" : "23,23,23";
      const edgeBaseColor = dark ? "120,120,120" : "120,120,120";

      for (const edge of edges) {
        const source = nodeMap.get(edge.source);
        const target = nodeMap.get(edge.target);
        if (!source || !target) continue;

        const highlighted = hovered === source.id || hovered === target.id;
        const alpha = edge.kind === "host"
          ? highlighted
            ? 0.5
            : 0.28
          : edge.kind === "mount"
            ? highlighted
              ? 0.38
              : 0.16
            : highlighted
              ? 0.32
              : 0.12;

        context.beginPath();
        context.moveTo(source.x, source.y);
        context.lineTo(target.x, target.y);

        if (edge.kind === "friend") {
          context.setLineDash([4, 4]);
          context.strokeStyle = `rgba(35,131,226,${alpha})`;
        } else if (edge.kind === "host") {
          context.setLineDash([]);
          context.strokeStyle = `rgba(${edgeBaseColor},${alpha})`;
        } else {
          context.setLineDash([]);
          context.strokeStyle = `rgba(${edgeBaseColor},${alpha})`;
        }

        context.lineWidth = edge.kind === "host" ? 1.3 : 0.9;
        context.stroke();
      }
      context.setLineDash([]);

      for (const node of nodes) {
        const hoveredNode = hovered === node.id;
        const pulse = Math.sin(node.pulsePhase) * 0.1 + 1;

        if (node.kind === "host") {
          const color = relationColor(node.host.relation, dark);
          const radius = node.radius * (hoveredNode ? 1.08 : 1) * pulse;

          context.beginPath();
          context.arc(node.x, node.y, radius + 10, 0, Math.PI * 2);
          context.fillStyle = `rgba(${color},0.08)`;
          context.fill();

          context.beginPath();
          context.arc(node.x, node.y, radius, 0, Math.PI * 2);
          context.fillStyle = `rgba(${color},0.18)`;
          context.fill();
          context.strokeStyle = `rgba(${color},0.9)`;
          context.lineWidth = hoveredNode ? 2 : 1.5;
          context.stroke();

          context.beginPath();
          context.arc(node.x, node.y, 4, 0, Math.PI * 2);
          context.fillStyle = `rgba(${color},0.95)`;
          context.fill();

          context.font = `600 11px "Inter", sans-serif`;
          context.fillStyle = `rgba(${bgTextColor},${hoveredNode ? 1 : 0.9})`;
          context.textAlign = "center";
          context.fillText(trunc(node.host.name, 18), node.x, node.y + radius + 16);

          context.font = `500 9px "Inter", sans-serif`;
          context.fillStyle = `rgba(${color},0.8)`;
          context.fillText(node.host.relation, node.x, node.y + radius + 28);
        } else {
          const color = node.isMe
            ? dark
              ? "76,160,224"
              : "35,131,226"
            : node.isFriend
              ? dark
                ? "170,170,170"
                : "85,85,85"
              : dark
                ? "132,132,132"
                : "145,145,145";

          const radius = node.radius * (hoveredNode ? 1.14 : 1);
          context.beginPath();
          context.arc(node.x, node.y, radius, 0, Math.PI * 2);
          context.fillStyle = `rgba(${color},${node.isMe ? 0.3 : 0.2})`;
          context.fill();
          context.strokeStyle = `rgba(${color},${node.isMe ? 0.95 : 0.72})`;
          context.lineWidth = node.isMe ? 1.6 : 1;
          context.stroke();

          if (node.isMe) {
            context.beginPath();
            context.arc(node.x, node.y, radius + 3.5, 0, Math.PI * 2);
            context.strokeStyle = `rgba(${color},0.4)`;
            context.lineWidth = 1;
            context.setLineDash([3, 3]);
            context.stroke();
            context.setLineDash([]);
          }

          context.font = `500 10px "Inter", sans-serif`;
          context.fillStyle = `rgba(${bgTextColor},${hoveredNode ? 0.96 : 0.68})`;
          context.textAlign = "center";
          context.fillText(trunc(node.entity.name, 14), node.x, node.y + radius + 14);
        }
      }

      let found: string | null = null;
      for (const node of nodes) {
        const dx = mouse.x - node.x;
        const dy = mouse.y - node.y;
        if (dx * dx + dy * dy <= (node.radius + 8) * (node.radius + 8)) {
          found = node.id;
          break;
        }
      }
      hoveredNodeRef.current = found;

      simulate(nodeMap);
      animFrameRef.current = requestAnimationFrame(draw);
    }

    resize();
    window.addEventListener("resize", resize);
    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("click", handleClick);
    animFrameRef.current = requestAnimationFrame(draw);

    return () => {
      alive = false;
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("click", handleClick);
      cancelAnimationFrame(animFrameRef.current);
    };
  }, [buildGraph]);

  const { w: cw, h: ch } = containerSizeRef.current;
  const cardLeft = Math.max(12, Math.min(detailPos.x + 18, cw - 280));
  const cardTop = Math.max(12, Math.min(detailPos.y - 48, ch - 220));

  return (
    <div className={cn("relative w-full h-full", className)}>
      <canvas ref={canvasRef} className="absolute inset-0 cursor-crosshair" />

      <AnimatePresence>
        {selectedNode && (
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 6 }}
            transition={{ duration: 0.2 }}
            className={cn(
              "absolute z-20 w-64 p-4 rounded-xl",
              "bg-card/92 backdrop-blur-xl border border-border",
              "shadow-[0_8px_32px_rgba(0,0,0,0.35)]",
            )}
            style={{ left: cardLeft, top: cardTop }}
          >
            <button
              onClick={() => setSelectedNode(null)}
              className="absolute top-2 right-2 p-1 rounded-md text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Close detail"
            >
              <X className="h-3.5 w-3.5" />
            </button>

            {selectedNode.kind === "host" ? (
              <div>
                <div className="flex items-center gap-2">
                  <div className="h-9 w-9 rounded-lg bg-surface border border-border flex items-center justify-center">
                    <Server className="h-4.5 w-4.5 text-muted-foreground" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold truncate">{selectedNode.host.name}</p>
                    <p className="text-[11px] text-muted-foreground truncate">{selectedNode.host.uid}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 mt-3">
                  <Badge variant="secondary" className="text-[10px] h-5 px-1.5 border-0">
                    {selectedNode.host.relation}
                  </Badge>
                  <Badge variant="secondary" className="text-[10px] h-5 px-1.5 border-0 bg-surface">
                    children {selectedNode.childCount}
                  </Badge>
                </div>

                {selectedNode.host.url && (
                  <p className="text-xs text-muted-foreground mt-3 break-all">{selectedNode.host.url}</p>
                )}
              </div>
            ) : (
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <Avatar className="h-10 w-10 border border-border">
                    {avatarCache[selectedNode.entity.entity_uid] && (
                      <AvatarImage src={avatarCache[selectedNode.entity.entity_uid]} />
                    )}
                    <AvatarFallback
                      className={cn(
                        "text-xs font-heading font-semibold",
                        kindAvatarClass(selectedNode.entity.kind),
                      )}
                    >
                      {selectedNode.entity.name.slice(0, 2).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold truncate">{selectedNode.entity.name}</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      {selectedNode.entity.kind === "agent" ? (
                        <Bot className="h-3 w-3 text-accent" />
                      ) : (
                        <User className="h-3 w-3 text-primary" />
                      )}
                      <Badge variant="secondary" className="text-[10px] h-4 px-1.5">
                        {selectedNode.entity.kind}
                      </Badge>
                    </div>
                  </div>
                </div>

                <p className="text-xs text-muted-foreground/80 mb-2">
                  mounted on {selectedNode.hostUid}:{selectedNode.entity.entity_uid}
                </p>

                {selectedNode.entity.description && (
                  <p className="text-xs text-muted-foreground mb-3 line-clamp-2">
                    {selectedNode.entity.description}
                  </p>
                )}

                {selectedNode.isMe ? (
                  <div className="flex items-center gap-1.5 text-xs text-accent">
                    <div className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
                    This is you
                  </div>
                ) : selectedNode.isFriend ? (
                  <div className="flex items-center gap-1.5 text-xs text-success">
                    <div className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
                    Connected
                  </div>
                ) : (
                  <Button
                    size="sm"
                    className="w-full h-8 bg-accent/10 text-accent hover:bg-accent/20 border-0"
                    disabled={addingUid === selectedNode.entity.entity_uid}
                    onClick={() => {
                      onAddFriend(selectedNode.entity);
                      setSelectedNode(null);
                    }}
                  >
                    {addingUid === selectedNode.entity.entity_uid ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                    ) : (
                      <UserPlus className="h-3.5 w-3.5 mr-1.5" />
                    )}
                    Add to Network
                  </Button>
                )}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
