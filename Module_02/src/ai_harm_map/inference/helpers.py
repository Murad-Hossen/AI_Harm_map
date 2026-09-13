import json
import re


def clean(value):
    return "" if value is None else str(value).strip()


def graph_text(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return clean(value)


def year_from(value):
    match = re.search(r"\b(19|20)\d{2}\b", clean(value))
    return int(match.group(0)) if match else None