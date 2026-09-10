# Dynamic AI Harm Map

Anonymous research code and reproducibility package for a **Dynamic AI Harm Map**:
an evidence-grounded, temporally evolving representation of documented AI harms.

The repository separates four concerns that were intertwined during development:

1. grounded event extraction and evidence preservation;
2. taxonomy/class-fit verification;
3. temporal graph learning with a Pairwise KG baseline and PHTKG;
4. downstream storage and map-ready export.

## Method overview

```text
AI-harm reports
      |
      v
Grounded event extraction
      |
      v
Exact source-evidence attachment
      |
      v
Taxonomy / class-fit verification
      |
      v
Structured AI-harm events
      |
      +-----------------------+
      |                       |
      v                       v
Pairwise temporal KG        PHTKG
(baseline)                  (proposed)
                              |
                              v
                   learned event representations
                   temporal recurrence estimates
                   similar-event structure
                   latent pattern analysis
                              |
                    +---------+---------+
                    |                   |
                    v                   v
              enriched JSON          Neo4j
                    |            graph-oriented storage
                    v
           Dynamic AI Harm Map
```

**Neo4j is an optional persistent graph-storage/query layer. The Dynamic AI Harm
Map is generated from the enriched JSON representation and does not depend on
Neo4j.**

## Repository layout

```text
configs/        Experiment and inference configuration
data/           Taxonomy, samples, and release placeholders
docs/           Architecture, schema, reproducibility, and anonymity notes
notebooks/      Cleaned snapshots of the current experimental pipeline
scripts/        Command-line entry points
src/            Reusable Python implementation
tests/          Integrity and model-shape tests
tools/          Checkpoint recovery and dataset validation utilities
```

## Installation

Python 3.10+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt
```

On Windows:

```powershell
.venv\Scripts\activate
```

Install the PyTorch build appropriate for the target CUDA runtime before
reproducing GPU experiments.

## Core event roles

PHTKG jointly models seven event roles:

```text
organization
ai_system
affected_group
action
harm_category
consequence
location
```

Each event also carries temporal and provenance information.

## Evidence policy

Evidence is attached mechanically from the source record rather than generated
or shortened by the extraction model:

- `original_evidence_span` is the complete source `original_text`;
- for English sources, `translated_evidence_span` is the same source text;
- for non-English sources, the supplied full `translated_text` is used when available;
- missing supplied translations remain explicitly missing.

See `src/ai_harm_map/evidence.py`.

## Models

### Pairwise temporal KG baseline

The baseline scores typed pairwise role interactions using a DistMult-style
event decomposition.

### PHTKG

The provenance-aware hypergraph temporal knowledge graph keeps the complete
multi-role incident joint. It combines role embeddings, continuous/periodic time
encoding, provenance conditioning, role-aware attention, recurrent event/entity
updates, temporal decay, an event scorer, and a recurrence head.

Reusable architecture definitions are in:

```text
src/ai_harm_map/models/pairwise.py
src/ai_harm_map/models/phtkg.py
```

The current full experimental implementation is retained in:

```text
notebooks/01_training_and_evaluation.ipynb
```

## Taxonomy

The authoritative taxonomy workbook is stored at:

```text
data/taxonomy/AI_Harm_Map_Taxonomy_Schema_vSHARED.xlsx
```

The extraction stage copies supplied classifications. Taxonomy class fit is
verified separately.

## Neo4j

Import an enriched event file with:

```bash
python scripts/export_neo4j.py \
  --input path/to/enriched_events.jsonl \
  --uri neo4j+s://YOUR_INSTANCE \
  --user neo4j
```

Raw extracted values remain on Event nodes while selected graph identities may
be canonicalized.
`


## Canonical files for this repository version

The current paper implementation is represented by the two notebooks in
`notebooks/`:

```text
01_full_model_training_evaluation.ipynb
02_incremental_inference.ipynb
```

