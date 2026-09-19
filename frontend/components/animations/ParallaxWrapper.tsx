"use client";

import { useEffect, useRef } from "react";
import { useGsapConfig, ScrollTrigger } from "@/lib/gsap-config";
import type { ReactNode } from "react";

type ParallaxWrapperProps = {
  children: ReactNode;
  speed?: number; // yPercent applied relative to scroll
  className?: string;
};

/**
 * Wraps any element in a smooth GSAP-driven parallax scrub tied to
 * ScrollTrigger. speed of -25 moves the child up as the page scrolls,
 * matching the hero terrain parallax spec.
 */
export function ParallaxWrapper({ children, speed = -25, className }: ParallaxWrapperProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const gsap = useGsapConfig();
    if (!ref.current) return;

    const ctx = gsap.context(() => {
      gsap.to(ref.current, {
        yPercent: speed,
        ease: "none",
        scrollTrigger: {
          trigger: ref.current,
          start: "top bottom",
          end: "bottom top",
          scrub: true,
        },
      });
    });

    return () => ctx.revert();
  }, [speed]);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}

/**
 * Staggered reveal for groups of siblings (e.g. bento cards) as they
 * enter the viewport: y:40, opacity:0 -> y:0, opacity:1.
 */
export function useScrollStagger(
  containerRef: React.RefObject<HTMLElement>,
  selector: string
) {
  useEffect(() => {
    const gsap = useGsapConfig();
    if (!containerRef.current) return;

    const ctx = gsap.context(() => {
      const items = gsap.utils.toArray<HTMLElement>(selector, containerRef.current);
      ScrollTrigger.batch(items, {
        start: "top 85%",
        onEnter: (batch) =>
          gsap.to(batch, {
            y: 0,
            opacity: 1,
            duration: 0.8,
            ease: "power2.out",
            stagger: 0.12,
          }),
        once: true,
      });
      gsap.set(items, { y: 40, opacity: 0 });
    }, containerRef);

    return () => ctx.revert();
  }, [containerRef, selector]);
}
