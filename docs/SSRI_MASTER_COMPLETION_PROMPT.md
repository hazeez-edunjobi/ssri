SSRI — MASTER COMPLETION PROMPT
From Current Repository State to Full PRD Completion and Scientific Validation

You are the lead ML engineer, geospatial scientist, backend engineer, frontend engineer, MLOps engineer, and validation engineer responsible for bringing the existing SSRI repository to full completion against its PRD.

This is NOT a greenfield project.

The repository already contains substantial engineering infrastructure. Your job is to:

inspect what already exists,
preserve working components,
identify every remaining gap,
implement missing functionality,
obtain and integrate legitimate datasets,
train real models,
perform real domain adaptation,
validate the scientific claims,
expose the validated model through the API,
complete the dashboard,
produce reproducible evidence,
and leave the repository in a state where the PRD can be defended with actual measurements rather than assertions.
1. PRIMARY OBJECTIVE

Bring SSRI from its current state:

RESEARCH-READY / LIVE GEOSPATIAL INFERENCE PIPELINE — SCIENTIFIC VALIDATION PENDING

to:

PRD-COMPLETE / SCIENTIFICALLY VALIDATED GEOLOGICAL DOMAIN ADAPTATION SYSTEM

The final system must support the PRD's central research claim:

SSRI uses Geological Domain Adaptation through adversarial domain adaptation to transfer geohazard prediction knowledge from labeled source geological regimes to unlabeled target geological regimes, including African environments, while producing calibrated uncertainty and domain-similarity information.

Do NOT declare this claim achieved until the repository contains measurable evidence supporting it.

2. NON-NEGOTIABLE ENGINEERING RULES
Rule 1 — Inspect before modifying

Before changing anything:

inspect the entire repository structure;
inspect existing model code;
inspect existing data pipelines;
inspect API;
inspect worker;
inspect frontend;
inspect tests;
inspect configuration;
inspect Docker/deployment configuration;
inspect existing model artifacts;
inspect migrations;
inspect documentation;
inspect existing scientific scripts;
inspect CI;
inspect generated reports;
inspect existing experiment outputs.

Do not rebuild existing functionality blindly.

Rule 2 — Existing functionality is valuable

If an existing implementation works:

preserve it;
extend it;
refactor only when necessary;
maintain backward compatibility;
do not replace functioning infrastructure merely for stylistic reasons.

Existing API contracts from earlier stages should remain stable unless the PRD requires a deliberate versioned change.

Rule 3 — Evidence over claims

Never say:

"implemented" merely because a file exists;
"trained" merely because training code exists;
"validated" because tests pass;
"domain adaptation works" because DANN classes exist;
"uncertainty is calibrated" because confidence intervals are returned;
"African transfer works" because an African coordinate produces a prediction.

Every scientific claim requires measurable evidence.

Rule 4 — Fixtures are not scientific evidence

Synthetic datasets, fixtures, mock checkpoints, random models, and placeholder outputs may be used to test engineering infrastructure.

They may NOT be presented as evidence for:

source-domain AUC;
African transfer AUC;
DANN improvement;
calibration;
domain discrimination;
real-world uncertainty;
geological transferability.
Rule 5 — Do not fabricate datasets

Do not invent:

labels;
geological observations;
landslide events;
subsidence events;
liquefaction labels;
source-domain centroids;
validation scores;
AUC;
ECE;
SHAP results;
DANN improvement.

If a dataset cannot legally/reliably be obtained automatically:

document the exact blocker;
build the ingestion interface;
provide the expected schema;
provide deterministic preprocessing;
provide validation scripts;
allow the dataset to be mounted/imported later.

But continue implementing every component that does not depend on that blocker.

3. PRD SUCCESS CRITERIA

The implementation must ultimately target these PRD requirements.

Scientific metrics
Source-domain performance

Target:

AUC-ROC >= 0.88

on a held-out source validation/test set.

African/target transfer

Target:

AUC-ROC >= 0.74

on an appropriately held-out African target evaluation dataset.

DANN improvement

DANN should improve over direct transfer by:

>= 12 AUC points

where:

DANN target AUC - direct-transfer target AUC >= 0.12

The exact comparison protocol must be documented and reproducible.

Calibration

Target:

ECE <= 0.08

with reliability diagrams and calibration statistics.

Domain discrimination

Target:

domain discrimination AUC >= 0.80

on a held-out geological-regime discrimination experiment.

API latency

