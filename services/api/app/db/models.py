"""Alembic revisions 0001_evidence_chain and 0002_evaluation are the schema contract.

The application inserts with explicit SQL. It does not call metadata.create_all.
runtime_case_v is an application column allowlist, not a database privilege boundary.
"""

RUNTIME_VIEW_COLUMNS = (
    "case_id",
    "cohort_id",
    "request_text",
    "observation_id",
    "observed_category",
    "confidence_bps",
    "classifier_version",
    "observation_origin",
    "fixture_version",
    "workflow_id",
    "workflow_version",
)

FORBIDDEN_ON_RUNTIME_VIEW = (
    "reference_category",
    "expected_disposition",
    "expected_resolution",
    "verdict",
    "critical_violation",
    "reference_label",
)

APPLICATION_TABLES = (
    "workflow_definition",
    "cohort_manifest",
    "case_input",
    "classification_observation",
    "reference_label",
    "strategy_revision",
    "execution_run",
    "decision_record",
    "attempt_record",
    "cost_entry",
    "outcome_assessment",
    "idempotency_key",
    "evaluation_run",
    "evaluation_case",
    "evaluation_gate",
)
