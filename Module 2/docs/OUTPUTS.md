# Output contract

## Full training / evaluation notebook

The full-model notebook writes the following project outputs:

```text
predicted_events_single_pass_fast.jsonl
extraction_errors_single_pass_fast.csv
extraction_summary.csv
extraction_details.csv

auto_phtkg_trials.csv
auto_phtkg_best_config.json
gold_phtkg_training.csv
predicted_phtkg_training.csv
phtkg_comparison.csv

gold_event_embeddings.jsonl
predicted_event_embeddings.jsonl

gold_phtkg.pt
predicted_phtkg.pt

gold_entity_drift_by_year.csv
predicted_entity_drift_by_year.csv
gold_recurrence_auc_by_transition.csv
predicted_recurrence_auc_by_transition.csv

manifest.json
provenance_gate_direct_diagnostic.csv
compatibility_corruption_detailed.csv
compatibility_corruption_by_role.csv
component_verification.csv

predicted_events_with_learned_representation.jsonl
predicted_events_with_learned_representation.json
```

## Incremental inference notebook

Persistent checkpoint:

```text
predicted_events.jsonl
```

Snapshots:

```text
snapshots/predicted_events_combined_XXXXX.jsonl
```

Incremental inference directory:

```text
incremental_inference/
  harm_category_fit_audit.jsonl
  harm_category_fit_summary.csv
  events_ALL_verified_for_retraining.jsonl
  incremental_new_event_entity_drift.csv
  clustering_k_search_ALL.csv
  pattern_evolution_ALL.csv
  predicted_events_ALL_with_verified_class_and_phtkg.jsonl
  predicted_events_ALL_with_verified_class_and_phtkg.json
  incremental_inference_manifest.json
```

The final enriched JSON/JSONL is the direct downstream source for the Dynamic
AI Harm Map. Neo4j is a separate persistent graph-storage representation.
