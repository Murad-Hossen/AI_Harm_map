from ai_harm_map.evidence import (
    attach_full_source_evidence,
    evidence_matches_source,
)


def test_english_evidence_is_exact_source_text():
    report = {
        "source_language": "en",
        "original_text": "Exact source text.",
        "translated_text": "",
    }
    event = attach_full_source_evidence(
        {"report_id": "R1"},
        report,
    )
    assert (
        event["original_evidence_span"]
        == "Exact source text."
    )
    assert (
        event["translated_evidence_span"]
        == "Exact source text."
    )
    assert evidence_matches_source(event, report)


def test_non_english_uses_supplied_translation():
    report = {
        "source_language": "fr",
        "original_text": "Texte original.",
        "translated_text": "Original text.",
    }
    event = attach_full_source_evidence(
        {"report_id": "R2"},
        report,
    )
    assert (
        event["original_evidence_span"]
        == "Texte original."
    )
    assert (
        event["translated_evidence_span"]
        == "Original text."
    )
