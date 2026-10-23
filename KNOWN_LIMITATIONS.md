# Known limitations

- Gate policy `gate-policy-v0-fail-closed` never stores `eligible = true` and is not in `APPROVED_ACTIVATION_POLICIES`. A v0 evaluation cannot activate.
- `gate-policy-synthetic-demo-v1` can activate only on workflow `service-desk-synthetic-demo` when the server runtime is `synthetic-demo`, provenance is synthetic, and the stored evaluation is eligible. That activation is not production authority. `production_authority` stays false.
- v0 quality, latency, and noninferiority stay `not_authoritative`. The synthetic-demo policy uses the RE-001-COMPLETE-001 comparison rules. Those rules are not statistical noninferiority and they are not a production gate.
- A database owner can still plant a pointer. That plant is not an API activation. The synthetic-demo API path now records the compared baseline as the first prior revision and can restore it.
- Verification does not claim an independent holdout. `HOLDOUT_CLAIMS_APPROVED` is false. Overlap with an acceptance case is denied before execution.
- A recorded regression does not move the active pointer and does not restore the prior revision by itself.
- `runtime_case_v` is an application allowlist. The database owner can still read `reference_label`.
- All execution, assessment, and modeled-cost figures in this branch are synthetic. They are not a statistical proof of real-world model equivalence and they are not a savings claim.
- The approved v0.6.4 workbench is not connected to this API. Operate, Investigate, Strategies, and Releases are not browser-verified against persisted records.
- Outcome Verification cannot mark UO-001 PASS until approved commands are mapped to UO-AC-01 through UO-AC-10. Editing the skill manifest to approve the Railway suite was not done.
- `--unattended` container execution is unavailable here. The local `python:3.12-alpine` image is absent, and it was not pulled. Supervised process-group runs were used instead.
- One Starlette `httpx` deprecation warning remains. It did not fail a test.
- Public Railway TCP proxy settings were not changed. No merge to `main` and no production deploy were performed.
