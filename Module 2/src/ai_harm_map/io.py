from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def load_json_or_jsonl(path):
    path = Path(path)
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    if raw.startswith("["):
        rows = json.loads(raw)
        if not isinstance(rows, list):
            raise ValueError("Top-level JSON must be an array.")
    else:
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]

    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("Every record must be a JSON object.")
    return rows


def append_jsonl_durable(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass


def write_jsonl_atomic(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")

    with temp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass

    temp.replace(path)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_by_report_id(rows, *, latest_wins=True):
    order = []
    by_id = {}

    for row in rows:
        report_id = str(row.get("report_id") or "").strip()
        if not report_id:
            continue

        if report_id not in by_id:
            order.append(report_id)
            by_id[report_id] = row
        elif latest_wins:
            by_id[report_id] = row

    return [by_id[report_id] for report_id in order]