# RE-001 — Reference Experience Design Slices

**Status:** In progress; no screen approved yet.
**Parent contract:** [UO-001](../../UO-001-user-outcome.md)

Each screen is an independently reviewable design slice: operator goal → reference workflow → interactive prototype → task walkthrough → edge states → visual and functional review → explicit approval. Approval of one slice does not approve the others.

| Slice | Screen | Intended operator outcome | Status |
|---|---|---|---|
| S01 | Workflow Overview | Identify workflow health, major cost drivers, and next action | Prototype v0.1; review |
| S02 | Execution Breakdown | Explore execution steps on a Miro-like connected canvas and inspect alternatives | Pending |
| S03 | Strategy Comparison | Compare policies on matched cases and review failures | Pending |
| S04 | Activation Review | Make an authorized, evidence-backed activation decision | Pending |
| S05 | Monitoring & Rollback | Monitor active policy and safely restore a prior version | Pending |

## Shared design principles
- Operator-first, no decorative KPIs or invented claims of savings.
- Every primary screen has one concrete user goal and an obvious next action.
- Synthetic fixture values are explicitly labeled and must not be mistaken for measured live-provider outcomes.
- Support empty, loading, degraded, inconclusive, and error states as relevant.
- Keep business outcome, policy status, and quality guardrails prominent.
- Use a coherent professional design language and progressive disclosure.
- Do not begin architecture or implementation until the relevant experience and contracts are approved.

## Review protocol
1. Walk through the operator scenario without explanation.
2. Record confusion, missing data, false affordances, and misleading labels.
3. Revise prototype and re-test.
4. Explicitly approve or reject the slice.
5. Lock approved screen contract, then proceed.
