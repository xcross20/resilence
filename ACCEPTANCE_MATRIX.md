# UO-001 acceptance matrix

Status date: 2026-10-23. Product commit under review: `f9716cb2f2490213ddd7013feff0e30c1d29a893`.

UO-001 is not accepted. Outcome Verification on that commit is `INCONCLUSIVE` (script exit 3) because UO-AC-01 through UO-AC-10 have no approved executable checks. A passing pytest suite does not change that contract status. Synthetic results stay labeled synthetic.

| ID | Acceptance condition | Product evidence on this branch | Outcome Verification | Acceptance |
| --- | --- | --- | --- | --- |
| UO-AC-01 | Inspect step-level execution strategy and attributable cost. | API persists one synthetic case, attempts, and cost entries. No workbench reads those records. | INCONCLUSIVE | Not accepted |
| UO-AC-02 | At least one candidate changes model selection based on task requirements. | Routing selects economy, premium, or deterministic from the observed category. Results are `synthetic_simulated`. | INCONCLUSIVE | Not accepted |
| UO-AC-03 | At least one candidate uses deterministic execution instead of an unnecessary LLM call. | Method `deterministic` / `synthetic-code-v1` is implemented and tested. It does not call a provider. | INCONCLUSIVE | Not accepted |
| UO-AC-04 | Baseline and candidate are compared on equivalent, versioned evaluation cases. | Paired evaluation binds one frozen manifest and two revision hashes. Unmatched cases write nothing. | INCONCLUSIVE | Not accepted |
| UO-AC-05 | Cost per verified successful outcome comes from execution records. | Integer micro-USD quotient uses persisted `verified_success` counts. A zero count stores null. Modeled labor, infrastructure, and risk stay outside the quotient. | INCONCLUSIVE | Not accepted |
| UO-AC-06 | Individual quality failures and policy violations are inspectable. | Case assessments and gate rows are persisted. The operator workbench is not connected. | INCONCLUSIVE | Not accepted |
| UO-AC-07 | A failing or inconclusive candidate cannot be activated as approved. | IMP-003 denies blocked, inconclusive, and v0 ineligible evaluations. Generation stays 0. `eligible=true` is a 422 and writes nothing. | INCONCLUSIVE | Not accepted |
| UO-AC-08 | Eligible activation and restoration work in the demo and leave an audit trail. | Restoration of a planted prior revision is audited. Eligible activation cannot run: `APPROVED_ACTIVATION_POLICIES` is empty. | INCONCLUSIVE | Not accepted |
| UO-AC-09 | The basic demonstration runs without enterprise credentials or services. | The API demo uses synthetic fixtures and Railway Postgres. The four-destination workbench is not wired. No live-provider credentials are used. | INCONCLUSIVE | Not accepted |
| UO-AC-10 | Simulated, replayed, estimated, and live-measured evidence are distinguished. | Origins are `synthetic_simulated`, `synthetic_rubric`, or `synthetic_modeled`. No live-measured provider evidence exists. | INCONCLUSIVE | Not accepted |
