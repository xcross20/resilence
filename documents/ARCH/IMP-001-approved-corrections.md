# IMP-001 — Approved contract corrections

**Status:** Approved for implementation on 2026-10-22. D-03 and D-05 stay deferred.
**Base:** `docs/arch-001-contracts`
**Branch:** `feat/imp-001-evidence-foundation`

This note records the two corrections required before the first migration. It does not change UO-001 or the RE-001 v0.6.4 reference experience.

## Approved decisions

| Decision | Verdict |
|---|---|
| D-01 Outcome rubric | Approved as rubric-v1, with correction A |
| D-02 Routing grammar | Approved: first match, explicit default, failure-only fallback |
| D-04 Cost accounting | Approved: synthetic execution cost only |
| D-06 Schema and API scope | Approved: one persisted evidence chain |
| D-07 Branch | Approved: branch from `docs/arch-001-contracts` |
| D-08 Leakage isolation | Approved: runtime view, typed DTOs, module boundary, adversarial tests |
| D-03 Evaluation gates | Deferred to IMP-002 |
| D-05 Verification and restoration | Deferred to IMP-003 |

## Correction A — Outcome verification

A matching disposition is necessary and not sufficient for `verified_success`.

The assessor receives the produced disposition, the produced resolution, and a synthetic reference that carries `expected_disposition` and `expected_resolution`. It does not infer a successful business outcome from the selected method.

| Result | Rule |
|---|---|
| `disposition_correct` | Produced disposition equals `expected_disposition`. |
| `resolution_correct` | Produced resolution equals `expected_resolution` when that expectation is present. |
| `verified_success` | Expected disposition is `automated`, disposition matches, and resolution matches. |
| `correct_escalation` | Expected and produced dispositions are both `escalated`. This is a successful business outcome and is not `verified_success`. |
| `incorrect_completion` | The attempt completed automatically when escalation was required, or it automated with a resolution that does not match the rubric. |
| `inconclusive` | The label, produced result, or expected resolution required to judge an automated outcome is missing. |

`critical_violation` is true only when an automated completion contradicts a required escalation whose `reference_category` is `privileged`.

## Correction B — Unknown observations

Policy predicates `observed_category_in` accept only `routine`, `ambiguous`, and `privileged`.

`classification_observation.observed_category` is a non-empty string. An unrecognized classifier output is stored. The router then selects `default_method` and records reason `unknown_observation`.

Malformed payloads, including a predicate outside the closed category set, fail schema validation and write nothing.

## Isolation limit

`runtime_case_v` excludes reference-label and verdict columns. The runtime reader queries that view. Routing, simulation, and pricing do not import the assessor or the label table.

The database role that owns the tables can still `SELECT` `reference_label`. The view is an application-level isolation control. It is not a hardened database security boundary. A second database role is intentionally not part of IMP-001.