Point:

p95 < 4 seconds

Polygon:

25 km² < 45 seconds

under documented hardware/runtime conditions.

4. FINAL ARCHITECTURE

The final system should contain these logical layers:

DATA SOURCES
    ↓
DATA INGESTION
    ↓
GEOREFERENCING / NORMALIZATION
    ↓
FEATURE STACK
    ↓
SOURCE DATASETS + TARGET DATASETS
    ↓
FOUNDATION MULTI-TASK MODEL
    ↓
DIRECT TRANSFER BASELINE
    ↓
DANN DOMAIN ADAPTATION
    ↓
VALIDATED TARGET MODEL
    ↓
MC DROPOUT UQ
    ↓
DOMAIN SIMILARITY
    ↓
SHAP / FEATURE ATTRIBUTION
    ↓
CONFIDENCE CALIBRATION
    ↓
FASTAPI INFERENCE
    ↓
POLYGON WORKER / RASTER OUTPUT
    ↓
NEXT.JS DASHBOARD
    ↓
MODEL CARD / SCIENTIFIC EVIDENCE

Do not bypass this architecture merely to produce attractive UI output.

5. PHASE 0 — COMPLETE REPOSITORY AUDIT

Start by performing a deep repository audit.

Inspect:

/model
/api
/frontend
/worker
/infra
/tests
/scripts
/data
/models
/docs

and any additional directories that exist.

Determine:

current architecture;
current Python environment;
current Node environment;
current database;
current PostGIS configuration;
current Redis/Celery configuration;
current GEE integration;
current OpenTopography integration;
current geophysical data integration;
current model implementation;
current training implementation;
current DANN implementation;
current checkpoint handling;
current UQ implementation;
current SHAP implementation;
current domain similarity implementation;
current API;
current polygon processing;
current dashboard;
current deployment.

Produce:

docs/COMPLETION_BASELINE.md

containing:

what exists;
what is verified;
what is partial;
what is synthetic;
what is missing;
what is blocked;
exact files involved;
exact tests involved.

Then continue implementation.

Do not stop after the audit.

6. PHASE 1 — DATA FOUNDATION

Implement a production-quality data ingestion system.

Required source datasets

The PRD identifies:

USGS

National Landslide Database / appropriate USGS landslide inventory.

British Geological Survey

Relevant mass movement/subsidence records.

Italian IFFI

Italian Landslide Inventory.

Target/African datasets

Acquire legitimate public datasets appropriate for evaluating transfer into African geological regimes.

Prioritize datasets with:

geographic coordinates;
event/absence information;
compatible hazard labels;
sufficient sample size;
documented provenance;
license permitting research use.

Potential African target regions should be selected based on actual data availability rather than invented coverage.

Document exactly:

dataset;
provider;
URL/source;
license;
geographic extent;
temporal extent;
label semantics;
sample count;
preprocessing;
train/validation/test role.
7. DATA SCHEMA

Create a canonical schema for all datasets.

Each sample should be capable of representing:

sample_id
latitude
longitude
source_domain
target_domain
hazard_type
label
geometry
timestamp
dataset_name
dataset_version
feature_availability
quality_flags

Support multi-task labels:

landslide
subsidence
liquefaction

Missing labels must be explicitly represented.

Do not silently convert missing labels to negative labels.

8. HAZARD CLASS CONSISTENCY

The final system must align with the PRD:

landslide
subsidence
liquefaction

If the existing implementation uses:

sinkhole

or another class:

do not silently rename it;
determine its scientific relationship to the PRD;
modify the canonical task definition;
maintain compatibility where necessary;
document the change.

The API should expose the PRD hazard vocabulary.

9. FEATURE STACK

The final feature stack must implement the PRD features.

DEM/topography

Include:

elevation;
slope;
plan curvature;
profile curvature;
TWI;
relative relief;
valley depth.

Use SRTM/Copernicus or another documented equivalent where appropriate.

Sentinel-2

Include:

NDVI;
NDWI;
clay mineral index;
iron oxide index;
B11/B12 clay ratio;
B4/B2 iron oxide ratio.

Use documented cloud masking.

Use an appropriate temporal composite.

Gravity

PRD target:

EIGEN-6C4

If current production code uses WGM2012:

determine whether it is scientifically interchangeable for the intended feature;
if not, implement EIGEN-6C4;
retain WGM2012 only as a clearly documented fallback/legacy source.

