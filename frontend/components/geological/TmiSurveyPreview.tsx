"use client";

import { useEffect, useMemo, useRef } from "react";
import type { TmiPreview } from "@/lib/geologicalApi";

type Props = {
  preview: TmiPreview | null;
};

/**
 * TMI spatial preview:
 * - WGS84-eligible → MapLibre points
 * - Otherwise → local survey XY canvas (not claimed as geographic map)
 */
export function TmiSurveyPreview({ preview }: Props) {
  const mapHost = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const local = preview?.survey_local;
  const wgs84 = Boolean(preview?.wgs84_map_eligible && preview.geojson);

  useEffect(() => {
    if (!wgs84 || !preview?.geojson || !mapHost.current) return;
    let cancelled = false;
    let map: import("maplibre-gl").Map | undefined;

    void (async () => {
      const imported = (await import("maplibre-gl")) as unknown as {
        default?: {
          Map: new (options: object) => import("maplibre-gl").Map;
        };
        Map: new (options: object) => import("maplibre-gl").Map;
      };
      if (cancelled || !mapHost.current) return;
      const maplibregl = imported.default ?? imported;
      map = new maplibregl.Map({
        container: mapHost.current,
        style: "https://demotiles.maplibre.org/style.json",
        center: [3.35, 7.15],
        zoom: 9,
      });
      map.on("load", () => {
        if (!map || !preview.geojson) return;
        map.addSource("tmi-points", {
          type: "geojson",
          data: preview.geojson as unknown as GeoJSON.GeoJSON,
        });
        map.addLayer({
          id: "tmi-circles",
          type: "circle",
          source: "tmi-points",
          paint: {
            "circle-radius": 3,
            "circle-color": [
              "interpolate",
              ["linear"],
              ["get", "tmi"],
              -200,
              "#2166ac",
              0,
              "#f7f7f7",
              200,
              "#b2182b",
            ],
            "circle-opacity": 0.85,
          },
        });
        const coords = preview.geojson.features
          .map((f) => f.geometry.coordinates)
          .filter((c) => Array.isArray(c) && c.length >= 2);
        if (coords.length) {
          const xs = coords.map((c) => c[0]);
          const ys = coords.map((c) => c[1]);
          map.fitBounds(
            [
              [Math.min(...xs), Math.min(...ys)],
              [Math.max(...xs), Math.max(...ys)],
            ],
            { padding: 40, maxZoom: 14 },
          );
        }
      });
    })();

    return () => {
      cancelled = true;
      map?.remove();
    };
  }, [wgs84, preview]);

  const localStats = useMemo(() => {
    if (!local?.points?.length) return null;
    const zs = local.points.map((p) => p.z);
    return {
      n: local.points.length,
      zmin: Math.min(...zs),
      zmax: Math.max(...zs),
    };
  }, [local]);

  useEffect(() => {
    if (wgs84 || !local?.points?.length || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx.fillStyle = "#f4f1ea";
    ctx.fillRect(0, 0, w, h);
    const { xmin, xmax, ymin, ymax } = local.extent;
    const dx = Math.max(xmax - xmin, 1e-9);
    const dy = Math.max(ymax - ymin, 1e-9);
    const zmin = Math.min(...local.points.map((p) => p.z));
    const zmax = Math.max(...local.points.map((p) => p.z));
    const zspan = Math.max(zmax - zmin, 1e-9);
    for (const p of local.points) {
      const px = ((p.x - xmin) / dx) * (w - 20) + 10;
      const py = h - (((p.y - ymin) / dy) * (h - 20) + 10);
      const t = (p.z - zmin) / zspan;
      const r = Math.round(33 + t * (178 - 33));
      const g = Math.round(102 + (1 - Math.abs(t - 0.5) * 2) * 80);
      const b = Math.round(172 + (1 - t) * (33 - 172));
      ctx.fillStyle = `rgb(${r},${g},${b})`;
      ctx.fillRect(px, py, 2, 2);
    }
    ctx.fillStyle = "#3d3a34";
    ctx.font = "12px monospace";
    ctx.fillText("Survey X/Y units (not WGS84 map)", 12, 18);
    if (localStats) {
      ctx.fillText(
        `TMI sample n=${localStats.n}  min=${localStats.zmin.toFixed(2)}  max=${localStats.zmax.toFixed(2)}`,
        12,
        34,
      );
    }
  }, [wgs84, local, localStats]);

  if (!preview?.ok) {
    return (
      <p className="mt-2 text-sm text-stone">
        {preview?.error || "No TMI preview available yet."}
      </p>
    );
  }

  return (
    <div className="mt-3 space-y-2" data-testid="tmi-survey-preview">
      <p className="text-xs text-stone">
        {wgs84
          ? "WGS84 MapLibre overlay (X=longitude, Y=latitude, colour=TMI)."
          : local?.note ||
            "Local survey preview in file X/Y units — not a geographic basemap."}
      </p>
      {wgs84 ? (
        <div
          ref={mapHost}
          className="h-72 w-full overflow-hidden rounded-xl border border-meadow"
          data-testid="tmi-wgs84-map"
        />
      ) : (
        <canvas
          ref={canvasRef}
          width={720}
          height={360}
          className="h-72 w-full rounded-xl border border-meadow bg-chalk"
          data-testid="tmi-survey-local-canvas"
        />
      )}
      {preview.tmi_statistics && (
        <pre className="overflow-auto rounded-lg bg-mist p-3 text-[11px] text-bark">
          {JSON.stringify(preview.tmi_statistics, null, 2)}
        </pre>
      )}
    </div>
  );
}
