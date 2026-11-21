"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Gauge, MapPin, Hexagon, Radio } from "lucide-react";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  type AssessResponse,
  type CheckpointGeography,
  type GeoJsonPolygon,
  type GeophysicsLayerMetadata,
  type GravityLayerResponse,
  type ShellHazard,
  type ShellSettings,
  fetchCheckpointGeography,
  getActiveTrainedModel,
  getGravityLayer,
  getHealth,
  getReady,
  getShellStatusFull,
  submitAssess,
} from "@/lib/api";
import { apiUrl } from "@/lib/env";
import {
  COORD_DECIMALS,
  coverageMessage,
  formatLatLon,
  isWithinCoverage,
  parseLatLon,
  pointInRegion,
} from "@/lib/coordinates";
import { AssessResultModal } from "@/components/AssessResultModal";
import { ProductCapabilities } from "@/components/product/ProductCapabilities";
import { LandPhoto } from "@/components/theme/LandPhoto";
import { RequireSession, useRequiredSession } from "@/components/auth/RequireSession";
import { buildConditioningGroups } from "@/lib/conditioning";
import { apiHealthLabel } from "@/lib/apiHealthStatus";
import {
  formatGravityUnavailableMessage,
  gravityLoadState,
  gravityVisibilityLabel,
} from "@/lib/gravityLayer";
import { TRAINING_HREF } from "@/lib/navigation";
import {
  PRODUCT_HAZARD_IDS,
  mergeHazardNames,
} from "@/lib/productCapabilities";
import { getSupabase } from "@/lib/supabase";

/** Canonical Stage 2.5 hazards mirrored until the backend registry responds. */
const FALLBACK_HAZARDS = PRODUCT_HAZARD_IDS;

const GRAVITY_SOURCE = "ssri-gravity";
const GRAVITY_LAYER = "ssri-gravity-fill";
const GRAVITY_OUTLINE = "ssri-gravity-outline";

const REGION_SOURCE = "ssri-training-region";
const REGION_FILL = "ssri-training-region-fill";
const REGION_LINE = "ssri-training-region-outline";

type Mode = "point" | "polygon";