Do not label WGM2012 as EIGEN-6C4.

Aeromagnetics

Integrate legitimate public national/regional magnetic anomaly data where available.

Document:

source;
resolution;
CRS;
processing;
normalization.
10. COMMON GRID

Normalize all feature sources onto a common grid.

Target:

30 m

unless the scientific validation protocol requires another resolution.

Ensure:

CRS consistency;
nodata handling;
interpolation rules;
alignment;
pixel dimensions;
deterministic preprocessing.

Create automated feature-stack validation tests.

11. FEATURE QUALITY CONTROL

Implement validation for:

missing values;
NaN;
infinite values;
unrealistic physical ranges;
projection errors;
empty AOIs;
inconsistent raster dimensions;
incorrect units;
corrupted downloads;
temporal inconsistencies.

Every feature stack should have a machine-readable metadata record.

12. PHASE 2 — FOUNDATION MODEL

Implement the actual trainable multi-task model.

Use PyTorch.

Architecture:

Input Feature Stack
        ↓
Shared CNN / deep representation backbone
        ↓
Shared embedding
   ┌────┼────┐
   ↓    ↓    ↓
Landslide
Head
Subsidence
Head
Liquefaction
Head

Each task head must support sigmoid probabilities.

Use appropriate loss handling for missing task labels.

Support:

class imbalance;
weighted BCE/focal loss where scientifically justified;
deterministic training;
configurable seeds;
checkpointing;
validation;
early stopping;
experiment metadata.
13. REAL SOURCE TRAINING

Train the foundation model on real source-domain data.

Do not stop at synthetic data once real data becomes available.

Implement:

training configuration
dataset version
feature version
model version
git commit
random seed
hyperparameters
hardware
training duration
metrics
checkpoint

Save a reproducible experiment manifest.

Required artifact:

models/ssri-foundation-v1.pt

or a clearly versioned successor.

14. SOURCE HOLDOUT

Create strict source-domain train/validation/test separation.

Avoid spatial leakage.

Do NOT randomly split neighboring pixels if this produces unrealistic leakage.

Prefer spatial/geographic grouping where scientifically appropriate.

Document:

split strategy;
geography;
sample counts;
class balance.

Evaluate:

ROC-AUC;
PR-AUC;
precision;
recall;
F1;
confusion matrix;
calibration.

The source benchmark must be reproducible.

15. SOURCE PERFORMANCE GATE

Do not claim foundation-model success until the source evaluation is measured.

Target:

AUC >= 0.88

If the metric is below target:

investigate;
improve preprocessing;
improve architecture;
address imbalance;
tune training;
investigate label quality;
document limitations.

Do not fabricate the target score.

16. PHASE 3 — DIRECT TRANSFER BASELINE

This is mandatory.

Before DANN, evaluate the source-trained model directly on the African target domain.

This produces:

DIRECT_TRANSFER_BASELINE

Measure:

target AUC;
PR-AUC;
calibration;
confidence distribution;
domain similarity;
per-hazard performance.

This baseline is necessary to prove whether DANN actually improves transfer.

17. PHASE 4 — DANN

Implement actual Domain-Adversarial Neural Network training.

Use the principles of:

Ganin et al., 2016.

Architecture:

                   ┌───────────────┐
                   │ Feature Stack │
                   └───────┬───────┘
                           ↓
                  Shared Feature Encoder
                           ↓
                     Feature Embedding
                      /            \
                     /              \
                    ↓                ↓
             Task Predictors     GRL
                                  ↓
                           Domain Discriminator

The domain discriminator must attempt to distinguish:

source
target

The feature encoder must learn representations that reduce domain discriminability while preserving task performance.

18. GRADIENT REVERSAL

Implement an explicit Gradient Reversal Layer.

Test it mathematically.

The test must prove that the gradient reaching the feature encoder is reversed/scaled by the expected coefficient.

Do not merely test that the class exists.

19. DANN TRAINING

Use:

source:
    Xs + Ys

target:
    Xt

Training objective should combine:

task loss
+
adversarial domain loss

with a documented schedule for the adversarial coefficient.

Support:

lambda schedule;
source/target batch balancing;
multi-task source labels;
unlabeled target samples;
checkpointing;
reproducibility.
20. DANN ABLATION

Run controlled experiments.

At minimum:

A. Source-only
B. Direct transfer
C. DANN

Prefer additional ablations where useful.

Record all results.

Never compare models trained with materially different preprocessing without documenting it.

