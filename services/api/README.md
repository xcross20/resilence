# Execution optimizer API

One persisted synthetic service-desk acceptance case, plus paired evaluation of two immutable strategy revisions. PostgreSQL is the record. The FastAPI process is the only service.

`runtime_case_v` excludes reference labels from the reader the router uses. Routing, simulation, and pricing do not import the assessor. This is an application isolation control. The database owner can still query `reference_label`. It is not a hardened database security boundary.

Results are `synthetic_simulated` or `synthetic_rubric`. They are not provider measurements and they are not a savings claim.

## Database

The database is Railway Postgres in the `resilence` project. Do not start a local Postgres container for this slice.

From a linked checkout, with the Railway CLI authenticated:

```bash
python -m pip install -e ".[dev]"
railway run --service Postgres alembic upgrade head
railway run --service Postgres python -m app.fixtures.seed
railway run --service Postgres python -m app.fixtures.seed
railway run --service Postgres pytest
```

`railway run --service Postgres` injects `RAILWAY_TCP_PROXY_DOMAIN`, `RAILWAY_TCP_PROXY_PORT`, and the database credentials. The test runner uses that public proxy because the private `*.railway.internal` hostname is only reachable inside Railway. The second seed command prints zero inserted rows.

The development password lives in Railway variable storage. It is not committed.

## Acceptance request

Post `app/fixtures/service_desk_v1/strategy.json` to `POST /api/v1/strategies/revisions`.

Then:

```bash
curl -s -X POST localhost:8000/api/v1/executions \
  -H 'content-type: application/json' \
  -H 'Idempotency-Key: sd081-once' \
  -d '{"workflow_id":"service-desk","cohort_id":"acceptance-sd081","case_id":"SD-081","revision_sha256":"<server hash>"}'
```

`SD-081` is observed as `ambiguous` and labeled `privileged`. The router matches the ambiguous observation. It does not receive the reference label.

## Paired evaluation

`POST /api/v1/evaluations` runs the baseline revision and the candidate revision on every case in the cohort manifest. The response binds the manifest hash, fixture version, price book, evaluator, accounting version, and gate policy. A missing case returns 409 `cohort_incomplete` and writes nothing.

`deterministic` is a code replacement. Its method version is `synthetic-code-v1`. It does not read the reference label. Economy and premium remain `synthetic-method-v1`.

Gate policy `gate-policy-v0-fail-closed` stores the execution-cost quotient over `verified_success` only. A zero denominator is null. Modeled labor, infrastructure, and risk are disclosed on the evaluation and are not added into that quotient. Quality and latency stay `not_authoritative` because numerical thresholds are not approved. This policy cannot be stored with `eligible = true`. A request field named `eligible` is rejected.

`gate-policy-synthetic-demo-v1` judges a separate synthetic workflow, `service-desk-synthetic-demo`. It can store `eligible = true` only from persisted paired evidence under the server runtime scope `synthetic-demo`. `EXECUTION_OPTIMIZER_RUNTIME_SCOPE=production` blocks that policy at evaluation time and again at activation. The setting cannot grant production authority. `APPROVED_ACTIVATION_POLICIES` contains only that demo policy. Activation still requires the demo workflow, synthetic provenance, five passing gates, a stored eligible row, and the confirmation `activate_synthetic_revision`. A `service-desk` or v0 evaluation cannot activate. A committed demo response keeps `production_authority` false. The first activation records the evaluation baseline as the prior revision so a confirmed restore can return to it.

Results remain synthetic. They are not a real-world equivalence claim.

## Release

`POST /api/v1/releases` requires `confirmation` `activate_synthetic_revision`, the expected generation, and the exact candidate revision. Gate policy v0 is not approved, so the call appends `activation_denied` and does not move the pointer. A request field named `eligible` is rejected.

`POST /api/v1/releases/{workflow_id}/verifications` runs only a `verification` cohort. Overlap with an acceptance case is disclosed and not executed. A critical violation on a planted active revision is stored as `regressed`. The result does not claim an independent holdout.

`POST /api/v1/releases/{workflow_id}/restore` restores the recorded prior revision. `release_event` is append-only.

## Deferred

The Next.js workbench is not in this service. A successful activation waits on an approved gate policy.
