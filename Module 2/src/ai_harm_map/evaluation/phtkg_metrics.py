from __future__ import annotations
import numpy as np

def paired_auc(positive,negative):
    n=min(len(positive),len(negative))
    if n==0:return float("nan")
    p=np.asarray(positive)[:n]; q=np.asarray(negative)[:n]
    return float(np.mean((p>q)+0.5*(p==q)))
