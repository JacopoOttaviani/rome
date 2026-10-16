"""Pack buildings into 600 m binary tiles + a city config JSON.

Local frame: metres from Piazza Venezia, x east, z south (three.js, y up).
Tile layout (little-endian, every section 4-byte aligned):
  header  u32 magic, nB, nP, nR, nV; f32 originX, originZ
  B       u32 gid[nB]; i16 year[nB]; u8 flag[nB]; u8 period[nB]; u8 floors[nB]; u8 use[nB] (see uses.py);
          u32 lay0[nB]; u32 lay1[nB] (layer bits, see s05_layers); u32 partStart[nB+1]
  P       f32 height[nP]; u32 ringStart[nP+1]
  R       u32 vertStart[nR+1]; u8 hole[nR]
  V       i16 xz[2*nV], decimetres from the tile origin
"""
import json
import struct
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from .city import ORIGIN
from .periods import PERIODS
from .uses import USES, use_of

TILE = 600.0
SIMPLIFY = 0.25
OUT = Path("web/data")
MAGIC = 0x33424241  # 'ABB3', the tile format of amsterdam-by-building


def pad4(b: bytes) -> bytes:
    return b + b"\0" * (-len(b) % 4)


def to_local(coords: np.ndarray) -> np.ndarray:
    return np.c_[coords[:, 0] - ORIGIN[0], -(coords[:, 1] - ORIGIN[1])]


def rings_of(geom):
    polys = getattr(geom, "geoms", [geom])
    for poly in polys:
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        yield shapely.get_coordinates(poly.exterior)[:-1], 0
        for hole in poly.interiors:
            yield shapely.get_coordinates(hole)[:-1], 1


def pack_tile(origin, rows):
    gid, year, flag, period, floors, use, lay0, lay1, part_start = [], [], [], [], [], [], [], [], [0]
    heights, ring_start, vert_start, holes, verts = [], [0], [0], [], []
    for b in rows:
        gid.append(b["gid"]); year.append(b["year"]); flag.append(b["flag"])
        period.append(b["period"]); floors.append(b["floors"])
        lay0.append(b["lay0"]); lay1.append(b["lay1"]); use.append(b["use"])
        for h, geom in b["parts"]:
            heights.append(h)
            for ring, hole in rings_of(geom):
                if len(ring) < 3:
                    continue
                loc = (to_local(ring) - origin) * 10
                verts.append(np.round(loc).astype(np.int16))
                holes.append(hole)
                vert_start.append(vert_start[-1] + len(ring))
            ring_start.append(len(holes))
        part_start.append(len(heights))
    nB, nP, nR = len(gid), len(heights), len(holes)
    V = np.concatenate(verts) if verts else np.zeros((0, 2), np.int16)
    out = struct.pack("<5I2f", MAGIC, nB, nP, nR, len(V), *origin)
    out += pad4(np.array(gid, "<u4").tobytes())
    out += pad4(np.array(year, "<i2").tobytes())
    out += pad4(np.array(flag, "u1").tobytes())
    out += pad4(np.array(period, "u1").tobytes())
    out += pad4(np.array(floors, "u1").tobytes())
    out += pad4(np.array(use, "u1").tobytes())
    out += np.array(lay0, "<u4").tobytes() + np.array(lay1, "<u4").tobytes()
    out += pad4(np.array(part_start, "<u4").tobytes())
    out += pad4(np.array(heights, "<f4").tobytes())
    out += pad4(np.array(ring_start, "<u4").tobytes())
    out += pad4(np.array(vert_start, "<u4").tobytes())
    out += pad4(np.array(holes, "u1").tobytes())
    out += pad4(V.astype("<i2").tobytes())
    return out


