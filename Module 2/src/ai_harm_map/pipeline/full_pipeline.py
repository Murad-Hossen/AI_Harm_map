import json
from pathlib import Path

import torch

from ai_harm_map.extraction import QwenExtractor
from ai_harm_map.io import load_json_or_jsonl, write_jsonl_atomic
from ai_harm_map.taxonomy import Taxonomy, TaxonomyVerifier
from ai_harm_map.training import train_phtkg


class FullPipeline:
    """Canonical connection point: reports -> extraction -> evidence -> taxonomy verification -> PHTKG."""

    def __init__(self, config):
        self.config = config

    def extract(self, reports):
        c = self.config.get("extraction", {})
        if not c.get("run_qwen", False):
            return reports

        model = QwenExtractor(
            c.get("model", "Qwen/Qwen2.5-3B-Instruct"),
            max_input_tokens=int(c.get("max_input_tokens", 7000)),
            max_new_tokens=int(c.get("max_new_tokens", 700)),
            use_sdpa=bool(c.get("use_sdpa", True)),
        )
        return model.extract_all(reports, batch_size=int(c.get("batch_size", 4)))

    def verify_taxonomy(self, events):
        c = self.config.get("taxonomy", {})
        if not c.get("enabled", True):
            return events

        taxonomy = Taxonomy(c["path"], c.get("sheet", "Taxonomy & Schema"))
        verifier = TaxonomyVerifier(c.get("model"), taxonomy)
        return verifier.verify_events(events)

    def train(self, events):
        return train_phtkg(events, self.config.get("phtkg", {}), seed=int(self.config.get("seed", 42)))

    def run(self, input_path, output_dir):
        reports = load_json_or_jsonl(input_path)
        events = self.extract(reports)
        events = self.verify_taxonomy(events)

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        write_jsonl_atomic(out / "verified_events.jsonl", events)

        model, graph, history, metrics, state = self.train(events)
        torch.save(
            {"model_state_dict": model.state_dict(), "graph": graph, "final_entity_state": state},
            out / "phtkg.pt",
        )

        (out / "phtkg_metrics.json").write_text(
            json.dumps(metrics, indent=2, default=str), encoding="utf-8"
        )
        (out / "run_manifest.json").write_text(
            json.dumps(
                {
                    "input_records": len(reports),
                    "event_records": len(events),
                    "extraction": (
                        "single-pass Qwen per report"
                        if self.config.get("extraction", {}).get("run_qwen")
                        else "pre-extracted input"
                    ),
                    "evidence": "original report text copied mechanically",
                    "taxonomy_verification": bool(self.config.get("taxonomy", {}).get("enabled", True)),
                    "model": "PHTKG",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        return {"events": events, "model": model, "graph": graph, "history": history, "metrics": metrics}