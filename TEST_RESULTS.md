# Test results

Commands ran from `/Users/immanuellewis/resilence-imp-001/services/api` unless noted. The database is Railway Postgres via `railway run --service Postgres`. No local Postgres container was started.

## Independent gates

| Gate | Commit | Reviewer session | Command | Exit | Result |
| --- | --- | --- | --- | --- | --- |
| IMP-001 | `040d5a9086e6faf54985fd482815588318f0f9a5` | `01a16718-cd7b-7fc2-b50c-cb6bde1c596f` | `railway run --service Postgres` then `pytest -q --tb=line` | 0 | ACCEPTED. 25 passed, 1 warning, 64.10s. Idempotency file: 3 passed, 41.62s. |
| IMP-002 | `c35d1c8a1cc6b2d23f5413408224fc32a2c8201d` | `01a16735-2c0a-7392-8faa-e16bf320690e` | `railway run --service Postgres .venv/bin/python -m pytest -q --tb=line` | 0 | ACCEPTED. 43 passed, 1 warning, 209.70s. |
| IMP-003 | `f9716cb2f2490213ddd7013feff0e30c1d29a893` | `01a1674e-8ea6-7e53-9f3c-e3145d22b519` | `railway run --service Postgres .venv/bin/python -m pytest -q --tb=line` | 0 | ACCEPTED. 53 passed, 1 warning, 305.33s. |

The builder does not accept its own work. Each reviewer inspected that exact commit on a clean tree and did not modify the repository.

Builder suite before the IMP-003 commit, same command: exit 0, 53 passed, 1 warning, 311.52s.

Focused builder checks before that suite:

- `pytest -q tests/test_release_policy.py tests/test_gates.py`: exit 0, 13 passed, 0.01s, no database.
- After correcting a duplicate-publish assertion in `test_release_api.py`: that one test exited 0, 1 passed, 44.11s.

The warning is Starlette's deprecation of `httpx` with `TestClient`. It did not fail a test.

## Outcome Verification

Command, with the API virtualenv, containment `process_group`, timeout 180 seconds. `--unattended` was not used.

Approved checks only: `imp001-assessment`, `imp001-routing`, `imp001-revision`.

| Check | Commit | Exit | Duration | Status |
| --- | --- | --- | --- | --- |
| `imp001-assessment` | `f9716cb2f2490213ddd7013feff0e30c1d29a893` | 0 | 659 ms | PASS |
| `imp001-routing` | same | 0 | 503 ms | PASS |
| `imp001-revision` | same | 0 | 441 ms | PASS |
| UO-AC-01 through UO-AC-10 | same | not executed | — | INCONCLUSIVE, no mapped command |
| IMP-001-DB | same | not executed | — | INCONCLUSIVE, command not approved |
| IMP-002 through IMP-005 | same | not executed | — | INCONCLUSIVE, no mapped command |

Overall status `INCONCLUSIVE`. `verify.py` exit 3. `worktree_dirty` false. Report path on the operator machine: `/tmp/re001-ov-imp003/report.json`. That file is not in the repository.

The skill self-test, run earlier against the installed skill, was 26 passed and 1 skipped. The skip is the missing local image `python:3.12-alpine`. Container unattended mode was not used. The host process-group runner is not claimed to be repaired.

## Not run

Playwright, accessibility, visual regression, Schemathesis, Hypothesis, mutmut, and a frontend production build were not run. IMP-004 was not started. No mutation score, query count, or browser-journey duration was measured.
