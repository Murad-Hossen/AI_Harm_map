from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from ai_harm_map.io import load_json_or_jsonl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    rows = load_json_or_jsonl(args.path)
    ids = [str(row.get("report_id") or "").strip() for row in rows]
    counts = Counter(ids)

    missing = [index + 1 for index, report_id in enumerate(ids) if not report_id]
    duplicates = sorted(
        report_id for report_id, count in counts.items() if report_id and count > 1
    )

    print(f"rows: {len(rows)}")
    print("unique report_ids:", len(set(ids) - {""}))
    print(f"missing report_ids: {len(missing)}")
    print(f"duplicate report_ids: {len(duplicates)}")

    if duplicates:
        print("first duplicates:", duplicates[:20])

    if missing or duplicates:
        raise SystemExit(1)


if __name__ == "__main__":
    main()