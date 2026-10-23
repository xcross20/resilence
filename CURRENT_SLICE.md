# Current slice

Milestone: P0 synthetic-demo gate policy.

Completed slice: pure `gate-policy-synthetic-demo-v1` judgment. It is not activation authority. `APPROVED_ACTIVATION_POLICIES` is still empty. v0 is unchanged.

Sensor, from `services/api`, no database:

`.venv/bin/python -m pytest -q tests/test_gates.py tests/test_synthetic_demo_policy.py tests/test_release_policy.py --tb=short`

Exit code 0. 29 passed. 1 Starlette httpx deprecation warning. 0.03 seconds.

Next slice: persist this policy through paired evaluation on a disposable database, including a deterministic 100-case fixture and one eligible plus several ineligible cohorts. Do not add the policy to the activation registry in that slice unless the server runtime boundary is enforced in the same change.

disposition: CONTINUE
