from sqlalchemy import text

from app.fixtures.seed import manifest_sha256, seed


def test_seed_is_repeatable(engine) -> None:
    first_cases = None
    with engine.connect() as connection:
        first_cases = connection.execute(text("SELECT count(*) FROM case_input WHERE case_id = 'SD-081'")).scalar_one()
        manifest = connection.execute(text("SELECT manifest_sha256, fixture_version FROM cohort_manifest")).one()
    assert first_cases == 1
    assert manifest.fixture_version == "service-desk-fixture-v1"
    assert manifest.manifest_sha256 == manifest_sha256(["SD-081"], "service-desk-fixture-v1")
    second = seed(engine)
    assert second["workflow"] == 0
    assert second["cohort"] == 0
    assert second["cases"] == 0
    assert second["observations"] == 0
    assert second["labels"] == 0
    assert second["manifest_sha256"] == manifest.manifest_sha256
