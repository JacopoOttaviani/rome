"""Resolve every layer to a 64-bit mask per building (two u32 words) and write the layer catalogue."""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from .layers import LAYERS
from .s03_tiles import DAM


def main():
    b = gpd.read_parquet("data/buildings.parquet", columns=["identificatie", "year", "geometry"])
    c = b.geometry.centroid
    where = dict(zip(b.identificatie.str.slice(-16), zip((c.x - DAM[0]).round(1), (-(c.y - DAM[1])).round(1))))
    bag = b.identificatie.str.slice(-16)
    mask = np.zeros(len(b), dtype=np.uint64)
    catalogue, bit = [], 0
    for L in LAYERS:
        members = L["source_fn"]()
        # A source returns {pand: group} or {pand: (group, note)}; notes carry the story behind a building.
        notes = {p: v[1] for p, v in members.items() if isinstance(v, tuple)}
        members = {p: (v[0] if isinstance(v, tuple) else v) for p, v in members.items()}
        groups = []
        for key, label in L["groups"]:
            hit = bag.map(lambda k: members.get(k) == key).to_numpy(bool)
            mask[hit] |= np.uint64(1) << np.uint64(bit)
            years = b.year[hit].value_counts().sort_index()
            groups.append(dict(key=key, label=label, bit=bit, count=int(hit.sum()),
                               years={str(int(y)): int(n) for y, n in years.items()}))
            bit += 1
        assert bit <= 64, "out of layer bits"
        meta = {k: v for k, v in L.items() if k not in ("source_fn", "groups", "source")}
        in_city = set(bag)
        meta.update(source=dict(label=L["source"][0], url=L["source"][1]), groups=groups,
                    count=sum(g["count"] for g in groups),
                    notes={p: dict(n, at=where[p]) if n.get("name") else n for p, n in notes.items() if p in in_city})
        catalogue.append(meta)
        print(f'{L["id"]:20s}', {g["key"]: g["count"] for g in groups})
    out = pd.DataFrame({"identificatie": b.identificatie,
                        "lay0": (mask & np.uint64(0xFFFFFFFF)).astype(np.uint32),
                        "lay1": (mask >> np.uint64(32)).astype(np.uint32)})
    out.to_parquet("data/layers.parquet")
    Path("web/data/layers.json").write_text(json.dumps(catalogue, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
