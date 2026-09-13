import copy
import json
import re
from pathlib import Path

import pandas as pd


def clean(v):
    if v is None:
        return ""
    return str(v).strip()


def normalize(v):
    return " ".join(re.sub(r"[^\w\s]", " ", clean(v).casefold()).split())


def canonical_id(v):
    if v is None:
        return ""
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return "" if pd.isna(v) else f"{v:.10f}".rstrip("0").rstrip(".")
    return clean(v)


def classification_candidates(value):
    if value in (None, "", []):
        return []
    if isinstance(value, dict):
        return [copy.deepcopy(value)]
    if isinstance(value, list):
        return [copy.deepcopy(x) for x in value if x not in (None, "", [])]
    if isinstance(value, str):
        try:
            return classification_candidates(json.loads(value))
        except Exception:
            pass
        parts = [x.strip() for x in value.split(";") if x.strip()]
        return parts if len(parts) > 1 else [value.strip()]
    return [copy.deepcopy(value)]


def candidate_id(c):
    if isinstance(c, dict):
        d = {str(k).strip().casefold(): v for k, v in c.items()}
        for k in ("subcategory_id", "subcategory id", "#", "id", "taxonomy_id", "taxonomy id"):
            if k in d and clean(d[k]):
                return canonical_id(d[k])
    if isinstance(c, (str, int, float)):
        x = canonical_id(c)
        return x if re.fullmatch(r"\d+(?:\.\d+)?", x) else ""
    return ""


def candidate_name(c):
    if isinstance(c, dict):
        d = {str(k).strip().casefold(): v for k, v in c.items()}
        for k in ("subcategory", "category", "harm_category", "harm category"):
            if k in d and clean(d[k]):
                return clean(d[k])
    return clean(c) if isinstance(c, str) else ""


class Taxonomy:
    def __init__(self, path, sheet_name="Taxonomy & Schema"):
        self.path = Path(path)
        self.sheet_name = sheet_name
        self.df = pd.read_excel(self.path, sheet_name=sheet_name).fillna("")
        self.rows = self.df.to_dict("records")
        self.by_id = {}
        self.by_name = {}
        for row in self.rows:
            tid = canonical_id(row.get("#"))
            name = normalize(row.get("Subcategory"))
            if tid:
                self.by_id[tid] = row
            if name:
                self.by_name[name] = row

    def match(self, candidate):
        tid = candidate_id(candidate)
        if tid and tid in self.by_id:
            return self.by_id[tid]
        name = normalize(candidate_name(candidate))
        return self.by_name.get(name)