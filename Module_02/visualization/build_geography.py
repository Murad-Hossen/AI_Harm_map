"""Rebuild the borderless land layer and country display anchors (requires shapely)."""
import json
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import polylabel, unary_union
from shapely.validation import make_valid

root = Path(__file__).parent
sample = json.loads((root / "data.js").read_text().removeprefix("window.MAP_SAMPLE = ").strip().removesuffix(";"))
needed = {record["k"] for record in sample["records"]}
geometries, anchors = [], {}
for feature in sample["countries"]["features"]:
    geometry = make_valid(shape(feature["geometry"]))
    geometries.append(geometry)
    country = feature["properties"]["Country"]
    if country in needed:
        polygons = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
        mainland = max(polygons, key=lambda polygon: polygon.area)
        point = polylabel(mainland, tolerance=0.02)
        assert geometry.covers(point), country
        anchors[country] = [point.y, point.x]

assert set(anchors) == needed, "Every country with reports must have a display anchor"
land = unary_union(geometries)
assert land.is_valid
payload = {"land": {"type": "Feature", "properties": {}, "geometry": mapping(land)}, "anchors": anchors}
(root / "geography.js").write_text("window.MAP_GEOGRAPHY = " + json.dumps(payload, separators=(",", ":")) + ";\n")
print(f"Dissolved {len(geometries)} country geometries; validated {len(anchors)} country display anchors.")
