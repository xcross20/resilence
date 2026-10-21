# RE-001 — Executable synthetic evidence slice

Run from the repository root with Node.js 20+:

```sh
node --test prototype/core/evidence.test.mjs
```

This is a **dependency-free JavaScript reference implementation** of the proposed evidence contract, designed to be imported into the eventual Next.js/TypeScript prototype. It is not yet the full typed UI data model, nor an application build.

- `buildLedger(strategy)` generates deterministic per-case records for S0, C1 and C2.
- `summarizeLedger(ledger)` derives all economic and quality aggregates from rows.
- `evaluate(strategy)` returns the exact fixture-based acceptance decision and evidence.
- `canActivate(revisionId, evaluation)` requires matching revision, contract, dataset, evaluator and all passing gates.

**Fixture limitations:** Per-case execution charges are allocated from declared synthetic strategy totals; they are not derived from token-level rate-card calculations. The latency fixture is illustrative. There are no actual model calls, real-provider savings, stateful releases, or statistically justified claims of generalization. The proposed next step is a rate-card-backed attempt ledger with immutable revisions and release state transitions.

The sample is deliberately separate from the earlier downloadable React ZIP, which has not been committed to this repository.
