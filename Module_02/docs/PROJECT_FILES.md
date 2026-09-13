# Project files

## Core research modules

- `src/ai_harm_map/extraction/prompts.py` — canonical single-pass extraction prompt.
- `src/ai_harm_map/extraction/qwen_extractor.py` — Qwen extraction implementation.
- `src/ai_harm_map/evidence.py` — deterministic source-evidence attachment.
- `src/ai_harm_map/taxonomy/loader.py` — authoritative taxonomy loader/matcher.
- `src/ai_harm_map/taxonomy/prompts.py` — strict supplied-class verification prompt.
- `src/ai_harm_map/taxonomy/verifier.py` — class-fit verification implementation.
- `src/ai_harm_map/models/phtkg.py` — PHTKG architecture.
- `src/ai_harm_map/training/graph.py` — chronological graph construction and train-only temporal statistics.
- `src/ai_harm_map/training/corruption.py` — controlled negative hyperedge corruption.
- `src/ai_harm_map/training/loss.py` — observed-vs-corrupted objective.
- `src/ai_harm_map/training/train.py` — PHTKG training and paired evaluation.
- `src/ai_harm_map/pipeline/full_pipeline.py` — complete interconnected pipeline.

## Entry points

- `scripts/run_full_pipeline.py` — end-to-end command-line entry point.
- `scripts/train_phtkg.py` — direct PHTKG training entry point.
- `notebooks/01_full_model_training_evaluation.ipynb` — full extraction/evaluation, Pairwise-KG baseline, PHTKG training/tuning/diagnostics, and representation analysis (see `notebooks/README.md`).
- `notebooks/02_incremental_inference.ipynb` — incremental inference workflow.
