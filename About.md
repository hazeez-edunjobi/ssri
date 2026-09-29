# About SSRI

**SSRI** stands for **SubSurface Risk Intelligence** (also described as Subsurface Structural Risk Intelligence).

## Overview

SSRI is a geospatial ground-risk platform. It helps people understand how susceptible a location may be to **subsidence** (ground settling), **landslides**, and **sinkholes**, by combining Earth observation and terrain data with a machine-learning model and presenting the result as a clear risk picture on a map.

It is designed so non-specialists can check a place and get plain-language scores and explanations—not only raw technical layers.

## The Problem

Decisions about where to build, plan roads, insure property, or site community projects often rely on what can be seen on the surface: maps, photos, and local knowledge. Those views do not always capture what the ground may do—slope failure, gradual settling, or collapse into voids.

People who need that insight rarely have easy access to specialist geotechnical studies for every parcel or corridor. SSRI aims to close that gap with a map-first assessment that is easier to approach than traditional subsurface investigation alone.

## The Solution

SSRI lets a user select a location (a point or a drawn area), gather relevant Earth data for that place when live acquisition is available, run a trained model, and return per-hazard susceptibility scores with uncertainty and a short explanation of what is driving the result.

When live data or a trained model is not available, the same workflow can run in **offline** mode (pre-prepared features) or **demo** mode (deterministic presentation results without live Earth-data calls).

## Who It's For

Intended audiences described in the product include:

- Planners and local authorities reviewing land use
- Builders and engineers screening sites early
- Insurers and risk teams exploring location context
- Community groups and landowners who want a clearer view of the ground
- Researchers and operators working with geospatial hazard pipelines

Marketing pages also speak to developers who might embed risk into other tools. Public SDKs and some advertised API shapes on those pages are **not** the fully shipped product surface today; the working consumer path is the web dashboard and the assess API behind it.

## What It Does

Today, a user can:

- Browse a public marketing site explaining the product and hazards
- Open a **Risk Assessment Workspace** (dashboard) with an interactive map
- Open a **Manual Training** workspace to upload a Stage 2.5 ZIP or a compatible spatial CSV, validate it, and train a model
- Sign in (when Supabase is configured) to keep datasets, training runs, and model versions on your account
- Select a **point** (click or enter coordinates) or draw a **polygon**
- Optionally view a **gravity data** preview layer on the map
- Run an **assessment** for one or more of: subsidence, landslide, sinkhole
- See scores, confidence-related information, and explanatory drivers in a results view

Behind the scenes, operators can also run the research and engineering stack (training data preparation, model checkpoints, jobs, and health checks) when the system is configured with the right credentials and services.

## Key Features

- **Map-based assessment** — Choose a place on a map and request a ground-risk reading without writing code.
- **Three hazard views (as implemented in assessments)** — Subsidence, landslide, and sinkhole susceptibility for the selected area.
- **Uncertainty and confidence language** — Results include interval-style uncertainty and confidence tiers that describe how much the *model* trusts its own output (not how severe a hazard event would be).
- **Live Earth-data path (when enabled)** — Can assemble location features from satellite/spectral sources, terrain (DEM), and local geophysics where configured.
- **Offline assessment** — Can score using prepared feature files and a model checkpoint path when live acquisition is not used.
- **Demo / presentation mode** — Can return consistent sample-style results for demos without calling live geospatial services.
- **Gravity layer preview** — Optional map overlay based on available gravity data products.
- **Manual model training** — Operators can upload a Stage 2.5 dataset (13-channel feature stacks + labels), or a compatible spatial CSV that is converted into that same dataset before training. A single X,Y,Z file is one feature layer and is not a supervised training set. They can validate the dataset, start an asynchronous training job using the existing SSRI trainer, monitor progress, and promote a resulting checkpoint for assessments. **Training completion does not equal scientific validation.**
- **Research training pipeline** — Catalog and feature-stack tooling, foundation model checkpoints, and evaluation reports exist for the research programme (separate from claiming a validated public hazard product).

## How It Works