21. DANN SCIENTIFIC GATE

Evaluate DANN on the held-out African target dataset.

Required comparison:

DANN target AUC
-
Direct transfer target AUC

Target:

>= 0.12

If it fails:

do not hide the failure;
investigate;
tune;
perform ablations;
determine whether the hypothesis is supported;
document the result honestly.

The PRD claim is an empirical claim, not an assumption.

22. AFRICAN TARGET VALIDATION

Create a strict target evaluation protocol.

The target test set must remain isolated from model tuning as much as practical.

Document:

country/region;
geological regime;
dataset;
hazard;
sample count;
positive/negative ratio;
feature coverage;
evaluation date;
model version.

Report:

target AUC
PR-AUC
precision
recall
F1
ECE
confidence distribution

per hazard and overall.

23. GEOLOGICAL REGIME SPLITS

Do not treat "Africa" as a single homogeneous domain.

Where data permits, evaluate across distinct geological regimes.

Examples may include:

crystalline basement;
sedimentary basin;
volcanic terrain;
rift-related terrain;
coastal sedimentary environments.

Use actual geological classification data.

Do not invent geological regimes.

24. PHASE 5 — UNCERTAINTY QUANTIFICATION

Implement genuine MC Dropout.

Inference:

N = 100

passes by default.

For every prediction:

run 100 stochastic forward passes;
collect predictions;
calculate median;
calculate empirical 80% interval;
calculate empirical 95% interval.

Example:

point estimate
credible_interval_80
credible_interval_95

Do not call deterministic confidence scores "credible intervals."

25. UQ VALIDATION

Evaluate whether uncertainty is meaningful.

Measure:

interval coverage;
interval width;
reliability;
calibration;
error vs uncertainty;
uncertainty on out-of-domain samples.

Verify:

80% interval ≈ 80% empirical coverage
95% interval ≈ 95% empirical coverage

within an explicitly documented tolerance.

26. CALIBRATION

Implement calibration methodology where necessary.

Possible methods:

temperature scaling;
isotonic regression;
beta calibration.

Select based on validation evidence.

Do not calibrate using the final test set.

Measure:

ECE
Brier score
reliability diagram

Target:

ECE <= 0.08
27. DOMAIN SIMILARITY

Implement domain similarity using the learned embedding.

PRD concept:

target embedding
        ↓
cosine distance
        ↓
source-domain centroid
        ↓
normalized 0–1 similarity

The source centroid must be calculated from real source training data.

Save it as a versioned artifact.

Do not use:

arbitrary zero vectors;
synthetic centroids;
placeholder centroids.
28. DOMAIN SIMILARITY CALIBRATION

Determine thresholds from held-out data.

Do not arbitrarily select thresholds such as:

0.8 = high
0.5 = moderate

unless justified by validation.

Measure domain discrimination.

Target:

AUC >= 0.80

on a held-out geological regime discrimination experiment.

29. CONFIDENCE TIERS

Implement:

High
Moderate
Low
Extrapolation Warning

Thresholds must be versioned and documented.

Confidence must incorporate scientifically meaningful signals, not merely the model probability.

Consider:

calibrated predictive confidence;
domain similarity;
predictive uncertainty.
30. SHAP / FEATURE ATTRIBUTION

Implement top-3 feature attribution.

For each assessment return:

primary_drivers

containing the three most influential features.

Ensure explanations correspond to actual model inputs.

Do not fabricate feature importance.

Where SHAP is computationally expensive:

use an appropriate explainer;
cache where safe;
support asynchronous computation if required;
preserve scientific validity.
31. NATURAL-LANGUAGE EXPLANATION

Build a deterministic explanation layer.

It should translate model outputs into geotechnical language.

Example conceptual output:

The assessment indicates elevated landslide susceptibility.
The strongest contributing factors were steep slope,
high topographic wetness, and vegetation/moisture indicators.

The explanation must be generated from actual model outputs.

Do not invent geological facts not represented in the feature stack.

32. PHASE 6 — API

Complete:

POST /v1/assess

Request:

{
  "coordinates": {},
  "hazard_types": [
    "landslide",
    "subsidence",
    "liquefaction"
  ],
  "resolution_m": 30,
  "uncertainty": true
}

Support point and polygon geometry.

33. POINT RESPONSE

Return:

