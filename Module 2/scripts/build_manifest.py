import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ai_harm_map.io import load_json_or_jsonl, sha256_file


def main():
    parser = argparse.ArgumentParser(description="Build a frozen dataset manifest.")
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--taxonomy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    events = load_json_or_jsonl(args.events)
    ids = [str(row.get("report_id") or "").strip() for row in events]

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "event_file": args.events.name,
        "event_count": len(events),
        "unique_report_ids": len(set(ids)),
        "event_file_sha256": sha256_file(args.events),
        "taxonomy_file": args.taxonomy.name,
        "taxonomy_sha256": sha256_file(args.taxonomy),
        "evidence_policy": "full_source_text_exact_copy",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()