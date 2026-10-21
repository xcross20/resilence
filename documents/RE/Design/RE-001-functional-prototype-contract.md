# RE-001 — Functional prototype contract (draft v0.1)

Status: **Proposed for review; not approved**  
Branch: `design/re-001-functional-contract`  
Scope: local Next.js/React demonstration; synthetic fixture execution only.

## Outcome and scenario

An AI application/platform engineer must diagnose expensive service-desk resolution drafting, construct a bounded execution change, reject an unsafe cheaper strategy, activate an exact evaluated safe revision, discover a later regression, and restore the baseline. The interface must preserve the evidence chain across **Operate → Investigate → Experiments → Releases**.

This is an execution-policy workbench, not a ticketing tool, agent builder, inference platform, or production deployment system.

## Canonical objects

- **WorkflowVersion**: immutable ID and ordered steps/branches. Initial service-desk steps: receive, classify, retrieve policy, draft, validate, resolve/escalate.
- **CaseDefinition**: stable case ID, category (routine/ambiguous/privileged), risk labels, reference disposition, policy version, input, reference evidence. Labels must be independent of candidate outputs.
- **Execution**: unique ID, case ID, startedAt, strategyRevisionId captured at start, workflowVersionId, ordered step attempts, final disposition, verification state, and evidence origin.
- **StepAttempt**: step ID, attempt index, method/provider/model, input/output evidence refs, token usage, observed or fixture charges, timing, error/fallback state, policy reference. Unknown cost is null, never zero.
- **Investigation**: ID, baseline revision, cohort definition, selected step, supporting execution IDs, hypothesis, timestamps.
- **StrategyRevision**: immutable ID after evaluation, parent revision, ordered routing rules, default route, fallback trigger and maximum attempts, model/template/policy dependencies, originating investigation. Editing a frozen revision creates a new draft ID.
- **AcceptanceContract**: ID/version, required coverage and quality/safety/economic gates, declared cost boundary, latency percentile convention.
- **EvaluationRun**: ID, exact frozen revision and baseline, dataset/version, evaluator/version, contract/version, per-case paired outcomes, execution status, decision status, timestamps and fixture provenance.
- **Release**: ID, exact revision and evaluation IDs, source revision, restoration target, check results, decision reason, activation timestamp, post-change verification batches, incidents, and append-only change history.

Use human-readable names in primary UI. Stable IDs appear in provenance/detail surfaces; do not use IDs as substitutes for descriptive language.

## State machines and invariants

**Revision:** Draft → Frozen for evaluation → Evaluated. Any edit to a frozen revision forks a new Draft; the old evaluation remains attached to the original.

**Evaluation execution:** Not started → Running → Completed | Failed to execute | Completed with missing evidence.

**Evaluation decision:** Inconclusive | Blocked | Eligible. Completion does not imply eligibility. A critical violation is Blocked. Missing required coverage is Inconclusive.

**Release:** Review → Blocked | Ready → Activating → Active awaiting evidence → Checks passed | Guardrail violated → Restoring → Restored. Represent activation/restore failures and unknown active state explicitly.

Enforce:
1. Only an exact frozen revision with a completed, eligible evaluation under the current contract/dependencies may activate.
2. All navigation paths use the same eligibility check; disabling one button is insufficient.
3. Existing executions retain the revision captured at start; newly started executions use the current active revision.
4. Restoration changes the revision for *future* executions, adds a history event, and never erases a failed release or repairs already-delivered incorrect guidance.
5. Every aggregate must reconcile to case/attempt records. Unknown outcome or cost cannot be treated as success or zero.
6. Correct human escalation is a correct disposition, **not** an automated resolution.
7. Fixture replay and modeled costs must never be labeled as observed real-provider performance or realized production savings.
8. Active health, candidate evaluation, and post-release verification are separately scoped statuses; no post-change evidence means unknown/awaiting, not healthy.

## Deterministic demonstration fixtures

Dataset `acceptance-v1`: 100 labeled cases: 70 routine, 20 ambiguous, 10 privileged.

Strategies:
- **S0**: premium classification and drafting for all.
- **C1-r1**: economy drafting for all; intentionally unsafe.
- **C2-r1**: economy drafting only for explicitly allowlisted routine categories; ambiguous, privileged, unknown → premium. Provider failure → premium once; bounded total attempts.

Expected outcome counts for fixture validation:

| Metric | S0 | C1-r1 | C2-r1 |
|---|---:|---:|---:|
| Verified automated | 80 | 80 | 81 |
| Correct escalations | 20 | 12 | 19 |
| Incorrect completions | 0 | 8 | 0 |
| Critical violations | 0 | 4 | 0 |
| Correct dispositions | 100 | 92 | 100 |
| Execution cost | $1.9800 | $0.8760 | $1.2072 |
| Modeled escalation labor | $40.00 | $24.00 | $38.00 |
| Modeled total | $41.9800 | $24.8760 | $39.2072 |

