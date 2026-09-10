# Model card

## Proposed model

**PHTKG** is a provenance-aware hypergraph temporal knowledge graph model for
structured AI-harm events. Each event jointly connects seven semantic roles:
organization, AI system, affected group, action, harm category, consequence,
and location.

The architecture uses entity and role embeddings, an event seed, linear and
periodic time encoding, missing-time handling, provenance conditioning,
role-aware attention, recurrent event/entity updates, role-specific
event-to-entity projections, temporal decay, an event scorer, and a
next-period recurrence head.

## Baseline

The Pairwise temporal KG baseline decomposes each event into typed role-pair
interactions and uses a DistMult-style scorer.

## Pretrained extraction model

The current extraction pipeline uses:

```text
Qwen/Qwen2.5-3B-Instruct
```

Qwen is used as an inference component; the PHTKG is the learned graph model.

## Incremental inference

Incremental inference loads the existing `predicted_phtkg.pt`. It does not
retrain graph-model weights. Updating entity state for newly appended events
should therefore be described as inference-time temporal rollout, not retraining.
