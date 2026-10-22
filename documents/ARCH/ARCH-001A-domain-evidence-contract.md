# ARCH-001A — Domain and Evidence Contract v0.1

**Status:** Proposed; implementation-ready starting schema, subject to review.
**Dependencies:** ARCH-001 invariants and locked UO-001.

## Authoritative records (minimum fields)

| Record | Required fields | Constraints |
|---|---|---|
| WorkflowDefinition | workflow_id, version, graph_nodes, graph_edges, created_at | Immutable version; graph is definition, not evidence |
| CohortManifest | cohort_id, version, case_ids, manifest_sha256, purpose (acceptance/verification), fixture_version | Frozen membership; hash covers ordered IDs and fixture version |
| CaseInput | case_id, cohort_id, request_text, observed_features, created_at | No ground-truth label in routing DTO |
| ClassificationObservation | observation_id, case_id, classifier_version, observed_category, confidence, evidence_origin | Distinct from ReferenceLabel |
| ReferenceLabel | case_id, reference_category, expected_disposition, rubric_version, policy_document_version | Evaluation module only |
| StrategyRevision | revision_sha256, schema_version, workflow_id, ordered_rules, default_route, fallback_route, canonical_json, created_at | Immutable; SHA-256 computed server-side |
| ExecutionRun | run_id, case_id, strategy_revision, workflow_version, fixture_version, status, started_at, completed_at | One run per case/strategy/evaluation attempt; unique idempotency scope |
| DecisionRecord | decision_id, run_id, step_id, observation_id, matched_rule_id, selected_method, reason_code, timestamp | Records rule and input evidence; cannot reference reference label |
| AttemptRecord | attempt_id, run_id, decision_id, method_id, method_version, input_digest, output_digest, simulated_latency_ms, status, evidence_origin | Multiple attempts/fallbacks allowed |
| CostEntry | cost_entry_id, attempt_id or allocation_ref, amount_micro_usd, cost_type, price_book_version, evidence_origin | Integer micro-USD; no negative values without explicit adjustment type |
| OutcomeAssessment | assessment_id, run_id, evaluator_version, rubric_version, verdict, correct_escalation, critical_violation, supporting_evidence_ids | Independent from routing; preserve uncertainty |
| EvaluationRun | evaluation_id, workflow_version, baseline_revision, candidate_revision, cohort_hash, evaluator_version, price_book_version, accounting_version, fixture_version, status, gate_results, created_at | Exact versions, per-case paired references, persisted eligibility |
| ReleaseEvent | event_id, release_id, event_type, actor, prior_revision, target_revision, evaluation_id, verification_id, correlation_id, occurred_at | Append-only, idempotency key; no in-place rewrite |
| ActivePolicyPointer | workflow_id, active_revision, generation, updated_at | Atomic CAS on generation |
| VerificationRun | verification_id, release_id, cohort_hash, activated_revision, status, result, evidence_refs | Must disclose cohort overlap or replay |

Prefer relational columns for keys and status; JSONB only for versioned payloads/evidence details with validation.

## Runtime routing DTO (strict)
```json
{
  "case_id": "SD-081",
  "request_text": "Unable to access VPN after password change",
  "observed": {
    "category": "ambiguous",
    "confidence": 0.62,
    "classifier_version": "synthetic-classifier-v1",
    "policy_tags": ["access"]
  },
  "workflow_version": "service-desk-v1"
}
```
This object MUST NOT contain `reference_category`, `expected_disposition`, `correct_route`, `critical_violation`, or `outcome`.

## Strategy revision DTO (illustrative grammar)
```json
{
  "schema_version": "1",
  "workflow_id": "service-desk",
  "rules": [
    {"rule_id":"R1","priority":10,"when":{"observed_category_in":["routine"],"min_confidence":0.85},"method":"economy"},
    {"rule_id":"R2","priority":20,"when":{"observed_category_in":["privileged","ambiguous"]},"method":"premium"}
  ],
  "default_method": "premium",
  "fallback_method": "premium"
}
```
Rules evaluate in ascending priority; priority and rule_id are unique; conditions use an allowlist of runtime-visible fields. Unknown/invalid observations fail to safe default. Fallback occurs only on declared attempt failure or uncertainty conditions; fallback attempts are recorded. No arbitrary code expression/eval. This grammar is **proposed**, not approved.

## Example evidence chain
`case SD-081 → observed classification OBS-081 → evaluation run EV-001 → execution EX-081-C → decision DEC-081-C (R2, premium) → attempt ATT-081-C → cost entry COST-081-C → outcome assessment OA-081-C`.

Every graph highlight must cite run_id/decision_id. Every table aggregate must cite evaluation_id, accounting_version and paired case membership.

## Costs and denominators
- Primary: `sum(execution_cost_entries) / count(independently_verified_successful_workflow_outcomes)` over same cohort. Define success as business outcome, **not just automated completion**.
- Separately: modeled labor allocations, modeled infrastructure, and risk cost. If shown, composite `(execution + disclosed modeled allocations) / verified successful outcomes`.
- `verified_automated_success` may be displayed as a secondary metric with its own explicitly named denominator.
- Denominator zero => null/inconclusive, never zero.
- Store integer micro-USD, integer ms, raw counts. UI formatting cannot alter gate math.

## PostgreSQL constraints and indexes
- FK for each run/decision/attempt/assessment/cost/evaluation/release reference.
- Unique `(workflow_id, revision_sha256)`, `(evaluation_id, case_id, strategy_role)`, `(workflow_id, generation)` release CAS.
- Index `(run_id, step_id)`, `(evaluation_id, case_id)`, `(workflow_id, occurred_at)`.
- Append-only event writes; prohibit UPDATE/DELETE for release event table at application role.
- Keep audit records and evaluations in one transaction for state transitions.

## Validation tests
- Reference-label injection into runtime DTO rejected (Pydantic extra=forbid).
- Observed classifier mislabel differs from ground truth without hidden correction.
- Two differently ordered equivalent canonical policy inputs hash identically when semantically equivalent; rule order remains significant.
- Attempt and cost reconciliation, no orphaned evidence, no missing paired case.
- Editing a rule yields a new revision; stale evaluation cannot activate.
- Invalid/unknown classification routes to safe default.
- Missing assessment, price book, or zero denominator returns inconclusive.

## Decisions needed
Agree on outcome rubric, condition grammar, cost boundaries, and event retention before freezing v1 schema.
