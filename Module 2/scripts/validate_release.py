import argparse
from pathlib import Path

from ai_harm_map.io import load_json_or_jsonl, sha256_file


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()

    rows = load_json_or_jsonl(args.input)
    ids = [str(row.get("report_id") or "").strip() for row in rows]

    missing = sum(not report_id for report_id in ids)
    duplicates = len(ids) - len(set(ids))

    print(f"records: {len(rows)}")
    print(f"missing report_id: {missing}")
    print(f"duplicate report_id: {duplicates}")
    print(f"sha256: {sha256_file(args.input)}")

    if missing or duplicates:
        raise SystemExit(1)


if __name__ == "__main__":
    main()