from __future__ import annotations

import copy
from typing import Any


def _missing(value: Any) -> bool:
    return value is None or value == "" or value == []


def supplied_classification(report: dict[str, Any]) -> tuple[Any, str | None]:
    """Copy upstream classification exactly; no model taxonomy prediction."""
    raw = report.get("classifications")
    source_field = "classifications"

    if _missing(raw):
        raw = report.get("classification")
        source_field = "classification"

    if _missing(raw):
        return [], None

    return copy.deepcopy(raw), source_field