from __future__ import annotations

import json
import re
from typing import Any


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def graph_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
        )
    return clean(value)


def year_from(value: Any) -> int | None:
    match = re.search(
        r"\b(19|20)\d{2}\b",
        clean(value),
    )
    return int(match.group(0)) if match else None
