from ai_harm_map.taxonomy.source_copy import (
    supplied_classification,
)


def test_supplied_classification_is_deep_copied():
    report = {
        "classification": {
            "branch": "Data",
            "subcategory_id": "4.2",
            "subcategory": "Surveillance harm",
        }
    }

    value, source = supplied_classification(report)

    assert source == "classification"
    assert value == report["classification"]
    assert value is not report["classification"]