function AssessmentWorkspace() {
  const router = useRouter();
  const { email } = useRequiredSession();
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("maplibre-gl").Map | undefined>();
  const markerRef = useRef<import("maplibre-gl").Marker | undefined>();
  const drawPointsRef = useRef<[number, number][]>([]);
  const [mapReady, setMapReady] = useState(true);
  const [apiStatus, setApiStatus] = useState<
    "checking" | "ok" | "degraded" | "down"
  >("checking");
  const [mode, setMode] = useState<Mode>("point");
  const [point, setPoint] = useState<{ latitude: number; longitude: number } | null>(
    null,
  );
  const [polygon, setPolygon] = useState<GeoJsonPolygon | null>(null);
  const [hazards, setHazards] = useState<string[]>([...FALLBACK_HAZARDS]);
  const [shellSettings, setShellSettings] = useState<ShellSettings | null>(null);
  const [selectedHazards, setSelectedHazards] = useState<string[]>([
    ...FALLBACK_HAZARDS,
  ]);
  const [checkpoint, setCheckpoint] = useState("");
  const [activeModelId, setActiveModelId] = useState<string | null>(null);
  const [activeModelLabel, setActiveModelLabel] = useState<string | null>(null);
  const [checkpointAvailable, setCheckpointAvailable] = useState(false);
  const [featuresPath, setFeaturesPath] = useState("");
  const [produceGeotiff, setProduceGeotiff] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AssessResponse | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [latInput, setLatInput] = useState("");
  const [lonInput, setLonInput] = useState("");
  const [coordError, setCoordError] = useState<string | null>(null);
  const [gravityVisible, setGravityVisible] = useState(false);
  const [gravityMeta, setGravityMeta] = useState<GeophysicsLayerMetadata | null>(
    null,
  );
  const [gravityError, setGravityError] = useState<string | null>(null);
  const [gravityLoaded, setGravityLoaded] = useState(false);
  const gravityState = gravityLoadState({
    loaded: gravityLoaded,
    error: gravityError,
  });
  const [mapLoaded, setMapLoaded] = useState(false);
  const [shellEnabled, setShellEnabled] = useState(false);
  // Release-shell geography is keyed by checkpoint so a stale value is never
  // shown while a new checkpoint's geography is still loading.
  const [geographyState, setGeographyState] = useState<{
    checkpoint: string;
    data: CheckpointGeography | null;
    error: string | null;
  } | null>(null);
  const [projectedState, setProjectedState] = useState<{
    key: string;
    value: CheckpointGeography["point_converted"];
  } | null>(null);
  const geography =
    shellEnabled && geographyState && geographyState.checkpoint === checkpoint
      ? geographyState.data
      : null;
  const geographyError =
    shellEnabled && geographyState && geographyState.checkpoint === checkpoint
      ? geographyState.error
      : null;
  const projectedKey =
    shellEnabled && checkpoint && point && geography?.crs_declared
      ? `${checkpoint}|${point.latitude}|${point.longitude}`
      : null;
  const projectedPoint =
    projectedKey && projectedState?.key === projectedKey
      ? projectedState.value
      : null;

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
  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await getHealth();
        try {
          await getReady();
          if (!cancelled) setApiStatus("ok");
        } catch {
          // API process is reachable; Redis/queue readiness failed separately.
          if (!cancelled) setApiStatus("degraded");
        }
      } catch {
        if (!cancelled) setApiStatus("down");
      }
      // Resolve promoted model metadata for status UI. Ordinary assessments omit
      // filesystem paths and let /assess resolve the registry server-side.
      try {
        const active = await getActiveTrainedModel();
        if (!cancelled) {
          const available = Boolean(
            active.checkpoint_available ?? active.checkpoint_path,
          );
          setCheckpointAvailable(available);
          setActiveModelId(active.model_id ?? active.active?.model_id ?? null);
          setActiveModelLabel(
            active.active
              ? `${active.active.name} (${active.active.model_id})`
              : null,
          );
          // Keep advanced operator field empty by default so clients never send
          // internal paths. Operators may paste a path under advanced options.
        }
      } catch {
        if (!cancelled) {
          setCheckpointAvailable(false);
          setActiveModelId(null);
          setActiveModelLabel(null);
        }
      }
      try {
        const status = await getShellStatusFull();
        const registry: ShellHazard[] = status.settings?.hazards ?? [];
        const names = mergeHazardNames(
          registry.filter((h) => h.enabled_by_default).map((h) => h.name),
        );
        if (!cancelled) {
          setHazards(names);
          setSelectedHazards(names);
        }
        if (!cancelled && status.settings) setShellSettings(status.settings);
        if (!cancelled) setShellEnabled(Boolean(status.release_shell_enabled));
      } catch {
        // Backend registry unavailable; keep the mirrored fallback list.
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
          if (!cancelled) {
            setMapReady(true);
            setMapLoaded(true);
          }
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
            setLatInput(lat.toFixed(COORD_DECIMALS));
            setLonInput(lng.toFixed(COORD_DECIMALS));
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
            setGravityVisible(true);
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
              setGravityVisible(false);
              setGravityMeta(null);
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

  // Release shell only: read the checkpoint's declared CRS + training region.
  useEffect(() => {
    if (!shellEnabled || !checkpoint) return;
    let cancelled = false;
    (async () => {
      try {
        const { geography: geo } = await fetchCheckpointGeography(checkpoint);
        if (!cancelled) {
          setGeographyState({ checkpoint, data: geo, error: null });
        }
      } catch (err) {
        if (!cancelled) {
          setGeographyState({
            checkpoint,
            data: null,
            error: err instanceof Error ? err.message : String(err),
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [shellEnabled, checkpoint]);

  // Release shell only: convert the selected map click on the backend (pyproj).
  useEffect(() => {
    if (!projectedKey || !point) return;
    const key = projectedKey;
    const geoPoint = point;
    let cancelled = false;
    (async () => {
      try {
        const { geography: geo } = await fetchCheckpointGeography(checkpoint, geoPoint);
        if (!cancelled) {
          setProjectedState({ key, value: geo.point_converted ?? null });
        }
      } catch {
        if (!cancelled) setProjectedState({ key, value: null });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectedKey, checkpoint, point]);

  // Draw the training region as a dashed outline (release shell only).
  useEffect(() => {
    const map = mapRef.current;
    const extent = geography?.region_extent;
    if (!map || !extent) return;
    const ring: [number, number][] = [
      [extent.lon_min, extent.lat_min],
      [extent.lon_max, extent.lat_min],
      [extent.lon_max, extent.lat_max],
      [extent.lon_min, extent.lat_max],
      [extent.lon_min, extent.lat_min],
    ];
    const data = {
      type: "FeatureCollection" as const,
      features: [
        {
          type: "Feature" as const,
          properties: {},
          geometry: { type: "Polygon" as const, coordinates: [ring] },
        },
      ],
    };
    const draw = () => {
      const active = mapRef.current;
      if (!active) return;
      const existing = active.getSource(REGION_SOURCE) as
        | import("maplibre-gl").GeoJSONSource
        | undefined;
      if (existing) {
        existing.setData(data);
        return;
      }
      active.addSource(REGION_SOURCE, { type: "geojson", data });
      active.addLayer({
        id: REGION_FILL,
        type: "fill",
        source: REGION_SOURCE,
        paint: { "fill-color": "#F4D35E", "fill-opacity": 0.08 },
      });
      active.addLayer({
        id: REGION_LINE,
        type: "line",
        source: REGION_SOURCE,
        paint: {
          "line-color": "#F4D35E",
          "line-width": 1.5,
          "line-dasharray": [2, 2],
        },
      });
    };
    if (map.isStyleLoaded()) draw();
    else map.once("load", draw);
  }, [geography, mapLoaded]);

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
    setLatInput(latitude.toFixed(COORD_DECIMALS));
    setLonInput(longitude.toFixed(COORD_DECIMALS));
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
    const parsed = parseLatLon(latInput, lonInput);
    if (!parsed.ok) {
      setCoordError(parsed.error);
      return;
    }
    const { latitude: lat, longitude: lon } = parsed;
    if (!isWithinCoverage(lat, lon)) {
      setCoordError(coverageMessage());
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
      setError("Click the map or enter coordinates to select a point.");
      return;
    }
    if (!featuresPath && mode === "polygon" && !polygon) {
      setError("Draw a polygon on the map (3+ clicks).");
      return;
    }
    if (!featuresPath && !point && !polygon) {
      setError("Select a point or polygon on the map before running an assessment.");
      return;
    }
    if (shellEnabled && checkpoint && geography && !geography.crs_declared) {
      setError(
        "This checkpoint does not declare a CRS, so the point cannot be placed " +
          "on the map. Add a declared CRS to the dataset manifest and re-train, " +
          "then run the assessment again.",
      );
      return;
    }
    if (!checkpoint.trim() && !checkpointAvailable) {
      setError(
        "No valid production checkpoint is configured. Ask an operator to promote " +
          "a trained Stage 2.5 (13-channel) model, then retry. Ordinary assessments " +
          "do not require a server filesystem path.",
      );
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    setModalOpen(true);
    try {
      const response = await submitAssess({
        // Always send the picked AOI: the backend accepts a point/polygon
        // alongside offline `features`, and the release-shell gate needs it to
        // decide in-region vs outside_training_region.
        point: mode === "point" ? point ?? undefined : undefined,
        polygon_geojson: mode === "polygon" ? polygon ?? undefined : undefined,
        features: featuresPath || undefined,
        // Ordinary clients omit checkpoint so the API resolves the promoted model.
        checkpoint: checkpoint.trim() || undefined,
        model_id:
          !checkpoint.trim() && activeModelId ? activeModelId : undefined,
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
    checkpointAvailable,
    activeModelId,
    featuresPath,
    selectedHazards,
    produceGeotiff,
    shellEnabled,
    geography,
  ]);

  const toggleHazard = (hazard: string) => {
    setSelectedHazards((prev) =>
      prev.includes(hazard) ? prev.filter((h) => h !== hazard) : [...prev, hazard],
    );
  };

  return (
    <main className="flex h-screen flex-col bg-mist text-bark md:flex-row">
      <aside className="z-10 w-full space-y-6 overflow-y-auto border-b border-meadow bg-chalk p-6 md:h-full md:w-96 md:border-b-0 md:border-r">
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-stone transition hover:text-moss"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to site
          </Link>
          <LandPhoto
            unsplash="fields"
            alt="Aerial view of the farmland you can assess"
            caption="Check the ground"
            className="mt-4"
            height="h-28"
          />
          <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-stone">
            <span className="truncate">{email}</span>
            <button
              type="button"
              className="shrink-0 text-moss"
              onClick={async () => {
                await getSupabase()?.auth.signOut();
                router.replace("/login?next=/dashboard");
              }}
            >
              Log out
            </button>
          </div>
          <p className="mt-4 font-mono text-[11px] uppercase tracking-widest text-leaf">
            SSRI Dashboard
          </p>
          <h1 className="mt-2 font-display text-xl font-medium text-bark">
            Risk Assessment Workspace
          </h1>
          <p className="mt-2 flex items-center gap-2 font-mono text-[11px] text-stone">
            <Radio className="h-3.5 w-3.5" />
            API {apiUrl} —{" "}
            <span data-testid="api-health-status">{apiHealthLabel(apiStatus)}</span>
          </p>
          <Link
            href={TRAINING_HREF}
            className="mt-3 inline-flex text-xs text-moss hover:underline"
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
              mode === "point" ? "border-leaf text-moss" : "border-meadow text-stone"
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
                ? "border-leaf text-moss"
                : "border-meadow text-stone"
            }`}
          >
            <Hexagon className="mr-1 inline h-3.5 w-3.5" />
            Polygon
          </button>
        </div>

        <div
          className="rounded-xl border border-meadow bg-chalk px-4 py-3"
          data-testid="gravity-layer-panel"
          data-gravity-state={gravityState}
        >
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] uppercase tracking-widest text-stone">
              Gravity overlay
            </p>
            <label className="flex items-center gap-2 font-mono text-[11px] text-bark">
              <input
                type="checkbox"
                data-testid="gravity-visibility-toggle"
                checked={gravityLoaded && gravityVisible}
                onChange={(e) => setGravityVisible(e.target.checked)}
                disabled={!gravityLoaded}
              />
              <span data-testid="gravity-visibility-label">
                {gravityVisibilityLabel(gravityState, gravityVisible)}
              </span>
            </label>
          </div>
          <p
            className="mt-2 text-[11px] text-stone"
            data-testid="gravity-layer-status"
          >
            {gravityState === "ready"
              ? "Optional map overlay ready (not required for assessment)."
              : gravityState === "unavailable"
                ? formatGravityUnavailableMessage(gravityError)
                : "Loading optional WGM2012 Bouguer overlay…"}
          </p>
          {gravityMeta ? (
            <div className="mt-2 space-y-1 text-[11px] text-stone">
              <p className="text-bark" data-testid="gravity-layer-title">
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
          ) : null}
        </div>

        <div className="rounded-xl border border-meadow bg-chalk px-4 py-4">
          <p className="text-xs uppercase tracking-widest text-stone">
            {mode === "point" ? "Selected point" : "Drawn polygon"}
          </p>
          <p className="mt-2 font-mono text-sm text-bark">
            {mode === "point"
              ? point
                ? formatLatLon(point.latitude, point.longitude)
                : "Click the map or enter coordinates below"
              : polygon
                ? `${polygon.coordinates[0].length - 1} vertices`
                : "Click 3+ times to draw; clear to reset"}
          </p>
          {mode === "polygon" && (
            <button
              type="button"
              onClick={clearPolygon}
              className="mt-2 text-[11px] text-stone underline"
            >
              Clear polygon
            </button>
          )}

          {mode === "point" && (
            <div
              className="mt-4 space-y-2 rounded-lg border border-meadow bg-mist p-3"
              data-testid="coordinate-entry"
            >
              <p className="text-[11px] uppercase tracking-widest text-stone">
                Enter coordinates
              </p>
              <div className="grid grid-cols-2 gap-2">
                <label className="block text-[11px] text-stone">
                  Latitude
                  <input
                    data-testid="coord-latitude"
                    value={latInput}
                    onChange={(e) => setLatInput(e.target.value)}
                    inputMode="decimal"
                    className="mt-1 w-full rounded border border-meadow bg-mist px-2 py-1.5 font-mono text-xs text-bark"
                    placeholder="6.5244"
                  />
                </label>
                <label className="block text-[11px] text-stone">
                  Longitude
                  <input
                    data-testid="coord-longitude"
                    value={lonInput}
                    onChange={(e) => setLonInput(e.target.value)}
                    inputMode="decimal"
                    className="mt-1 w-full rounded border border-meadow bg-mist px-2 py-1.5 font-mono text-xs text-bark"
                    placeholder="3.3792"
                  />
                </label>
              </div>
              <button
                type="button"
                data-testid="coord-locate"
                onClick={locateFromCoordinates}
                className="w-full rounded-lg border border-leaf px-3 py-1.5 text-xs text-moss hover:bg-meadow"
              >
                Locate
              </button>
              {coordError && (
                <p
                  className="text-[11px] text-amber-900"
                  data-testid="coord-error"
                  role="alert"
                >
                  {coordError}
                </p>
              )}
              {shellEnabled && geography && (
                <div
                  className="space-y-1 border-t border-meadow pt-2 text-[10px] leading-snug text-stone"
                  data-testid="checkpoint-geography"
                >
                  <p data-testid="checkpoint-crs">
                    Declared CRS: {geography.crs ?? "none — assessment is blocked"}
                  </p>
                  {geography.region_extent && (
                    <p data-testid="training-region">
                      Training region:{" "}
                      {geography.region_extent.lat_min.toFixed(3)}–
                      {geography.region_extent.lat_max.toFixed(3)}°N,{" "}
                      {geography.region_extent.lon_min.toFixed(3)}–
                      {geography.region_extent.lon_max.toFixed(3)}°E (dashed
                      outline on the map)
                    </p>
                  )}
                  {point && projectedPoint && (
                    <p data-testid="projected-point">
                      {projectedPoint.crs}: x {projectedPoint.x.toFixed(3)}, y{" "}
                      {projectedPoint.y.toFixed(3)} ({projectedPoint.axis_order})
                    </p>
                  )}
                </div>
              )}
              {shellEnabled && geographyError && (
                <p
                  className="text-[11px] text-amber-900"
                  data-testid="geography-error"
                  role="alert"
                >
                  {geographyError}
                </p>
              )}
              {shellEnabled &&
                point &&
                geography?.region_extent &&
                !pointInRegion(
                  point.latitude,
                  point.longitude,
                  geography.region_extent,
                ) && (
                  <p
                    className="text-[11px] text-amber-900"
                    data-testid="region-warning"
                    role="alert"
                  >
                    This point is outside the training region. The backend reports
                    outside_training_region and withholds scores for it.
                  </p>
                )}
            </div>
          )}

          <div
            className="mt-4 rounded-lg border border-meadow bg-mist px-3 py-2"
            data-testid="active-model-status"
          >
            <p className="text-[11px] uppercase tracking-widest text-stone">
              Production model
            </p>
            {checkpointAvailable && activeModelLabel ? (
              <p className="mt-1 text-xs text-bark" data-testid="active-model-label">
                Using promoted registry model: {activeModelLabel}
              </p>
            ) : (
              <p className="mt-1 text-xs text-amber-900" data-testid="active-model-missing">
                No promoted Stage 2.5 checkpoint is configured. Assessments cannot run
                until an operator promotes a trained model.
              </p>
            )}
            <p className="mt-1 text-[10px] text-stone">
              Live inference uses the 13-channel Stage 2.5 contract. Schema-v2
              (16-channel) stacks are not used for live map assessment.
            </p>
          </div>

          <details
            className="mt-4 rounded-lg border border-meadow bg-mist px-3 py-2"
            data-testid="advanced-operator-options"
          >
            <summary className="cursor-pointer text-[11px] text-stone">
              Advanced operator options
            </summary>
            <p className="mt-2 text-[10px] leading-snug text-stone">
              Server filesystem paths for operators and tests only. Ordinary assessments
              resolve the promoted registry model on the server and do not send internal
              paths. Prefer{" "}
              <Link href="/training/operator" className="underline">
                operator training
              </Link>{" "}
              or <Link href="/shell" className="underline">/shell</Link> for schema-v2
              offline workflows.
            </p>
            <label className="mt-3 block text-[11px] text-stone">
              Checkpoint path override (operators)
              <input
                value={checkpoint}
                onChange={(e) => setCheckpoint(e.target.value)}
                className="mt-1 w-full rounded border border-meadow bg-chalk px-2 py-1.5 font-mono text-xs text-bark"
                placeholder="Leave empty to use the promoted model"
                data-testid="checkpoint-path"
              />
            </label>
            <label className="mt-3 block text-[11px] text-stone">
              Offline features .npy (optional)
              <input
                value={featuresPath}
                onChange={(e) => setFeaturesPath(e.target.value)}
                className="mt-1 w-full rounded border border-meadow bg-chalk px-2 py-1.5 font-mono text-xs text-bark"
                placeholder="/data/features/sample.npy"
                data-testid="offline-features"
              />
            </label>
          </details>

          <div className="mt-3" data-testid="hazard-selector">
            <p className="text-[11px] uppercase tracking-widest text-stone">
              Hazards
            </p>
            <div className="mt-1 flex flex-wrap gap-2">
              {hazards.map((hazard) => (
                <button
                  key={hazard}
                  type="button"
                  onClick={() => toggleHazard(hazard)}
                  data-testid={`hazard-option-${hazard}`}
                  className={`rounded border px-2 py-1 text-[11px] ${
                    selectedHazards.includes(hazard)
                      ? "border-leaf text-moss"
                      : "border-meadow text-stone"
                  }`}
                >
                  {hazard}
                </button>
              ))}
            </div>
            <p className="mt-1 text-[10px] text-stone" data-testid="hazard-visibility-note">
              All three Stage 2.5 hazards are listed: subsidence, landslide, and
              sinkhole.
              {shellSettings
                ? ` Channel schema: ${shellSettings.default_channel_schema}${
                    shellSettings.channel_schemas?.[
                      shellSettings.default_channel_schema
                    ]
                      ? ` (${shellSettings.channel_schemas[shellSettings.default_channel_schema].channel_count} channels)`
                      : ""
                  }.`
                : ""}
            </p>
          </div>

          <div className="mt-4" data-testid="geological-conditioning-panel">
            <p className="text-[11px] uppercase tracking-widest text-stone">
              Geological conditioning
            </p>
            <ul className="mt-2 space-y-1 text-[11px] text-stone">
              <li data-testid="geo-cap-overburden">
                Overburden thickness — offline conditioning supported; live inference
                integration pending
              </li>
              <li data-testid="geo-cap-lineament-density">
                Lineament density — available for geological data management; live
                inference integration pending
              </li>
              <li data-testid="geo-cap-lineament-distance">
                Distance to lineaments — available for geological data management; live
                inference integration pending
              </li>
            </ul>
            <p className="mt-2 text-[10px] text-stone">
              These are not hazards. They do not currently change live map assessment
              scores (13-channel Stage 2.5). Manage datasets at{" "}
              <Link href="/geological" className="underline">
                /geological
              </Link>
              .
            </p>
          </div>

          <label className="mt-3 flex items-center gap-2 text-[11px] text-stone">
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
            className="mt-4 w-full rounded-lg bg-leaf px-4 py-2 text-sm font-medium text-chalk disabled:opacity-40"
          >
            {loading ? "Assessing…" : "Run assessment"}
          </button>
          <p className="mt-2 text-[11px] text-stone">
            Live map assessments use the Stage 2.5 v1 (13-channel) stack. Lineaments and
            overburden appear in results as available/unavailable analytics; they are only
            used in inference when present in a schema-v2 offline stack. Scores remain
            NOT_VALIDATED.
          </p>

          <ProductCapabilities variant="panel" className="mt-4" />
        </div>

        {error && !modalOpen && (
          <div className="rounded-xl border border-amber-300 bg-chalk px-4 py-3 text-xs text-amber-900">
            {error}
          </div>
        )}

        {result && !modalOpen && (
          <div
            className="rounded-xl border border-meadow bg-chalk px-4 py-3 text-left text-xs text-bark"
            data-testid="assess-analytics-summary"
          >
            <button
              type="button"
              data-testid="reopen-assess-result"
              onClick={() => setModalOpen(true)}
              className="flex w-full items-center justify-between text-left"
            >
              <span className="flex items-center gap-2">
                <Gauge className="h-3.5 w-3.5 text-leaf" />
                Last result · {result.assessment_id}
              </span>
              <span className="text-moss">View</span>
            </button>
            <div className="mt-3 space-y-2 border-t border-meadow pt-3">
              <p className="text-[10px] uppercase tracking-widest text-stone">
                Lineament &amp; overburden
              </p>
              {buildConditioningGroups(result.conditioning_features).map((group) => (
                <div key={group.id} data-testid={`assess-summary-${group.id}`}>
                  <p className="font-medium text-bark">{group.title}</p>
                  <ul className="mt-1 space-y-0.5 text-[11px] text-stone">
                    {group.metrics.map((metric) => (
                      <li key={metric.key}>
                        {metric.label}: {metric.valueText}
                        {metric.status === "available" && metric.unit
                          ? ` ${metric.unit}`
                          : ` · ${metric.status}`}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>

      <div className="relative flex-1">
        <div
          ref={mapContainer}
          data-testid="ssri-map"
          className="h-full w-full"
        />
        {!mapReady && (
          <div className="absolute inset-0 flex items-center justify-center bg-mist">
            <span className="font-mono text-xs text-stone">Loading map…</span>
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
            ? formatLatLon(point.latitude, point.longitude)
            : mode === "polygon" && polygon
              ? `Polygon (${polygon.coordinates[0].length - 1} vertices)`
              : featuresPath
                ? `Offline features: ${featuresPath}`
                : null
        }
        point={mode === "point" ? point : null}
        projectedPoint={projectedPoint}
        settings={shellSettings}
        onClose={() => setModalOpen(false)}
        onViewMap={() => setModalOpen(false)}
      />
    </main>
  );
}

export default function DashboardPage() {
  return (
    <RequireSession nextPath="/dashboard">
      <AssessmentWorkspace />
    </RequireSession>
  );
}
