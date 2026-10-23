# UO-001 acceptance matrix

Status date: 2026-10-23. Independently accepted product remains `f9716cb2f2490213ddd7013feff0e30c1d29a893`. Later synthetic-demo commits are builder evidence, not acceptance.

UO-001 is not accepted. A passing pytest suite does not change that contract status. Synthetic results stay labeled synthetic. The project manifest maps UO-AC-01 through UO-AC-10 to commands that the outcome-verification child cannot run, because that child does not receive a database URL.

| ID | Acceptance condition | Product evidence on this branch | Outcome Verification | Acceptance |
| --- | --- | --- | --- | --- |
| UO-AC-01 | Inspect step-level execution strategy and attributable cost. | The workbench reads stored revisions, workflow steps, and evaluation cases. | INCONCLUSIVE | Not accepted |
| UO-AC-02 | At least one candidate changes model selection based on task requirements. | Routing selects economy, premium, or deterministic from the observed category. Results are `synthetic_simulated`. | INCONCLUSIVE | Not accepted |
| UO-AC-03 | At least one candidate uses deterministic execution instead of an unnecessary LLM call. | Method `deterministic` / `synthetic-code-v1` is implemented and tested. It does not call a provider. | INCONCLUSIVE | Not accepted |
| UO-AC-04 | Baseline and candidate are compared on equivalent, versioned evaluation cases. | Paired evaluation binds one frozen manifest and two revision hashes. Unmatched cases write nothing. | INCONCLUSIVE | Not accepted |
| UO-AC-05 | Cost per verified successful outcome comes from execution records. | Integer micro-USD quotient uses persisted `verified_success` counts. A zero count stores null. Modeled labor, infrastructure, and risk stay outside the quotient. | INCONCLUSIVE | Not accepted |
| UO-AC-06 | Individual quality failures and policy violations are inspectable. | Evaluation case reads show verdict, reason, and critical-violation flag. They do not include `reference_category`. | INCONCLUSIVE | Not accepted |
| UO-AC-07 | A failing or inconclusive candidate cannot be activated as approved. | Unsafe, v0, forged, stale, and production-scoped activation requests leave the pointer unchanged. | INCONCLUSIVE | Not accepted |
| UO-AC-08 | Eligible activation and restoration work in the demo and leave an audit trail. | A disposable test activates the demo workflow, records verification without a holdout claim, and restores the compared baseline. | INCONCLUSIVE | Not accepted |
| UO-AC-09 | The basic demonstration runs without enterprise credentials or services. | The new demo tests use a local disposable Postgres and synthetic prices. No live-provider call is made. | INCONCLUSIVE | Not accepted |
| UO-AC-10 | Simulated, replayed, estimated, and live-measured evidence are distinguished. | Origins are `synthetic_simulated`, `synthetic_rubric`, or `synthetic_modeled`. No live-measured provider evidence exists. | INCONCLUSIVE | Not accepted |
