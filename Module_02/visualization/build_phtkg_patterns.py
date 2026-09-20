#!/usr/bin/env python3
"""Export real PHTKG representations and a compact map-facing pattern index."""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT / "src"))

from ai_harm_map.models.phtkg import PHTKG, PHTKGConfig  # noqa: E402

EMPTY = "__EMPTY__"
SEED = 42
MIN_PATTERN_SIZE = 5
COARSE_K_POINTS = 18
KMEANS_N_INIT = 20


def clean(value):
    return "" if value is None else str(value).strip()


def normalize(value):
    return " ".join(re.sub(r"[^\w\s]", " ", clean(value).casefold()).split())


def graph_text(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return clean(value)


def year_from(value):
    match = re.search(r"\b(?:19|20)\d{2}\b", clean(value))
    return int(match.group(0)) if match else 0


def role_values(event):
    return {
        "organization": clean(event.get("organization")) or EMPTY,
        "ai_system": clean(event.get("ai_system")) or EMPTY,
        "affected_group": clean(event.get("affected_group")) or EMPTY,
        "action": clean(event.get("action")) or EMPTY,
        "harm_category": graph_text(event.get("harm_category")) or EMPTY,
        "consequence": clean(event.get("consequence")) or EMPTY,
        "location": clean(event.get("location")) or EMPTY,
    }


def training_split(rows):
    dated = sorted((r for r in rows if r["raw_year"]), key=lambda r: (r["raw_year"], r["event_id"]))
    undated = [r for r in rows if not r["raw_year"]]
    if len(dated) < 8:
        dated = list(rows)
        random.Random(SEED).shuffle(dated)
        undated = []
    test_n = max(1, round(len(dated) * 0.15))
    val_n = max(1, round(len(dated) * 0.15))
    return dated[: len(dated) - val_n - test_n] + undated


def encode(events, roles, vocab, offsets, year_min, year_max):
    rows = []
    unknown = Counter()
    for event in events:
        values = role_values(event)
        ids = []
        for role in roles:
            value = normalize(values[role]) or EMPTY
            if value not in vocab[role]:
                unknown[role] += 1
            ids.append(offsets[role] + vocab[role].get(value, 0))
        raw_year = year_from(event.get("event_date"))
        rows.append({
            "event_id": clean(event["report_id"]),
            "global_ids": ids,
            "year": (raw_year - year_min) / max(1, year_max - year_min) if raw_year else 0.0,
            "known": float(bool(raw_year)),
            "raw_year": raw_year,
            "provenance": float(np.clip(float(event.get("confidence", 0.5)), 0.0, 1.0)),
        })
    return rows, unknown


def tensors(rows):
    return (
        torch.tensor([r["global_ids"] for r in rows], dtype=torch.long),
        torch.tensor([r["year"] for r in rows], dtype=torch.float32),
        torch.tensor([r["known"] for r in rows], dtype=torch.float32),
        torch.tensor([r["provenance"] for r in rows], dtype=torch.float32),
    )


def time_context(rows, total_nodes, role_count):
    ids, years, known, _ = tensors(rows)
    sums = torch.zeros(total_nodes)
    counts = torch.zeros(total_nodes)
    for role_index in range(role_count):
        role_ids = ids[:, role_index]
        sums.index_add_(0, role_ids, years * known)
        counts.index_add_(0, role_ids, known)
    return sums / torch.clamp(counts, min=1.0), (counts > 0).float()


def cluster_embeddings(embeddings):
    n_events = len(embeddings)
    max_k = min(n_events - 1, max(2, n_events // MIN_PATTERN_SIZE))
    coarse_ks = sorted(set(np.linspace(2, max_k, num=min(COARSE_K_POINTS, max_k - 1), dtype=int)))
    results = {}

    def fit(k):
        if k in results:
            return
        km = KMeans(n_clusters=k, random_state=SEED, n_init=KMEANS_N_INIT, algorithm="lloyd")
        labels = km.fit_predict(embeddings)
        counts = np.bincount(labels, minlength=k)
        results[k] = {
            "labels": labels,
            "centers": km.cluster_centers_,
            "silhouette": float(silhouette_score(embeddings, labels, metric="euclidean")),
            "valid": int(counts.min()) >= MIN_PATTERN_SIZE,
        }

    for k in coarse_ks:
        fit(k)
    candidates = [k for k in coarse_ks if results[k]["valid"]] or coarse_ks
    coarse_best = max(candidates, key=lambda k: results[k]["silhouette"])
    position = coarse_ks.index(coarse_best)
    left = coarse_ks[max(0, position - 1)]
    right = coarse_ks[min(len(coarse_ks) - 1, position + 1)]
    for k in range(left, right + 1):
        fit(k)
    candidates = [k for k, result in results.items() if result["valid"]] or list(results)
    chosen = max(candidates, key=lambda k: results[k]["silhouette"])
    return chosen, results[chosen]["labels"], results[chosen]["centers"], results[chosen]["silhouette"]


def harm_label(event):
    categories = event.get("harm_category") or []
    if isinstance(categories, dict):
        categories = [categories]
    for category in categories:
        if isinstance(category, dict):
            label = clean(category.get("subcategory"))
            if label:
                label = re.sub(r"\s*/\s*", " and ", label)
                label = re.sub(r"\s+harm$", "", label, flags=re.IGNORECASE)
                label = re.sub(r"information hazard$", "information hazards", label, flags=re.IGNORECASE)
                return label
    return "Mixed AI harms"


def display_attribute(value):
    if value.casefold() == "ai chatbot":
        return "AI chatbots"
    return value


def common_values(events, field, limit=2):
    values = [clean(event.get(field)) for event in events]
    return [value for value, _ in Counter(v for v in values if v and v != EMPTY).most_common(limit)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=MODULE_ROOT / "data/releases/ground_truth_annotated.json")
    parser.add_argument("--checkpoint", type=Path, default=MODULE_ROOT / "checkpoints/gold_phtkg.pt")
    parser.add_argument("--output", type=Path, default=MODULE_ROOT / "results/phtkg/phtkg_learned_representations.json")
    parser.add_argument("--browser-output", type=Path, default=Path(__file__).with_name("phtkg_patterns.js"))
    args = parser.parse_args()

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    events = json.loads(args.input.read_text(encoding="utf-8"))
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    roles = checkpoint["roles"]
    config = checkpoint["phtkg_config"]
    state = checkpoint["model_state_dict"]
    total_nodes = int(state["entity_embeddings.weight"].shape[0])
    model = PHTKG(total_nodes, PHTKGConfig(
        embedding_dim=int(config["EMBEDDING_DIM"]),
        layers=int(config["LAYERS"]),
        dropout=float(config["DROPOUT"]),
    ))
    model.load_state_dict(state, strict=True)
    model.eval()

    rows, unknown = encode(events, roles, checkpoint["vocab"], checkpoint["offsets"], checkpoint["year_min"], checkpoint["year_max"])
    train_rows = training_split(rows)
    if "time_mean" in checkpoint and "time_known" in checkpoint:
        time_mean, time_known = checkpoint["time_mean"], checkpoint["time_known"]
    else:
        time_mean, time_known = time_context(train_rows, total_nodes, len(roles))
    ids, years, known, provenance = tensors(rows)
    initial_state = checkpoint.get("final_entity_state", model.entity_embeddings.weight.detach())
    with torch.inference_mode():
        output = model(ids, years, known, provenance, time_mean, time_known, entity_state_init=initial_state)
    embeddings = output["embedding"].cpu().numpy()
    embeddings /= np.clip(np.linalg.norm(embeddings, axis=1, keepdims=True), 1e-12, None)
    scores = torch.sigmoid(output["score"]).cpu().numpy()

    pattern_count, labels, centers, silhouette = cluster_embeddings(embeddings)
    centers /= np.clip(np.linalg.norm(centers, axis=1, keepdims=True), 1e-12, None)
    similarities = embeddings @ centers.T
    logits = similarities / 0.10
    logits -= logits.max(axis=1, keepdims=True)
    probabilities = np.exp(logits)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    pairwise = embeddings @ embeddings.T

    clusters = defaultdict(list)
    for index, label in enumerate(labels):
        clusters[int(label)].append(index)
    cluster_meta = {}
    for label, indices in clusters.items():
        members = [events[i] for i in indices]
        years_present = [year_from(event.get("event_date")) for event in members if year_from(event.get("event_date"))]
        top_harm = Counter(harm_label(event) for event in members).most_common(1)[0][0]
        common = []
        for field in ("ai_system", "affected_group"):
            values = common_values(members, field, 1)
            if values:
                common.append(display_attribute(values[0]))
        cluster_meta[label] = {
            "label": top_harm,
            "report_count": len(indices),
            "location_count": len({clean(event.get("location")) for event in members if clean(event.get("location"))}),
            "year_start": min(years_present) if years_present else None,
            "year_end": max(years_present) if years_present else None,
            "common_elements": common[:3],
        }

    learned = []
    browser = {}
    for i, (event, row) in enumerate(zip(events, rows)):
        label = int(labels[i])
        assigned = int(np.argmax(probabilities[i]))
        ranking = [int(j) for j in np.argsort(-pairwise[i]) if int(j) != i][:5]
        representation = {
            "report_id": row["event_id"],
            "event_embedding": [round(float(value), 6) for value in embeddings[i]],
            "phtkg_event_score": round(float(scores[i]), 6),
            "pattern_assignment": f"pattern_{assigned + 1}",
            "pattern_probability": round(float(probabilities[i, assigned]), 6),
            "novelty_score": round(float(np.clip(1 - ((similarities[i].max() + 1) / 2), 0, 1)), 6),
            "similar_events": [{"report_id": rows[j]["event_id"], "similarity": round(float(pairwise[i, j]), 6)} for j in ranking],
        }
        learned.append(representation)
        meta = cluster_meta[label]
        browser[row["event_id"]] = {
            "pattern": representation["pattern_assignment"],
            "label": meta["label"],
            "confidence": representation["pattern_probability"],
            "reports": meta["report_count"],
            "locations": meta["location_count"],
            "yearStart": meta["year_start"],
            "yearEnd": meta["year_end"],
            "common": meta["common_elements"],
            "similar": [item["report_id"] for item in representation["similar_events"][:3]],
        }

    payload = {
        "metadata": {
            "source": str(args.input.relative_to(MODULE_ROOT)),
            "checkpoint": str(args.checkpoint.relative_to(MODULE_ROOT)),
            "report_count": len(events),
            "pattern_count": pattern_count,
            "silhouette": round(silhouette, 6),
            "embedding_dimension": embeddings.shape[1],
            "unknown_role_values": dict(unknown),
            "method": "fixed-checkpoint PHTKG inference followed by repository coarse-to-fine KMeans",
        },
        "events": learned,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.browser_output.write_text(
        "window.PHTKG_PATTERNS = " + json.dumps(browser, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["metadata"], indent=2))
    print(f"Wrote {args.output}")
    print(f"Wrote {args.browser_output}")


if __name__ == "__main__":
    main()
