from __future__ import annotations

from dataclasses import dataclass
import math

import torch
import torch.nn as nn
import torch.nn.functional as F

from ai_harm_map.constants import ROLES


@dataclass(frozen=True)
class PHTKGConfig:
    embedding_dim: int = 64
    layers: int = 2
    dropout: float = 0.1


class PHTKG(nn.Module):
    """Provenance-aware temporal hypergraph architecture."""

    def __init__(self, total_nodes: int, config: PHTKGConfig | None = None):
        super().__init__()
        cfg = config or PHTKGConfig()

        d = int(cfg.embedding_dim)
        self.layers = int(cfg.layers)
        self.dimension = d

        self.entity_embeddings = nn.Embedding(total_nodes, d)
        self.role_embeddings = nn.Parameter(torch.randn(len(ROLES), d) * 0.02)
        self.event_seed = nn.Parameter(torch.randn(d) * 0.02)

        self.time_linear_weight = nn.Parameter(torch.randn(d))
        self.time_linear_bias = nn.Parameter(torch.zeros(d))
        self.time_periodic_weight = nn.Parameter(torch.randn(d))
        self.time_periodic_bias = nn.Parameter(torch.zeros(d))
        self.missing_time = nn.Parameter(torch.randn(d) * 0.02)

        self.provenance_message = nn.Sequential(nn.Linear(1, d), nn.Tanh())
        self.entity_key = nn.Linear(d, d, bias=False)
        self.entity_value = nn.Linear(d, d, bias=False)
        self.event_query = nn.Linear(d, d, bias=False)
        self.role_bias = nn.Parameter(torch.zeros(len(ROLES)))

        self.dropout = nn.Dropout(float(cfg.dropout))
        self.event_update = nn.GRUCell(d, d)
        self.entity_update = nn.GRUCell(d, d)
        self.event_to_entity = nn.ModuleList(
            [nn.Linear(d, d, bias=False) for _ in ROLES]
        )
        self.temporal_decay = nn.Parameter(torch.zeros(len(ROLES)))
        self.scorer = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))
        self.next_year_head = nn.Sequential(
            nn.Linear(2 * d, d), nn.GELU(), nn.Linear(d, 1)
        )

    def encode_time(
        self, year_normalized: float, device: torch.device
    ) -> torch.Tensor:
        year = torch.tensor([[year_normalized]], dtype=torch.float32, device=device)
        vector = (
            year * self.time_linear_weight
            + self.time_linear_bias
            + torch.sin(year * self.time_periodic_weight + self.time_periodic_bias)
        )
        return vector.squeeze(0)

    def forward(
        self,
        global_ids: torch.Tensor,
        years: torch.Tensor,
        known: torch.Tensor,
        provenance: torch.Tensor,
        time_mean: torch.Tensor,
        time_known: torch.Tensor,
        entity_state_init: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        event_count = global_ids.shape[0]
        entity_state = (
            self.entity_embeddings.weight
            if entity_state_init is None
            else entity_state_init
        )
        event_state = self.event_seed.unsqueeze(0).expand(event_count, -1)

        years_column = years.unsqueeze(-1)
        known_column = known.unsqueeze(-1)
        observed_time = (
            years_column * self.time_linear_weight
            + self.time_linear_bias
            + torch.sin(
                years_column * self.time_periodic_weight + self.time_periodic_bias
            )
        )
        time_message = (
            known_column * observed_time + (1 - known_column) * self.missing_time
        )
        provenance_message = self.provenance_message(provenance.unsqueeze(-1))
        provenance_gate = torch.sigmoid(provenance).unsqueeze(-1)

        for _ in range(self.layers):
            incident = entity_state[global_ids] + self.role_embeddings.unsqueeze(0)
            keys = self.entity_key(incident)
            values = self.entity_value(incident)
            query = self.event_query(event_state).unsqueeze(1)

            logits = (
                (query * keys).sum(-1) / math.sqrt(self.dimension)
                + self.role_bias.unsqueeze(0)
            )
            attention = F.softmax(logits, dim=1)
            entity_message = self.dropout(
                (attention.unsqueeze(-1) * values).sum(1)
            )
            event_state = self.event_update(
                entity_message + time_message + provenance_message,
                event_state,
            )

            aggregate = torch.zeros_like(entity_state)
            denominator = torch.zeros(
                entity_state.shape[0], 1, device=entity_state.device
            )

            for role_index in range(len(ROLES)):
                ids = global_ids[:, role_index]
                temporal_known = known * time_known[ids]
                gap = torch.abs(years - time_mean[ids])
                decay = F.softplus(self.temporal_decay[role_index])
                temporal_weight = (
                    temporal_known * torch.exp(-decay * gap) + (1 - temporal_known)
                )
                weight = temporal_weight * provenance_gate.squeeze(-1)
                message = (
                    self.event_to_entity[role_index](event_state)
                    * weight.unsqueeze(-1)
                )

                aggregate.index_add_(0, ids, message)
                denominator.index_add_(0, ids, weight.unsqueeze(-1))

            entity_input = self.dropout(
                aggregate / torch.clamp(denominator, min=1.0)
            )
            proposed_state = self.entity_update(entity_input, entity_state)
            entity_state = torch.where(denominator > 0, proposed_state, entity_state)

        embedding = F.normalize(event_state, dim=-1)
        return {
            "embedding": embedding,
            "score": self.scorer(embedding).squeeze(-1),
            "entity_state": entity_state,
        }

    def predict_recurrence(
        self,
        entity_ids: torch.Tensor,
        entity_state: torch.Tensor,
        target_year_normalized: float,
    ) -> torch.Tensor:
        time_query = self.encode_time(target_year_normalized, entity_state.device)
        time_query = time_query.unsqueeze(0).expand(len(entity_ids), -1)
        logits = self.next_year_head(
            torch.cat([entity_state[entity_ids], time_query], dim=-1)
        ).squeeze(-1)
        return torch.sigmoid(logits)