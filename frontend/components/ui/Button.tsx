"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type ButtonProps = {
  children: ReactNode;
  variant?: "primary" | "ghost" | "outline";
  icon?: boolean;
  className?: string;
  onClick?: () => void;
  href?: string;
  type?: "button" | "submit";
};

export function Button({
  children,
  variant = "primary",
  icon = false,
  className,
  onClick,
  href,
  type = "button",
}: ButtonProps) {
  const styles = {
    primary:
      "bg-leaf text-chalk hover:bg-moss shadow-soft",
    ghost: "bg-transparent text-bark hover:bg-meadow/60",
    outline:
      "bg-transparent text-bark border border-meadow hover:border-leaf hover:text-moss",
  };

  const content = (
    <motion.span
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 400, damping: 22 }}
      className={cn(
        "inline-flex items-center gap-2 rounded-md px-6 py-3 text-sm font-semibold tracking-tight transition-colors",
        styles[variant],
        className
      )}
    >
      {children}
      {icon && <ArrowUpRight className="h-4 w-4" strokeWidth={2} />}
    </motion.span>
  );

  if (href) {
    const isInternal = href.startsWith("/") || href.startsWith("#");

    if (isInternal) {
      return (
        <Link href={href} onClick={onClick} className="inline-block">
          {content}
        </Link>
      );
    }

    return (
      <a href={href} onClick={onClick} className="inline-block">
        {content}
      </a>
    );
  }

  return (
    <button type={type} onClick={onClick} className="inline-block">
      {content}
    </button>
  );
}