{
  "assessment_id": "...",
  "hazard_profiles": {
    "landslide": {
      "susceptibility": 0.0,
      "credible_interval_80": [0.0, 0.0],
      "credible_interval_95": [0.0, 0.0],
      "domain_similarity_score": 0.0,
      "confidence_tier": "Moderate",
      "primary_drivers": []
    }
  }
}

Use actual values.

34. POLYGON PIPELINE

Implement:

polygon
 ↓
tile
 ↓
feature acquisition
 ↓
feature stack
 ↓
batch inference
 ↓
raster output
 ↓
mosaic
 ↓
cloud/object storage
 ↓
signed URL

Support asynchronous processing.

Use Celery/Redis or the repository's existing worker architecture where already implemented.

35. POLYGON PERFORMANCE

Benchmark:

25 km²

Target:

<45 seconds

Record:

hardware;
concurrency;
AOI;
resolution;
feature acquisition time;
inference time;
mosaic time;
upload time.

Do not report a benchmark without recording the environment.

36. POINT PERFORMANCE

Benchmark:

p95 < 4 seconds

Measure under realistic runtime conditions.

Do not benchmark only mocked inference.

37. API SAFETY

Ensure:

input validation;
coordinate validation;
polygon-size limits;
hazard validation;
resolution validation;
timeout handling;
rate limiting;
structured errors;
request IDs;
model version in response;
feature-stack version in response;
reproducibility metadata.
38. PHASE 7 — FRONTEND

Complete the dashboard around the actual API.

The frontend must support:

Map
point selection;
polygon drawing;
map navigation;
location search where appropriate;
assessment loading;
result visualization.
Hazard selection
Landslide
Subsidence
Liquefaction
Result panel

Display:

susceptibility;
80% interval;
95% interval;
confidence tier;
domain similarity;
top 3 drivers;
natural-language explanation.
39. SPATIAL VISUALIZATION

For polygon results:

display GeoTIFF/raster layer;
show legend;
show hazard intensity;
allow layer visibility;
provide signed download URL where available.

Handle:

loading;
processing;
failed;
completed;
expired URL.
40. RESEARCH TRANSPARENCY

The frontend must make clear when:

scientific validation is unavailable

rather than presenting fixture/demo results as validated science.

If a fixture model exists for development, clearly label it as:

DEMO / UNVALIDATED MODEL

until a validated checkpoint is deployed.

41. PHASE 8 — TESTING

Create comprehensive tests.

Unit tests

Cover:

feature calculations;
raster alignment;
preprocessing;
dataset loading;
labels;
model architecture;
task heads;
GRL;
domain discriminator;
MC Dropout;
interval calculation;
calibration;
domain similarity;
confidence tiers;
SHAP;
API schemas.
42. INTEGRATION TESTS

Test:

AOI
→ feature stack
→ model
→ UQ
→ domain similarity
→ explanation
→ API response

Use fixtures where appropriate.

Clearly distinguish integration tests from scientific validation.

43. END-TO-END TEST

Create at least one complete end-to-end test:

coordinate
→ real/live feature acquisition where test environment allows
→ validated model
→ assessment
→ API response

If live external services cannot be used in CI:

create deterministic service adapters;
integration-test them separately;
maintain a reproducible real-environment validation command.
44. SCIENTIFIC VALIDATION TESTS

Create scripts under something like:

/scripts/validation/

including:

validate_source.py
validate_transfer.py
validate_dann.py
validate_calibration.py
validate_uq.py
validate_domain_similarity.py
benchmark_api.py
generate_model_card.py

These scripts must produce machine-readable results.

45. EXPERIMENT TRACKING

Every major training run must record:

experiment_id
timestamp
git_commit
dataset_versions
feature_version
model_version
seed
hyperparameters
hardware
training duration
source metrics
target metrics
calibration metrics
DANN configuration

Store results in a reproducible format.

46. MODEL REGISTRY

Implement versioned model artifacts.

At minimum:

foundation model
direct-transfer model
DANN model
calibration artifact
source centroid
feature metadata

Every model must have:

model_version
training_dataset
training_date
git_commit
feature_version
metrics
limitations
47. MODEL CARD

Generate:

docs/MODEL_CARD.md

It must contain:

Model
architecture;
version;
parameters;
training procedure.
Data
source datasets;
target datasets;
provenance;
licensing.
Features
DEM;
Sentinel-2;
gravity;
magnetics.
Evaluation
source AUC;
target AUC;
direct transfer;
DANN;
DANN improvement;
ECE;
domain discrimination AUC;
UQ coverage.
Limitations

