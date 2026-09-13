from __future__ import annotations
import argparse,yaml
from .full_pipeline import FullPipeline
p=argparse.ArgumentParser(); p.add_argument("--config",required=True); p.add_argument("--input",required=True); p.add_argument("--output",required=True)
a=p.parse_args()
with open(a.config,encoding="utf-8") as f: config=yaml.safe_load(f)
FullPipeline(config).run(a.input,a.output)
