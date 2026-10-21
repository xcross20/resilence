# RE-001 / S01 — Workflow Overview

**Status:** Prototype v0.1, awaiting operator review.  
**Phase:** Reference Experience, not implementation acceptance.  
**Primary persona:** AI Platform / Enterprise AI Operations Engineer.

## User goal

> Open the application, determine whether the service-desk workflow is operating acceptably, locate the most consequential economic optimization opportunity, and move directly into the supporting evidence.

## Scenario

The operator supports a synthetic internal service-desk AI workflow. A premium model is used in places where less expensive execution may be sufficient. The operator must not assume cheaper is better until quality is verified.

## Information hierarchy

1. Product navigation and active workflow identity.
2. Active execution policy and operational/quality status.
3. Verified outcome rate, observed execution spend, cost per verified outcome, and latency.
4. Actionable opportunity with affected step, rationale, and estimated—not realized—benefit.
5. Step-level cost breakdown and recent evaluations.
6. Direct navigation to workflow canvas and comparison/evidence.

## Primary user actions

- Change the time window (changes the fixture cohort and displayed metrics).
- Inspect the top opportunity and see its explanation.
- Open the workflow execution breakdown (S02).
- Review a recent evaluation (S03).
- Inspect an individual execution record when available.

## Explicit data provenance

All v0.1 numbers and events are **synthetic UX fixtures**. They are not benchmark measurements, real provider bills, or verified savings. The implementation must replace fixtures with reconciled workflow events and independent outcome evaluation.

## Prototype review tasks

1. Without instructions, identify which workflow and policy are active.
2. Determine whether quality guardrails are healthy.
3. Locate the largest current cost contributor.
4. Explain what the proposed optimization would change and what evidence is still missing.
5. Find the next action to investigate the workflow or evaluation.
6. Confirm that an unverified opportunity is not represented as achieved savings.

## Edge states for follow-up revisions

- No recent runs or missing cost events.
- Candidate has not been evaluated.
- Quality regression or inconclusive evaluation.
- Partial workflow outage.
- Operator has view-only permissions.
- Multiple workflows (deferred; initial demo has one).

## Approval criteria

- Workflow status is clear within five seconds.
- Primary CTA follows the operator's next natural action.
- Quality and business outcome metrics are not hidden behind cost metrics.
- Estimated savings and observed results cannot be confused.
- Cost drivers can be traced to workflow steps.
- The overview does not require the operator to understand infrastructure internals.
- Navigation is coherent with S02–S05.
- Prototype supports realistic interactions rather than static screenshots.

**Decision:** Pending explicit user review and approval.
