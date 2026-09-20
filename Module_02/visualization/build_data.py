#!/usr/bin/env python3
"""Build browser-safe map data from the frozen 3,041-report release corpus."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
RELEASES = ROOT.parent / "data" / "releases"
TARGET = ROOT / "data.js"

ALIASES = {
    "United States": "United States of America",
    "Palestinian Territories": "Palestine",
    "Hong Kong": "Hong Kong S.A.R.",
    "Serbia": "Republic of Serbia",
}
EU_PLACEMENTS = ["Austria", "Belgium", "Czechia", "Denmark", "Estonia", "France", "Germany", "Hungary", "Ireland", "Italy", "Netherlands", "Poland", "Slovakia", "Spain", "Sweden"]
GLOBAL_PLACEMENTS = ["Argentina", "Australia", "Brazil", "Canada", "China", "France", "Germany", "India", "Indonesia", "Japan", "Kenya", "Mexico", "Nigeria", "Philippines", "South Africa", "South Korea", "United Kingdom", "United States of America"]


def load(name: str):
    return json.loads((RELEASES / name).read_text())


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def choose(report_id: str, values: list[str]) -> str:
    digest = hashlib.sha256(report_id.encode()).digest()
    return values[int.from_bytes(digest[:4], "big") % len(values)]


def placement(country: str, report_id: str) -> str:
    if country == "Global":
        return choose(report_id, GLOBAL_PLACEMENTS)
    if country == "European Union":
        return choose(report_id, EU_PLACEMENTS)
    return ALIASES.get(country, country)


def classifications(row: dict) -> list[dict]:
    value = row.get("classification") or row.get("classifications") or []
    return [value] if isinstance(value, dict) else value


def title_from_url(url: str) -> str:
    slug = unquote(urlparse(url).path).rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"\.(?:html?|php)$", "", slug, flags=re.I)
    slug = clean(re.sub(r"[-_]+", " ", slug))
    return (slug[:1].upper() + slug[1:]) if slug else "Documented AI harm report"


def metadata_summary(row: dict, annotation: dict | None, harms: list[str], country: str, date: str) -> str:
    if annotation:
        statements = [clean(annotation.get("action")), clean(annotation.get("consequence"))]
        summary = ". ".join(value.rstrip(".") for value in statements if value)
        if summary:
            return summary + "."
    status = clean(row.get("occurrence_status")) or "documented"
    labels = ", ".join(harms) or "an unmapped AI harm category"
    host = urlparse(clean(row.get("source_url"))).hostname or "the linked source"
    return f"A {status} AI harm report in {country}, classified as {labels}. Published {date or 'on an unspecified date'} by {host}."


def build_record(row: dict, annotation: dict | None) -> dict:
    report_id = clean(row.get("report_id"))
    cats = classifications(row)
    branches = list(dict.fromkeys(clean(c.get("branch")) for c in cats if clean(c.get("branch")) != "UNMAPPED"))
    harms = []
    for category in cats:
        name = clean(category.get("subcategory"))
        code = clean(category.get("subcategory_id"))
        if name:
            harms.append(f"{code}  {name}" if code else name)
    durations = list(dict.fromkeys(clean(c.get("event_type")) for c in cats if clean(c.get("event_type"))))
    country = clean(row.get("country")) or clean((annotation or {}).get("location")) or "Global"
    date = clean((annotation or {}).get("event_date")) or clean(row.get("publication_date"))
    return {
        "i": report_id,
        "k": country,
        "p": placement(country, report_id),
        "b": branches,
        "h": harms,
        "t": clean((annotation or {}).get("event_type")) or title_from_url(clean(row.get("source_url"))),
        "s": metadata_summary(row, annotation, harms, country, date),
        "u": clean(row.get("source_url")),
        "d": date,
        "e": ", ".join(durations) or "Not specified",
    }


def main() -> None:
    existing = json.loads(TARGET.read_text().removeprefix("window.MAP_SAMPLE = ").strip().removesuffix(";"))
    raw = load("ground_truth_raw.json")
    annotations = {row["report_id"]: row for row in load("ground_truth_annotated.json")}
    rows = raw + load("validation_data.json")
    ids = [clean(row.get("report_id")) for row in rows]
    if len(rows) != 3041 or len(set(ids)) != 3041 or any(not value for value in ids):
        raise ValueError("Expected exactly 3,041 unique report IDs")
    records = [build_record(row, annotations.get(row.get("report_id"))) for row in rows]
    geometry_names = {feature["properties"]["Country"] for feature in existing["countries"]["features"]}
    missing = sorted({record["p"] for record in records} - geometry_names)
    if missing:
        raise ValueError(f"Missing map geometry: {missing}")
    output = {"records": records, "filters": existing["filters"], "ramps": existing["ramps"], "countries": existing["countries"]}
    TARGET.write_text("window.MAP_SAMPLE = " + json.dumps(output, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"Wrote {len(records):,} reports to {TARGET}")


if __name__ == "__main__":
    main()
