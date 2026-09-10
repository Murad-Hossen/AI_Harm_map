from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".yaml", ".yml", ".toml",
    ".json", ".jsonl", ".ipynb", ".cfg", ".ini", ".sh",
}
PATTERNS = {
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "personal Kaggle dataset path": re.compile(r"/kaggle/input/datasets/[^\s/]+", re.I),
}

violations = []
for path in ROOT.rglob("*"):
    if not path.is_file() or "__pycache__" in path.parts:
        continue
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        continue
    if path.resolve() == Path(__file__).resolve():
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for label, pattern in PATTERNS.items():
        if pattern.search(text):
            violations.append((path.relative_to(ROOT), label))

if violations:
    print("Potential anonymity issues:")
    for path, reason in violations:
        print(f"  {path}: {reason}")
    raise SystemExit(1)

print("Anonymity check passed.")
