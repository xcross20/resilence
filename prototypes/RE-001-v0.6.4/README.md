# RE-001 v0.6.4 — Approved reference experience

Status: **APPROVED by product owner (2026-10-22)**

## Artifact
Approved local package: `execution-optimizer-re001-v064-preview.zip` (67 KB, available in the conversation working environment). **The ZIP itself has not yet been committed to this branch.** Place it at `prototypes/RE-001-v0.6.4/execution-optimizer-re001-v064-preview.zip` before treating the archive as complete.

## Product mission
Optimize fully loaded cost per verified successful AI-assisted business outcome without compromising correctness, critical safety constraints, or operational reliability.

## Approved reference behavior
- Graph-centered inspection of observed synthetic classifications and decisions.
- Bounded policy revision and projected routing separated from evaluated outcomes.
- Matched baseline/candidate evaluation on the same synthetic cohort.
- Per-case evidence, routing differences, quality gates, and comparable cost accounting.
- Release of the **exact** eligible revision; separate post-activation verification and restoration.
- No production integration, live model traces, or real provider charges claimed.

## Implementation handoff
Use this prototype as a **behavioral reference**, not as an approved backend architecture. Begin ARCH-001 with domain/evidence contracts, routing policy semantics, matched evaluation, cost boundary, release state machine, and APIs. Then implement one end-to-end synthetic service-desk vertical slice.

## Guardrails
No generalized workflow builder, autonomous optimization, multitenancy, or live provider integrations in first slice. Any strategy edit invalidates prior evaluation. Evaluation reference labels must not be accessible to runtime routing. Failed gates prohibit activation.

## Acceptance before merging implementation
Reproducible build; tests for routing leakage, revision invalidation, safety gates, economic denominator, activation and restoration; browser smoke tests for the approved journeys; clear evidence provenance.
