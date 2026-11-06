# Questions for the client (Abeokuta data)

We received `sheet 260_Abeokuta.csv` (a copy; the original was not modified).
Before we can train anything on it we need answers to the questions below.
Nothing here is a criticism of the data — we simply must not guess on these
points, because a wrong assumption would make every result meaningless.

## 1. What the values mean

- What does the **Z / value** column measure? (overburden thickness, depth to
  bedrock, ground elevation, water level, something else?)
- What are its **units** — metres, feet, or other?
- If it is **depth to bedrock**, tell us explicitly. We store that under a
  separate name and will **not** silently treat it as thickness.
- Should **negative Z** values (11,250 rows, minimum −212.76) be treated as real
  measurements, or as a missing/sentinel marker? If real, what does a negative
  value physically mean here?

## 2. Coordinates and CRS

- What is the **CRS**, as an **EPSG code** or the **full WKT/PROJ definition**?
- The **X values are negative** (about −163,800 to −107,800) and Y is about
  777,400–833,500. Please confirm what projection these belong to and why X is
  negative (for example, no false easting, or a local grid). We will not assume
  a CRS.

## 3. Gaps in the grid

- The grid is regular (100-unit spacing) but is **not** a full rectangle: it is
  missing **7,129 cells** out of a 561 × 562 = 315,282 full grid. The gaps are
  **clustered** (a few contiguous voids, largest ≈1,952 cells).
- Are these gaps **intentional** (AOI edge, mask, no-data area) or **data loss**?
  Should the missing cells be treated as "no data" or interpolated?

## 4. Hazard location data (per hazard, same area)

For each of **landslide, subsidence, and sinkhole**, please provide:

- locations/outlines of known events **in the same area**;
- the **date** (or date range) of each event;
- how confident the record is (confirmed vs suspected);
- the coordinate reference system (if different from the above).

## 5. Lineaments

- Do you have **lineament vector data** (faults, lineaments, fracture traces) as
  GeoJSON / shapefile / GeoPackage? If yes, with what CRS.

## 6. Any other hazard data

- Anything else that describes ground instability for this area (erosion,
  settlement records, boreholes, InSAR, imagery with dates, existing maps).

## Why we ask

The model learns from whatever we give it. If the Z value is, say, depth to
bedrock rather than thickness, or if the CRS is wrong, the trained output looks
plausible but is wrong. We would rather wait for these answers than produce a
confident-looking number that cannot be trusted.
