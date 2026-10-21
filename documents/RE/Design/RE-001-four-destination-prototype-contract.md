# RE-001 — Four-Destination Clickable Prototype Contract

**Decision:** Four-destination IA approved by founder, 2026-10-21.
**Design status:** Prototypes under review, not accepted.
**Primary operator:** Application-facing AI platform engineer.
**Environment:** Local demonstration, synthetic IT service-desk workflow.

## Destinations

| Destination | Operator question | Required interactions |
|---|---|---|
| Operate | What needs attention? | Filter attention items; inspect quality, economics and evidence origin; open scoped investigation |
| Investigate | What is happening and why? | Read-only interactive topology, step table, selected-node inspector, trace/case selection, candidate creation |
| Experiments | Is the candidate acceptable? | Configure bounded change, run/replay evaluation fixture, paired case comparison, failure inspection, eligible/blocked/inconclusive gating |
| Releases | Can this exact change be activated, verified, and reversed? | Frozen evidence review, explicit activation, post-change verification, rollback and release history |

## Design slices

- RE-S01A — Operate attention queue and workflow health.
- RE-S01B — Operate scoped issue and metric definitions.
- RE-S02A — Investigate topology and synchronized step inspector.
- RE-S02B — Investigate traces and candidate creation.
- RE-S03A — Experiments candidate configuration and evaluation setup.
- RE-S03B — Experiments paired results and regression inspection.
- RE-S04A — Releases guarded activation.
- RE-S04B — Releases post-change verification and rollback.
- RE-S05 — End-to-end operator acceptance.

## Required demo story

1. Operator identifies a cost concern while confirming quality health.
2. Opens the scoped workflow inspection; identifies a costly model step and views representative executions.
3. Creates naive candidate C1; evaluation fixture shows lower cost but quality regressions, and release is blocked.
4. Creates bounded candidate C2 with low-risk classification and deterministic policy template plus baseline fallback; a separate fixture demonstrates eligibility under the declared synthetic contract.
5. Operator activates C2 in local demonstration state, then runs a post-change verification scenario.
6. Regression scenario fails a guardrail; operator explicitly restores baseline S0 and can inspect immutable historical activity.

## Data honesty

- The initial clickable prototype uses *synthetic UX fixtures* and *simulated state transitions*.
- It does not execute models, independently verify quality, or deploy real software.
- Activation in the prototype updates local UI state only; later implementation acceptance must require actual execution-policy changes.
- Distinguish eligible, blocked, inconclusive and awaiting evidence.
- Never claim that fixture comparisons prove safety or measured savings.

## Screen-level UX principles

- Primary action is state-dependent and tied to a specific operator decision.
- Read-only workflow graph is not an authoring surface.
- The step table and node inspector share selection state.
- Baseline/candidate comparison is case-aligned and quality-first.
- Candidate revisions invalidate prior eligibility in the real implementation.
- Release review refers to a frozen experiment, and rollback preserves history.
- Visual and functional acceptance are separate from approval of the information architecture.

## Review gate

The user must interact with all four destinations, report workflow and visual issues, and explicitly approve or request revision. Architecture and implementation remain pending.
