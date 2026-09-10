from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from ai_harm_map.io import (
    load_json_or_jsonl,
    unique_by_report_id,
    write_jsonl_atomic,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recover predicted_events.jsonl "
            "from overlapping snapshots."
        )
    )
    parser.add_argument(
        "--checkpoint",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--snapshots",
        required=True,
        type=Path,
    )
    args = parser.parse_args()

    snapshot_files = sorted(
        args.snapshots.glob(
            "predicted_events_combined_*.jsonl"
        ),
        key=lambda path: (
            path.stat().st_mtime,
            path.name,
        ),
    )

    sources = snapshot_files + (
        [args.checkpoint]
        if args.checkpoint.exists()
        else []
    )
    if not sources:
        raise SystemExit(
            "No checkpoint or snapshot files found."
        )

    combined = []
    for path in sources:
        rows = load_json_or_jsonl(path)
        print(f"{path.name}: {len(rows)} rows")
        combined.extend(rows)

    recovered = unique_by_report_id(
        combined,
        latest_wins=True,
    )

    if args.checkpoint.exists():
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        backup = args.checkpoint.with_name(
            f"{args.checkpoint.stem}"
            f"_before_recovery_{timestamp}"
            f"{args.checkpoint.suffix}"
        )
        shutil.copy2(args.checkpoint, backup)
        print(f"backup: {backup}")

    write_jsonl_atomic(
        args.checkpoint,
        recovered,
    )
    print(
        f"recovered unique events: {len(recovered)}"
    )
    print(f"checkpoint: {args.checkpoint}")


if __name__ == "__main__":
    main()
