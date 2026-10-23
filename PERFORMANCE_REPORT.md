# Performance report

These figures are measured command durations. They are not API latency, database query counts, or browser-journey times. No optimization was applied.

| Measurement | Commit | Seconds | What it includes |
| --- | --- | --- | --- |
| IMP-001 reviewer full pytest | `040d5a9` | 64.10 | Railway Postgres round trips for 25 tests |
| IMP-001 reviewer idempotency file | `040d5a9` | 41.62 | 3 tests, including concurrent locks |
| IMP-002 reviewer full pytest | `c35d1c8` | 209.70 | 43 tests |
| IMP-002 reviewer session | `c35d1c8` | 563.72 | Review plus the suite |
| IMP-003 builder full pytest | `f9716cb` parent worktree | 311.52 | 53 tests |
| IMP-003 reviewer full pytest | `f9716cb` | 305.33 | 53 tests |
| IMP-003 reviewer session | `f9716cb` | 505.25 | Review plus the suite |
| IMP-003 domain-only pytest | worktree before commit | 0.01 | 13 tests, no database |
| Outcome Verification `imp001-assessment` | `f9716cb` | 0.659 | `tests/test_assessment.py` |
| Outcome Verification `imp001-routing` | `f9716cb` | 0.503 | `tests/test_routing_labels.py` |
| Outcome Verification `imp001-revision` | `f9716cb` | 0.441 | `tests/test_strategy_hash.py` |

The suite grew from 25 to 53 tests and from about 64 seconds to about 305 seconds. Most of that time is Railway TCP proxy traffic, not local compute. That statement is an inference from where the tests connect. Per-query timings were not collected.

Not measured: API p50/p95, SQL query counts, mutation survival, flaky-test rate, browser journey duration, and frontend build time.

No recommendation in this file is a measurement.