Explicitly state:

geographic limitations;
label limitations;
geological regime limitations;
uncertainty limitations;
known failure modes.
48. RESEARCH REPORT

Generate:

docs/SCIENTIFIC_VALIDATION_REPORT.md

This must contain:

hypothesis;
datasets;
preprocessing;
model architecture;
baseline;
DANN method;
experimental protocol;
source results;
target results;
DANN improvement;
calibration;
UQ;
domain similarity;
ablations;
limitations;
conclusion.
49. REPRODUCIBILITY

A new engineer should be able to clone the repository and determine:

how to acquire data
how to preprocess data
how to train foundation model
how to train DANN
how to evaluate source
how to evaluate target
how to calculate calibration
how to calculate UQ
how to calculate domain similarity
how to generate model card
how to launch API
how to launch frontend

Document exact commands.

50. DATA PROVENANCE

Every external dataset must have:

provider
source URL
version/date
license
download method
checksum where practical
processing script

Do not silently depend on undocumented downloads.

51. CONFIGURATION

Do not hardcode:

credentials;
API keys;
dataset paths;
storage credentials;
GEE credentials;
model paths;
database passwords.

Use environment variables/configuration.

Provide:

.env.example

with all required variables documented.

52. DEPLOYMENT

Complete production deployment.

Ensure:

frontend
API
worker
database
redis
object storage
model artifacts

can operate together.

Where appropriate:

Dockerize services;
add health checks;
add startup validation;
add logging;
add metrics;
add graceful failure handling.
53. OBSERVABILITY

Record:

request ID;
assessment ID;
model version;
feature version;
latency;
model inference time;
feature acquisition time;
worker status;
failure reason.

Do NOT log sensitive credentials or unnecessary private data.

54. CI/CD

CI should execute:

linting;
type checks;
unit tests;
integration tests;
API tests;
frontend tests;
model smoke tests.

Scientific validation should be separately executable because it may require large datasets/GPU/external services.

55. NO FALSE GREEN

This is critical.

The project is NOT complete merely because:

pytest passes
npm test passes
API returns 200
dashboard renders
Docker starts

Those prove engineering correctness.

Scientific completion additionally requires:

real datasets
real training
real source evaluation
real target evaluation
real direct-transfer baseline
real DANN comparison
real calibration
real UQ evaluation
real domain similarity evaluation
56. ACCEPTANCE GATES

Do not mark the project COMPLETE until every applicable gate has evidence.

Gate A — Data
[ ] Source datasets acquired
[ ] Target/African datasets acquired
[ ] Provenance documented
[ ] Labels validated
[ ] Dataset versions frozen
Gate B — Features
[ ] DEM features
[ ] Sentinel-2 features
[ ] Gravity
[ ] Magnetics
[ ] Common 30m grid
[ ] Feature QC
Gate C — Foundation model
[ ] Real training
[ ] Real checkpoint
[ ] Source holdout
[ ] Source AUC measured
Gate D — Transfer baseline
[ ] Direct transfer implemented
[ ] African evaluation
[ ] Target AUC measured
Gate E — DANN
[ ] GRL verified
[ ] Domain discriminator verified
[ ] Real source + target training
[ ] DANN checkpoint
[ ] DANN target evaluation
[ ] DANN improvement measured
Gate F — UQ
[ ] MC Dropout N=100
[ ] 80% intervals
[ ] 95% intervals
[ ] empirical coverage evaluated
Gate G — Calibration
[ ] calibration method
[ ] held-out calibration data
[ ] ECE
[ ] reliability diagram
[ ] Brier score
Gate H — Domain similarity
[ ] real source centroid
[ ] similarity calculation
[ ] calibration
[ ] held-out domain discrimination
[ ] AUC measured
Gate I — Explanation
[ ] SHAP
[ ] top 3 drivers
[ ] natural-language explanation
Gate J — API
[ ] POST /v1/assess
[ ] point
[ ] polygon
[ ] uncertainty
[ ] domain similarity
[ ] drivers
[ ] signed GeoTIFF
Gate K — Performance
[ ] point p95 < 4s
[ ] polygon 25km² < 45s
Gate L — Frontend
[ ] map
[ ] point
[ ] polygon
[ ] hazards
[ ] result panel
[ ] uncertainty
[ ] domain similarity
[ ] drivers
[ ] raster visualization
Gate M — Evidence
[ ] scientific validation report
[ ] model card
[ ] experiment manifests
[ ] reproducibility instructions
[ ] limitations
57. REQUIRED FINAL SCORECARD

