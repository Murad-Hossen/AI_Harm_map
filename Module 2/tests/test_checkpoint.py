from ai_harm_map.extraction.checkpoint import (
    unseen_reports,
)


def test_existing_reports_are_skipped():
    reports = [
        {"report_id": "R1"},
        {"report_id": "R2"},
        {"report_id": "R3"},
    ]
    assert unseen_reports(
        reports,
        {"R1", "R3"},
    ) == [{"report_id": "R2"}]
