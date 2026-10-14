"""Resolve every layer to a 64-bit mask per building (two u32 words) and write the layer catalogue."""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from .city import ORIGIN
from .i18n_it import IT
from .layers import LAYERS


def main():
    b = gpd.read_parquet("data/buildings.parquet", columns=["id", "year", "geometry"])
    c = b.geometry.centroid
    where = dict(zip(b.id, zip((c.x - ORIGIN[0]).round(1), (-(c.y - ORIGIN[1])).round(1))))
    ids = b.id
    mask = np.zeros(len(b), dtype=np.uint64)
    catalogue, bit = [], 0
    for L in LAYERS:
        members = L["source_fn"]()
        # A source returns {building: group} or {building: (group, note)}; notes carry the story behind a building.
        # ... or {building: [(group, note), ...]} when a building belongs to several groups of the layer.
        notes, groups_of = {}, {}
        for p, v in members.items():
            for item in (v if isinstance(v, list) else [v]):
                g, n = item if isinstance(item, tuple) else (item, None)
                groups_of.setdefault(p, set()).add(g)
                if n and p not in notes:
                    notes[p] = n
        members = groups_of
        groups = []
        for key, label in L["groups"]:
            hit = ids.map(lambda k: key in members.get(k, ())).to_numpy(bool)
            mask[hit] |= np.uint64(1) << np.uint64(bit)
            years = b.year[hit].value_counts().sort_index()
            groups.append(dict(key=key, label=label, bit=bit, count=int(hit.sum()),
                               years={str(int(y)): int(n) for y, n in years.items()}))
            bit += 1
        assert bit <= 64, "out of layer bits"
        meta = {k: v for k, v in L.items() if k not in ("source_fn", "groups", "source")}
        in_city = set(ids)
        meta.update(source=dict(label=L["source"][0], url=L["source"][1]), groups=groups,
                    count=sum(g["count"] for g in groups),
                    notes={p: dict(n, at=where[p]) if n.get("name") else n for p, n in notes.items() if p in in_city})
        catalogue.append(meta)
        print(f'{L["id"]:12s}', {g["key"]: g["count"] for g in groups}, f"{len(meta['notes'])} named")
    out = pd.DataFrame({"id": b.id,
                        "lay0": (mask & np.uint64(0xFFFFFFFF)).astype(np.uint32),
                        "lay1": (mask >> np.uint64(32)).astype(np.uint32)})
    out.to_parquet("data/layers.parquet")
    # Italian next to English for every text the dictionary knows; list the rest so they get translated.
    missing = set()

    def it(obj, *keys):
        for k in keys:
            v = obj.get(k)
            if v and f"{k}_it" not in obj:
                if v in IT:
                    obj[f"{k}_it"] = IT[v]
                else:
                    missing.add(v)
    for L in catalogue:
        it(L, "section", "title", "era", "text", "caveat")
        it(L["source"], "label")
        for g in L["groups"]:
            it(g, "label")
    if missing:
        print(f"{len(missing)} texts without Italian:", *sorted(missing)[:20], sep="\n  ")
    Path("web/data/layers.json").write_text(json.dumps(catalogue, ensure_ascii=False, separators=(",", ":")))
    print(f"layers.json {Path('web/data/layers.json').stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
