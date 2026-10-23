# RE-001 decisions

Approved IMP-001 decisions D-01, D-02, D-04, D-06, D-07, and D-08 stay in force. D-05 stays deferred to IMP-003. This file records IMP-002 choices that the approved contracts left open. These choices are conservative defaults. They are not approved numerical thresholds.

## D-09 — Deterministic code replacement

The contracts require one deterministic execution method and do not name its resolution string.

- Method id: `deterministic`.
- Method version: `synthetic-code-v1`.
- A non-privileged observed category produces `automated` and `synthetic-deterministic-template`.
- An observed `privileged` category produces `escalated` and `synthetic-escalation`.
- The method reads the observed category only. It does not read the reference label.
- Its price and latency come from `synthetic-price-v2` (`400` micro-USD, `40` ms). That row is a synthetic price, not a tariff.
- Attempt and cost origin stay `synthetic_simulated`. The method version distinguishes code replacement from `synthetic-method-v1` model methods.
- Economy and premium behavior is unchanged.

## D-10 — Gate policy v0 fails closed

Policy id: `gate-policy-v0-fail-closed`.

Numerical quality, latency, noninferiority, and minimum-evidence thresholds are not approved. This policy therefore never stores `eligible = true`. The database rejects that combination. A client field named `eligible` is a validation error and writes nothing.

| Gate | v0 result |
|---|---|
| Safety | `blocked` / `critical_violation` when the candidate has any critical violation. Otherwise `pass`. |
| Completeness | `inconclusive` on a manifest mismatch, an unmatched pair, or any inconclusive assessment. Otherwise `pass`. |
| Economic | `inconclusive` / `invalid_pricing` when a persisted price version disagrees. `inconclusive` / `zero_verified_success_denominator` when the candidate has no `verified_success`. Otherwise `not_authoritative` / `noninferiority_not_approved`. |
| Quality | `not_authoritative` / `threshold_not_approved`. |
| Latency | `not_authoritative` / `threshold_not_approved`. |

Evaluation status is `completed_blocked` if any gate is blocked, otherwise `inconclusive` if any gate is inconclusive, otherwise `completed_ineligible` while any gate is `not_authoritative`. `completed_eligible` is reserved for a later approved policy.

Accounting version: `accounting-v0-integer-micro-usd`. The primary quotient is integer micro-USD execution cost divided by the `verified_success` count. The remainder is retained. A zero count stores null, not zero. `correct_escalation` is disclosed and is not added to that denominator.

Modeled allocations are stored on `evaluation_run`, not in `cost_entry`: labor `250000`, infrastructure `10000`, and risk `50000` micro-USD, origin `synthetic_modeled`. They are not added into the primary quotient. The numbers are synthetic disclosures, not tariffs.

Cohort purpose stays `acceptance` only. Verification purpose is IMP-003.

## D-11 — Release denies until a gate policy is approved

`APPROVED_ACTIVATION_POLICIES` is empty. `POST /api/v1/releases` cannot commit an activation while it stays empty. A v0 evaluation, a blocked evaluation, an inconclusive evaluation, and a completed-but-ineligible evaluation all append `activation_denied` and leave generation unchanged.

Cohort purpose may be `acceptance` or `verification`. A verification manifest that repeats an acceptance case id is `verification_cohort_overlap`. It does not execute those cases and does not claim an independent holdout. `HOLDOUT_CLAIMS_APPROVED` is false, so a clean synthetic recording also does not claim holdout.

Restoration swaps the active revision with the recorded prior revision and appends an event. It does not rewrite history. `release_event` rejects UPDATE and DELETE. With no recorded prior, restoration is `nothing_to_restore`.

A database owner can plant a pointer in tests. That plant is not an API activation and it does not approve a numerical threshold.

## Stop boundary

Do not invent a passing noninferiority margin or a minimum sample size. Do not treat a v0 evaluation as authorization to activate a strategy. IMP-004 cannot demonstrate a successful activation until a human approves a gate policy and adds it to `APPROVED_ACTIVATION_POLICIES`.

## Recorded stop — 2026-10-23

Independent QA accepted IMP-003 at `f9716cb2f2490213ddd7013feff0e30c1d29a893`. The next milestone's success path needs an approved gate policy. That approval is absent, so IMP-004 and IMP-005 were not started. This stop does not change D-09, D-10, or D-11. It does not accept UO-001.

## D-12 — Synthetic-demo gate calculator

Work order RE-001-COMPLETE-001 authorizes `gate-policy-synthetic-demo-v1` for a synthetic demonstration. This decision records the calculator. It does not add the policy to `APPROVED_ACTIVATION_POLICIES`. v0 behavior is unchanged.

The calculator reads server-stamped `runtime_scope`, `evidence_origin`, `label_origin`, and `live_provider_attempt_count`. It has no `eligible` argument. `runtime_scope=production` blocks safety with `production_runtime`. A live-provider attempt blocks with `live_provider_execution`. Any other non-demo scope or origin blocks with `nonsynthetic_evidence`.

| Gate | Demo rule |
|---|---|
| Safety | Block on a production runtime, a live-provider attempt, nonsynthetic provenance, a critical violation, an incorrect required escalation, or a required escalation marked `verified_success`. |
| Quality | Candidate `verified_success` count must be at least the baseline count. Candidate correct required-escalation count must be at least the baseline count. `correct_escalation` is not part of the `verified_success` numerator. An inconclusive assessment stays inconclusive instead of becoming a regression. |
| Latency | Nearest-rank p95. One-based rank is `ceil(95 * n / 100)`, computed as `(95 * n + 99) // 100`. No interpolation. Candidate p95 must be less than or equal to baseline p95. |
| Completeness | Manifest ids, both sides, assessments, costs, and latencies must match. Fewer than 100 matched cases is `insufficient_sample`. |
| Economics | Invalid pricing, then a missing cost, then a zero verified-success denominator on either side. Otherwise the candidate execution-cost ratio must be strictly lower by cross multiplication: `candidate_cost * baseline_success < baseline_cost * candidate_success`. Integer quotients are not the comparison. Modeled labor, infrastructure, and risk are not in the sum. |

Per-case latency and execution cost are the sums of every persisted attempt, including a failed attempt that preceded fallback. A case with no attempts is missing evidence, not zero.

Eligibility from this function is not an activation. The release path still denies every policy until a later slice enforces the demo workflow boundary and a nonproduction server configuration.
