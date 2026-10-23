import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.database_url import create_database_engine, railway_database_url
from app.fixtures.seed import seed
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def reset_runtime_rows(engine) -> None:
    statements = [
        "TRUNCATE TABLE release_event RESTART IDENTITY",
        "DELETE FROM verification_case",
        "DELETE FROM verification_run",
        "UPDATE active_policy_pointer SET generation = 0, revision_sha256 = NULL, prior_revision_sha256 = NULL, evaluation_id = NULL",
        "DELETE FROM evaluation_gate",
        "DELETE FROM evaluation_case",
        "DELETE FROM evaluation_run",
        "DELETE FROM idempotency_key",
        "DELETE FROM outcome_assessment",
        "DELETE FROM cost_entry",
        "DELETE FROM attempt_record",
        "DELETE FROM decision_record",
        "DELETE FROM execution_run",
        "DELETE FROM strategy_revision",
        "DELETE FROM reference_label WHERE cohort_id <> 'acceptance-sd081' OR case_id <> 'SD-081'",
        "DELETE FROM classification_observation WHERE cohort_id <> 'acceptance-sd081' OR case_id <> 'SD-081'",
        "DELETE FROM case_input WHERE cohort_id <> 'acceptance-sd081' OR case_id <> 'SD-081'",
        "DELETE FROM cohort_manifest WHERE cohort_id <> 'acceptance-sd081'",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


@pytest.fixture(scope="session")
def engine():
    try:
        url = railway_database_url()
    except RuntimeError as exc:
        pytest.fail(str(exc))
    os.environ["DATABASE_URL"] = url
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    database = create_database_engine(url)
    seed(database)
    yield database
    database.dispose()


@pytest.fixture
def client(engine):
    reset_runtime_rows(engine)
    application = create_app(engine)
    with TestClient(application) as test_client:
        yield test_client
    reset_runtime_rows(engine)
