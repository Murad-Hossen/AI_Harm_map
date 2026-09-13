from __future__ import annotations
import json,re
from collections import defaultdict
from typing import Any
import numpy as np
from ai_harm_map.constants import ROLES,MISSING_TEXT

def clean(v:Any)->str:return "" if v is None else str(v).strip()
def graph_text(v:Any)->str:
    return json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list)) else clean(v)
def year_from(v:Any)->int:
    m=re.search(r"\b(?:19|20)\d{2}\b",clean(v)); return int(m.group()) if m else 0

def prepare_graph(events,validation_fraction=.15,test_fraction=.15):
    rows=[]
    for e in events:
        values={r:graph_text(e.get(r)) or MISSING_TEXT for r in ROLES}
        rows.append({"event_id":clean(e.get("event_id") or e.get("report_id")),"report_id":clean(e.get("report_id")),"values":values,"raw_year":year_from(e.get("event_date") or e.get("publication_date")),"provenance":float(e.get("confidence",1.0) or 0.0)})
    dated=sorted([r for r in rows if r["raw_year"]>0],key=lambda x:(x["raw_year"],x["event_id"]))
    undated=[r for r in rows if r["raw_year"]<=0]
    n=len(dated)
    n_test=max(1,int(round(n*test_fraction))) if n>=3 else 0
    n_val=max(1,int(round(n*validation_fraction))) if n>=5 else 0
    n_train=max(1,n-n_val-n_test) if n else len(undated)
    train=dated[:n_train]+undated
    validation=dated[n_train:n_train+n_val]
    test=dated[n_train+n_val:]
    vocab={r:{MISSING_TEXT:0} for r in ROLES}; offsets={}; total=0
    for role in ROLES:
        vals=sorted({x["values"][role] for x in rows})
        for v in vals:
            if v!=MISSING_TEXT:vocab[role][v]=len(vocab[role])
        offsets[role]=total; total+=len(vocab[role])
    def encode(split):
        out=[]
        for x in split:
            x=dict(x); x["global_ids"]=[offsets[r]+vocab[r].get(x["values"][r],0) for r in ROLES]; out.append(x)
        return out
    train,validation,test=map(encode,(train,validation,test))
    year_min=min([r["raw_year"] for r in train if r["raw_year"]>0] or [0]); year_max=max([r["raw_year"] for r in train if r["raw_year"]>0] or [year_min+1])
    scale=max(year_max-year_min,1)
    for split in (train,validation,test):
        for r in split:
            r["year"]=(r["raw_year"]-year_min)/scale if r["raw_year"]>0 else 0.0; r["year_known"]=r["raw_year"]>0
    time_mean=np.zeros(total,dtype=np.float32); time_known=np.zeros(total,dtype=np.float32); counts=np.zeros(total,dtype=np.float32)
    for r in train:
        if r["raw_year"]<=0:continue
        for role,idx in zip(ROLES,r["global_ids"]):
            time_mean[idx]+=r["year"]; counts[idx]+=1
    mask=counts>0; time_mean[mask]/=counts[mask]; time_known[mask]=1.0
    by_year=defaultdict(list)
    for r in sorted(train,key=lambda x:(x["raw_year"] or 10**9,x["event_id"])):
        if r["raw_year"]>0:by_year[r["raw_year"]].append(r)
    return {"train":train,"validation":validation,"test":test,"vocab":vocab,"offsets":offsets,"total_nodes":total,"year_min":year_min,"year_max":year_max,"time_mean":time_mean,"time_known":time_known,"train_by_year":sorted(by_year.items()),"all":rows}
