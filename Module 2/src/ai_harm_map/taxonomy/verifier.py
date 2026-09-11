import json
from .loader import classification_candidates, clean
from .prompts import FIT_SYSTEM_PROMPT


def first_json(text):
    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object returned by verifier")

    depth = 0
    ins = False
    esc = False
    for i, ch in enumerate(text[start:], start):
        if ins:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                ins = False
        else:
            if ch == '"':
                ins = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i + 1])

    raise ValueError("Incomplete verifier JSON")


def event_view(event):
    keys = [
        "event_type", "ai_system", "organization", "affected_group",
        "action", "consequence", "location", "event_date",
        "original_evidence_span", "translated_evidence_span",
    ]
    return {k: event.get(k, "") for k in keys}


def build_fit_prompt(event, candidate, row):
    payload = {
        "original_report": event.get("original_evidence_span", event.get("original_text", "")),
        "translated_report": event.get("translated_evidence_span", event.get("translated_text", "")),
        "event": event_view(event),
        "candidate_classification": candidate,
        "authoritative_taxonomy_row": {
            k: row.get(k, "")
            for k in [
                "#", "Branch", "Subcategory", "Short definition",
                "Inclusion test (proximate cause)", "Protected interest",
                "Event type", "Occurrence status admitted",
            ]
        },
    }
    return "Does THIS supplied class fit THIS event? Evaluate only that candidate.\n\n" + json.dumps(
        payload, ensure_ascii=False, indent=2
    )


class TaxonomyVerifier:
    def __init__(self, model_name=None, taxonomy=None):
        self.taxonomy = taxonomy
        self.model = None
        self.tokenizer = None
        if model_name:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForCausalLM.from_pretrained(model_name, device_map="auto", dtype="auto")
            self.model.eval()

    def verify_one(self, event, candidate):
        row = self.taxonomy.match(candidate)
        result = {"candidate": candidate, "taxonomy_matched": row is not None}

        if row is None:
            result.update({
                "status": "uncertain",
                "confidence": 0.0,
                "reason": "Candidate class could not be matched to the authoritative taxonomy row.",
            })
            return result

        if self.model is None:
            result.update({
                "status": "not_run",
                "confidence": 0.0,
                "reason": "No verifier model configured.",
            })
            return result

        prompt = build_fit_prompt(event, candidate, row)
        messages = [
            {"role": "system", "content": FIT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        enc = self.tokenizer([text], return_tensors="pt", truncation=True, max_length=9000)
        device = next(self.model.parameters()).device
        enc = {k: v.to(device) for k, v in enc.items()}

        import torch
        with torch.inference_mode():
            out = self.model.generate(
                **enc, do_sample=False, max_new_tokens=180, pad_token_id=self.tokenizer.pad_token_id
            )
        completion = self.tokenizer.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True)

        parsed = first_json(completion)
        status = parsed.get("status")
        if status not in {"fit", "not_fit", "uncertain"}:
            status = "uncertain"

        result.update({
            "status": status,
            "confidence": float(parsed.get("confidence", 0.0)),
            "reason": clean(parsed.get("reason"))[:500],
            "taxonomy_id": clean(row.get("#")),
            "taxonomy_name": clean(row.get("Subcategory")),
        })
        return result

    def verify_events(self, events):
        output = []
        for event in events:
            candidates = classification_candidates(event.get("harm_category"))
            checks = [self.verify_one(event, c) for c in candidates]
            item = dict(event)
            item["taxonomy_verification"] = checks
            output.append(item)
        return output