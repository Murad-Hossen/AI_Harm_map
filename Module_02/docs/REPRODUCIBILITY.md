# Reproducibility

## Recommended experiment order

1. Freeze the curated report input and taxonomy version.
2. Run grounded event extraction.
3. Attach full source evidence by exact `report_id`.
4. Run taxonomy/class-fit verification.
5. Freeze the verified structured event corpus.
6. Train/evaluate the Pairwise temporal KG baseline.
7. Train/evaluate PHTKG under the applicable matched temporal protocol.
8. Run final fixed-checkpoint inference on the frozen corpus.
9. Compute similar-event structure, recurrence outputs, and latent patterns.
10. Generate the map-ready enriched JSON.
11. Optionally import that enriched JSON into Neo4j.

## Temporal evaluation

Dated events are ordered chronologically. Validation/test periods follow the
training period. Undated events remain in training rather than being injected
into future evaluation periods.

## Tuning

Auto-PHTKG is for model selection. Final paper-result reproduction should reuse
the frozen selected configuration rather than performing a fresh search.

## Incremental extraction

`predicted_events.jsonl` is an append-only operational checkpoint. Snapshot
recovery must union overlapping files by `report_id`; snapshots must not simply
be concatenated.

## Frozen release manifest

After the final corpus is ready:

```bash
python scripts/build_manifest.py \
  --events data/releases/ai_harm_events_v1.jsonl \
  --taxonomy data/taxonomy/AI_Harm_Map_Taxonomy_Schema_vSHARED.xlsx \
  --output results/manifests/dataset_manifest.json
```

Record hashes for the final event file, taxonomy, and PHTKG checkpoint.
