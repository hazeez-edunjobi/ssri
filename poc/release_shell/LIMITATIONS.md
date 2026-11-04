# Known limitations (plain language)

SSRI’s upload-and-train shell helps you run a **research workflow**: upload labelled tiles, check them, train a model, see an automatic evaluation report, and call assess with that checkpoint.

**What the scores are:** relative susceptibility **rankings** from the trained model on your uploaded geography. They are **not** probabilities, **not** risk estimates, **not** detection alerts, and **not** scientifically validated.

**Status:** always **NOT_VALIDATED**. A hazard may show **evaluated** only if it beats a slope-only baseline on held-out blocks under fixed gates. Otherwise it shows **trained, no demonstrated skill beyond slope**. The word **validated** is never used as a product status.

**Geography:** models are trained only on the uploaded data’s geography. Using them elsewhere returns **outside_training_region** when that check is available; treat other regions as unsupported.

**Slope baseline:** slope alone often matches or beats trained models. The evaluation report always compares against slope-only.

**Data quality:** missing CRS/coordinates blocks training. Channels that are all nodata (for example spectral bands filled with -9999) fail validation. Hazards below minimum labelled size (default 300 tiles / 8 blocks / 3 held out) are **DISABLED** for skill claims.

**Must never be used for:** insurance underwriting, engineering design, safety-critical decisions, or emergency response.

**No weights ship** with this shell. Demo ZIPs labelled **SYNTHETIC** are fake data for process demos only.
