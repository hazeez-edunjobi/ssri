# 5-minute demo (SYNTHETIC only)

**Label every demo artifact SYNTHETIC.** Do not imply real geology, risk, probability, detection, or validation.

## Prep (2 min)

1. API with `SSRI_RELEASE_SHELL=true` and lowered mins for the template (4/4/2) if needed.  
2. Open `/shell` or have `OWNER_API_GUIDE.md` ready.  
3. ZIP: `poc/release_shell/templates/SYNTHETIC_stage25_template.zip`.

## Script (3 min)

1. **No model yet** — assess `{}` → `no_trained_model`.  
2. **Upload SYNTHETIC ZIP** — validation PASS or WARN; `can_train` true. Say: “This is fabricated data.”  
3. **Start training (3 seeds)** — show job progress on `GET /jobs/{id}`.  
4. **Evaluation** — show gate strings only; status **NOT_VALIDATED**.  
5. **Assess inside geography** — scores only if gate is `evaluated`; otherwise `not_available` / null score.  
6. **Assess far away** — `outside_training_region`, score null.

## Never say

Validated, calibrated, probability of failure, risk score, detection, production-ready, insurance-ready.
