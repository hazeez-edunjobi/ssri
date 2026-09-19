"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, useAnimationFrame, useMotionValue, useSpring } from "framer-motion";
import { cn } from "@/lib/utils";

type TerrainGraphicProps = {
  className?: string;
  scan?: boolean;
  variant?: "electric" | "mono";
  /** Lets the contour lines deform toward the pointer like a live scan. */
  interactive?: boolean;
};

const VIEW_W = 800;
const VIEW_H = 420;
const POINT_COUNT = 41; // ~20px spacing across the viewBox

const LAYERS = [
  { base: 260, amp: 22, freq: 0.012, phase: 0.4, response: 1 },
  { base: 300, amp: 18, freq: 0.014, phase: 1.6, response: 0.7 },
  { base: 340, amp: 14, freq: 0.016, phase: 2.7, response: 0.45 },
  { base: 190, amp: 20, freq: 0.011, phase: 0.9, response: 0.85 },
];

const ELEVATION_NODES: [number, number][] = [
  [320, 260],
  [520, 300],
  [340, 190],
];

const COLORS_ELECTRIC = ["#3EA6FF", "#22D3EE", "#34D399", "#3EA6FF55"];
const COLORS_MONO = ["#7C8699", "#7C869988", "#7C869955", "#7C869933"];

function smoothPath(points: [number, number][]) {
  if (points.length < 2) return "";
  let d = `M${points[0][0]},${points[0][1]}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] ?? points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] ?? p2;
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C${c1x},${c1y} ${c2x},${c2y} ${p2[0]},${p2[1]}`;
  }
  return d;
}

export function TerrainGraphic({
  className,
  scan = true,
  variant = "electric",
  interactive = true,
}: TerrainGraphicProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const pathRefs = useRef<(SVGPathElement | null)[]>([]);
  const nodeRefs = useRef<(SVGCircleElement | null)[]>([]);
  const probeRef = useRef<SVGLineElement>(null);
  const [depthLabel, setDepthLabel] = useState<string | null>(null);
  const reducedMotion = useRef(false);

  const mouseX = useMotionValue(VIEW_W / 2);
  const active = useMotionValue(0);
  const springX = useSpring(mouseX, { stiffness: 90, damping: 18 });
  const springActive = useSpring(active, { stiffness: 120, damping: 20 });
  const clock = useRef(0);

  useEffect(() => {
    reducedMotion.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  const strokeColors = variant === "electric" ? COLORS_ELECTRIC : COLORS_MONO;

  useAnimationFrame((_, delta) => {
    if (!reducedMotion.current) clock.current += delta / 1000;
    const mx = springX.get();
    const amt = interactive && !reducedMotion.current ? springActive.get() : 0;

    LAYERS.forEach((layer, li) => {
      const points: [number, number][] = [];
      for (let i = 0; i < POINT_COUNT; i++) {
        const x = (i / (POINT_COUNT - 1)) * VIEW_W;
        const wave = Math.sin(x * layer.freq + layer.phase + clock.current * 0.25) * layer.amp;
        const dist = x - mx;
        const bump = amt * layer.response * 46 * Math.exp(-(dist * dist) / (2 * 90 * 90));
        points.push([x, layer.base + wave - bump]);
      }
      pathRefs.current[li]?.setAttribute("d", smoothPath(points));
    });

    ELEVATION_NODES.forEach(([x], i) => {
      const layer = LAYERS[0];
      const wave = Math.sin(x * layer.freq + layer.phase + clock.current * 0.25) * layer.amp;
      const dist = x - mx;
      const bump = amt * layer.response * 46 * Math.exp(-(dist * dist) / (2 * 90 * 90));
      nodeRefs.current[i]?.setAttribute("cy", String(layer.base + wave - bump));
    });

    if (probeRef.current) {
      probeRef.current.setAttribute("x1", String(mx));
      probeRef.current.setAttribute("x2", String(mx));
      probeRef.current.style.opacity = String(amt * 0.4);
    }
  });

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      if (!interactive || !svgRef.current) return;
      const rect = svgRef.current.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * VIEW_W;
      const y = ((e.clientY - rect.top) / rect.height) * VIEW_H;
      mouseX.set(x);
      active.set(1);
      setDepthLabel(`${Math.round(20 + (y / VIEW_H) * 180)}m`);
    },
    [interactive, mouseX, active]
  );

  const handlePointerLeave = useCallback(() => {
    active.set(0);
    setDepthLabel(null);
  }, [active]);

  return (
    <div className={cn("relative overflow-hidden", className)}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className={cn("h-full w-full touch-none", interactive && "cursor-crosshair")}
        preserveAspectRatio="xMidYMid slice"
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
      >
        <defs>
          <radialGradient id="terrain-glow" cx="50%" cy="35%" r="70%">
            <stop offset="0%" stopColor="#3EA6FF" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#3EA6FF" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width={VIEW_W} height={VIEW_H} fill="url(#terrain-glow)" />

        <line ref={probeRef} y1={0} y2={VIEW_H} stroke="#22D3EE" strokeDasharray="2 6" style={{ opacity: 0 }} />

        {LAYERS.map((_, i) => (
          <path
            key={i}
            ref={(el) => { pathRefs.current[i] = el; }}
            fill="none"
            stroke={strokeColors[i % strokeColors.length]}
            strokeWidth={i === 0 ? 1.6 : 1}
            strokeOpacity={0.75 - i * 0.1}
            strokeLinecap="round"
          />
        ))}

        {ELEVATION_NODES.map(([cx, cy], i) => (
          <circle key={i} ref={(el) => { nodeRefs.current[i] = el; }} cx={cx} cy={cy} r={3} fill="#22D3EE" />
        ))}
      </svg>

      {scan && (
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 h-1/3 bg-gradient-to-b from-cyan/0 via-cyan/10 to-cyan/0"
          initial={{ y: "-100%" }}
          animate={{ y: "220%" }}
          transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
        />
      )}

      {interactive && depthLabel && (
        <div className="pointer-events-none absolute right-3 top-3 rounded-full border border-meadow bg-canopy/80 px-2.5 py-1 font-mono text-[10px] text-sprout backdrop-blur">
          probe · {depthLabel}
        </div>
      )}
    </div>
  );
}