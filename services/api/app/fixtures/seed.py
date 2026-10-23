import hashlib
import json
from pathlib import Path

from sqlalchemy import text

from app.db.database_url import create_database_engine

FIXTURE_DIR = Path(__file__).resolve().parent / "service_desk_v1"
FIXTURE_VERSION = "service-desk-fixture-v1"
COHORT_ID = "acceptance-sd081"
COHORT_VERSION = "acceptance-sd081-v1"


def manifest_sha256(case_ids: list[str], fixture_version: str) -> str:
    payload = {"case_ids": case_ids, "fixture_version": fixture_version}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _load(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def seed(engine) -> dict[str, int]:
    """Insert the SD-081 fixture. A second call writes nothing."""
    workflow = _load("workflow.json")
    cases = _load("cases.json")
    observations = _load("observations.json")
    labels = _load("reference_labels.json")
    case_ids = [item["case_id"] for item in cases]
    digest = manifest_sha256(case_ids, FIXTURE_VERSION)
    with engine.begin() as connection:
        workflow_inserted = connection.execute(
            text(
                """
                INSERT INTO workflow_definition (workflow_id, version, graph_json)
                VALUES (:workflow_id, :version, CAST(:graph_json AS json))
                ON CONFLICT (workflow_id) DO NOTHING
                """
            ),
            {
                "workflow_id": workflow["workflow_id"],
                "version": workflow["version"],
                "graph_json": json.dumps(workflow["graph"]),
            },
        ).rowcount
        cohort_inserted = connection.execute(
            text(
                """
                INSERT INTO cohort_manifest (
                    cohort_id, workflow_id, version, purpose, fixture_version, manifest_sha256, case_ids
                )
                VALUES (
                    :cohort_id, :workflow_id, :version, 'acceptance', :fixture_version,
                    :manifest_sha256, CAST(:case_ids AS json)
                )
                ON CONFLICT (cohort_id) DO NOTHING
                """
            ),
            {
                "cohort_id": COHORT_ID,
                "workflow_id": workflow["workflow_id"],
                "version": COHORT_VERSION,
                "fixture_version": FIXTURE_VERSION,
                "manifest_sha256": digest,
                "case_ids": json.dumps(case_ids),
            },
        ).rowcount
        cases_inserted = 0
        for case in cases:
            cases_inserted += connection.execute(
                text(
                    """
                    INSERT INTO case_input (cohort_id, case_id, request_text)
                    VALUES (:cohort_id, :case_id, :request_text)
                    ON CONFLICT (cohort_id, case_id) DO NOTHING
                    """
                ),
                case,
            ).rowcount
        observations_inserted = 0
        for observation in observations:
            observations_inserted += connection.execute(
                text(
                    """
                    INSERT INTO classification_observation (
                        observation_id, cohort_id, case_id, classifier_version,
                        observed_category, confidence_bps, evidence_origin
                    )
                    VALUES (
                        :observation_id, :cohort_id, :case_id, :classifier_version,
                        :observed_category, :confidence_bps, :evidence_origin
                    )
                    ON CONFLICT (observation_id) DO NOTHING
                    """
                ),
                observation,
            ).rowcount
        labels_inserted = 0
        for label in labels:
            labels_inserted += connection.execute(
                text(
                    """
                    INSERT INTO reference_label (
                        cohort_id, case_id, reference_category, expected_disposition,
                        expected_resolution, rubric_version, label_origin
                    )
                    VALUES (
                        :cohort_id, :case_id, :reference_category, :expected_disposition,
                        :expected_resolution, :rubric_version, :label_origin
                    )
                    ON CONFLICT (cohort_id, case_id) DO NOTHING
                    """
                ),
                label,
            ).rowcount
    return {
        "workflow": workflow_inserted,
        "cohort": cohort_inserted,
        "cases": cases_inserted,
        "observations": observations_inserted,
        "labels": labels_inserted,
        "manifest_sha256": digest,
    }


def main() -> None:
    engine = create_database_engine()
    print(json.dumps(seed(engine), sort_keys=True))


if __name__ == "__main__":
    main()
