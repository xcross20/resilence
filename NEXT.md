# Next

1. Extend release judgment so `gate-policy-synthetic-demo-v1` can commit only when the server runtime is `synthetic-demo`, the workflow is `service-desk-synthetic-demo`, the evaluation is `completed_eligible`, all five gates passed, provenance is synthetic, and the human confirmation matches.
2. Keep every `service-desk` activation and every production runtime denied.
3. Prove duplicate, concurrent, stale-generation, and missing-confirmation denials leave the demo pointer unchanged.
4. Add the policy id to `APPROVED_ACTIVATION_POLICIES` only in that same change.
5. Run the new release tests on a disposable database. Do not point them at Railway.

Sensor: disposable-database pytest for the release file, plus `tests/test_release_policy.py` and `tests/test_synthetic_demo_policy.py`.

IMP-004 stays waiting until that activation and a denied unsafe activation both exist as API behavior. Do not merge or deploy.
