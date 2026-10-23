# Known limitations

- Gate policy `gate-policy-v0-fail-closed` never stores `eligible = true`. `APPROVED_ACTIVATION_POLICIES` is empty. The API cannot commit an activation.
- `gate-policy-synthetic-demo-v1` can persist an eligible evaluation on `service-desk-synthetic-demo`. `APPROVED_ACTIVATION_POLICIES` is empty, so that eligibility does not activate a revision and it is not production authority.
- Numerical quality, latency, noninferiority, and minimum-evidence thresholds are not approved. Quality and latency gates stay `not_authoritative`.
- Restoration in tests uses a pointer planted by the database owner. That plant is not an API activation and it is not an eligibility grant.
- Verification does not claim an independent holdout. `HOLDOUT_CLAIMS_APPROVED` is false. Overlap with an acceptance case is denied before execution.
- A recorded regression does not move the active pointer and does not restore the prior revision by itself.
- `runtime_case_v` is an application allowlist. The database owner can still read `reference_label`.
- All execution, assessment, and modeled-cost figures in this branch are synthetic. They are not a statistical proof of real-world model equivalence and they are not a savings claim.
- The approved v0.6.4 workbench is not connected to this API. Operate, Investigate, Strategies, and Releases are not browser-verified against persisted records.
- Outcome Verification cannot mark UO-001 PASS until approved commands are mapped to UO-AC-01 through UO-AC-10. Editing the skill manifest to approve the Railway suite was not done.
- `--unattended` container execution is unavailable here. The local `python:3.12-alpine` image is absent, and it was not pulled. Supervised process-group runs were used instead.
- One Starlette `httpx` deprecation warning remains. It did not fail a test.
- Public Railway TCP proxy settings were not changed. No merge to `main` and no production deploy were performed.
