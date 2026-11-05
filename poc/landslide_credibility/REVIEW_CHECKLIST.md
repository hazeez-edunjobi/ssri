# Independent reviewer checklist

Try to break the claims. Prefer falsification.

1. **Leakage:** Confirm train/test 5° blocks disjoint; recompute min NN ≥50 km.  
2. **Pseudo-replication:** Inspect presence thinning and source-cap counts in manifest.  
3. **Absence design:** Is NEAR (5–20 km) circular (hard vs easy negatives)? Compare FAR.  
4. **Inventory bias:** Are absences only where mapping exists?  
5. **Slope dominance:** Does any model beat slope with CI?  
6. **Calibration:** ECE and reliability — are scores usable as probabilities? (Protocol says no.)  
7. **Bootstrap:** Block vs tile resample — was block resampling used?  
8. **Feature causality:** Any event/date features? (Must be none.)  
9. **Claims language:** Marketing vs MODEL_CARD framing.  
10. **Repro:** Run `scripts/verify_repro.py` from clean checkout.
