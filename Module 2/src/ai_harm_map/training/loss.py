from __future__ import annotations
import torch
import torch.nn.functional as F

def observed_vs_corrupted_loss(pos_logits,neg_logits):
    pos=-F.logsigmoid(pos_logits).mean()
    neg=-F.logsigmoid(-neg_logits).mean()
    return 0.5*(pos+neg)
