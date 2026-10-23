import json
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
STRATEGY = json.loads((ROOT / "app/fixtures/service_desk_v1/strategy.json").read_text(encoding="utf-8"))


def test_unrecognized_category_is_stored_and_routes_to_the_safe_default(client, engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO case_input (cohort_id, case_id, request_text) VALUES ('acceptance-sd081', 'SD-UNK', 'Unrecognized classifier output')")
        )
        connection.execute(
            text(
                """
                INSERT INTO classification_observation (
                    observation_id, cohort_id, case_id, classifier_version, observed_category,
                    confidence_bps, evidence_origin
                )
                VALUES (
                    'OBS-UNK', 'acceptance-sd081', 'SD-UNK', 'synthetic-classifier-v1', 'vpn-outage',
                    NULL, 'synthetic_simulated'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO reference_label (
                    cohort_id, case_id, reference_category, expected_disposition, expected_resolution,
                    rubric_version, label_origin
                )
                VALUES (
                    'acceptance-sd081', 'SD-UNK', 'routine', 'automated', 'synthetic-automation',
                    'rubric-v1', 'synthetic_rubric'
                )
                """
            )
        )
    revision = client.post("/api/v1/strategies/revisions", json=STRATEGY)
    assert revision.status_code == 201
    response = client.post(
        "/api/v1/executions",
        json={
            "workflow_id": "service-desk",
            "cohort_id": "acceptance-sd081",
            "case_id": "SD-UNK",
            "revision_sha256": revision.json()["revision_sha256"],
        },
        headers={"Idempotency-Key": "unknown-observation"},
    )
    assert response.status_code == 201, response.text
    evidence = response.json()
    assert evidence["observation"]["observed_category"] == "vpn-outage"
    decision = evidence["decisions"][0]
    assert decision["reason_code"] == "unknown_observation"
    assert decision["selected_method"] == "premium"
    assert decision["matched_rule_id"] is None


def test_empty_category_cannot_be_stored(engine) -> None:
    connection = engine.connect()
    transaction = connection.begin()
    try:
        connection.execute(
            text("INSERT INTO case_input (cohort_id, case_id, request_text) VALUES ('acceptance-sd081', 'SD-EMPTY', 'blank')")
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    """
                    INSERT INTO classification_observation (
                        observation_id, cohort_id, case_id, classifier_version, observed_category,
                        confidence_bps, evidence_origin
                    )
                    VALUES (
                        'OBS-EMPTY', 'acceptance-sd081', 'SD-EMPTY', 'synthetic-classifier-v1', '',
                        NULL, 'synthetic_simulated'
                    )
                    """
                )
            )
    finally:
        transaction.rollback()
        connection.close()
