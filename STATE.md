# State

disposition: CONTINUE

- IMP-001 accepted at `040d5a9086e6faf54985fd482815588318f0f9a5`.
- IMP-002 accepted at `c35d1c8a1cc6b2d23f5413408224fc32a2c8201d`.
- IMP-003 accepted at `f9716cb2f2490213ddd7013feff0e30c1d29a893`.
- P0 calculator `92b1ded9dbcdf216ae3f9113d2b70b7c877f5c2f` judges the demo policy in memory.
- P0 persistence slice stores an eligible synthetic-demo evaluation on workflow `service-desk-synthetic-demo`. Activation is still denied.
- IMP-004 has not started. UO-001 is not accepted.
- Railway networking was not changed. The new database tests did not use Railway. No merge and no deploy.

## Slice sensor

Command, from `services/api`, against disposable Postgres `127.0.0.1:54329`:

`DISPOSABLE_DATABASE_URL=postgresql+psycopg://demo:demo@127.0.0.1:54329/demo .venv/bin/python -m pytest -q tests/test_gates.py tests/test_synthetic_demo_policy.py tests/test_synthetic_demo_evaluation.py tests/test_release_policy.py --tb=short`

Exit code 0. 37 passed. 1 warning. 9.49 seconds.
