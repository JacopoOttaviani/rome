"""Rome's postcodes (CAP) for the search box: where each one's addresses are, and how far they spread.

Source: the addresses OpenStreetMap (ODbL) tags with a postcode, fetched by s00_fetch_osm. Rome has no open map of
its postcode areas, so a CAP is placed at the middle (the median) of its addresses, after setting aside the few
that sit far from the rest (a typo, or a building that is in another CAP). The spread is how far out the closest
80% of them reach: the viewer flies far enough back to take it in.

web/data/postcodes.json: {"00153": [x, z, spread, addresses], …}, metres in the viewer's frame.
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np

from .city import ORIGIN, TO_UTM

# Rome's CAPs as Poste Italiane assigns them, with 00120 for the Vatican City.
CAPS = ["00118", "00119", "00120"] + [f"001{d}{u}" for d in range(2, 10) for u in range(1, 10) if (d, u) != (2, 9)]
MIN_ADDRESSES = 10


def main():
    a = gpd.read_parquet("data/raw/osm/postcodes.parquet")
    x, y = TO_UTM.transform(a.geometry.x.to_numpy(), a.geometry.y.to_numpy())
    a["x"], a["z"] = x - ORIGIN[0], -(y - ORIGIN[1])
    out, few = {}, []
    for cap in CAPS:
        p = a.loc[a.cap == cap, ["x", "z"]].to_numpy()
        if len(p) < MIN_ADDRESSES:
            few.append(f"{cap} ({len(p)})")
            continue
        mid = np.median(p, axis=0)
        d = np.hypot(*(p - mid).T)
        keep = p[d <= max(4 * np.median(d), 1000)]
        mid = np.median(keep, axis=0)
        spread = np.percentile(np.hypot(*(keep - mid).T), 80)
        out[cap] = [round(float(mid[0])), round(float(mid[1])), round(float(spread)), int(len(keep))]
    Path("web/data/postcodes.json").write_text(json.dumps(out, separators=(",", ":")))
    print(len(out), "postcodes from", sum(v[3] for v in out.values()), "addresses;",
          "too few addresses:", ", ".join(few) or "none")


if __name__ == "__main__":
    main()
