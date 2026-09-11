from ai_harm_map.constants import MISSING_TEXT

EVENT_FIELDS = [
    "event_type",
    "ai_system",
    "organization",
    "affected_group",
    "action",
    "consequence",
    "location",
    "event_date",
    "confidence",
]


def normalize_event(event):
    out = {}
    for f in EVENT_FIELDS:
        v = event.get(f, MISSING_TEXT)
        if v is None or v == "":
            v = 0.0 if f == "confidence" else MISSING_TEXT
        out[f] = v
    return out