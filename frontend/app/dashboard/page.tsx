"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Gauge, MapPin, Hexagon, Radio } from "lucide-react";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  type AssessResponse,
  type GeoJsonPolygon,
  type GeophysicsLayerMetadata,
  type GravityLayerResponse,
  getActiveTrainedModel,
  getGravityLayer,
  getHealth,
  getReady,
  submitAssess,
} from "@/lib/api";
import { apiUrl } from "@/lib/env";
import { AssessResultModal } from "@/components/AssessResultModal";
import { TRAINING_HREF } from "@/lib/navigation";

/** Soft guidance for Lagos geophysics clip (~2.5–4.5°E, ~5.5–7.5°N). */
const LAGOS_GEO_HINT = {
  minLon: 2.5,
  maxLon: 4.5,
  minLat: 5.5,
  maxLat: 7.5,
};

const HAZARDS = ["subsidence", "landslide", "sinkhole"] as const;
const GRAVITY_SOURCE = "ssri-gravity";
const GRAVITY_LAYER = "ssri-gravity-fill";
const GRAVITY_OUTLINE = "ssri-gravity-outline";

type Mode = "point" | "polygon";

export default function DashboardPage() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("maplibre-gl").Map | undefined>();
  const markerRef = useRef<import("maplibre-gl").Marker | undefined>();
  const drawPointsRef = useRef<[number, number][]>([]);
  const [mapReady, setMapReady] = useState(true);
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "down">("checking");
  const [mode, setMode] = useState<Mode>("point");
  const [point, setPoint] = useState<{ latitude: number; longitude: number } | null>(
    null,
  );
  const [polygon, setPolygon] = useState<GeoJsonPolygon | null>(null);
  const [selectedHazards, setSelectedHazards] = useState<string[]>([...HAZARDS]);
  const [checkpoint, setCheckpoint] = useState("");
  const [featuresPath, setFeaturesPath] = useState("");
  const [produceGeotiff, setProduceGeotiff] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AssessResponse | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [latInput, setLatInput] = useState("");
  const [lonInput, setLonInput] = useState("");
  const [coordError, setCoordError] = useState<string | null>(null);
  const [gravityVisible, setGravityVisible] = useState(true);
  const [gravityMeta, setGravityMeta] = useState<GeophysicsLayerMetadata | null>(
    null,
  );
  const [gravityError, setGravityError] = useState<string | null>(null);
  const [gravityLoaded, setGravityLoaded] = useState(false);

  const redrawPolygon = useCallback(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const pts = drawPointsRef.current;
    const geojson = {
      type: "FeatureCollection" as const,
      features:
        pts.length >= 2
          ? [
              {
                type: "Feature" as const,
                properties: {},
                geometry: {
                  type: "LineString" as const,
                  coordinates: pts,
                },
              },
            ]
          : [],
    };
    const source = map.getSource("draw-line") as
      | import("maplibre-gl").GeoJSONSource
      | undefined;
    if (source) source.setData(geojson);
    else {
      map.addSource("draw-line", { type: "geojson", data: geojson });
      map.addLayer({
        id: "draw-line-layer",
        type: "line",
        source: "draw-line",
        paint: { "line-color": "#3EA6FF", "line-width": 2 },
      });
    }

    if (pts.length >= 3) {
      const ring = [...pts, pts[0]];
      const poly = {
        type: "FeatureCollection" as const,
        features: [
          {
            type: "Feature" as const,
            properties: {},
            geometry: { type: "Polygon" as const, coordinates: [ring] },
          },
        ],
      };
      const polySource = map.getSource("draw-poly") as
        | import("maplibre-gl").GeoJSONSource
        | undefined;
      if (polySource) polySource.setData(poly);
      else {
        map.addSource("draw-poly", { type: "geojson", data: poly });
        map.addLayer({
          id: "draw-poly-fill",
          type: "fill",
          source: "draw-poly",
          paint: { "fill-color": "#3EA6FF", "fill-opacity": 0.2 },
        });
      }
      setPolygon({ type: "Polygon", coordinates: [ring] });
    } else {
      setPolygon(null);
    }
  }, []);

  const modeRef = useRef(mode);
  modeRef.current = mode;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await getHealth();
        await getReady();
        if (!cancelled) setApiStatus("ok");
        try {
          const active = await getActiveTrainedModel();
          if (!cancelled && active.checkpoint_path) {
            setCheckpoint(active.checkpoint_path);
          }
        } catch {
          // Active model is optional; leave checkpoint empty.
        }
      } catch {
        if (!cancelled) setApiStatus("down");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let map: import("maplibre-gl").Map | undefined;
    let cancelled = false;
    const readyTimer = window.setTimeout(() => {
      if (!cancelled) setMapReady(true);
    }, 2500);

    const applyGravity = (
      active: import("maplibre-gl").Map,
      layer: GravityLayerResponse,
    ) => {
      const vmin = layer.metadata.value_min ?? 0;
      const vmax = layer.metadata.value_max ?? 1;
      const geojson = {
        type: "FeatureCollection" as const,
        features: layer.features,
      };
      const existing = active.getSource(GRAVITY_SOURCE) as
        | import("maplibre-gl").GeoJSONSource
        | undefined;
      if (existing) {
        existing.setData(geojson);
      } else {
        active.addSource(GRAVITY_SOURCE, { type: "geojson", data: geojson });
        active.addLayer({
          id: GRAVITY_LAYER,
          type: "fill",
          source: GRAVITY_SOURCE,
          paint: {
            "fill-color": [
              "interpolate",
              ["linear"],
              ["get", "value"],
              vmin,
              "#0B3D5C",
              (vmin + vmax) / 2,
              "#3EA6FF",
              vmax,
              "#F4D35E",
            ],
            "fill-opacity": 0.55,
          },
        });
        active.addLayer({
          id: GRAVITY_OUTLINE,
          type: "line",
          source: GRAVITY_SOURCE,
          paint: {
            "line-color": "#9CC9E8",
            "line-width": 0.4,
            "line-opacity": 0.35,
          },
        });
      }
      active.setLayoutProperty(
        GRAVITY_LAYER,
        "visibility",
        gravityVisible ? "visible" : "none",
      );
      active.setLayoutProperty(
        GRAVITY_OUTLINE,
        "visibility",
        gravityVisible ? "visible" : "none",
      );
    };

    (async () => {
      try {
        const imported = (await import("maplibre-gl")) as unknown as {
          default?: {
            Map: new (options: object) => import("maplibre-gl").Map;
            Marker: new (options?: object) => import("maplibre-gl").Marker;
            NavigationControl: new () => object;
          };
          Map: new (options: object) => import("maplibre-gl").Map;
          Marker: new (options?: object) => import("maplibre-gl").Marker;
          NavigationControl: new () => object;
        };
        const maplibregl = imported.default ?? imported;
        if (cancelled || !mapContainer.current) return;

        // Prefer a geographic basemap; fall back to local empty style for offline/CI.
        const preferredStyle =
          process.env.NEXT_PUBLIC_MAP_STYLE_URL ||
          "https://demotiles.maplibre.org/style.json";
        map = new maplibregl.Map({
          container: mapContainer.current,
          style: preferredStyle,
          center: [3.38, 6.52],
          zoom: 9,
          attributionControl: false,
        });
        mapRef.current = map;
        const markReady = () => {
          if (!cancelled) setMapReady(true);
        };
        map.on("load", markReady);
        map.on("error", (event) => {
          // If remote basemap fails, swap to local empty style once.
          const err = String(event.error ?? "");
          if (
            map &&
            !cancelled &&
            err &&
            map.getStyle()?.sources &&
            Object.keys(map.getStyle()?.sources ?? {}).length === 0
          ) {
            map.setStyle("/map-style.json");
          }
          markReady();
        });
        map.addControl(new maplibregl.NavigationControl() as never, "bottom-right");
        map.on("click", (event) => {
          const { lng, lat } = event.lngLat;
          setError(null);
          const active = mapRef.current;
          if (!active) return;
          if (modeRef.current === "point") {
            setPoint({ latitude: lat, longitude: lng });
            setLatInput(lat.toFixed(5));
            setLonInput(lng.toFixed(5));
            setCoordError(null);
            if (markerRef.current) markerRef.current.remove();
            markerRef.current = new maplibregl.Marker({ color: "#3EA6FF" })
              .setLngLat([lng, lat])
              .addTo(active);
          } else {
            drawPointsRef.current = [...drawPointsRef.current, [lng, lat]];
            redrawPolygon();
          }
        });

        map.once("load", async () => {
          try {
            const layer = await getGravityLayer();
            if (cancelled || !mapRef.current) return;
            applyGravity(mapRef.current, layer);
            setGravityMeta(layer.metadata);
            setGravityLoaded(true);
            setGravityError(null);
            // Fit to gravity extent when available.
            const coords = layer.features.flatMap((f) => f.geometry.coordinates[0]);
            if (coords.length > 0) {
              let minLng = coords[0][0];
              let minLat = coords[0][1];
              let maxLng = coords[0][0];
              let maxLat = coords[0][1];
              for (const [lng, lat] of coords) {
                minLng = Math.min(minLng, lng);
                minLat = Math.min(minLat, lat);
                maxLng = Math.max(maxLng, lng);
                maxLat = Math.max(maxLat, lat);
              }
              mapRef.current.fitBounds(
                [
                  [minLng, minLat],
                  [maxLng, maxLat],
                ],
                { padding: 40, maxZoom: 11 },
              );
            }
          } catch (err) {
            if (!cancelled) {
              setGravityLoaded(false);
              setGravityError(
                err instanceof Error ? err.message : "Gravity layer failed to load",
              );
            }
          }
        });
      } catch {
        if (!cancelled) setMapReady(true);
      }
    })();

    return () => {
      cancelled = true;
      window.clearTimeout(readyTimer);
      map?.remove();
    };
    // gravityVisible is applied via dedicated effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [redrawPolygon]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !gravityLoaded) return;
    const visibility = gravityVisible ? "visible" : "none";
    if (map.getLayer(GRAVITY_LAYER)) {
      map.setLayoutProperty(GRAVITY_LAYER, "visibility", visibility);
    }
    if (map.getLayer(GRAVITY_OUTLINE)) {
      map.setLayoutProperty(GRAVITY_OUTLINE, "visibility", visibility);
    }
  }, [gravityVisible, gravityLoaded]);

  const clearPolygon = useCallback(() => {
    drawPointsRef.current = [];
    setPolygon(null);
    const map = mapRef.current;
    if (!map) return;
    const empty = { type: "FeatureCollection" as const, features: [] };
    (map.getSource("draw-line") as import("maplibre-gl").GeoJSONSource | undefined)?.setData(
      empty,
    );
    (map.getSource("draw-poly") as import("maplibre-gl").GeoJSONSource | undefined)?.setData(
      empty,
    );
  }, []);

  const placePointMarker = useCallback((latitude: number, longitude: number) => {
    const active = mapRef.current;
    if (!active) return;
    setPoint({ latitude, longitude });
    setLatInput(latitude.toFixed(5));
    setLonInput(longitude.toFixed(5));
    if (markerRef.current) markerRef.current.remove();
    void import("maplibre-gl").then((maplibregl) => {
      const map = mapRef.current;
      if (!map) return;
      markerRef.current = new maplibregl.Marker({ color: "#3EA6FF" })
        .setLngLat([longitude, latitude])
        .addTo(map);
    });
  }, []);

  const locateFromCoordinates = useCallback(() => {
    setCoordError(null);
    const lat = Number(latInput.trim());
    const lon = Number(lonInput.trim());
    if (
      !Number.isFinite(lat) ||
      !Number.isFinite(lon) ||
      latInput.trim() === "" ||
      lonInput.trim() === ""
    ) {
      setCoordError("Enter numeric latitude and longitude.");
      return;
    }
    if (lat < -90 || lat > 90) {
      setCoordError("Latitude must be between -90 and 90.");
      return;
    }
    if (lon < -180 || lon > 180) {
      setCoordError("Longitude must be between -180 and 180.");
      return;
    }
    if (
      lon < LAGOS_GEO_HINT.minLon ||
      lon > LAGOS_GEO_HINT.maxLon ||
      lat < LAGOS_GEO_HINT.minLat ||
      lat > LAGOS_GEO_HINT.maxLat
    ) {
      setCoordError(
        `Coordinates are outside the Lagos geophysics coverage (~${LAGOS_GEO_HINT.minLon}–${LAGOS_GEO_HINT.maxLon}°E, ${LAGOS_GEO_HINT.minLat}–${LAGOS_GEO_HINT.maxLat}°N). Live gravity/magnetics may be empty outside this clip.`,
      );
    } else {
      setCoordError(null);
    }
    setMode("point");
    clearPolygon();
    placePointMarker(lat, lon);
    const map = mapRef.current;
    if (map) {
      map.flyTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 12) });
    }
  }, [latInput, lonInput, clearPolygon, placePointMarker]);

  const onAssess = useCallback(async () => {
    if (!featuresPath && mode === "point" && !point) {
      setError("Click the map to select a point, or provide offline features path.");
      return;
    }
    if (!featuresPath && mode === "polygon" && !polygon) {
      setError("Draw a polygon (3+ clicks) or provide offline features path.");
      return;
    }
    if (!featuresPath && !point && !polygon) {
      setError(
        "Provide offline features, or select a point/polygon on the map.",
      );
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    setModalOpen(true);
    try {
      const response = await submitAssess({
        point: mode === "point" && !featuresPath ? point ?? undefined : undefined,
        polygon_geojson:
          mode === "polygon" && !featuresPath ? polygon ?? undefined : undefined,
        features: featuresPath || undefined,
        checkpoint: checkpoint || undefined,
        hazards: selectedHazards,
        mc_samples: 20,
        produce_geotiff: produceGeotiff,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [
    mode,
    point,
    polygon,
    checkpoint,
    featuresPath,
    selectedHazards,
    produceGeotiff,
  ]);

  const toggleHazard = (hazard: string) => {
    setSelectedHazards((prev) =>
      prev.includes(hazard) ? prev.filter((h) => h !== hazard) : [...prev, hazard],
    );
  };

  return (
    <main className="flex h-screen flex-col bg-void text-ink md:flex-row">
      <aside className="glass z-10 w-full space-y-6 overflow-y-auto border-b border-line p-6 md:h-full md:w-96 md:border-b-0 md:border-r">
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-muted transition hover:text-electric"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to site
          </Link>
          <p className="mt-4 font-mono text-[11px] uppercase tracking-widest text-cyan">
            SSRI Dashboard
          </p>
          <h1 className="mt-2 font-display text-xl font-medium text-ink">
            Risk Assessment Workspace
          </h1>
          <p className="mt-2 flex items-center gap-2 font-mono text-[11px] text-muted">
            <Radio className="h-3.5 w-3.5" />
            API {apiUrl} —{" "}
            {apiStatus === "checking"
              ? "checking…"
              : apiStatus === "ok"
                ? "reachable"
                : "unreachable"}
          </p>
          <Link
            href={TRAINING_HREF}
            className="mt-3 inline-flex text-xs text-electric hover:underline"
          >
            Open Manual Training →
          </Link>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => {
              setMode("point");
              clearPolygon();
            }}
            className={`flex-1 rounded-lg border px-3 py-2 text-xs ${
              mode === "point" ? "border-electric text-electric" : "border-line text-muted"
            }`}
          >
            <MapPin className="mr-1 inline h-3.5 w-3.5" />
            Point
          </button>
          <button
            type="button"
            onClick={() => setMode("polygon")}
            className={`flex-1 rounded-lg border px-3 py-2 text-xs ${
              mode === "polygon"
                ? "border-electric text-electric"
                : "border-line text-muted"
            }`}
          >
            <Hexagon className="mr-1 inline h-3.5 w-3.5" />
            Polygon
          </button>
        </div>

        <div
          className="rounded-xl border border-line bg-core px-4 py-3"
          data-testid="gravity-layer-panel"
        >
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] uppercase tracking-widest text-muted">
              Gravity layer
            </p>
            <label className="flex items-center gap-2 font-mono text-[11px] text-ink">
              <input
                type="checkbox"
                data-testid="gravity-visibility-toggle"
                checked={gravityVisible}
                onChange={(e) => setGravityVisible(e.target.checked)}
                disabled={!gravityLoaded}
              />
              Visible
            </label>
          </div>
          {gravityMeta ? (
            <div className="mt-2 space-y-1 text-[11px] text-muted">
              <p className="text-ink" data-testid="gravity-layer-title">
                {gravityMeta.title}
              </p>
              <p>
                {gravityMeta.units}
                {gravityMeta.value_min != null && gravityMeta.value_max != null
                  ? ` · ${gravityMeta.value_min.toFixed(1)}–${gravityMeta.value_max.toFixed(1)}`
                  : ""}
              </p>
              <p>{gravityMeta.native_resolution}</p>
              <p className="text-[10px] leading-snug">{gravityMeta.scientific_limitation}</p>
            </div>
          ) : (
            <p className="mt-2 text-[11px] text-muted" data-testid="gravity-layer-status">
              {gravityError
                ? `Unavailable: ${gravityError}`
                : "Loading WGM2012 Bouguer layer…"}
            </p>
          )}
        </div>

        <div className="rounded-xl border border-line bg-core px-4 py-4">
          <p className="text-xs uppercase tracking-widest text-muted">
            {mode === "point" ? "Selected point" : "Drawn polygon"}
          </p>
          <p className="mt-2 font-mono text-sm text-ink">
            {mode === "point"
              ? point
                ? `${point.latitude.toFixed(5)}, ${point.longitude.toFixed(5)}`
                : "Click the map or enter coordinates below"
              : polygon
                ? `${polygon.coordinates[0].length - 1} vertices`
                : "Click 3+ times to draw; clear to reset"}
          </p>
          {mode === "polygon" && (
            <button
              type="button"
              onClick={clearPolygon}
              className="mt-2 text-[11px] text-muted underline"
            >
              Clear polygon
            </button>
          )}

          {mode === "point" && (
            <div
              className="mt-4 space-y-2 rounded-lg border border-line/80 bg-void/60 p-3"
              data-testid="coordinate-entry"
            >
              <p className="text-[11px] uppercase tracking-widest text-muted">
                Enter coordinates
              </p>
              <div className="grid grid-cols-2 gap-2">
                <label className="block text-[11px] text-muted">
                  Latitude
                  <input
                    data-testid="coord-latitude"
                    value={latInput}
                    onChange={(e) => setLatInput(e.target.value)}
                    inputMode="decimal"
                    className="mt-1 w-full rounded border border-line bg-void px-2 py-1.5 font-mono text-xs text-ink"
                    placeholder="6.5244"
                  />
                </label>
                <label className="block text-[11px] text-muted">
                  Longitude
                  <input
                    data-testid="coord-longitude"
                    value={lonInput}
                    onChange={(e) => setLonInput(e.target.value)}
                    inputMode="decimal"
                    className="mt-1 w-full rounded border border-line bg-void px-2 py-1.5 font-mono text-xs text-ink"
                    placeholder="3.3792"
                  />
                </label>
              </div>
              <button
                type="button"
                data-testid="coord-locate"
                onClick={locateFromCoordinates}
                className="w-full rounded-lg border border-electric/60 px-3 py-1.5 text-xs text-electric hover:bg-electric/10"
              >
                Locate
              </button>
              {coordError && (
                <p
                  className="text-[11px] text-amber-200"
                  data-testid="coord-error"
                  role="alert"
                >
                  {coordError}
                </p>
              )}
            </div>
          )}

          <label className="mt-4 block text-[11px] text-muted">
            Checkpoint path (server-visible)
            <input
              value={checkpoint}
              onChange={(e) => setCheckpoint(e.target.value)}
              className="mt-1 w-full rounded border border-line bg-void px-2 py-1.5 font-mono text-xs text-ink"
              placeholder="/data/models/best.pt"
            />
          </label>
          <label className="mt-3 block text-[11px] text-muted">
            Offline features .npy (optional)
            <input
              value={featuresPath}
              onChange={(e) => setFeaturesPath(e.target.value)}
              className="mt-1 w-full rounded border border-line bg-void px-2 py-1.5 font-mono text-xs text-ink"
              placeholder="/data/features/sample.npy"
            />
          </label>

          <div className="mt-3 flex flex-wrap gap-2">
            {HAZARDS.map((hazard) => (
              <button
                key={hazard}
                type="button"
                onClick={() => toggleHazard(hazard)}
                className={`rounded border px-2 py-1 text-[11px] ${
                  selectedHazards.includes(hazard)
                    ? "border-electric text-electric"
                    : "border-line text-muted"
                }`}
              >
                {hazard}
              </button>
            ))}
          </div>

          <label className="mt-3 flex items-center gap-2 text-[11px] text-muted">
            <input
              type="checkbox"
              checked={produceGeotiff}
              onChange={(e) => setProduceGeotiff(e.target.checked)}
            />
            Produce GeoTIFF / signed URL when available
          </label>

          <button
            type="button"
            onClick={onAssess}
            disabled={loading || selectedHazards.length === 0}
            className="mt-4 w-full rounded-lg bg-electric px-4 py-2 text-sm font-medium text-void disabled:opacity-40"
          >
            {loading ? "Assessing…" : "Run assessment"}
          </button>
          <p className="mt-2 text-[11px] text-muted">
            Live AOI needs GEE/OpenTopo + SSRI_LIVE_ACQUISITION_ENABLED. Offline path uses
            features + checkpoint on the API host.
          </p>
        </div>

        {error && !modalOpen && (
          <div className="rounded-xl border border-amber-500/40 bg-core px-4 py-3 text-xs text-amber-200">
            {error}
          </div>
        )}

        {result && !modalOpen && (
          <button
            type="button"
            data-testid="reopen-assess-result"
            onClick={() => setModalOpen(true)}
            className="flex w-full items-center justify-between rounded-xl border border-line bg-core px-4 py-3 text-left text-xs text-ink"
          >
            <span className="flex items-center gap-2">
              <Gauge className="h-3.5 w-3.5 text-cyan" />
              Last result · {result.assessment_id}
            </span>
            <span className="text-electric">View</span>
          </button>
        )}
      </aside>

      <div className="relative flex-1">
        <div
          ref={mapContainer}
          data-testid="ssri-map"
          className="h-full w-full"
        />
        {!mapReady && (
          <div className="absolute inset-0 flex items-center justify-center bg-void">
            <span className="font-mono text-xs text-muted">Loading map…</span>
          </div>
        )}
        <div
          data-testid="ssri-map-status"
          data-map-ready={mapReady ? "true" : "false"}
          data-gravity-loaded={gravityLoaded ? "true" : "false"}
          data-gravity-visible={gravityVisible ? "true" : "false"}
          className="sr-only"
        >
          {mapReady ? "map-ready" : "map-loading"}
          {gravityLoaded ? " gravity-loaded" : " gravity-pending"}
        </div>
      </div>

      <AssessResultModal
        open={modalOpen}
        loading={loading}
        error={error}
        result={result}
        locationLabel={
          mode === "point" && point
            ? `${point.latitude.toFixed(5)}, ${point.longitude.toFixed(5)}`
            : mode === "polygon" && polygon
              ? `Polygon (${polygon.coordinates[0].length - 1} vertices)`
              : featuresPath
                ? `Offline features: ${featuresPath}`
                : null
        }
        onClose={() => setModalOpen(false)}
        onViewMap={() => setModalOpen(false)}
      />
    </main>
  );
}
