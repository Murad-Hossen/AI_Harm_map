# Dynamic AI Harm Map — PHTKG Research Repository

Research implementation of an evidence-grounded, temporal, provenance-aware hypergraph model for AI-harm events.

## Canonical pipeline

```text
multilingual reports
      ↓
single-pass Qwen event extraction
      ↓
original report retained as source evidence
      ↓
upstream classification copied verbatim
      ↓
strict taxonomy class-fit verification
      ↓
role-aware temporal provenance-aware hypergraph
      ↓
PHTKG training on observed vs controlled corrupted hyperedges
      ↓
learned event/entity representations + evaluation
```

The extraction model does **not** freely classify the harm category. The supplied upstream classification is preserved, matched to the authoritative taxonomy spreadsheet, and verified for fit against the grounded event and original report.

## Code map

### Extraction
- `src/ai_harm_map/extraction/prompts.py` — canonical extraction prompt.
- `src/ai_harm_map/extraction/qwen_extractor.py` — batched deterministic Qwen extraction.
- `src/ai_harm_map/extraction/schema.py` — output normalization.

### Evidence
- `src/ai_harm_map/evidence.py` — mechanically copies `original_text` as `original_evidence_span`; translated text is retained separately.

### Taxonomy verification
- `src/ai_harm_map/taxonomy/loader.py` — loads and matches the authoritative taxonomy Excel.
- `src/ai_harm_map/taxonomy/prompts.py` — strict class-fit verifier prompt.
- `src/ai_harm_map/taxonomy/verifier.py` — verifies the already-supplied class; it is not a free classifier.

### PHTKG
- `src/ai_harm_map/models/phtkg.py` — trainable PHTKG architecture with role embeddings, attention, temporal encoding/decay, provenance message/gating, GRU updates and compatibility scoring.
- `src/ai_harm_map/training/graph.py` — chronological splits and train-only temporal statistics.
- `src/ai_harm_map/training/corruption.py` — controlled same-role hyperedge corruption.
- `src/ai_harm_map/training/train.py` — training loop and paired observed-vs-corrupted evaluation.

### Integration
- `src/ai_harm_map/pipeline/full_pipeline.py` — the single interconnected entry point.
- `scripts/run_full_pipeline.py` — command-line wrapper.
- `scripts/train_phtkg.py` — train PHTKG from structured events.

### Experiment interface
- `notebooks/01_full_model_training_evaluation.ipynb` — the canonical research notebook: single-pass extraction, taxonomy class-fit verification, Pairwise-KG baseline, PHTKG training with Auto-PHTKG validation-only tuning, component-wise verification diagnostics (attention, role geometry, temporal decay, provenance gate, GRUs, multi-hop passing), learned-representation clustering, and recurrence analysis. Outputs and author-identifying metadata are stripped for review; `src/ai_harm_map/` holds the reusable subset of this logic as an importable package for `scripts/run_full_pipeline.py`.
- `notebooks/02_incremental_inference.ipynb` — incremental inference workflow.

## Run

Install the package in editable mode:

```bash
pip install -e .
```

Run the interconnected pipeline:

```bash
python scripts/run_full_pipeline.py \
  --config configs/full_pipeline.yaml \
  --input data/samples/sample_reports.jsonl \
  --output results/full_pipeline_demo
```

For LLM extraction, set `extraction.run_qwen: true` and provide the required model. For LLM taxonomy verification, set `taxonomy.model` to the chosen local/Hugging Face verifier model. The default configuration keeps those expensive stages disabled so the repository can be inspected and tested without model downloads.

## Evidence policy

The original report is the evidence. The extractor produces a structured interpretation; it does not manufacture evidence spans. `original_evidence_span` is copied mechanically from `original_text`.

## Reproducibility

The final paper configuration should be frozen in YAML before reporting results. Do not tune on the test split. Use chronological train/validation/test separation and keep test-only statistics out of model selection.
