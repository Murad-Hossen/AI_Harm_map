import copy
import json

import torch

from ai_harm_map.constants import MISSING_TEXT
from ai_harm_map.evidence import attach_full_source_evidence
from .prompts import EXTRACTION_PROMPT
from .schema import normalize_event


def clean(v):
    return "" if v is None else str(v).strip()


def first_json(text):
    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object returned by extractor")

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

    raise ValueError("Incomplete JSON object returned by extractor")


def supplied_classification(report):
    value = report.get("classifications")
    if value in (None, "", []):
        value = report.get("classification")
    return copy.deepcopy(value) if value not in (None, "", []) else []


class QwenExtractor:
    """One independent Qwen completion per report; batching is only a throughput optimization."""

    def __init__(self, model_name, max_input_tokens=7000, max_new_tokens=700, use_sdpa=True):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.max_input_tokens = max_input_tokens
        self.max_new_tokens = max_new_tokens
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.tokenizer.padding_side = "left"
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        kwargs = {}
        if torch.cuda.is_available():
            kwargs.update(device_map="auto", dtype=torch.float16)
            if use_sdpa:
                kwargs["attn_implementation"] = "sdpa"
        else:
            kwargs["dtype"] = torch.float32

        try:
            self.model = AutoModelForCausalLM.from_pretrained(model_name, **kwargs)
        except Exception:
            kwargs.pop("attn_implementation", None)
            self.model = AutoModelForCausalLM.from_pretrained(model_name, **kwargs)

        self.model.eval()

    def build_prompt(self, report):
        user_text = f"""REPORT ID:
{clean(report.get('report_id'))}

SOURCE:
{clean(report.get('source_url'))}

PUBLICATION DATE:
{clean(report.get('publication_date'))}

SOURCE LANGUAGE:
{clean(report.get('source_language'))}

COUNTRY / DATASET LOCATION HINT:
{clean(report.get('country'))}

ORIGINAL-LANGUAGE REPORT:
{clean(report.get('original_text'))}

CANONICAL ENGLISH TRANSLATION:
{clean(report.get('translated_text'))}""".strip()

        return self.tokenizer.apply_chat_template(
            [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": user_text},
            ],
            tokenize=False,
            add_generation_prompt=True,
        )

    def extract_batch(self, reports):
        if not reports:
            return []

        prompts = [self.build_prompt(r) for r in reports]
        enc = self.tokenizer(
            prompts, return_tensors="pt", padding=True, truncation=True, max_length=self.max_input_tokens
        )
        device = next(self.model.parameters()).device
        enc = {k: v.to(device) for k, v in enc.items()}
        width = enc["input_ids"].shape[1]

        with torch.inference_mode():
            out = self.model.generate(
                **enc, do_sample=False, max_new_tokens=self.max_new_tokens, pad_token_id=self.tokenizer.pad_token_id
            )

        rows = []
        for i, report in enumerate(reports):
            parsed = first_json(self.tokenizer.decode(out[i, width:], skip_special_tokens=True))
            event = parsed.get("harm_event")
            if not isinstance(event, dict):
                raise ValueError(f"{report.get('report_id')}: missing harm_event")

            event = attach_full_source_evidence(normalize_event(event), report)
            event.update({
                "report_id": report["report_id"],
                "harm_category": supplied_classification(report),
                "source": clean(report.get("source_url")) or MISSING_TEXT,
                "evidence_audit": {
                    "method": "full_source_text_copy",
                    "source_field": "original_text",
                },
                "inference_audit": {
                    "mode": "single_pass_batched",
                    "max_input_tokens": self.max_input_tokens,
                    "max_new_tokens": self.max_new_tokens,
                },
            })
            rows.append(event)

        return rows

    def extract_all(self, reports, batch_size=4):
        result = []
        for i in range(0, len(reports), batch_size):
            result.extend(self.extract_batch(reports[i:i + batch_size]))
        return result