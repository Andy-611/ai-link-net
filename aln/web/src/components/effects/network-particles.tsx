/* Animated network particle background — nodes connected by lines.
   Represents the FP network topology visually. */

import { useCallback, useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  opacity: number;
}

interface NetworkParticlesProps {
  className?: string;
  particleCount?: number;
  connectionDistance?: number;
  colors?: { node: string; line: string };
}

export function NetworkParticles({
  className,
  particleCount = 40,
  connectionDistance = 150,
  colors = { node: "150, 150, 150", line: "150, 150, 150" },
}: NetworkParticlesProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const animFrameRef = useRef<number>(0);
  const mouseRef = useRef({ x: -1000, y: -1000 });
  const colorsRef = useRef(colors);
  colorsRef.current = colors;

  const initParticles = useCallback(
    (w: number, h: number) => {
      const particles: Particle[] = [];
      for (let i = 0; i < particleCount; i++) {
        particles.push({
          x: Math.random() * w,
          y: Math.random() * h,
          vx: (Math.random() - 0.5) * 0.4,
          vy: (Math.random() - 0.5) * 0.4,
          radius: Math.random() * 1.8 + 0.8,
          opacity: Math.random() * 0.4 + 0.35,
        });
      }
      particlesRef.current = particles;
    },
    [particleCount],
  );

  const draw = useCallback(
    (ctx: CanvasRenderingContext2D, w: number, h: number) => {
      ctx.clearRect(0, 0, w, h);
      const particles = particlesRef.current;
      const mouse = mouseRef.current;
      const c = colorsRef.current;

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;

        const dx = mouse.x - p.x;
        const dy = mouse.y - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 250) {
          p.vx += dx * 0.0002;
          p.vy += dy * 0.0002;
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${c.node}, ${p.opacity})`;
        ctx.fill();
      }

      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const a = particles[i];
          const b = particles[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < connectionDistance) {
            const opacity = (1 - dist / connectionDistance) * 0.38;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.strokeStyle = `rgba(${c.line}, ${opacity})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
      }

      animFrameRef.current = requestAnimationFrame(() => draw(ctx, w, h));
    },
    [connectionDistance],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.parentElement?.getBoundingClientRect();
      const w = rect?.width ?? window.innerWidth;
      const h = rect?.height ?? window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      initParticles(w, h);
    };

    resize();
    window.addEventListener("resize", resize);
    // Use window-level mousemove so canvas can be pointer-events-none
    const handleWindowMouse = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };
    window.addEventListener("mousemove", handleWindowMouse);
    draw(ctx, canvas.width / (window.devicePixelRatio || 1), canvas.height / (window.devicePixelRatio || 1));

    return () => {
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", handleWindowMouse);
      cancelAnimationFrame(animFrameRef.current);
    };
  }, [initParticles, draw]);

  return (
    <canvas
      ref={canvasRef}
      className={cn("absolute inset-0 pointer-events-none", className)}
    />
  );
}