At the end, create:

docs/SSRI_COMPLETION_SCORECARD.md

Use this exact structure:

# SSRI Completion Scorecard

## Engineering

API:
Frontend:
Worker:
Database:
Feature pipeline:
Deployment:
Tests:

## Scientific

Source AUC:
Target AUC:
Direct Transfer AUC:
DANN AUC:
DANN Improvement:
ECE:
80% Coverage:
95% Coverage:
Domain Discrimination AUC:

## PRD Gates

Foundation Model:
DANN:
UQ:
Domain Similarity:
SHAP:
API:
Polygon:
Frontend:
Validation:
Model Card:

## Overall Status

NOT READY
RESEARCH READY
ENGINEERING COMPLETE
SCIENTIFICALLY VALIDATED
PRD COMPLETE

Every metric must include:

value;
dataset;
experiment ID;
model version;
date;
evidence file.
58. CLAIM BOUNDARY

The final documentation must explicitly classify the system.

If all scientific gates pass:

PRD COMPLETE — SCIENTIFICALLY VALIDATED

If engineering is complete but scientific targets fail:

ENGINEERING COMPLETE — SCIENTIFIC PERFORMANCE TARGETS NOT MET

If some scientific experiments remain:

RESEARCH READY — SCIENTIFIC VALIDATION INCOMPLETE

Never upgrade the status merely because the application works.

59. IMPLEMENTATION ORDER

Follow this dependency order.

1. Repository audit
2. Data acquisition
3. Canonical dataset schema
4. Feature-stack correctness
5. Foundation model
6. Real source training
7. Source validation
8. Direct transfer baseline
9. DANN
10. DANN target validation
11. UQ
12. Calibration
13. Domain similarity
14. SHAP
15. API integration
16. Polygon pipeline
17. Performance optimization
18. Frontend integration
19. Deployment
20. Scientific report
21. Model card
22. Final scorecard

Do not jump to frontend polish while the scientific pipeline is blocked unless the frontend is required to unblock integration testing.

60. HANDLING BLOCKERS

If a phase is blocked:

Do not stop the entire project.

Instead:

identify the exact blocker;
document it;
implement everything independent of the blocker;
create the correct interface;
create tests;
create ingestion tooling;
continue to the next non-dependent task;
return to the blocker when its dependency becomes available.

Example:

If a dataset download requires manual credentials:

do not fabricate data
do not stop the project
do not claim validation

Instead build:

dataset schema
ingestion script
validation script
feature extraction
training pipeline
evaluation pipeline

and document exactly what remains.

61. PERFORMANCE OPTIMIZATION

Only optimize after correctness.

Profile:

feature acquisition;
raster processing;
model inference;
MC Dropout;
SHAP;
polygon tiling;
mosaic;
storage upload.

Use:

batching;
caching;
parallelism;
GPU inference where available;
asynchronous workers;
precomputed static data where scientifically legitimate.

Do not optimize by reducing scientific validity.

For example, do not replace 100 MC Dropout passes with one deterministic pass merely to satisfy latency.

If an approximation is necessary, document it and preserve the PRD-compliant research path.

62. SCIENTIFIC INTEGRITY REQUIREMENT

Treat SSRI as a research system.

For every result ask:

What data produced this?
What model produced this?
Was the target data used during training?
Was this dataset used for tuning?
Is there spatial leakage?
Is this result reproducible?
Is this metric independently evaluated?

If the answer is unclear:

UNVERIFIED
63. DO NOT GAME THE METRICS

Do not:

tune on the test set;
repeatedly inspect target test labels and then retune;
spatially leak neighboring samples;
cherry-pick favorable regions;
remove difficult examples without scientific justification;
alter thresholds solely to produce a desired score;
fabricate negative samples;
overfit the validation set;
report only successful hazards;
hide failed experiments.

The objective is a defensible scientific result.

64. EXPERIMENT REPRODUCTION

For every reported headline metric, provide a command such as:

python scripts/validation/validate_source.py \
  --model ... \
  --dataset ... \
  --split test

or equivalent.

A reviewer must be able to reproduce the number.

65. FINAL FULL-SYSTEM TEST

After implementation:

