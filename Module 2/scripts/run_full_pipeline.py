#!/usr/bin/env python
from __future__ import annotations
import argparse, yaml
from ai_harm_map.pipeline import FullPipeline

parser=argparse.ArgumentParser(description="Run extraction -> taxonomy verification -> PHTKG")
parser.add_argument("--config",required=True)
parser.add_argument("--input",required=True)
parser.add_argument("--output",required=True)
args=parser.parse_args()
with open(args.config,encoding="utf-8") as f: config=yaml.safe_load(f)
FullPipeline(config).run(args.input,args.output)
