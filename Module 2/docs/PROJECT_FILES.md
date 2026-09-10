# Project file map

## Canonical code

```text
notebooks/01_full_model_training_evaluation.ipynb
notebooks/02_incremental_inference.ipynb
src/ai_harm_map/
scripts/
tools/
```

## Taxonomy

```text
data/taxonomy/AI_Harm_Map_Taxonomy_Schema_vSHARED.xlsx
```

## Local research artifacts

The master working bundle also contains `local_artifacts/`, which is excluded
from Git. It contains exact notebook originals, current source/reference files,
current available outputs, and historical snapshot branches used for recovery.

This separation lets the working archive remain complete while keeping the
GitHub/review repository clean and safer to publish.
