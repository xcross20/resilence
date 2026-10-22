# ARCH-001B–D — Execution, Evaluation, Release and API Contracts v0.1

**Status:** Proposed for architecture review, not yet approved.
**Runtime:** FastAPI + PostgreSQL; deterministic synthetic fixture adapter.

## Policy evaluation semantics
1. Normalize observed input via validated RuntimeRequest DTO; reject extra fields.
2. Evaluate ordered, unique-priority rules using runtime-visible allowlisted predicates.
3. First match selects method. Unknown category/confidence, invalid fields, or no match selects explicit safe default.
4. Record decision before attempt; invoke synthetic adapter; record attempt, status, latency, method/version, and cost.
5. On declared fallback condition, record fallback decision/attempt; never overwrite initial attempt.
6. Execute validation/escalation; evaluator independently judges final business outcome against reference labels.
7. Freeze evidence records and provenance before aggregate computation.

## Evaluation lifecycle
`CREATED → RUNNING → COMPLETED_ELIGIBLE | COMPLETED_BLOCKED | INCONCLUSIVE | FAILED`.

An evaluation binds baseline_revision, candidate_revision, cohort_hash, fixture_version, evaluator_version, price_book_version, accounting_version and gate_policy_version. If any required pair is absent, mismatched, or fails validation, status is INCONCLUSIVE/FAILED, never eligible.

Paired case rows: case_id, baseline_run_id, candidate_run_id, baseline_assessment_id, candidate_assessment_id, route_changed, first_divergent_decision_id, outcome_delta, execution_cost_delta_micro_usd, modeled_cost_delta_micro_usd, violations.

## Gate framework (proposed, numbers NOT approved)
- Critical policy violations = 0 and incorrect completion of required escalation = 0.
- Complete matched cohort and attributable evidence = mandatory.
- Candidate verified business success rate must satisfy an explicitly versioned noninferiority tolerance and minimum sample-size policy. A small 100-case synthetic cohort is for functional demonstration, not statistical equivalence.
- Latency/failure-rate caps, escalation correctness, and economic improvement must be explicit gate_policy_version inputs.
- If insufficient evidence, confidence, or missing price/assessment: INCONCLUSIVE.
- Release is not authorized by a UI-provided `eligible: true` flag.

## Release state machine
`DRAFT → EVALUATED_BLOCKED | EVALUATED_ELIGIBLE → ACTIVATION_REQUESTED → ACTIVE → VERIFYING → VERIFIED | REGRESSED → RESTORED`.

For simplicity, model immutable evaluation status separately from release events rather than mutating a single state enum across unrelated entities. A release record can be `PROPOSED, ACTIVE, VERIFYING, VERIFIED, REGRESSED, RESTORED`; rejected activation creates a denied audit event but never changes active pointer.

Activation transaction:
1. Lock workflow active policy row.
2. Verify operator's expected_generation and expected_prior_revision.
3. Verify candidate revision equals the immutable revision in an eligible evaluation, all required evidence versions still valid, and operator confirmation recorded.
4. Atomically set active revision and increment generation; append event referencing evaluation and prior revision.
5. Commit. Concurrent request with stale generation returns 409.

Verification must reference exact active revision and a separately versioned verification cohort. Duplicate acceptance cases cannot be described as independent holdout. A regression must be visible; restoration explicitly targets recorded prior approved revision and appends an event. No silent self-activation or automatic restore in MVP.

## Initial API proposals
| Method | Path | Meaning |
|---|---|---|
| GET | /api/v1/workflows/{id} | Definition + current active policy reference |
| GET | /api/v1/workflows/{id}/cases?cohort_id= | Versioned case listing |
| GET | /api/v1/executions/{run_id}/evidence | Case execution evidence + graph projection |
| POST | /api/v1/strategies/revisions | Validate/canonicalize/store immutable strategy |
| POST | /api/v1/evaluations | Start matched evaluation; return evaluation_id + status |
| GET | /api/v1/evaluations/{id} | Aggregate, gates, evidence refs |
| GET | /api/v1/evaluations/{id}/cases | Paginated paired evidence |
| POST | /api/v1/releases | Human-confirmed activation, expected generation |
| POST | /api/v1/releases/{id}/verifications | Run separate verification batch |
| POST | /api/v1/releases/{id}/restore | Explicit rollback to recorded prior revision |
| GET | /api/v1/releases/{id}/events | Append-only release history |

All mutating POSTs require `Idempotency-Key` (unique per operation + actor + request body digest); replay same request returns original result, conflicting reuse returns 409. Server assigns UTC timestamps and correlation IDs. Errors use consistent machine-readable `code`, `message`, `correlation_id`, optional `details`. Never return internal stack traces or secret-bearing raw logs.

## Example activation request
```json
{
  "workflow_id": "service-desk",
  "evaluation_id": "EV-001",
  "candidate_revision": "sha256:<64 hex chars>",
  "expected_prior_revision": "sha256:<64 hex chars>",
  "expected_generation": 7,
  "confirmation": "activate_synthetic_revision"
}
```

## HTTP behavior
- 200/201: existing or created immutable resource; 202 for async evaluation/verification job.
- 400/422: malformed payload or invalid predicate.
- 404: unknown resource.
- 409: revision mismatch, stale generation, conflicting idempotency key, duplicate active transition.
- 412: failed precondition if explicit HTTP conditional header is adopted; choose one consistent contract.
- 422 or 403 (choose one consistently): activation denied by eligibility/safety policy with gate details.
- 503: fixture/worker dependency unavailable, no release side effects.

## Test matrix
- No runtime access to reference labels; first-match/unknown/default/fallback cases.
- Equivalent paired cohort; rejected unmatched IDs and evaluator version mismatch.
- Ledger-to-aggregate reconciliation, zero denominator, rounding.
- Failed critical gate blocks activation; inconclusive cannot activate.
- Exact evaluated revision only; stale generation conflict; idempotent retry.
- Injected verification regression; restoration returns prior revision; history preserved.
- Separate verification manifest with overlap disclosure.
- Browser: inspect → edit → evaluate → blocked → safe revision → eligible → confirm activation → verify → restore.

## Explicit pending decisions
Numerical gates, confidence handling, model/price fixture versions, persistence schema migration naming, job execution mode and release authorization details require review before contract freeze.
