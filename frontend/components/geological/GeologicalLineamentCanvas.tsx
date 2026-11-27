"use client";

import { useEffect, useMemo, useRef, type MouseEvent } from "react";
import type { LineamentFeature } from "@/lib/geologicalPresentation";

type Props = {
  features: LineamentFeature[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  crsLabel?: string | null;
};

/**
 * Interactive canvas for candidate lineaments in survey / processing CRS.
 * Used when GeoJSON is not WGS84 (typical for Abeokuta EPSG:32631 products).
 */
export function GeologicalLineamentCanvas({
  features,
  selectedId,
  onSelect,
  crsLabel,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const extent = useMemo(() => {
    let xmin = Infinity;
    let xmax = -Infinity;
    let ymin = Infinity;
    let ymax = -Infinity;
    for (const feature of features) {
      for (const [x, y] of feature.coordinates) {
        xmin = Math.min(xmin, x);
        xmax = Math.max(xmax, x);
        ymin = Math.min(ymin, y);
        ymax = Math.max(ymax, y);
      }
    }
    if (!Number.isFinite(xmin)) {
      return { xmin: 0, xmax: 1, ymin: 0, ymax: 1 };
    }
    const padX = Math.max((xmax - xmin) * 0.04, 1);
    const padY = Math.max((ymax - ymin) * 0.04, 1);
    return {
      xmin: xmin - padX,
      xmax: xmax + padX,
      ymin: ymin - padY,
      ymax: ymax + padY,
    };
  }, [features]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;
    const { xmin, xmax, ymin, ymax } = extent;
    const dx = Math.max(xmax - xmin, 1e-9);
    const dy = Math.max(ymax - ymin, 1e-9);
    const project = (x: number, y: number): [number, number] => {
      const px = ((x - xmin) / dx) * (w - 24) + 12;
      const py = h - (((y - ymin) / dy) * (h - 24) + 12);
      return [px, py];
    };

    ctx.fillStyle = "#eef3ea";
    ctx.fillRect(0, 0, w, h);
    // subtle grid
    ctx.strokeStyle = "rgba(45, 106, 79, 0.08)";
    ctx.lineWidth = 1;
    for (let i = 1; i < 8; i += 1) {
      const x = (w / 8) * i;
      const y = (h / 8) * i;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    for (const feature of features) {
      const selected = feature.id === selectedId;
      ctx.strokeStyle = selected ? "#c45c26" : "#2f6f4e";
      ctx.lineWidth = selected ? 2.5 : 1.4;
      ctx.beginPath();
      feature.coordinates.forEach(([x, y], index) => {
        const [px, py] = project(x, y);
        if (index === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      ctx.stroke();
      if (selected && feature.coordinates.length) {
        const mid = feature.coordinates[Math.floor(feature.coordinates.length / 2)];
        const [cx, cy] = project(mid[0], mid[1]);
        ctx.fillStyle = "#c45c26";
        ctx.beginPath();
        ctx.arc(cx, cy, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    }

    ctx.fillStyle = "#5c6b5f";
    ctx.font = "11px ui-monospace, monospace";
    ctx.fillText(
      crsLabel
        ? `Candidate lineaments · ${crsLabel} (not a confirmed fault map)`
        : "Candidate lineaments (survey coordinates)",
      12,
      18,
    );
  }, [features, selectedId, extent, crsLabel]);

  const onClick = (event: MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !features.length) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const clickX = (event.clientX - rect.left) * scaleX;
    const clickY = (event.clientY - rect.top) * scaleY;
    const { xmin, xmax, ymin, ymax } = extent;
    const dx = Math.max(xmax - xmin, 1e-9);
    const dy = Math.max(ymax - ymin, 1e-9);
    const project = (x: number, y: number): [number, number] => {
      const px = ((x - xmin) / dx) * (canvas.width - 24) + 12;
      const py = canvas.height - (((y - ymin) / dy) * (canvas.height - 24) + 12);
      return [px, py];
    };

    let bestId: string | null = null;
    let bestDist = 14;
    for (const feature of features) {
      for (let i = 0; i < feature.coordinates.length - 1; i += 1) {
        const [x0, y0] = project(
          feature.coordinates[i][0],
          feature.coordinates[i][1],
        );
        const [x1, y1] = project(
          feature.coordinates[i + 1][0],
          feature.coordinates[i + 1][1],
        );
        const dist = distanceToSegment(clickX, clickY, x0, y0, x1, y1);
        if (dist < bestDist) {
          bestDist = dist;
          bestId = feature.id;
        }
      }
    }
    if (bestId) onSelect(bestId);
  };

  if (!features.length) {
    return (
      <div className="flex h-full min-h-[18rem] items-center justify-center rounded-xl bg-mist/50 px-4 text-center text-sm text-stone">
        No candidate lineaments loaded for this dataset yet.
      </div>
    );
  }

  return (
    <canvas
      ref={canvasRef}
      width={960}
      height={640}
      className="h-full w-full cursor-crosshair rounded-xl"
      onClick={onClick}
      data-testid="geological-lineament-canvas"
      role="img"
      aria-label="Interactive candidate lineament map"
    />
  );
}

function distanceToSegment(
  px: number,
  py: number,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
): number {
  const dx = x1 - x0;
  const dy = y1 - y0;
  if (dx === 0 && dy === 0) return Math.hypot(px - x0, py - y0);
  const t = Math.max(0, Math.min(1, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(px - (x0 + t * dx), py - (y0 + t * dy));
}
