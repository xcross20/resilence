# Current slice

Milestone: RE-001-COMPLETE-001 synthetic demonstration.

Completed in this stretch:

- `gate-policy-synthetic-demo-v1` can activate only on `service-desk-synthetic-demo` when the server runtime, provenance, gates, and confirmation match. v0 and `service-desk` stay denied. The first activation records the compared baseline so restore can return to it.
- The workbench at `services/web` has Operate, Investigate, Strategies, and Releases. It reads stored rows. A Synthetic Demo strip stays visible.
- Outcome verification remains INCONCLUSIVE for UO-AC-01 through UO-AC-10. The verifier does not receive a database URL. UO-001 is not accepted.

Sensor, from `services/api`, on a fresh disposable Postgres:

`DISPOSABLE_DATABASE_URL` set to the local disposable database, then `.venv/bin/python -m pytest -q tests/test_gates.py tests/test_synthetic_demo_policy.py tests/test_release_policy.py tests/test_synthetic_demo_evaluation.py --tb=line`

Exit code 0. 40 passed. 1 Starlette httpx deprecation warning. 11.43 seconds.

`services/web`: `npx next build` exit 0. Headless Chrome walk: Operate, Investigate, a case, Strategies, Releases, missing confirmation, then `activation_committed` with `production_authority` false. The `service-desk` pointer stayed inactive.

disposition: READY_FOR_INDEPENDENT_FINAL_QA

This is not production readiness and not UO-001 acceptance. Do not merge or deploy.
