from copy import deepcopy

from .constants import MISSING_TEXT


def _clean(value):
    return "" if value is None else str(value).strip()


def attach_full_source_evidence(event, report):
    """Attach evidence mechanically from the source report."""
    out = deepcopy(event)

    original_text = _clean(report.get("original_text"))
    translated_text = _clean(report.get("translated_text"))
    source_language = _clean(report.get("source_language")).lower()

    out["original_evidence_span"] = original_text or MISSING_TEXT

    if source_language == "en":
        out["translated_evidence_span"] = original_text or MISSING_TEXT
    else:
        out["translated_evidence_span"] = translated_text or MISSING_TEXT

    out["original_text"] = original_text
    out["translated_text"] = original_text if source_language == "en" else translated_text
    return out


def evidence_matches_source(event, report):
    expected = _clean(report.get("original_text")) or MISSING_TEXT
    return event.get("original_evidence_span") == expected