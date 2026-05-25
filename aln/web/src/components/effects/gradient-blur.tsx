/* Gradient blur — pulsing blurred gradient orbs for layered background depth.
   Multiple staggered orbs create a cinematic ambient effect. */

import { cn } from "@/lib/utils";

interface GradientBlurProps {
  className?: string;
  colors?: string[];
}

export function GradientBlur({ className, colors }: GradientBlurProps) {
  const defaultColors = [
    "bg-primary/20",
    "bg-accent/15",
    "bg-primary/10",
  ];
  const blurColors = colors ?? defaultColors;

  return (
    <div className={cn("absolute inset-0 overflow-hidden pointer-events-none", className)}>
      {blurColors.map((color, i) => (
        <div
          key={i}
          className={cn(
            "absolute rounded-full blur-[120px] animate-pulse-soft",
            color,
            i === 0 && "top-0 -left-1/4 h-[500px] w-[500px]",
            i === 1 && "top-1/3 -right-1/4 h-[400px] w-[400px]",
            i === 2 && "-bottom-1/4 left-1/3 h-[600px] w-[600px]",
          )}
          style={{
            animationDelay: `${i * 2}s`,
            animationDuration: `${6 + i * 2}s`,
          }}
        />
      ))}
    </div>
  );
}
