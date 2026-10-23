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
