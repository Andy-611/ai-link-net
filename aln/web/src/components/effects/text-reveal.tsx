/* Text reveal animations — word-by-word and char-by-char with blur dissolve.
   Creates premium typography entrance effects. */

import { motion } from "framer-motion";

import { cn, EASE_SMOOTH } from "@/lib/utils";

interface TextRevealProps {
  text: string;
  className?: string;
  delay?: number;
  as?: "h1" | "h2" | "h3" | "p" | "span";
}

export function TextReveal({
  text,
  className,
  delay = 0,
  as: Component = "h1",
}: TextRevealProps) {
  const words = text.split(" ");

  return (
    <Component className={cn("flex flex-wrap", className)}>
      {words.map((word, i) => (
        <span key={i} className="overflow-hidden mr-[0.25em]">
          <motion.span
            className="inline-block"
            initial={{ y: "100%", opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{
              duration: 0.5,
              delay: delay + i * 0.08,
              ease: EASE_SMOOTH,
            }}
          >
            {word}
          </motion.span>
        </span>
      ))}
    </Component>
  );
}

interface TextGenerateProps {
  text: string;
  className?: string;
  delay?: number;
}

export function TextGenerate({
  text,
  className,
  delay = 0,
}: TextGenerateProps) {
  const chars = text.split("");

  return (
    <motion.p
      className={cn(className)}
      initial="hidden"
      animate="visible"
    >
      {chars.map((char, i) => (
        <motion.span
          key={i}
          variants={{
            hidden: { opacity: 0, filter: "blur(4px)" },
            visible: { opacity: 1, filter: "blur(0px)" },
          }}
          transition={{
            duration: 0.3,
            delay: delay + i * 0.015,
            ease: "easeOut",
          }}
        >
          {char}
        </motion.span>
      ))}
    </motion.p>
  );
}
