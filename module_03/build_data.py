#!/usr/bin/env python3
"""Build browser map data from the deduplicated 2,527 placed-event corpus."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
RELEASES = ROOT.parent / "data" / "releases"
PREDICTED = REPO_ROOT / "module_03" / "predicted_v2.json"
REFERENCE_MAP = REPO_ROOT / "module_03" / "2dot_map.html"
TARGET = ROOT / "data.js"
RECORD_CHUNK_SIZE = 400
MODULE_01 = REPO_ROOT / "module_01"
# Optional {source_url: original headline}. Without it, hover titles fall back to the cleaned URL slug.
HEADLINES = ROOT / "headlines.json"
SOURCE_DOMAINS = 27
LAST_UPDATED = __import__("datetime").date.today().isoformat()
# After removing the 352 duplicated Guardian records (R2195-R2546).
EXPECTED_PLACED = 2527
EXPECTED_COUNTRIES = 81
COUNTRY_CHUNK_SIZE = 20

GEOGRAPHIC_OVERRIDES = {
    # Approximate Ambler Road corridor placement, not an incident coordinate.
    "R847": {"coordinates": [67.5, -156.0], "display_location": "Alaska, United States"},
}

DATE_OVERRIDES = {
    # The stored evidence says the Replicator initiative was unveiled in August 2023.
    "R873": {"date": "2023-08", "basis": "reported month in source"},
}

COUNTRY_ALIASES = {
    "United States": "United States of America",
    "Palestinian Territories": "Palestine",
    "Hong Kong": "Hong Kong S.A.R.",
    "Serbia": "Republic of Serbia",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def extract_reference_data() -> tuple[list[dict], list[dict]]:
    html = REFERENCE_MAP.read_text(encoding="utf-8")
    records_match = re.search(r"var RECORDS = (\[.*?\]), FILTERS = ", html, re.S)
    filters_match = re.search(r", FILTERS = (\[.*?\]);\n  var TOTAL", html, re.S)
    if not records_match or not filters_match:
        raise ValueError("Could not read RECORDS/FILTERS from 2dot_map.html")
    return json.loads(records_match.group(1)), json.loads(filters_match.group(1))


def publication_dates() -> dict[str, str]:
    """source_url -> publication date, from the classifier outputs in module_01."""
    dates = {}
    for path in sorted(MODULE_01.rglob("*.json")):
        try:
            rows = load_json(path)
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("source_url") and row.get("publication_date"):
                dates.setdefault(clean(row["source_url"]), clean(row["publication_date"]))
    return dates


ACRONYMS = {"ai", "us", "uk", "eu", "un", "nhs", "idf", "gps", "llm", "llms", "gpt", "fbi", "ice", "dhs", "cbp", "nyc", "bbc", "abc", "nsa", "cia", "faa", "ftc", "sec", "lapd", "nypd"}


def slug_headline(url: str, fallback: str) -> str:
    """Readable headline from the article URL slug (used when no stored headline exists)."""
    slug = re.sub(r"\.(html?|php|aspx?)$", "", url.rstrip("/").rsplit("/", 1)[-1])
    words = [w for w in re.split(r"[-_+]+", slug) if w and not re.fullmatch(r"[0-9a-f]{6,}|\d{5,}", w)]
    if len(words) < 3:
        return fallback
    words = [w.upper() if w.lower() in ACRONYMS else w for w in words]
    text = " ".join(words)
    return text[:1].upper() + text[1:]


def harm_labels(event: dict) -> tuple[str, ...]:
    labels = []
    for harm in event.get("harm_category") or []:
        code = clean(harm.get("subcategory_id"))
        name = clean(harm.get("subcategory"))
        labels.append(f"{code}  {name}".strip())
    return tuple(labels)


def exact_key(event: dict) -> tuple:
    return (
        clean(event.get("source")),
        clean(event.get("original_evidence_span")),
        clean(event.get("event_date")),
        harm_labels(event),
    )


def reference_key(record: dict) -> tuple:
    return (clean(record.get("u")), clean(record.get("s")), clean(record.get("d")), tuple(record.get("h") or []))


def loose_key(event: dict) -> tuple:
    return (clean(event.get("source")), clean(event.get("original_evidence_span")), clean(event.get("event_date")))


def choose_candidate(candidates: list[dict], map_country: str, raw_by_id: dict[str, dict]) -> dict:
    for candidate in candidates:
        raw_country = clean(raw_by_id.get(candidate["report_id"], {}).get("country"))
        if COUNTRY_ALIASES.get(raw_country, raw_country) == map_country:
            return candidate
    return candidates[0]


def browser_filters(reference_filters: list[dict]) -> list[dict]:
    current_branch = None
    filters = []
    for item in reference_filters:
        if item["k"] == "b":
            current_branch = item["v"]
        filters.append({"k": item["k"], "v": item["v"], "b": current_branch})
    return filters


def write_browser_chunks(output: dict) -> None:
    """Write small script assets for proxies that time out on the full data.js."""
    for old_chunk in ROOT.glob("data-records-*.js"):
        old_chunk.unlink()
    for old_chunk in ROOT.glob("data-countries-*.js"):
        old_chunk.unlink()

    (ROOT / "data-bootstrap.js").write_text(
        "window.MAP_DATA_RECORDS=[];window.MAP_DATA_COUNTRIES=[];\n",
        encoding="utf-8",
    )
    for index, start in enumerate(range(0, len(output["records"]), RECORD_CHUNK_SIZE), 1):
        chunk = output["records"][start : start + RECORD_CHUNK_SIZE]
        (ROOT / f"data-records-{index:02d}.js").write_text(
            "window.MAP_DATA_RECORDS.push(..."
            + json.dumps(chunk, ensure_ascii=False, separators=(",", ":"))
            + ");\n",
            encoding="utf-8",
        )

    country_features = output["countries"]["features"]
    for index, start in enumerate(range(0, len(country_features), COUNTRY_CHUNK_SIZE), 1):
        chunk = country_features[start : start + COUNTRY_CHUNK_SIZE]
        (ROOT / f"data-countries-{index:02d}.js").write_text(
            "window.MAP_DATA_COUNTRIES.push(..."
            + json.dumps(chunk, ensure_ascii=False, separators=(",", ":"))
            + ");\n",
            encoding="utf-8",
        )

    (ROOT / "data-finalize.js").write_text(
        "window.MAP_SAMPLE={records:window.MAP_DATA_RECORDS,filters:"
        + json.dumps(output["filters"], ensure_ascii=False, separators=(",", ":"))
        + ",meta:"
        + json.dumps(output["meta"], ensure_ascii=False, separators=(",", ":"))
        + ",unplaced:"
        + json.dumps(output["unplaced"], ensure_ascii=False, separators=(",", ":"))
        + ",ramps:"
        + json.dumps(output["ramps"], ensure_ascii=False, separators=(",", ":"))
        + ",countries:{type:"
        + json.dumps(output["countries"].get("type", "FeatureCollection"))
        + ",features:window.MAP_DATA_COUNTRIES}};"
        + "delete window.MAP_DATA_RECORDS;delete window.MAP_DATA_COUNTRIES;\n",
        encoding="utf-8",
    )


def main() -> None:
    existing = json.loads(TARGET.read_text().removeprefix("window.MAP_SAMPLE = ").strip().removesuffix(";"))
    predicted = load_json(PREDICTED)
    reference_records, reference_filters = extract_reference_data()
    release_rows = load_json(RELEASES / "ground_truth_raw.json") + load_json(RELEASES / "validation_data.json")
    raw_by_id = {row["report_id"]: row for row in release_rows}

    pub_dates = publication_dates()
    stored_headlines = load_json(HEADLINES) if HEADLINES.exists() else {}
    exact = defaultdict(list)
    loose = defaultdict(list)
    for event in predicted:
        exact[exact_key(event)].append(event)
        loose[loose_key(event)].append(event)

    used_ids = set()
    records = []
    for reference in reference_records:
        candidates = [event for event in exact.get(reference_key(reference), []) if event["report_id"] not in used_ids]
        if not candidates:
            key = (clean(reference.get("u")), clean(reference.get("s")), clean(reference.get("d")))
            candidates = [event for event in loose.get(key, []) if event["report_id"] not in used_ids]
        if not candidates:
            raise ValueError(f"Could not recover stable report ID for {reference.get('u')}")
        event = choose_candidate(candidates, reference["k"], raw_by_id)
        report_id = event["report_id"]
        used_ids.add(report_id)
        raw = raw_by_id.get(report_id, {})
        date_override = DATE_OVERRIDES.get(report_id)
        publication_date = clean(raw.get("publication_date"))
        display_date = date_override["date"] if date_override else publication_date or clean(event.get("event_date"))
        context = {
            "occurrenceStatus": clean(raw.get("occurrence_status")),
            "publicationDate": publication_date,
            "sourceLanguage": clean(raw.get("source_language")),
            "dateBasis": date_override["basis"] if date_override else "publication date",
            "extractedEventDate": clean(event.get("event_date")),
            "organization": clean(event.get("organization")),
            "aiSystem": clean(event.get("ai_system")),
            "affectedGroup": clean(event.get("affected_group")),
            "action": clean(event.get("action")),
            "consequence": clean(event.get("consequence")),
        }
        url = clean(reference["u"])
        headline = clean(stored_headlines.get(url)) or slug_headline(url, reference["t"])
        record = {
            "i": report_id,
            "hd": headline,
            "pd": pub_dates.get(url, ""),
            "k": reference["k"],
            "p": reference["k"],
            "b": reference["b"],
            "h": reference["h"],
            "t": reference["t"],
            "s": reference["s"],
            "u": reference["u"],
            "d": display_date,
            "e": reference["e"],
            "x": {key: value for key, value in context.items() if value},
        }
        override = GEOGRAPHIC_OVERRIDES.get(report_id)
        if override:
            record["c"] = override["coordinates"]
            record["l"] = override["display_location"]
        records.append(record)

    if len(records) != EXPECTED_PLACED or len(used_ids) != EXPECTED_PLACED:
        raise ValueError(f"Expected {EXPECTED_PLACED:,} unique placed reports, found {len(records)} records and {len(used_ids)} IDs")
    countries = {record["k"] for record in records}
    if len(countries) != EXPECTED_COUNTRIES:
        raise ValueError(f"Expected 81 countries, found {len(countries)}")
    geometry_names = {feature["properties"]["Country"] for feature in existing["countries"]["features"]}
    missing_geometry = sorted(countries - geometry_names)
    if missing_geometry:
        raise ValueError(f"Missing map geometry: {missing_geometry}")

    placed_urls = {clean(record["u"]) for record in records}
    unplaced = []
    for event in predicted:
        url = clean(event.get("source"))
        if url in placed_urls:
            continue
        labels = list(harm_labels(event))
        unplaced.append({
            "i": event["report_id"],
            "hd": slug_headline(url, clean(event.get("event_type")) or url),
            "u": url,
            "h": labels,
            "b": sorted({clean(h.get("branch")) for h in event.get("harm_category") or []}),
            "l": clean(event.get("location")),
            "pd": pub_dates.get(url, ""),
        })
    us = sum(record["k"] == "United States of America" for record in records)
    meta = {
        "sourceDomains": SOURCE_DOMAINS,
        "lastUpdated": LAST_UPDATED,
        "cases": len(records) + len(unplaced),
        "placed": len(records),
        "unplaced": len(unplaced),
        "countries": len(countries),
        "usShare": round(100 * us / len(records)),
    }
    output = {
        "meta": meta,
        "unplaced": unplaced,
        "records": records,
        "filters": browser_filters(reference_filters),
        "ramps": existing["ramps"],
        "countries": existing["countries"],
    }
    TARGET.write_text("window.MAP_SAMPLE = " + json.dumps(output, ensure_ascii=False, separators=(",", ":")) + ";\n")
    write_browser_chunks(output)
    print(f"Wrote {len(records):,} reports across {len(countries)} countries to {TARGET}; "
          f"{len(unplaced)} unplaced reports listed separately; meta={meta}")


if __name__ == "__main__":
    main()
