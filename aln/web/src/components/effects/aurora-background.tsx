/* Aurora background — animated repeating gradient with mix-blend-difference.
   Creates a cinematic, ethereal backdrop for hero/login sections. */

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface AuroraBackgroundProps {
  children: ReactNode;
  className?: string;
  showRadialGradient?: boolean;
  onMouseMove?: React.MouseEventHandler<HTMLDivElement>;
}

export function AuroraBackground({
  children,
  className,
  showRadialGradient = true,
  onMouseMove,
}: AuroraBackgroundProps) {
  return (
    <div
      onMouseMove={onMouseMove}
      className={cn(
        "relative flex flex-col items-center justify-center overflow-hidden",
        className,
      )}
    >
      <div className="absolute inset-0 overflow-hidden">
        <div
          className={cn(
            "pointer-events-none absolute -inset-[10px] opacity-[0.12]",
            "[background-image:repeating-linear-gradient(100deg,var(--color-primary)_10%,var(--color-muted-foreground)_15%,var(--color-accent)_20%,var(--color-muted-foreground)_25%,var(--color-primary)_30%)]",
            "[background-size:300%_200%]",
            "[background-position:50%_50%]",
            "blur-[10px]",
            "after:content-[''] after:absolute after:inset-0",
            "after:[background-image:repeating-linear-gradient(100deg,var(--color-primary)_10%,var(--color-muted-foreground)_15%,var(--color-accent)_20%,var(--color-muted-foreground)_25%,var(--color-primary)_30%)]",
            "after:[background-size:200%_100%]",
            "after:animate-aurora after:mix-blend-difference",
          )}
        />
      </div>
      {showRadialGradient && (
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_20%,var(--color-background))]" />
      )}
      <div className="relative z-10">{children}</div>
    </div>
  );
}