A typical user journey looks like this:

1. Visit the SSRI website and learn what the product is about.
2. Open the dashboard (“check a location on the map”).
3. Confirm the service is reachable, and optionally turn on the gravity overlay.
4. Pick a **point** or draw a **polygon** covering the area of interest.
5. Choose which hazards to assess (and, in advanced setups, which model or feature inputs to use).
6. Run the assessment.
7. Review the result panel: scores per hazard, uncertainty, confidence tier, and primary drivers—plus any warnings if the run used demo data, a test model, or uncalibrated settings.

For live runs, the system gathers Earth data for the area, builds a structured “feature stack,” runs the model, and returns the assessment response. For demo runs, it skips live geospatial calls and returns presentation-safe results.

## Why It Matters

Early, map-based ground-risk context can help people ask better questions before committing to land, construction, or community decisions. SSRI packages that idea as a single workflow: pick a place, get a structured risk reading, and see what the model thinks is driving the score.

Its practical value today is strongest as a **research and demonstration platform** with a working end-to-end assessment path—not as a substitute for licensed geotechnical investigation, regulatory approval, or insured hazard advice.

## Current Status

Overall project posture documented in the repository:

**Research ready — live engineering pipeline verified. Scientific validation incomplete. Not production-qualified.**

### Implemented

- Marketing website (home, about, hazards, platform, developers pages)
- Dashboard map workspace with point/polygon selection and assessment UI
- Manual Training page and `/api/v1/training/*` workflow (dataset upload/validation, async training jobs, checkpoint registry/promotion)
- Working assess API path (demo, offline, and gated live acquisition)
- Gravity layer preview endpoint and UI toggle
- Docker-based API, worker, database, and queue stack for local/staging operation
- Research data and model pipeline (including foundation checkpoints and evaluation artifacts)

### Partially implemented

- Optional authentication and access control (present in code; often off in default/dev configuration)
- Optional map export / GeoTIFF-style outputs (depends on storage and flags)
- Model quality and calibration relative to research gates (improved over early pilots; published scientific gates not yet fully met)
- Domain-similarity / confidence calibration (often uncalibrated without a reference centroid)

### Planned / not shipping as claimed on marketing alone

- Public developer SDKs and some advertised API routes as shown on marketing pages
- Partner logos, pricing, FAQ, and similar commercial packaging (placeholders where present)
- Full African transfer learning and field-validated African/Nigerian product readiness
- Treating **liquefaction** as the live assessment class (plans/PRD mention it; the live assess path still uses **sinkhole**, which is a different phenomenon)
- Production scientific readiness and legal/product sign-off for high-stakes decisions

## Important Notes

- **Not field-validated for production hazard decisions.** Passing software tests or completing a live demo run does not mean geological truth has been proven for every location.
- **Susceptibility ≠ severity.** Scores estimate relative susceptibility from the model; they are not a guarantee of when or how badly an event would occur.
- **Confidence tiers describe the model, not the danger level.** A “low confidence” result means the system is less sure of its estimate—not that the hazard is mild.
- **Demo mode is for presentation.** It should not be used as scientific evidence.
- **Hazard naming:** Assessments implement **sinkhole**. Broader product plans and some marketing language also discuss **liquefaction** (soft, wet ground). Those are not the same; do not treat them as interchangeable.
- **Data and credentials matter.** Live assessments need configured Earth-data access and geophysics inputs; otherwise use offline features or demo mode.
- **Large catalogs and rasters** used for research are generally kept locally and are not part of a lightweight “clone and go” story without setup.

## Project Vision

Evidence in the repository points to a longer-term direction of:

- Making subsurface-aware ground risk readable on a map for non-specialists
- Strengthening scientific validation (source-domain quality gates, then careful transfer toward African target settings where data allows)
- Growing from a research/demo assess workflow toward a more operational service—with authentication, jobs, and clearer product packaging—only after scientific and operational readiness criteria are met

That vision is aspirational relative to today’s **research-ready** status. The repository does not support claiming a finished, production-validated commercial hazard product yet.
