"""IMP-003 release pointer and append-only audit.

Revision ID: 0003_release
Revises: 0002_evaluation
Create Date: 2026-10-23

Denied attempts are recorded. UPDATE and DELETE of release_event are rejected.
Cohort purpose may be acceptance or verification.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_release"
down_revision: Union[str, None] = "0002_evaluation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_cohort_purpose_acceptance", "cohort_manifest", type_="check")
    op.create_check_constraint(
        "ck_cohort_purpose",
        "cohort_manifest",
        "purpose IN ('acceptance', 'verification')",
    )
    op.create_table(
        "active_policy_pointer",
        sa.Column("workflow_id", sa.String(64), sa.ForeignKey("workflow_definition.workflow_id"), primary_key=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("revision_sha256", sa.String(71), sa.ForeignKey("strategy_revision.revision_sha256"), nullable=True),
        sa.Column("prior_revision_sha256", sa.String(71), sa.ForeignKey("strategy_revision.revision_sha256"), nullable=True),
        sa.Column("evaluation_id", sa.String(64), sa.ForeignKey("evaluation_run.evaluation_id"), nullable=True),
        sa.CheckConstraint("generation >= 0", name="ck_pointer_generation_nonnegative"),
        sa.CheckConstraint(
            "(generation = 0 AND revision_sha256 IS NULL) OR (generation > 0 AND revision_sha256 IS NOT NULL)",
            name="ck_pointer_generation",
        ),
    )
    op.create_table(
        "verification_run",
        sa.Column("verification_id", sa.String(64), primary_key=True),
        sa.Column("workflow_id", sa.String(64), sa.ForeignKey("workflow_definition.workflow_id"), nullable=False),
        sa.Column("cohort_id", sa.String(64), sa.ForeignKey("cohort_manifest.cohort_id"), nullable=False),
        sa.Column("manifest_sha256", sa.String(71), nullable=False),
        sa.Column("activated_revision", sa.String(71), nullable=True),
        sa.Column("overlap_case_ids", sa.JSON(), nullable=False),
        sa.Column("claims_independent_holdout", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('denied_overlap', 'denied_no_active_policy', 'denied_wrong_revision', 'denied_cohort_purpose', 'denied_incomplete', 'denied_version_mismatch', 'denied_stale_generation', 'regressed', 'recorded', 'inconclusive')",
            name="ck_verification_status",
        ),
        sa.CheckConstraint(
            "claims_independent_holdout = false OR status = 'recorded'",
            name="ck_holdout_claim",
        ),
    )
    op.create_table(
        "verification_case",
        sa.Column("verification_id", sa.String(64), sa.ForeignKey("verification_run.verification_id"), nullable=False),
        sa.Column("case_ordinal", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("execution_run.run_id"), nullable=False),
        sa.Column("assessment_id", sa.String(64), sa.ForeignKey("outcome_assessment.assessment_id"), nullable=False),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("critical_violation", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("verification_id", "case_id", name="pk_verification_case"),
        sa.UniqueConstraint("verification_id", "case_ordinal", name="uq_verification_case_ordinal"),
    )
    op.create_table(
        "release_event",
        sa.Column("event_seq", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("workflow_id", sa.String(64), sa.ForeignKey("workflow_definition.workflow_id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("prior_revision", sa.String(71), nullable=True),
        sa.Column("target_revision", sa.String(71), nullable=True),
        sa.Column("prior_generation", sa.Integer(), nullable=False),
        sa.Column("resulting_generation", sa.Integer(), nullable=False),
        sa.Column("evaluation_id", sa.String(64), nullable=True),
        sa.Column("verification_id", sa.String(64), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("event_id", name="uq_release_event_id"),
        sa.CheckConstraint(
            "event_type IN ('activation_denied', 'activation_committed', 'verification_denied', 'verification_recorded', 'restoration_denied', 'restoration_committed')",
            name="ck_release_event_type",
        ),
    )
    op.create_index("ix_release_event_workflow", "release_event", ["workflow_id", "event_seq"])
    op.execute(
        """
        CREATE FUNCTION reject_release_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'release_event is append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER release_event_append_only
        BEFORE UPDATE OR DELETE ON release_event
        FOR EACH ROW
        EXECUTE FUNCTION reject_release_event_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS release_event_append_only ON release_event")
    op.execute("DROP FUNCTION IF EXISTS reject_release_event_mutation()")
    op.drop_index("ix_release_event_workflow", table_name="release_event")
    op.drop_table("release_event")
    op.drop_table("verification_case")
    op.drop_table("verification_run")
    op.drop_table("active_policy_pointer")
    op.drop_constraint("ck_cohort_purpose", "cohort_manifest", type_="check")
    op.create_check_constraint(
        "ck_cohort_purpose_acceptance",
        "cohort_manifest",
        "purpose = 'acceptance'",
    )
