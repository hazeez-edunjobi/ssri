# SSRI Client User Guide

SubSurface Risk Intelligence (SSRI) helps you upload supported geospatial datasets, validate them, run compatible analyses, and download outputs. Scientific status for research workflows remains **NOT_VALIDATED** until independent evaluation says otherwise.

## Sign in

1. Open the application URL provided by your administrator.
2. Use **Login** with your organisation email and password (or the SSO method your admin configured).
3. After sign-in you land on **Workspace** (`/workspace`).
4. Use **Logout** from the account menu when finished.

If you cannot sign in, contact your administrator — do not share passwords or API keys.

## Assessment map (`/dashboard`)

- The map opens focused on the **SW Nigeria product region** (Lagos–Abeokuta corridor), not a world overview.
- Gravity / geophysics layers and **verified** geological footprints appear when available.
- Projected coordinates (e.g. UTM easting/northing) are **not** plotted until a verified transform to WGS84 exists.
- Click the map to place an assessment point, or enter latitude/longitude (WGS84).
- Outside soft coverage you will see a warning; that does not invent risk scores.

## Upload a geological dataset (`/geological`)

1. Enter a display name and choose asset kind (point-grid CSV or lineament vectors).
2. Select your file and **Create & upload**.
3. Open the new dataset detail page.
4. **Declare metadata**:
   - Measurement type (e.g. Total Magnetic Intensity).
   - **Source CRS** (required EPSG — never assumed).
   - Processing / working CRS when required for metric operations.
   - X, Y, and Z/value column names.
   - Units when known.
5. For Abeokuta Sheet 260, use **Apply Abeokuta TMI metadata** (source EPSG:32632, processing EPSG:32631, display EPSG:4326; X=easting, Y=northing, Z=TMI).
6. Run **Validate**.

### Validation outcomes

| Outcome | Meaning |
|---|---|
| Ready | Required structure and CRS checks passed for compatible operations. |
| Ready with warnings | Processing allowed; read every warning before relying on results. |
| Blocked (FAIL) | Fix the listed issues; analysis buttons stay disabled. |

SSRI does not silently reinterpret coordinates to “make them fit” the map.

## Run magnetic analysis (Sheet 260)

On a validated TMI dataset:

1. Process the TMI grid (metres in the processing CRS).
2. Run individual operations: RTE, Gaussian, analytic signal, vertical/horizontal derivatives, tilt, RAPS.
3. Inspect previews, statistics, gridding reconciliation, and processing history.
4. Download original CSV and derived GeoTIFF / PNG products from the detail page / derived routes.

Magnetic anomalies are **not** confirmed faults, sinkholes, or landslides. Status remains **NOT_VALIDATED**.

## Download outputs

- **Original file**: always preserved; download from the dataset page.
- **Derived grids / previews**: listed under magnetic products after processing.
- Assessment reports: use the assessment result modal export when an assess run completes.

## What SSRI will not do for you

- Treat a 3-column TMI CSV as a 13-channel Stage 2.5 training stack.
- Replace EMAG2 magnetics with client TMI.
- Invent CRS, hazard labels, depth estimates, or scientific validation.
- Run unsupported analyses because a button is visible but disabled.
