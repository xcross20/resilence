# Next

1. A human approves a versioned gate policy, including numerical quality, latency, noninferiority, and minimum-evidence requirements, or confirms that activation stays denied.
2. Only after that approval, add the policy id to `APPROVED_ACTIVATION_POLICIES` and prove one eligible activation against the approved thresholds.
3. Then start IMP-004 against the approved v0.6.4 destinations. Denial of an ineligible strategy can be shown before that approval. A successful activation cannot.
4. Map approved Outcome Verification commands to UO-AC-01 through UO-AC-10 before claiming user-outcome acceptance.
5. Do not merge to `main`, deploy, change Railway networking, or spend on a live model provider as part of this stop.

If a later review finds a defect in `f9716cb`, repair only that defect. Do not reopen the accepted IMP-001 race fix or the IMP-002 rubric unless a new failure appears.
