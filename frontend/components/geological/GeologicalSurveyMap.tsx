"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { fetchGeologicalDerived } from "@/lib/geologicalApi";
import type { MagneticProductEntry, TmiPreview } from "@/lib/geologicalApi";
import {
  colorForValue,
  computeViewTransform,
  extentFromCoordinates,
  extentFromProvenance,
  extentFromSurveyLocal,
  featureCentroid,
  niceScaleMetres,
  screenToWorld,
  unionSurveyExtents,
  worldToScreen,
  type ViewTransform,
} from "@/lib/geologicalMapView";
import {
  previewFilenameForProduct,
  productDisplayTitle,
  type LineamentFeature,
} from "@/lib/geologicalPresentation";
import { cn } from "@/lib/utils";

type Props = {
  geoId: string;
  products: MagneticProductEntry[];
  activeOperation: string;
  onChangeOperation: (operation: string) => void;
  showLineaments: boolean;
  onToggleLineaments: (value: boolean) => void;
  lineamentFeatures: LineamentFeature[];
  selectedLineamentId: string | null;
  onSelectLineament: (id: string) => void;
  lineamentCrs: string | null;
  tmiPreview: TmiPreview | null;
  griddingProvenance: Record<string, unknown> | null;
  valueRangeLabel: string | null;
  focusToken?: number;
  focusMode?: "all" | "selected";
};

/**
 * Survey-CRS exploration map: equal-aspect projection, DPR-correct canvas,
 * product underlay + candidate lineament overlay. Does not invent geography.
 */
