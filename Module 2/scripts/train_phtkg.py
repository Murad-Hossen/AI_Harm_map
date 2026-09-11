#!/usr/bin/env python
from __future__ import annotations
import argparse,yaml
from ai_harm_map.io import load_json_or_jsonl
from ai_harm_map.training import train_phtkg

parser=argparse.ArgumentParser(description="Train PHTKG on structured events")
parser.add_argument("--input",required=True)
parser.add_argument("--config",required=True)
args=parser.parse_args()
with open(args.config,encoding="utf-8") as f: config=yaml.safe_load(f)
train_phtkg(load_json_or_jsonl(args.input),config.get("phtkg",{}))
