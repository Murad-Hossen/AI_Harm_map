import re
from collections import Counter

import pandas as pd


def norm(v):
    return " ".join(re.sub(r"[^\w\s]", " ", str(v or "").casefold()).split())


def token_f1(a, b):
    pa = norm(a).split()
    pb = norm(b).split()
    if not pa and not pb:
        return 1.0
    if not pa or not pb:
        return 0.0

    overlap = sum((Counter(pa) & Counter(pb)).values())
    p = overlap / len(pa)
    r = overlap / len(pb)
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def evaluate_extraction(predictions, gold, fields=None):
    fields = fields or [
        "event_type",
        "ai_system",
        "organization",
        "affected_group",
        "action",
        "harm_category",
        "consequence",
        "location",
        "event_date",
    ]

    pred = {r["report_id"]: r for r in predictions}
    rows = []
    for g in gold:
        p = pred.get(g["report_id"], {})
        for f in fields:
            a = norm(p.get(f))
            b = norm(g.get(f))
            rows.append({
                "report_id": g["report_id"],
                "field": f,
                "exact_match": float(a == b),
                "token_f1": token_f1(a, b),
            })

    d = pd.DataFrame(rows)
    s = d.groupby("field", as_index=False).agg(
        exact_match=("exact_match", "mean"),
        token_f1=("token_f1", "mean"),
    )
    return d, s