export function GeologicalSurveyMap({
  geoId,
  products,
  activeOperation,
  onChangeOperation,
  showLineaments,
  onToggleLineaments,
  lineamentFeatures,
  selectedLineamentId,
  onSelectLineament,
  lineamentCrs,
  tmiPreview,
  griddingProvenance,
  valueRangeLabel,
  focusToken = 0,
  focusMode = "all",
}: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [size, setSize] = useState({ w: 640, h: 420 });
  const [zoom, setZoom] = useState(1);
  const [center, setCenter] = useState<{ x: number; y: number } | null>(null);
  const [cursorWorld, setCursorWorld] = useState<[number, number] | null>(null);
  const [previewImage, setPreviewImage] = useState<HTMLImageElement | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [layersOpen, setLayersOpen] = useState(true);
  const dragRef = useRef<{
    pointerId: number;
    originX: number;
    originY: number;
    center: { x: number; y: number };
  } | null>(null);

  const activeProduct = products.find((p) => p.operation === activeOperation);
  const previewFile = useMemo(() => {
    const product = products.find((p) => p.operation === activeOperation);
    return product ? previewFilenameForProduct(product) : null;
  }, [products, activeOperation]);
  const hasProductPreview = Boolean(previewFile);

  const layerOptions = products.filter(
    (p) =>
      p.operation !== "candidate_lineament_extraction" &&
      (p.preview_exists || p.operation === activeOperation),
  );

  const baseExtent = useMemo(() => {
    const fromLines = extentFromCoordinates(
      lineamentFeatures.map((f) => f.coordinates),
    );
    const fromGrid = extentFromProvenance(griddingProvenance);
    const fromSurvey = extentFromSurveyLocal(tmiPreview?.survey_local?.extent);
    const united = unionSurveyExtents([fromGrid, fromSurvey, fromLines]);
    if (united) return united;
    // Preview-only fallback so product charts still render without stretch.
    if (hasProductPreview) {
      return { xmin: 0, xmax: 1000, ymin: 0, ymax: 1000 };
    }
    return null;
  }, [lineamentFeatures, griddingProvenance, tmiPreview, hasProductPreview]);

  const fitExtent = useCallback(
    (mode: "all" | "selected" = "all") => {
      if (!baseExtent) return;
      if (mode === "selected") {
        const selected = lineamentFeatures.find((f) => f.id === selectedLineamentId);
        if (selected) {
          const local = extentFromCoordinates([selected.coordinates], 0.35);
          if (local) {
            const cx = (local.xmin + local.xmax) / 2;
            const cy = (local.ymin + local.ymax) / 2;
            const worldW = Math.max(baseExtent.xmax - baseExtent.xmin, 1);
            const localW = Math.max(local.xmax - local.xmin, 1);
            const nextZoom = Math.min(8, Math.max(1.4, (worldW / localW) * 0.55));
            setCenter({ x: cx, y: cy });
            setZoom(nextZoom);
            return;
          }
        }
      }
      setCenter({
        x: (baseExtent.xmin + baseExtent.xmax) / 2,
        y: (baseExtent.ymin + baseExtent.ymax) / 2,
      });
      setZoom(1);
    },
    [baseExtent, lineamentFeatures, selectedLineamentId],
  );

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const apply = () => {
      const rect = host.getBoundingClientRect();
      setSize({
        w: Math.max(320, Math.floor(rect.width)),
        h: Math.max(280, Math.floor(rect.height)),
      });
    };
    apply();
    const observer = new ResizeObserver(() => apply());
    observer.observe(host);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!baseExtent) return;
    const timer = window.setTimeout(() => fitExtent(focusMode), 0);
    return () => window.clearTimeout(timer);
  }, [focusToken, focusMode, baseExtent, fitExtent]);

  useEffect(() => {
    if (!previewFile) {
      const timer = window.setTimeout(() => {
        setPreviewImage(null);
        setPreviewError(null);
      }, 0);
      return () => window.clearTimeout(timer);
    }
    let cancelled = false;
    let objectUrl: string | null = null;
    const timer = window.setTimeout(() => {
      setPreviewError(null);
      void fetchGeologicalDerived(geoId, previewFile)
        .then(async (blob) => {
          objectUrl = URL.createObjectURL(blob);
          const img = new Image();
          await new Promise<void>((resolve, reject) => {
            img.onload = () => resolve();
            img.onerror = () => reject(new Error("Preview image failed to load"));
            img.src = objectUrl!;
          });
          if (!cancelled) setPreviewImage(img);
        })
        .catch((err: Error) => {
          if (!cancelled) {
            setPreviewImage(null);
            setPreviewError(err.message || "Preview unavailable");
          }
        });
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [geoId, previewFile]);

  const transform = useMemo(() => {
    if (!baseExtent) return null;
    return computeViewTransform(size.w, size.h, baseExtent, zoom, center);
  }, [baseExtent, size, zoom, center]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !transform) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(size.w * dpr);
    canvas.height = Math.floor(size.h * dpr);
    canvas.style.width = `${size.w}px`;
    canvas.style.height = `${size.h}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawMap(ctx, {
      width: size.w,
      height: size.h,
      transform,
      previewImage,
      surveyPoints: tmiPreview?.survey_local?.points ?? null,
      features: showLineaments ? lineamentFeatures : [],
      selectedId: selectedLineamentId,
      showLineaments,
    });
  }, [
    size,
    transform,
    previewImage,
    tmiPreview,
    showLineaments,
    lineamentFeatures,
    selectedLineamentId,
  ]);

  const onPointerDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (!transform || !baseExtent) return;
    if (event.button !== 0) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    dragRef.current = {
      pointerId: event.pointerId,
      originX: px,
      originY: py,
      center: center ?? {
        x: (baseExtent.xmin + baseExtent.xmax) / 2,
        y: (baseExtent.ymin + baseExtent.ymax) / 2,
      },
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (!transform) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    setCursorWorld(screenToWorld(px, py, transform));
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = px - drag.originX;
    const dy = py - drag.originY;
    setCenter({
      x: drag.center.x - dx * transform.metresPerPixel,
      y: drag.center.y + dy * transform.metresPerPixel,
    });
  };

  const onPointerUp = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId || !transform) {
      dragRef.current = null;
      return;
    }
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) {
      dragRef.current = null;
      return;
    }
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const moved =
      Math.hypot(px - drag.originX, py - drag.originY) > 5;
    dragRef.current = null;
    if (moved || !showLineaments || !lineamentFeatures.length) return;

    let bestId: string | null = null;
    let bestDist = 12;
    for (const feature of lineamentFeatures) {
      for (let i = 0; i < feature.coordinates.length - 1; i += 1) {
        const [x0, y0] = worldToScreen(
          feature.coordinates[i][0],
          feature.coordinates[i][1],
          transform,
        );
        const [x1, y1] = worldToScreen(
          feature.coordinates[i + 1][0],
          feature.coordinates[i + 1][1],
          transform,
        );
        const dist = distanceToSegment(px, py, x0, y0, x1, y1);
        if (dist < bestDist) {
          bestDist = dist;
          bestId = feature.id;
        }
      }
    }
    if (bestId) onSelectLineament(bestId);
  };

  const empty = !baseExtent;

  return (
    <div
      ref={hostRef}
      className="relative h-[min(70vh,36rem)] min-h-[22rem] w-full overflow-hidden rounded-2xl border border-meadow bg-[#dfe8d8]"
      data-testid="geological-survey-map"
    >
      <div className="absolute left-3 top-3 z-20 max-w-[15rem]">
        <button
          type="button"
          onClick={() => setLayersOpen((v) => !v)}
          className="mb-1 rounded-lg border border-meadow/80 bg-chalk/95 px-2.5 py-1.5 text-[10px] font-medium uppercase tracking-wider text-leaf shadow-soft"
        >
          Map layers {layersOpen ? "▴" : "▾"}
        </button>
        {layersOpen && (
          <div className="space-y-1 rounded-xl border border-meadow/80 bg-chalk/95 p-2 shadow-soft">
            {layerOptions.map((product) => (
              <label
                key={product.operation}
                className={cn(
                  "flex cursor-pointer items-center gap-2 rounded-lg px-1.5 py-1 text-[11px] text-bark hover:bg-mist",
                  activeOperation === product.operation && "bg-meadow/40",
                )}
              >
                <input
                  type="radio"
                  name="geological-survey-layer"
                  checked={activeOperation === product.operation}
                  onChange={() => onChangeOperation(product.operation)}
                />
                <span>{productDisplayTitle(product)}</span>
              </label>
            ))}
            <label className="flex cursor-pointer items-center gap-2 rounded-lg px-1.5 py-1 text-[11px] text-bark hover:bg-mist">
              <input
                type="checkbox"
                checked={showLineaments}
                onChange={(e) => onToggleLineaments(e.target.checked)}
              />
              <span>
                Candidate magnetic lineaments
                {lineamentFeatures.length
                  ? ` · ${lineamentFeatures.length}`
                  : ""}
              </span>
            </label>
          </div>
        )}
      </div>

      <div className="absolute right-3 top-3 z-20 flex flex-col gap-1">
        <MapControlButton
          label="Zoom in"
          onClick={() => setZoom((z) => Math.min(12, z * 1.35))}
        >
          +
        </MapControlButton>
        <MapControlButton
          label="Zoom out"
          onClick={() => setZoom((z) => Math.max(0.5, z / 1.35))}
        >
          −
        </MapControlButton>
        <MapControlButton label="Fit all features" onClick={() => fitExtent("all")}>
          ⤢
        </MapControlButton>
      </div>

      <div
        className="pointer-events-none absolute right-3 top-[7.5rem] z-20 flex h-10 w-10 items-center justify-center rounded-full border border-meadow/80 bg-chalk/95 text-xs font-semibold text-bark shadow-soft"
        aria-hidden
        title="North"
      >
        N
        <span className="absolute -top-1 text-[10px]">▲</span>
      </div>

      {empty ? (
        <div className="flex h-full items-center justify-center px-6 text-center text-sm text-stone">
          {previewError ||
            "No spatial extent is available yet. Process the grid or extract lineaments to populate the map."}
        </div>
      ) : (
        <canvas
          ref={canvasRef}
          className="h-full w-full cursor-grab touch-none active:cursor-grabbing"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={() => {
            dragRef.current = null;
          }}
          data-testid="geological-survey-canvas"
          role="img"
          aria-label="Geological survey map"
        />
      )}

      {transform && !empty && (
        <div className="pointer-events-none absolute bottom-3 left-3 right-3 z-20 flex items-end justify-between gap-3">
          <div className="rounded-lg border border-meadow/80 bg-chalk/95 px-3 py-2 text-[10px] text-stone shadow-soft">
            <p className="font-medium text-bark">
              {productDisplayTitle(activeProduct || { operation: activeOperation })}
            </p>
            {valueRangeLabel && <p>{valueRangeLabel}</p>}
            <p className="mt-1 max-w-[16rem] leading-snug">
              {lineamentCrs
                ? `Survey frame ${lineamentCrs}. Candidate magnetic lineaments — not confirmed faults.`
                : "Survey / processing coordinates (not a WGS84 basemap)."}
            </p>
            <ScaleBar transform={transform} />
          </div>
          <div className="rounded-lg border border-meadow/80 bg-chalk/95 px-2.5 py-1.5 font-mono text-[10px] text-bark shadow-soft">
            {cursorWorld
              ? `${cursorWorld[0].toFixed(0)}, ${cursorWorld[1].toFixed(0)}`
              : "—"}
          </div>
        </div>
      )}
    </div>
  );
}

function MapControlButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="flex h-8 w-8 items-center justify-center rounded-lg border border-meadow/80 bg-chalk/95 text-sm font-medium text-bark shadow-soft hover:bg-mist"
    >
      {children}
    </button>
  );
}

function ScaleBar({ transform }: { transform: ViewTransform }) {
  const scale = niceScaleMetres(transform.metresPerPixel, 72);
  return (
    <div className="mt-2 flex items-end gap-2" aria-hidden>
      <div
        className="h-1.5 border border-bark/70 border-b-2 bg-transparent"
        style={{ width: Math.max(24, Math.min(120, scale.pixels)) }}
      />
      <span>{scale.label}</span>
    </div>
  );
}

function drawMap(
  ctx: CanvasRenderingContext2D,
  args: {
    width: number;
    height: number;
    transform: ViewTransform;
    previewImage: HTMLImageElement | null;
    surveyPoints: Array<{ x: number; y: number; z: number }> | null;
    features: LineamentFeature[];
    selectedId: string | null;
    showLineaments: boolean;
  },
) {
  const {
    width,
    height,
    transform,
    previewImage,
    surveyPoints,
    features,
    selectedId,
    showLineaments,
  } = args;

  const bg = ctx.createLinearGradient(0, 0, 0, height);
  bg.addColorStop(0, "#e7eee1");
  bg.addColorStop(1, "#d5decc");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, width, height);

  const { frame } = transform;
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, 0, width, height);
  ctx.clip();

  // Product chart PNG: letterbox inside the equal-aspect frame (no CSS stretch).
  // Matplotlib titles/colorbars stay in-image; we do not pretend they are georeferenced.
  if (previewImage && !showLineaments) {
    drawContainedImage(ctx, previewImage, frame);
  } else {
    ctx.fillStyle = "#c8d4ba";
    ctx.fillRect(frame.x, frame.y, frame.width, frame.height);

    // Spatially aligned TMI sample underlay when lineaments are on.
    if (surveyPoints?.length) {
      const zs = surveyPoints.map((p) => p.z);
      const zmin = Math.min(...zs);
      const zmax = Math.max(...zs);
      const radius = Math.max(
        1.2,
        Math.min(2.8, 180 / Math.sqrt(surveyPoints.length)),
      );
      for (const p of surveyPoints) {
        const [px, py] = worldToScreen(p.x, p.y, transform);
        ctx.fillStyle = colorForValue(p.z, zmin, zmax);
        ctx.beginPath();
        ctx.arc(px, py, radius, 0, Math.PI * 2);
        ctx.fill();
      }
    } else if (previewImage) {
      // Best-effort product context under lineaments: contain, reduced opacity.
      ctx.globalAlpha = 0.35;
      drawContainedImage(ctx, previewImage, frame);
      ctx.globalAlpha = 1;
    }

    // Survey grid
    ctx.strokeStyle = "rgba(35, 55, 40, 0.14)";
    ctx.lineWidth = 1;
    const stepGuess = niceScaleMetres(transform.metresPerPixel, 90).metres;
    const { extent } = transform;
    const xStart = Math.ceil(extent.xmin / stepGuess) * stepGuess;
    for (let x = xStart; x <= extent.xmax; x += stepGuess) {
      const [px] = worldToScreen(x, extent.ymin, transform);
      ctx.beginPath();
      ctx.moveTo(px, frame.y);
      ctx.lineTo(px, frame.y + frame.height);
      ctx.stroke();
    }
    const yStart = Math.ceil(extent.ymin / stepGuess) * stepGuess;
    for (let y = yStart; y <= extent.ymax; y += stepGuess) {
      const [, py] = worldToScreen(extent.xmin, y, transform);
      ctx.beginPath();
      ctx.moveTo(frame.x, py);
      ctx.lineTo(frame.x + frame.width, py);
      ctx.stroke();
    }
  }

  if (showLineaments && features.length) {
    const ordered = [...features].sort((a, b) => {
      if (a.id === selectedId) return 1;
      if (b.id === selectedId) return -1;
      return 0;
    });
    for (const feature of ordered) {
      const selected = feature.id === selectedId;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      if (selected) {
        ctx.strokeStyle = "rgba(255,255,255,0.95)";
        ctx.lineWidth = 5;
        strokeFeature(ctx, feature, transform);
        ctx.strokeStyle = "#c45c26";
        ctx.lineWidth = 2.6;
        strokeFeature(ctx, feature, transform);
        const mid = featureCentroid(feature.coordinates);
        if (mid) {
          const [cx, cy] = worldToScreen(mid.x, mid.y, transform);
          ctx.fillStyle = "#c45c26";
          ctx.beginPath();
          ctx.arc(cx, cy, 5.5, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = "#fff";
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      } else {
        ctx.strokeStyle = "rgba(18, 64, 40, 0.35)";
        ctx.lineWidth = 2.4;
        strokeFeature(ctx, feature, transform);
        ctx.strokeStyle = "rgba(36, 110, 72, 0.92)";
        ctx.lineWidth = 1.35;
        strokeFeature(ctx, feature, transform);
      }
    }
  }

  ctx.restore();

  ctx.strokeStyle = "rgba(45, 74, 55, 0.5)";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(frame.x + 0.5, frame.y + 0.5, frame.width - 1, frame.height - 1);
}

function drawContainedImage(
  ctx: CanvasRenderingContext2D,
  image: HTMLImageElement,
  frame: { x: number; y: number; width: number; height: number },
) {
  const imgW = Math.max(image.naturalWidth || image.width, 1);
  const imgH = Math.max(image.naturalHeight || image.height, 1);
  const imgAspect = imgW / imgH;
  const frameAspect = frame.width / Math.max(frame.height, 1e-9);
  let dw: number;
  let dh: number;
  if (imgAspect > frameAspect) {
    dw = frame.width;
    dh = dw / imgAspect;
  } else {
    dh = frame.height;
    dw = dh * imgAspect;
  }
  const dx = frame.x + (frame.width - dw) / 2;
  const dy = frame.y + (frame.height - dh) / 2;
  ctx.fillStyle = "#b7c4a8";
  ctx.fillRect(frame.x, frame.y, frame.width, frame.height);
  ctx.drawImage(image, dx, dy, dw, dh);
}

function strokeFeature(
  ctx: CanvasRenderingContext2D,
  feature: LineamentFeature,
  transform: ViewTransform,
) {
  if (feature.coordinates.length < 2) return;
  ctx.beginPath();
  feature.coordinates.forEach(([x, y], index) => {
    const [px, py] = worldToScreen(x, y, transform);
    if (index === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.stroke();
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
  const t = Math.max(
    0,
    Math.min(1, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)),
  );
  return Math.hypot(px - (x0 + t * dx), py - (y0 + t * dy));
}