def main():
    b = gpd.read_parquet("data/buildings.parquet")
    b = b.merge(pd.read_parquet("data/layers.parquet"), on="id", how="left")
    b[["lay0", "lay1"]] = b[["lay0", "lay1"]].fillna(0)
    b["use_class"] = [use_of(k, u, t) for k, u, t in zip(b.kind, b.use, b.ty)]
    q = gpd.read_parquet("data/parts.parquet")
    gid = {k: i for i, k in enumerate(b.id)}

    q = q[q.id.isin(gid)].copy()
    q["h"] = (q.UN_VOL_QE - q.ground).clip(lower=2.5).fillna(2.5)
    q["geometry"] = shapely.simplify(q.geometry.values, SIMPLIFY, preserve_topology=True)
    parts = q.groupby("id")[["h", "geometry"]].apply(lambda d: list(zip(d.h, d.geometry))).to_dict()

    c = to_local(np.c_[b.geometry.centroid.x, b.geometry.centroid.y])
    b["tx"] = np.floor(c[:, 0] / TILE).astype(int)
    b["tz"] = np.floor(c[:, 1] / TILE).astype(int)

    (OUT / "tiles").mkdir(parents=True, exist_ok=True)
    for old in (OUT / "tiles").glob("*.bin"):
        old.unlink()
    index = []
    for (tx, tz), grp in b.groupby(["tx", "tz"]):
        origin = np.array([tx * TILE, tz * TILE])
        rows = [dict(gid=gid[r.id], year=int(r.year), flag=int(r.date_flag),
                     period=int(r.period), floors=int(r.floors),
                     lay0=int(r.lay0), lay1=int(r.lay1), use=int(r.use_class), parts=parts.get(r.id, []))
                for r in grp.itertuples()]
        data = pack_tile(origin, rows)
        name = f"{tx}_{tz}.bin"
        (OUT / "tiles" / name).write_bytes(data)
        cx, cz = origin + TILE / 2
        index.append(dict(file=name, tx=int(tx), tz=int(tz), n=len(rows), bytes=len(data),
                          dist=round(float(np.hypot(cx, cz)))))
    index.sort(key=lambda t: t["dist"])

    # Bundle tiles into a few packs, nearest Piazza Venezia first, so the city loads centre-out in few requests.
    packs, n_packs = [], 8
    per = -(-len(index) // n_packs)
    for k in range(n_packs):
        chunk = index[k * per:(k + 1) * per]
        if not chunk:
            break
        name, offset, blob = f"pack{k}.bin", 0, bytearray()
        for t in chunk:
            data = (OUT / "tiles" / t["file"]).read_bytes()
            t.update(pack=name, offset=offset, length=len(data))
            blob += data; offset += len(data)
        (OUT / name).write_bytes(blob)
        packs.append(name)

    # Per-building lookup for hover and cards: id, height (dm), floors, date flag, year and the span it stands for,
    # use, period, layer bits, Wikipedia entry, centre, and where the height comes from (0 survey, 1 Wikidata,
    # 2 default, 3 OpenStreetMap, 4 the median of its neighbours).
    attrs = np.zeros(len(b), dtype=[("id", "<f8"), ("h", "<u2"), ("floors", "u1"), ("flag", "u1"), ("year", "<i2"),
                                    ("y0", "<i2"), ("y1", "<i2"), ("use", "u1"), ("period", "u1"),
                                    ("lay0", "<u4"), ("lay1", "<u4"), ("wk", "<i4"), ("x", "<f4"), ("z", "<f4"),
                                    ("hsrc", "u1"), ("pad", "u1", 3)])
    attrs["id"] = b.id.astype("int64").to_numpy()
    attrs["h"] = np.round(b.height.fillna(0) * 10).clip(0, 65535)
    attrs["floors"] = b.floors; attrs["flag"] = b.date_flag
    attrs["year"] = b.year; attrs["y0"] = b.y0; attrs["y1"] = b.y1
    attrs["use"] = b.use_class; attrs["period"] = b.period
    attrs["lay0"] = b.lay0; attrs["lay1"] = b.lay1
    wk_path = Path("data/wiki_index.parquet")
    wk = pd.read_parquet(wk_path).set_index("id").wk if wk_path.exists() else pd.Series(dtype=int)
    attrs["wk"] = b.id.map(wk).fillna(-1).astype(int)
    cen = to_local(np.c_[b.geometry.centroid.x, b.geometry.centroid.y])
    attrs["x"], attrs["z"] = cen[:, 0], cen[:, 1]
    attrs["hsrc"] = b.hsrc.map({"survey": 0, "wikidata": 1, "default": 2, "osm": 3, "neighbours": 4}).fillna(0).astype(int)
    (OUT / "attrs.bin").write_bytes(attrs.tobytes())

    years = b.year.to_numpy()
    hist = {}
    for p, y in zip(b.period, years):
        hist.setdefault(int(y), [0] * len(PERIODS))[p] += 1
    flags = b.date_flag
    config = dict(
        city="rome", label="Rome", tileSize=TILE, origin=ORIGIN,
        home=dict(x=-1100, z=-250, azimuth=340, elevation=40, span=7800),  # from the south-west, north up: Vatican to Termini
        periods=[dict(key=k, label=l, from_=a, to=bb, color=col) for k, l, a, bb, col in PERIODS],
        yearMin=int(years.min()), yearMax=int(years.max()),
        histogram={str(k): v for k, v in sorted(hist.items())},
        attrStride=attrs.dtype.itemsize,
        uses=dict(keys=[k for k, _, _ in USES], labels=[l for _, l, _ in USES], colors=[c for _, _, c in USES],
                  counts=[int((b.use_class == i).sum()) for i in range(len(USES))]),
        tiles=index,
        packs=packs,
        stats=dict(buildings=len(b), wikidata=int((flags == 0).sum()), wikidataApprox=int((flags == 1).sum()),
                   census=int((flags == 2).sum()), censusOld=int((flags == 3).sum()), estimated=int((flags == 4).sum()),
                   undated=int((flags == 5).sum()), construction=int((flags == 6).sum()),
                   ispra=int((flags == 7).sum()), ispraNew=int((flags == 8).sum()), ispraBuilt=int((flags == 10).sum()), surveyNew=int((flags == 11).sum()),
                   surveyed=int((b.kind != "osm").sum()), newer=int((b.kind == "osm").sum()),
                   residential=int(((flags == 2) | (flags == 3)).sum())),
    )
    (OUT / "rome.json").write_text(json.dumps(config, ensure_ascii=False, separators=(",", ":")).replace('"from_"', '"from"'))
    total = sum(t["bytes"] for t in index)
    print(f"{len(index)} tiles, {total/1e6:.1f} MB, attrs {attrs.nbytes/1e6:.1f} MB")


if __name__ == "__main__":
    main()
