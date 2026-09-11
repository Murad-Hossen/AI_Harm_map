import shutil
from pathlib import Path

from ai_harm_map.io import (
    append_jsonl_durable,
    load_json_or_jsonl,
    unique_by_report_id,
)


def existing_report_ids(path):
    if not Path(path).exists():
        return set()
    rows = unique_by_report_id(load_json_or_jsonl(path))
    return {str(row["report_id"]).strip() for row in rows}


def unseen_reports(reports, existing_ids):
    return [
        row
        for row in reports
        if str(row.get("report_id") or "").strip() not in existing_ids
    ]


def append_event(path, event):
    report_id = str(event.get("report_id") or "").strip()
    if not report_id:
        raise ValueError("Cannot append an event without report_id.")
    append_jsonl_durable(path, event)


def snapshot_checkpoint(checkpoint_path, snapshot_dir, *, expected_unique_count=None):
    checkpoint_path = Path(checkpoint_path)
    snapshot_dir = Path(snapshot_dir)

    rows = load_json_or_jsonl(checkpoint_path)
    unique_rows = unique_by_report_id(rows)

    if expected_unique_count is not None and len(unique_rows) != expected_unique_count:
        raise RuntimeError(
            f"Snapshot aborted: expected {expected_unique_count} unique events, found {len(unique_rows)}."
        )

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    target = snapshot_dir / f"predicted_events_combined_{len(unique_rows):05d}.jsonl"
    shutil.copy2(checkpoint_path, target)
    return target