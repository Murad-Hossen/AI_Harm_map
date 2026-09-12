from __future__ import annotations
import random
import torch
from ai_harm_map.constants import ROLES

def corrupt_same_role(global_ids,vocab,offsets,copies=1,seed=42,real_signatures=None):
    rng=random.Random(seed); negatives=[]
    real_signatures=real_signatures or set()
    for row in global_ids.tolist():
        role_order=list(range(len(ROLES))); rng.shuffle(role_order)
        for _ in range(copies):
            chosen=None
            best_effort=None 
            for role in role_order:
                candidate=row.copy(); options=list(range(1,len(vocab[ROLES[role]])))
                if not options: continue
                original=candidate[role]-offsets[ROLES[role]]
                options=[x for x in options if x!=original]
                rng.shuffle(options)
                for local in options:
                    candidate[role]=offsets[ROLES[role]]+local
                    if best_effort is None: best_effort=candidate.copy()
                    if tuple(candidate) not in real_signatures:
                        chosen=candidate.copy(); break
                if chosen is not None: break
            if chosen is None:
                chosen=best_effort if best_effort is not None else row.copy()
            negatives.append(chosen)
    return torch.tensor(negatives,dtype=torch.long,device=global_ids.device) if negatives else torch.empty((0,global_ids.shape[1]),dtype=torch.long,device=global_ids.device)