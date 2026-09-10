from __future__ import annotations

import torch
import torch.nn as nn


class PairwiseBaseline(nn.Module):
    """Typed DistMult scorer over all role pairs in an event."""

    def __init__(self, total_nodes: int, n_roles: int, embedding_dim: int = 64):
        super().__init__()
        self.entity = nn.Embedding(total_nodes, embedding_dim)
        self.relation = nn.Embedding(n_roles * n_roles, embedding_dim)
        self.n_roles = n_roles

    def forward(self, global_ids: torch.Tensor) -> torch.Tensor:
        h = self.entity(global_ids)
        batch_size, n_roles, dim = h.shape

        left = h.unsqueeze(2).expand(batch_size, n_roles, n_roles, dim)
        right = h.unsqueeze(1).expand(batch_size, n_roles, n_roles, dim)

        relation_ids = torch.arange(n_roles * n_roles, device=h.device).view(
            n_roles, n_roles
        )

        relations = self.relation(relation_ids).unsqueeze(0)
        relations = relations.expand(batch_size, n_roles, n_roles, dim)

        return (left * relations * right).sum(-1).mean(dim=(1, 2))