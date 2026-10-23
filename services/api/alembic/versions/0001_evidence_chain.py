"""IMP-001 evidence chain.

Revision ID: 0001_evidence_chain
Revises:
Create Date: 2026-10-22

runtime_case_v hides reference labels from the application reader.
The owning role can still select reference_label. That view is not a
database security boundary.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_evidence_chain"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_definition",
        sa.Column("workflow_id", sa.String(64), primary_key=True),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("graph_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "cohort_manifest",
        sa.Column("cohort_id", sa.String(64), primary_key=True),
        sa.Column("workflow_id", sa.String(64), sa.ForeignKey("workflow_definition.workflow_id"), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("fixture_version", sa.String(64), nullable=False),
        sa.Column("manifest_sha256", sa.String(71), nullable=False),
        sa.Column("case_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("purpose = 'acceptance'", name="ck_cohort_purpose_acceptance"),
    )
    op.create_table(
        "case_input",
        sa.Column("cohort_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cohort_id"], ["cohort_manifest.cohort_id"]),
        sa.PrimaryKeyConstraint("cohort_id", "case_id"),
    )
    op.create_table(
        "classification_observation",
        sa.Column("observation_id", sa.String(64), primary_key=True),
        sa.Column("cohort_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("classifier_version", sa.String(64), nullable=False),
        sa.Column("observed_category", sa.Text(), nullable=False),
        sa.Column("confidence_bps", sa.Integer(), nullable=True),
        sa.Column("evidence_origin", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cohort_id", "case_id"], ["case_input.cohort_id", "case_input.case_id"]),
        sa.UniqueConstraint("cohort_id", "case_id", name="uq_observation_case"),
        sa.CheckConstraint("char_length(observed_category) > 0", name="ck_observed_category_nonempty"),
        sa.CheckConstraint("confidence_bps IS NULL OR (confidence_bps >= 0 AND confidence_bps <= 10000)", name="ck_confidence_bps"),
        sa.CheckConstraint("evidence_origin = 'synthetic_simulated'", name="ck_observation_origin"),
    )
    op.create_table(
        "reference_label",
        sa.Column("cohort_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("reference_category", sa.String(64), nullable=False),
        sa.Column("expected_disposition", sa.String(32), nullable=False),
        sa.Column("expected_resolution", sa.Text(), nullable=True),
        sa.Column("rubric_version", sa.String(64), nullable=False),
        sa.Column("label_origin", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["cohort_id", "case_id"], ["case_input.cohort_id", "case_input.case_id"]),
        sa.PrimaryKeyConstraint("cohort_id", "case_id"),
        sa.CheckConstraint("expected_disposition IN ('automated', 'escalated')", name="ck_expected_disposition"),
        sa.CheckConstraint("label_origin = 'synthetic_rubric'", name="ck_label_origin"),
    )
    op.create_table(
        "strategy_revision",
        sa.Column("revision_sha256", sa.String(71), primary_key=True),
        sa.Column("workflow_id", sa.String(64), sa.ForeignKey("workflow_definition.workflow_id"), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workflow_id", "revision_sha256", name="uq_workflow_revision"),
    )
    op.create_table(
        "execution_run",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("cohort_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("strategy_revision", sa.String(71), sa.ForeignKey("strategy_revision.revision_sha256"), nullable=False),
        sa.Column("workflow_version", sa.String(64), nullable=False),
        sa.Column("fixture_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cohort_id", "case_id"], ["case_input.cohort_id", "case_input.case_id"]),
        sa.CheckConstraint("status = 'completed'", name="ck_run_status"),
    )
    op.create_table(
        "decision_record",
        sa.Column("decision_id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("execution_run.run_id"), nullable=False),
        sa.Column("step_id", sa.String(64), nullable=False),
        sa.Column("observation_id", sa.String(64), sa.ForeignKey("classification_observation.observation_id"), nullable=False),
        sa.Column("matched_rule_id", sa.String(64), nullable=True),
        sa.Column("selected_method", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("selected_method IN ('economy', 'premium')", name="ck_decision_method"),
        sa.CheckConstraint(
            "reason_code IN ('matched_rule', 'default', 'unknown_observation', 'fallback')",
            name="ck_decision_reason",
        ),
    )
    op.create_index("ix_decision_run_step", "decision_record", ["run_id", "step_id"])
    op.create_table(
        "attempt_record",
        sa.Column("attempt_id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("execution_run.run_id"), nullable=False),
        sa.Column("decision_id", sa.String(64), sa.ForeignKey("decision_record.decision_id"), nullable=False),
        sa.Column("attempt_ordinal", sa.Integer(), nullable=False),
        sa.Column("method_id", sa.String(32), nullable=False),
        sa.Column("method_version", sa.String(64), nullable=False),
        sa.Column("input_digest", sa.String(71), nullable=False),
        sa.Column("output_digest", sa.String(71), nullable=False),
        sa.Column("produced_disposition", sa.String(32), nullable=False),
        sa.Column("produced_resolution", sa.Text(), nullable=False),
        sa.Column("simulated_latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("evidence_origin", sa.String(32), nullable=False),
        sa.CheckConstraint("method_id IN ('economy', 'premium')", name="ck_attempt_method"),
        sa.CheckConstraint("status IN ('succeeded', 'failed')", name="ck_attempt_status"),
        sa.CheckConstraint("produced_disposition IN ('automated', 'escalated', 'none')", name="ck_produced_disposition"),
        sa.CheckConstraint("simulated_latency_ms >= 0", name="ck_latency_nonnegative"),
        sa.CheckConstraint("evidence_origin = 'synthetic_simulated'", name="ck_attempt_origin"),
        sa.UniqueConstraint("run_id", "attempt_ordinal", name="uq_attempt_ordinal"),
    )
    op.create_table(
        "cost_entry",
        sa.Column("cost_entry_id", sa.String(64), primary_key=True),
        sa.Column("attempt_id", sa.String(64), sa.ForeignKey("attempt_record.attempt_id"), nullable=False),
        sa.Column("amount_micro_usd", sa.Integer(), nullable=False),
        sa.Column("cost_type", sa.String(32), nullable=False),
        sa.Column("price_book_version", sa.String(64), nullable=False),
        sa.Column("evidence_origin", sa.String(32), nullable=False),
        sa.CheckConstraint("amount_micro_usd >= 0", name="ck_cost_nonnegative"),
        sa.CheckConstraint("cost_type = 'execution'", name="ck_cost_type_execution"),
        sa.CheckConstraint("evidence_origin = 'synthetic_simulated'", name="ck_cost_origin"),
    )
    op.create_table(
        "outcome_assessment",
        sa.Column("assessment_id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("execution_run.run_id"), nullable=False),
        sa.Column("evaluator_version", sa.String(64), nullable=False),
        sa.Column("rubric_version", sa.String(64), nullable=False),
        sa.Column("disposition_correct", sa.Boolean(), nullable=True),
        sa.Column("resolution_correct", sa.Boolean(), nullable=True),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("correct_escalation", sa.Boolean(), nullable=False),
        sa.Column("critical_violation", sa.Boolean(), nullable=False),
        sa.Column("supporting_evidence_ids", sa.JSON(), nullable=False),
        sa.UniqueConstraint("run_id", name="uq_assessment_run"),
        sa.CheckConstraint(
            "verdict IN ('verified_success', 'correct_escalation', 'incorrect_completion', 'inconclusive')",
            name="ck_verdict",
        ),
    )
    op.create_table(
        "idempotency_key",
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("body_sha256", sa.String(71), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("actor", "operation", "idempotency_key"),
    )
    # Column allowlist for the router. Owners of reference_label can still read it.
    op.execute(
        """
        CREATE VIEW runtime_case_v AS
        SELECT
            c.case_id,
            c.cohort_id,
            c.request_text,
            o.observation_id,
            o.observed_category,
            o.confidence_bps,
            o.classifier_version,
            o.evidence_origin AS observation_origin,
            m.fixture_version,
            m.workflow_id,
            w.version AS workflow_version
        FROM case_input AS c
        JOIN classification_observation AS o
          ON o.cohort_id = c.cohort_id AND o.case_id = c.case_id
        JOIN cohort_manifest AS m ON m.cohort_id = c.cohort_id
        JOIN workflow_definition AS w ON w.workflow_id = m.workflow_id
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS runtime_case_v")
    op.drop_table("idempotency_key")
    op.drop_table("outcome_assessment")
    op.drop_table("cost_entry")
    op.drop_table("attempt_record")
    op.drop_index("ix_decision_run_step", table_name="decision_record")
    op.drop_table("decision_record")
    op.drop_table("execution_run")
    op.drop_table("strategy_revision")
    op.drop_table("reference_label")
    op.drop_table("classification_observation")
    op.drop_table("case_input")
    op.drop_table("cohort_manifest")
    op.drop_table("workflow_definition")