Illustrative model rate card: premium P-1 $5/M input tokens, $20/M output; economy E-1 $1/M input, $4/M output. Human escalation: 4 minutes at $30/hour = $2 each. Include costs of incorrect cases in total numerator. Unit cost = modeled total cost of all cases / number of verified automated outcomes. Excludes enterprise overhead, remediation and licensing. Do not call it universally fully loaded.

These are proposed synthetic fixture targets from the independent review, **not measured model results**. Implement a case ledger and tests that derive these totals; never hardcode dashboard aggregates independently. Keep the main acceptance cohort retry-free; use a separate timeout fixture for fallback/attempt accounting.

Contract `AC-1`: all 100 comparable paired cases complete; exact workflow/policy/dataset/evaluator versions match; zero critical violations and incorrect completions; at least 80 verified automated outcomes; all 10 privileged cases correctly escalated; fixture p95 ≤6.5s (document percentile method); modeled unit cost lower than S0; unchanged exact evaluated revision. No statistical population-confidence claims.

Post-change fixture: separate 20 new cases (14 routine, 4 ambiguous, 2 privileged). Normal batch: 16 verified automated, 4 correct escalations, zero incorrect. Regression batch: one ambiguous contractor request misclassified as routine; 16 verified automated, 3 correct escalations, 1 incorrect. Independent reference check detects violation; restore S0 and rerun offending case with a new execution ID, preserving both executions.

## Four destinations and interaction continuity

### Operate
Question: **What warrants action?** Show scoped active condition, verified outcome counts, declared economic numerator/denominator, active revision, and attention queue. Findings must identify scope (active/candidate/evaluation), severity, evidence, and next action. Clicking drafting cost opens Investigate with cohort and draft step selected; clicking unsafe candidate opens its paired regressions.

### Investigate
Question: **What is happening, and where is a bounded change justified?** Hybrid synchronized topology, aggregate step table, execution list, and case trace/inspector. Definition, cohort aggregate, and selected execution are distinct scopes. Select step → synchronize map/table/inspector; select case → highlight actual route and attempts. Creating a candidate carries investigation ID, baseline, selected step, cohort and cited cases. Topology read-only with pan/zoom/fit and table alternative.

### Experiments
Question: **Does this exact revision pass?** Structured ordered-rule editor and per-case route preview; explicit defaults/fallback triggers; paired case evaluation and gate inspection. Before run prioritize configuration; after run prioritize gates, regressions, cost boundary and provenance. Show C1 as blocked despite lower cost; C2 as eligible only if all required evidence exists. Edit after evaluation → new unevaluated revision.

### Releases
Question: **Can this exact revision be safely activated and restored?** Exact source→target diff, computed checks, bound evaluation/contract, local scope, restoration target and reason. Activation changes new local executions, not merely a badge. Separate demo fixture controls from real operator actions. Post-change batch produces new executions and independently checked outcomes; regression creates incident; restoration changes subsequent routing and preserves history.

## P0 acceptance tests

- Aggregate reconciliation from case ledger, including cost numerator/denominator and escalations.
- Reject C1 activation from every entry point; incomplete/missing evidence is inconclusive.
- C2 exact revision becomes eligible under AC-1; changing its rule invalidates eligibility for the new revision.
- Navigation preserves investigation/cohort/step/case and revision/evaluation provenance.
- Selected step/case synchronizes topology, table, inspector and execution waterfall.
- Activation changes routing of newly created executions; historical executions retain original revision.
- Regression verification produces a new independently labeled incorrect case and guardrail violation.
- Restoration returns subsequent executions to S0, preserves incident and prior evidence.
- All screens show fixture provenance and scoped health; no fake observed savings.
- Desktop UI uses available width, legible typography, unclipped six-step topology, keyboard-reachable primary actions.

## Implementation sequencing

1. Define typed objects and deterministic case-ledger fixture with reconciliation tests.
2. Implement one shared local state machine and stable URL/context selection.
3. Build Experiments strategy/routing preview, paired results and gates.
4. Connect Investigate step/cohort/case evidence and candidate creation.
5. Build Releases activation, new execution creation, verification, incident and restoration.
6. Refine Operate and visual system using real shared records.
7. Independent QA: functional invariants, end-to-end operator tasks, visual and accessibility review.

**Approval gate:** This document is a proposed implementation contract, not RE-001 signoff. Review fixture semantics, scope, and the exact operator journey before building the next prototype iteration.
