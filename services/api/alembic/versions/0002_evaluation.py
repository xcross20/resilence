"""IMP-002 paired evaluation records.

Revision ID: 0002_evaluation
Revises: 0001_evidence_chain
Create Date: 2026-10-23

gate-policy-v0-fail-closed cannot be stored as eligible.
Modeled labor, infrastructure, and risk stay off cost_entry.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_evaluation"
down_revision: Union[str, None] = "0001_evidence_chain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RATIO_CHECK = """
(
    {prefix}_verified_success_count = 0
    AND {prefix}_quotient_micro_usd IS NULL
    AND {prefix}_remainder_micro_usd IS NULL
)
OR (
    {prefix}_verified_success_count > 0
    AND {prefix}_quotient_micro_usd IS NOT NULL
    AND {prefix}_remainder_micro_usd IS NOT NULL
    AND {prefix}_remainder_micro_usd >= 0
    AND {prefix}_remainder_micro_usd < {prefix}_verified_success_count
    AND {prefix}_execution_cost_micro_usd
        = {prefix}_quotient_micro_usd * {prefix}_verified_success_count
        + {prefix}_remainder_micro_usd
)
"""


def upgrade() -> None:
    op.drop_constraint("ck_decision_method", "decision_record", type_="check")
    op.create_check_constraint(
        "ck_decision_method",
        "decision_record",
        "selected_method IN ('economy', 'premium', 'deterministic')",
    )
    op.drop_constraint("ck_attempt_method", "attempt_record", type_="check")
    op.create_check_constraint(
        "ck_attempt_method",
        "attempt_record",
        "method_id IN ('economy', 'premium', 'deterministic')",
    )
    op.create_table(
        "evaluation_run",
        sa.Column("evaluation_id", sa.String(64), primary_key=True),
        sa.Column("workflow_id", sa.String(64), sa.ForeignKey("workflow_definition.workflow_id"), nullable=False),
        sa.Column("cohort_id", sa.String(64), sa.ForeignKey("cohort_manifest.cohort_id"), nullable=False),
        sa.Column("manifest_sha256", sa.String(71), nullable=False),
        sa.Column("fixture_version", sa.String(64), nullable=False),
        sa.Column("price_book_version", sa.String(64), nullable=False),
        sa.Column("evaluator_version", sa.String(64), nullable=False),
        sa.Column("accounting_version", sa.String(64), nullable=False),
        sa.Column("gate_policy_version", sa.String(64), nullable=False),
        sa.Column("baseline_revision", sa.String(71), sa.ForeignKey("strategy_revision.revision_sha256"), nullable=False),
        sa.Column("candidate_revision", sa.String(71), sa.ForeignKey("strategy_revision.revision_sha256"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modeled_labor_micro_usd", sa.Integer(), nullable=False),
        sa.Column("modeled_infrastructure_micro_usd", sa.Integer(), nullable=False),
        sa.Column("modeled_risk_micro_usd", sa.Integer(), nullable=False),
        sa.Column("modeled_origin", sa.String(32), nullable=False),
        sa.Column("baseline_verified_success_count", sa.Integer(), nullable=False),
        sa.Column("candidate_verified_success_count", sa.Integer(), nullable=False),
        sa.Column("baseline_correct_escalation_count", sa.Integer(), nullable=False),
        sa.Column("candidate_correct_escalation_count", sa.Integer(), nullable=False),
        sa.Column("baseline_execution_cost_micro_usd", sa.Integer(), nullable=False),
        sa.Column("candidate_execution_cost_micro_usd", sa.Integer(), nullable=False),
        sa.Column("baseline_quotient_micro_usd", sa.Integer(), nullable=True),
        sa.Column("candidate_quotient_micro_usd", sa.Integer(), nullable=True),
        sa.Column("baseline_remainder_micro_usd", sa.Integer(), nullable=True),
        sa.Column("candidate_remainder_micro_usd", sa.Integer(), nullable=True),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('completed_blocked', 'inconclusive', 'completed_ineligible', 'completed_eligible')",
            name="ck_evaluation_status",
        ),
        sa.CheckConstraint(
            "gate_policy_version <> 'gate-policy-v0-fail-closed' OR eligible = false",
            name="ck_fail_closed_not_eligible",
        ),
        sa.CheckConstraint(
            "eligible = false OR status = 'completed_eligible'",
            name="ck_eligible_status",
        ),
        sa.CheckConstraint("modeled_origin = 'synthetic_modeled'", name="ck_modeled_origin"),
        sa.CheckConstraint("modeled_labor_micro_usd >= 0", name="ck_modeled_labor"),
        sa.CheckConstraint("modeled_infrastructure_micro_usd >= 0", name="ck_modeled_infrastructure"),
        sa.CheckConstraint("modeled_risk_micro_usd >= 0", name="ck_modeled_risk"),
        sa.CheckConstraint("case_count > 0", name="ck_evaluation_case_count"),
        sa.CheckConstraint(_RATIO_CHECK.format(prefix="baseline"), name="ck_baseline_cost_ratio"),
        sa.CheckConstraint(_RATIO_CHECK.format(prefix="candidate"), name="ck_candidate_cost_ratio"),
    )
    op.create_table(
        "evaluation_case",
        sa.Column("evaluation_id", sa.String(64), sa.ForeignKey("evaluation_run.evaluation_id"), nullable=False),
        sa.Column("case_ordinal", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("baseline_run_id", sa.String(64), sa.ForeignKey("execution_run.run_id"), nullable=False),
        sa.Column("candidate_run_id", sa.String(64), sa.ForeignKey("execution_run.run_id"), nullable=False),
        sa.Column("baseline_assessment_id", sa.String(64), sa.ForeignKey("outcome_assessment.assessment_id"), nullable=False),
        sa.Column("candidate_assessment_id", sa.String(64), sa.ForeignKey("outcome_assessment.assessment_id"), nullable=False),
        sa.Column("route_changed", sa.Boolean(), nullable=False),
        sa.Column("verdict_changed", sa.Boolean(), nullable=False),
        sa.Column("execution_cost_delta_micro_usd", sa.Integer(), nullable=False),
        sa.Column("first_divergent_decision_id", sa.String(64), sa.ForeignKey("decision_record.decision_id"), nullable=True),
        sa.PrimaryKeyConstraint("evaluation_id", "case_id", name="pk_evaluation_case"),
        sa.UniqueConstraint("evaluation_id", "case_ordinal", name="uq_evaluation_case_ordinal"),
        sa.CheckConstraint("case_ordinal > 0", name="ck_case_ordinal"),
    )
    op.create_index("ix_evaluation_case", "evaluation_case", ["evaluation_id", "case_id"])
    op.create_table(
        "evaluation_gate",
        sa.Column("evaluation_id", sa.String(64), sa.ForeignKey("evaluation_run.evaluation_id"), nullable=False),
        sa.Column("gate_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("evaluation_id", "gate_id", name="pk_evaluation_gate"),
        sa.CheckConstraint(
            "gate_id IN ('safety', 'quality', 'latency', 'completeness', 'economic')",
            name="ck_gate_id",
        ),
        sa.CheckConstraint(
            "status IN ('pass', 'blocked', 'inconclusive', 'not_authoritative')",
            name="ck_gate_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("evaluation_gate")
    op.drop_index("ix_evaluation_case", table_name="evaluation_case")
    op.drop_table("evaluation_case")
    op.drop_table("evaluation_run")
    op.drop_constraint("ck_attempt_method", "attempt_record", type_="check")
    op.create_check_constraint(
        "ck_attempt_method",
        "attempt_record",
        "method_id IN ('economy', 'premium')",
    )
    op.drop_constraint("ck_decision_method", "decision_record", type_="check")
    op.create_check_constraint(
        "ck_decision_method",
        "decision_record",
        "selected_method IN ('economy', 'premium')",
    )
