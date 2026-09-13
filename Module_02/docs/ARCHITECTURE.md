# Architecture

The project treats a documented AI-harm incident as a multi-role event rather
than a collection of independent binary facts.

```text
Source report
   |
   v
Grounded extraction
   |
   v
Structured event
   |-- organization
   |-- ai_system
   |-- affected_group
   |-- action
   |-- harm_category
   |-- consequence
   `-- location
   |
   +-- event_date
   +-- provenance/confidence
   +-- exact source evidence
   |
   +------------------------+
   |                        |
   v                        v
Pairwise baseline          PHTKG
                            |
                            v
                    enriched event JSON
                      |             |
                      v             v
                 map pipeline     Neo4j storage
```

## Separation of responsibilities

- Extraction structures the curated source report.
- Evidence attachment is deterministic and source-derived.
- Taxonomy fit is a separate verification step.
- PHTKG performs temporal/relational learning.
- Clustering operates on learned PHTKG representations.
- Neo4j stores a persistent graph view of the corpus.
- The Dynamic AI Harm Map consumes enriched JSON directly.

## Scientific checkpoint rule

A fixed PHTKG checkpoint does not retroactively learn newly appended events.
Incremental state rollout is inference, not retraining. If a paper claim states
that PHTKG was trained on the final verified combined corpus, a final retrain on
that frozen corpus is required.
