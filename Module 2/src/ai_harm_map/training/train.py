from __future__ import annotations
import copy,random
import numpy as np
import torch
from torch.optim import AdamW
from ai_harm_map.constants import ROLES
from ai_harm_map.models.phtkg import PHTKG,PHTKGConfig
from .corruption import corrupt_same_role
from .graph import prepare_graph
from .loss import observed_vs_corrupted_loss

def to_tensors(rows,device):
    ids=torch.tensor([r["global_ids"] for r in rows],dtype=torch.long,device=device)
    years=torch.tensor([r["year"] for r in rows],dtype=torch.float32,device=device)
    known=torch.tensor([float(r["year_known"]) for r in rows],dtype=torch.float32,device=device)
    prov=torch.tensor([r["provenance"] for r in rows],dtype=torch.float32,device=device)
    return ids,years,known,prov

def real_signatures(graph):return {tuple(r["global_ids"]) for split in ("train","validation","test") for r in graph[split]}

def evaluate(model,graph,rows,device,draws=3):
    if not rows:return {"count":0,"paired_auc":float("nan")}
    ids,years,known,prov=to_tensors(rows,device); tm=torch.tensor(graph["time_mean"],device=device); tk=torch.tensor(graph["time_known"],device=device)
    model.eval(); wins=[]
    with torch.inference_mode():
        pos=model(ids,years,known,prov,tm,tk)["score"]
        sig=real_signatures(graph)
        for d in range(draws):
            neg_ids=corrupt_same_role(ids,graph["vocab"],graph["offsets"],1,seed=1000+d,real_signatures=sig)
            if len(neg_ids)==0:continue
            neg=model(neg_ids,years[:len(neg_ids)] if len(neg_ids)<=len(years) else years.repeat((len(neg_ids)+len(years)-1)//len(years))[:len(neg_ids)],known[:len(neg_ids)] if len(neg_ids)<=len(known) else known.repeat((len(neg_ids)+len(known)-1)//len(known))[:len(neg_ids)],prov[:len(neg_ids)] if len(neg_ids)<=len(prov) else prov.repeat((len(neg_ids)+len(prov)-1)//len(prov))[:len(neg_ids)],tm,tk)["score"]
            n=min(len(pos),len(neg)); wins.append(float((pos[:n]>neg[:n]).float().mean().item()))
    return {"count":len(rows),"paired_auc":float(np.mean(wins)) if wins else float("nan"),"paired_auc_std":float(np.std(wins)) if wins else float("nan")}

def train_phtkg(events,config=None,device=None,seed=42):
    cfg=config or {}; random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    graph=prepare_graph(events,cfg.get("validation_fraction",.15),cfg.get("test_fraction",.15))
    device=torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    mc=PHTKGConfig(embedding_dim=int(cfg.get("embedding_dim",64)),layers=int(cfg.get("layers",2)),dropout=float(cfg.get("dropout",.1)))
    model=PHTKG(graph["total_nodes"],mc).to(device); opt=AdamW(model.parameters(),lr=float(cfg.get("learning_rate",1e-3)),weight_decay=float(cfg.get("weight_decay",3e-4)))
    tm=torch.tensor(graph["time_mean"],device=device); tk=torch.tensor(graph["time_known"],device=device); epochs=int(cfg.get("epochs",120)); negatives=int(cfg.get("negatives",6)); patience=int(cfg.get("patience",25)); clip=float(cfg.get("grad_clip",1.5)); sig=real_signatures(graph)
    best=None; best_auc=-1; wait=0; history=[]; state=None
    for epoch in range(1,epochs+1):
        model.train(); total=0.0
        for year,bucket in graph["train_by_year"]:
            ids,years,known,prov=to_tensors(bucket,device)
            out=model(ids,years,known,prov,tm,tk,entity_state_init=state)
            state=out["entity_state"].detach()
            neg_ids=corrupt_same_role(ids,graph["vocab"],graph["offsets"],negatives,seed=seed+epoch,real_signatures=sig)
            if len(neg_ids):
                neg=model(neg_ids,years.repeat((len(neg_ids)+len(years)-1)//len(years))[:len(neg_ids)],known.repeat((len(neg_ids)+len(known)-1)//len(known))[:len(neg_ids)],prov.repeat((len(neg_ids)+len(prov)-1)//len(prov))[:len(neg_ids)],tm,tk,entity_state_init=state)["score"]
                loss=observed_vs_corrupted_loss(out["score"],neg)
                opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),clip); opt.step(); total+=float(loss.item())
        val=evaluate(model,graph,graph["validation"],device)
        history.append({"epoch":epoch,"loss":total,"validation_paired_auc":val["paired_auc"]})
        if val["paired_auc"]==val["paired_auc"] and val["paired_auc"]>best_auc:
            best_auc=val["paired_auc"]; best=copy.deepcopy(model.state_dict()); wait=0
        else: wait+=1
        if wait>=patience:break
    if best is not None:model.load_state_dict(best)
    metrics={"validation":evaluate(model,graph,graph["validation"],device),"test":evaluate(model,graph,graph["test"],device)}
    return model,graph,history,metrics,state
