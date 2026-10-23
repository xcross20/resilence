# Current slice

Milestone: P0 synthetic-demo gate policy.

Completed slice: persist `gate-policy-synthetic-demo-v1` for workflow `service-desk-synthetic-demo` on a disposable Postgres. One 100-case cohort stores `eligible=true` from execution records. Ineligible cohorts, v0, a forged body, and a production runtime stay ineligible. `APPROVED_ACTIVATION_POLICIES` is still empty.

Sensor, from `services/api`:

`DISPOSABLE_DATABASE_URL=postgresql+psycopg://demo:demo@127.0.0.1:54329/demo .venv/bin/python -m pytest -q tests/test_gates.py tests/test_synthetic_demo_policy.py tests/test_synthetic_demo_evaluation.py tests/test_release_policy.py --tb=short`

Exit code 0. 37 passed. 1 Starlette httpx deprecation warning. 9.49 seconds. The database was a local disposable Postgres, not Railway.

Next slice: teach the release path to commit a synthetic-demo activation only when the server scope, demo workflow, five passing gates, synthetic provenance, and human confirmation all match. Production scope must still deny.

disposition: CONTINUE
