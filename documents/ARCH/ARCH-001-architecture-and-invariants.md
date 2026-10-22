# ARCH-001 — Architecture Decision and Invariants

**Status:** Architecture direction APPROVED; detailed contracts PROPOSED FOR REVIEW.
**Date:** 2026-10-22
**Authority:** UO-001 approved/locked; RE-001 v0.6.4 visual reference approved. No production implementation accepted.
**Decisions:** FastAPI modular monolith, PostgreSQL, deterministic synthetic execution first, explicit human activation enforced by backend gates.

## Mission
Reduce fully loaded cost per independently verified successful AI-assisted workflow outcome while preserving quality, escalation, reliability, latency, and policy compliance. First scenario: synthetic internal IT service desk. This is an execution strategy optimizer, **not** a universal gateway, generic workflow builder, or autonomous orchestration platform.

## Logical architecture
- Next.js/React/TypeScript workbench: graph, cases, policy editor, paired evidence, release UI. All displayed authoritative states come from API read models. Client may calculate **labeled previews** but never eligibility or release authority.
- FastAPI application boundary: Pydantic validation, idempotency, request correlation, status codes, policy authorization boundary (single local operator in MVP), typed OpenAPI.
- Domain modules within one process: (1) execution + strategy routing, (2) evaluation + economics, (3) release + verification. Shared domain models and repositories are modules, not network services.
- PostgreSQL: versioned cohort definitions, observed inputs, strategy revisions, execution/decision/attempt ledgers, assessments, cost entries, evaluation results, release pointer and append-only audit events. Alembic migrations.
- Deterministic fixture adapter: versioned synthetic input, classification observations, policy documents, simulated method results and costs. Optional provider adapter is a future boundary, not a first-slice dependency.
- Jobs: evaluation can initially run synchronously in development for 100 cases but must expose durable job state; if asynchronous, use database-backed claim/lease or an explicit local worker, not unbounded FastAPI background tasks. No queue/broker required at MVP.

## Data flow
1. Load immutable workflow definition and versioned cohort.
2. Create canonical immutable strategy revision (SHA-256 of normalized, versioned strategy content).
3. Evaluate baseline and candidate on matched cohort; runtime routing consumes **observed** fields only.
4. Persist execution, decision, attempt, cost, and independently versioned outcome-assessment evidence for each case.
5. Reconcile economics; evaluate safety, quality, latency and evidence completeness; persist gate results.
6. On explicit human request, atomically activate the exact revision with a passing eligible evaluation and expected active revision (compare-and-swap).
7. Execute separately identified verification cohort; record results and restore prior revision on explicit operator action (or a later separately approved policy).
8. Graph/read models project persisted evidence; the graph never becomes the source of truth.

## Hard invariants
I-01 Routing engine cannot access reference labels, evaluator results, or assessment fields. Enforce via distinct types/modules and adversarial tests.
I-02 Strategy revisions are immutable and canonical; any edit creates a different SHA-256 revision ID.
I-03 Evaluations bind exact strategy revision, workflow version, cohort manifest hash, evaluator version, pricing version, accounting version and simulation fixture version.
I-04 Baseline and candidate use the same cohort membership, outcome definitions, price assumptions, and evaluator; no unmatched case drops.
I-05 All displayed outcome and cost aggregates reconcile to case-level/attempt-level records, with rounding only at presentation.
I-06 Evidence source type is mandatory: synthetic_simulated, fixture_replay, estimated, provider_measured. Never label simulation as provider observation.
I-07 Required escalation and critical policy violations are hard blockers. Missing/inconclusive evidence blocks release. Numerical quality/latency gates are explicit and versioned, not inferred.
I-08 Activation references the exact eligible evaluation/revision; enforce atomically in database, not frontend. Concurrent release attempts fail conflict.
I-09 Release, verification, and restoration append audit events with actor, time, expected prior state, new state, evidence refs and correlation ID. No event rewriting.
I-10 A verification cohort is identified separately from acceptance and must be genuinely non-overlapping to claim independent holdout; re-labeled duplicates must be described as replay only.
I-11 The primary UO-001 metric is observed/simulated **execution cost per independently verified successful outcome**. Estimated labor, infrastructure and risk allocations are separately disclosed; a modeled fully loaded composite may be shown as secondary, with explicit denominator and assumptions.
I-12 A passing result on a small synthetic cohort is not proof of real-world equivalence; display counts, denominators, and limitations.

## Module boundaries
- execution: StrategyRevision, PolicyRule, ObservedRequest, RoutingDecision, ExecutionRun, Attempt, ExecutionCostEntry. Never imports reference labels.
- evaluation: CohortManifest, ReferenceLabel, OutcomeAssessment, EvaluationRun, PairedComparison, GateResult, CostReconciliation. Imports execution evidence; never feeds reference labels to routing.
- release: ReleaseTransition, ActivePolicyPointer, VerificationRun, AuditEvent. Only reads immutable eligible evaluation, never trusts UI-provided gate booleans.
- presentation: graph and case read models built from persisted domain records, not independent fixture arrays.

## Engineering trade-offs
- PostgreSQL over SQLite: transactional release pointer, constraints, durable evidence; local Docker Compose is enough.
- FastAPI over Next.js-only backend: Python domain/evaluation testability, typed API, separation of release authority.
- No Kafka, Temporal, Redis, Kubernetes, OTel collector, or auth/SSO for first slice. Add only against a demonstrated requirement.
- Preserve v0.6.4 workbench as behavioral reference, not implementation source of truth.
- Avoid assuming the current v0.6.4 demo passes production-build/browser acceptance; previous status was preview with unverified browser QA.

## Explicit exclusions
Production integrations, real provider pricing claims, live enterprise data, multi-tenancy, generalized graph editing, agentic policy generation, automatic rollout, universal inference proxy, FinOps chargeback.

## Open decisions before implementation
D-01 Exact reference-label and outcome rubric.
D-02 Strategy rule grammar, default/fallback semantics, and allowed observed fields.
D-03 Gate thresholds and minimum cohort evidence requirements.
D-04 Execution and labor cost price book and denominator definition.
D-05 Post-release verification sample design and fail/restore policy.
D-06 API and database contract acceptance.

The architecture direction is approved; these detailed choices remain reviewable and must not be silently treated as approved.
