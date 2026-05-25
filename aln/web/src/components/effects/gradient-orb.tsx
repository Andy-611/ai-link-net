/* Animated gradient orb — floating ambient light effect.
   Creates depth and visual warmth in dark backgrounds. */

import { motion } from "framer-motion";

import { cn } from "@/lib/utils";

interface GradientOrbProps {
  className?: string;
  /** CSS color, e.g. "rgba(35, 131, 226, 0.15)" */
  color?: string;
  /** Size in px */
  size?: number;
  /** Animation duration in seconds */
  duration?: number;
}

export function GradientOrb({
  className,
  color = "rgba(35, 131, 226, 0.1)",
  size = 400,
  duration = 20,
}: GradientOrbProps) {
  return (
    <motion.div
      className={cn("absolute rounded-full blur-3xl pointer-events-none", className)}
      style={{
        width: size,
        height: size,
        background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
      }}
      animate={{
        x: [0, 30, -20, 10, 0],
        y: [0, -20, 15, -10, 0],
        scale: [1, 1.1, 0.95, 1.05, 1],
      }}
      transition={{
        duration,
        repeat: Infinity,
        ease: "easeInOut",
      }}
    />
  );
}
