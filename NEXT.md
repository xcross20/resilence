# Next

1. Build a deterministic synthetic cohort of at least 100 matched cases, plus ineligible variants and a non-overlapping verification cohort.
2. Persist `gate-policy-synthetic-demo-v1` through the evaluation service on a disposable database. Do not point destructive cleanup at the shared Railway Postgres.
3. Keep `APPROVED_ACTIVATION_POLICIES` empty until the release path checks server-controlled nonproduction scope, synthetic provenance, the demo workflow, five passing gates, and human confirmation.
4. After that boundary exists, add only `gate-policy-synthetic-demo-v1` to the registry and prove production scope still denies activation.
5. IMP-004 starts after an eligible synthetic activation and a denied unsafe activation both exist as persisted API behavior.

Sensor for the next slice: the new evaluation tests against the disposable database, plus the existing domain tests in `tests/test_gates.py` and `tests/test_synthetic_demo_policy.py`.

Do not merge, deploy, or spend on a live model provider.