clean environment;
install dependencies;
run migrations;
build model environment;
run tests;
load validated model;
start API;
start worker;
start frontend;
execute point assessment;
execute polygon assessment;
verify UQ;
verify domain similarity;
verify drivers;
verify signed raster output;
benchmark latency;
run scientific validation;
regenerate scorecard;
regenerate model card.

Fix all genuine failures.

66. REQUIRED FINAL RESPONSE FROM THE AGENT

When implementation is complete, do NOT merely say:

Done.

Return a detailed completion report containing:

1. Executive status

One of:

PRD COMPLETE — SCIENTIFICALLY VALIDATED
ENGINEERING COMPLETE — SCIENTIFIC TARGETS NOT MET
RESEARCH READY — VALIDATION INCOMPLETE
BLOCKED
2. What was implemented

List exact files/modules.

3. What was already present

Separate inherited functionality from newly implemented functionality.

4. Data

List:

datasets;
versions;
provenance;
sample counts;
train/validation/test splits.
5. Models

List:

foundation model;
direct-transfer model;
DANN model;
model versions;
checkpoint paths.
6. Scientific results

Provide a table:

Metric	Result	PRD Target	Status
Source AUC	
	>= 0.88	

Target AUC	
	>= 0.74	

DANN improvement	
	>= 0.12	

ECE	
	<= 0.08	

Domain AUC	
	>= 0.80	

80% UQ coverage	
	calibrated	

95% UQ coverage	
	calibrated	

Point p95	
	< 4s	

Polygon 25km²	
	< 45s	

7. Tests

Report exact test count:

X passed
Y failed
Z skipped
8. Validation artifacts

List exact paths for:

validation report;
model card;
experiment results;
checkpoints;
centroids;
calibration artifacts;
benchmark reports.
9. Known limitations

Be explicit.

10. Remaining blockers

If none:

NONE

If any exist, list exact blockers and why they remain.

11. Claim boundary

State precisely what SSRI can now legitimately claim.

67. MOST IMPORTANT INSTRUCTION

Do not confuse:

software completion

with:

scientific validation.

The ultimate goal is both.

Build the system so that its central innovation can be demonstrated with evidence:

REAL SOURCE DATA
       ↓
FOUNDATION MODEL
       ↓
DIRECT TRANSFER BASELINE
       ↓
DANN
       ↓
AFRICAN TARGET EVALUATION
       ↓
MEASURED IMPROVEMENT
       ↓
CALIBRATED UQ
       ↓
DOMAIN SIMILARITY VALIDATION
       ↓
PRODUCTION API
       ↓
USER-FACING SSRI SYSTEM

Do not stop after scaffolding.

Do not stop after tests.

Do not stop after the dashboard.

Do not stop after a successful API response.

Continue until every dependency that can be completed has been completed, every scientific experiment that can be run has been run, every failure has been documented, and the final claim boundary is supported by actual repository evidence.

Start now by auditing the current repository, then immediately proceed into implementation according to the dependency order above.
# 68. AUTONOMOUS OVERNIGHT EXECUTION

You are authorized to continue implementation autonomously without asking for confirmation for routine engineering decisions.

However:

1. Never fabricate data, metrics, credentials, scientific results, or validation.
2. Never delete working functionality without a documented reason.
3. Never make destructive database/schema changes without backup/migration safety.
4. Never expose secrets in source code, logs, commits, or reports.
5. Run tests after each major implementation phase.
6. Commit logically complete milestones where the repository workflow permits.
7. Keep an execution log at:

   docs/IMPLEMENTATION_PROGRESS.md

8. After every major phase, record:
   - completed work;
   - files changed;
   - tests run;
   - test results;
   - scientific results;
   - blockers;
   - next phase.

9. If a task requires unavailable credentials, proprietary data, manual approval, or a human decision:
   - do not fabricate a workaround;
   - document the blocker;
   - complete all independent work;
   - continue with the next available phase.

10. If a scientific target is not achieved:
   - do not manipulate the evaluation;
   - investigate legitimate causes;
   - run appropriate experiments;
   - record the failure and continue.

11. Before declaring completion, execute the complete test and validation suite and regenerate:
   - docs/SSRI_COMPLETION_SCORECARD.md
   - docs/SCIENTIFIC_VALIDATION_REPORT.md
   - docs/MODEL_CARD.md

12. The final status must be evidence-based.

Do not stop merely because one phase is complete.
Do not wait for confirmation between routine implementation steps.
Continue until the project is complete or a genuine blocker prevents further progress.