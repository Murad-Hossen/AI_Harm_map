import copy


def _missing(value):
    return value is None or value == "" or value == []


def supplied_classification(report):
    """Copy upstream classification exactly; no model taxonomy prediction."""
    raw = report.get("classifications")
    source_field = "classifications"

    if _missing(raw):
        raw = report.get("classification")
        source_field = "classification"

    if _missing(raw):
        return [], None

    return copy.deepcopy(raw), source_field