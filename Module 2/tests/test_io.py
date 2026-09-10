from ai_harm_map.io import (
    load_json_or_jsonl,
    unique_by_report_id,
)


def test_load_jsonl(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"report_id":"R1"}\n{"report_id":"R2"}\n',
        encoding="utf-8",
    )
    rows = load_json_or_jsonl(path)
    assert [row["report_id"] for row in rows] == [
        "R1",
        "R2",
    ]


def test_latest_value_wins_without_reordering():
    rows = [
        {"report_id": "R1", "value": 1},
        {"report_id": "R2", "value": 2},
        {"report_id": "R1", "value": 3},
    ]
    result = unique_by_report_id(rows)
    assert [
        row["report_id"] for row in result
    ] == ["R1", "R2"]
    assert result[0]["value"] == 3
