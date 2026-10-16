"""Rome's named streets, squares and paths for the search box: where each one runs, and its postcode.

Source: OpenStreetMap (ODbL), fetched by s00_fetch_osm (search_streets, postcodes), clipped to the comune. A street's
ways are merged by name; ways of the same name more than CLUSTER metres apart are told apart as different streets
(Rome has a few names twice, in Acilia or Ostia and in the city), each with the postcode most of its addresses carry,
so the search can show which is which. OpenStreetMap mostly spells a closing ordinal out ("Corso Vittorio Emanuele
Secondo") and sometimes not ("… II"): the two are one street, under the numeral when a way uses it. The line is
simplified to a couple of metres, enough to draw it on the map.

web/data/streets.json: [[name, cap, rank, x, z, r, [part, …]], …], metres in the viewer's frame. (x, z) is a point on
the street near its middle, the pin; r is half its extent, how far back the camera flies; rank is 3 for the main roads,
2 for the secondary ones and squares, 1 for the residential streets, 0 for service roads, footpaths and steps. Each
part is a line as [x0 - x, z0 - z, x1 - x0, z1 - z0, …]. Main roads first, then the longest.
"""
import json
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely
from scipy.spatial import cKDTree
from shapely.geometry import MultiLineString, Polygon
from shapely.ops import nearest_points

from .city import CRS, ORIGIN
from .s09_postcodes import CAPS

CLUSTER = 1200.0
SIMPLIFY = 2.0
RANK = {**dict.fromkeys(["motorway", "trunk", "primary", "motorway_link", "trunk_link", "primary_link"], 3),
        **dict.fromkeys(["secondary", "tertiary", "secondary_link", "tertiary_link", "square"], 2),
        **dict.fromkeys(["residential", "unclassified", "living_street", "pedestrian", "road"], 1)}


ORDINALS = {"Primo": "I", "Secondo": "II", "Terzo": "III", "Quarto": "IV", "Quinto": "V", "Sesto": "VI", "Settimo": "VII",
            "Ottavo": "VIII", "Nono": "IX", "Decimo": "X", "Undicesimo": "XI", "Dodicesimo": "XII", "Tredicesimo": "XIII",
            "Quattordicesimo": "XIV", "Quindicesimo": "XV", "Sedicesimo": "XVI", "Ventitreesimo": "XXIII"}


def numeral(name):
    """The name with a closing ordinal as a Roman numeral: what the spelled and the numeral forms have in common."""
    head, _, last = name.rpartition(" ")
    return f"{head} {ORDINALS[last]}" if head and last in ORDINALS else name


def local(geom):
    return shapely.transform(geom, lambda c: np.c_[c[:, 0] - ORIGIN[0], -(c[:, 1] - ORIGIN[1])])


def lines_of(geom):
    return [g for g in getattr(geom, "geoms", [geom]) if g.geom_type in ("LineString", "LinearRing") and g.length > 0]


def clusters(parts):
    """Ways of one name grouped by distance: each group is one street."""
    if len(parts) == 1:
        return [parts]
    zones = shapely.union_all(shapely.buffer(parts, CLUSTER / 2))
    zones = getattr(zones, "geoms", [zones])
    if len(zones) == 1:
        return [parts]
    groups = [[] for _ in zones]
    for p in parts:
        groups[next(i for i, z in enumerate(zones) if z.intersects(p))].append(p)
    return [g for g in groups if g]


def main():
    outline = gpd.read_parquet("data/outline.parquet").geometry.iloc[0]
    s = gpd.read_parquet("data/raw/osm/search_streets.parquet").to_crs(CRS)
    s = s[s.intersects(outline)].copy()
    s["geometry"] = s.geometry.intersection(outline)
    s["geometry"] = local(s.geometry.values)

    # Addresses with a postcode, by the street they are on.
    a = gpd.read_parquet("data/raw/osm/postcodes.parquet").to_crs(CRS)
    a = a[a.cap.isin(CAPS)]
    axz = np.c_[a.geometry.x - ORIGIN[0], -(a.geometry.y - ORIGIN[1])]
    near_any = cKDTree(axz)
    by_street = {}
    for street, idx in a.reset_index(drop=True).groupby(a.street.str.lower().values).groups.items():
        by_street[street] = (axz[idx], a.cap.values[idx])

    out = []
    s["length"] = s.geometry.length
    for _, ways in s.groupby(s.name.map(numeral)):
        # Under the numeral if a way is named so, else under the spelling that covers most of the street.
        names = ways.groupby("name")["length"].sum()
        name = numeral(names.index[0]) if numeral(names.index[0]) in names.index else names.idxmax()
        rank = max(RANK.get(h, 0) for h in ways.highway)
        square = (ways.highway == "square").all()
        parts = [p for g in ways.geometry for p in lines_of(g)]
        for group in clusters(parts):
            merged = shapely.line_merge(MultiLineString([list(p.coords) for p in group]))
            lines = [l.simplify(SIMPLIFY) for l in lines_of(merged)]
            geom = MultiLineString(lines)
            x0, z0, x1, z1 = geom.bounds
            if square:
                mid = Polygon(max(lines, key=lambda l: l.length).coords).representative_point()
            else:
                mid = nearest_points(geom, shapely.Point((x0 + x1) / 2, (z0 + z1) / 2))[0]
            cx, cz = round(mid.x), round(mid.y)
            # The postcode most of this street's own addresses carry, else that of the addresses around its middle.
            cap = ""
            own = [by_street[n.lower()] for n in names.index if n.lower() in by_street]
            if own:
                d = shapely.distance(geom, shapely.points(np.concatenate([o[0] for o in own])))
                caps = np.concatenate([o[1] for o in own])[d < 400]
                if len(caps):
                    cap = Counter(caps).most_common(1)[0][0]
            if not cap:
                near = near_any.query_ball_point((cx, cz), 600)
                if near:
                    cap = Counter(a.cap.values[near]).most_common(1)[0][0]
            enc = []
            for l in lines:
                c = np.rint(np.asarray(l.coords)).astype(int)
                c = c[np.r_[True, (np.diff(c, axis=0) != 0).any(axis=1)]]
                d = np.r_[[c[0] - (cx, cz)], np.diff(c, axis=0)]
                enc.append(d.ravel().tolist())
            r = max(30, round(np.hypot(x1 - x0, z1 - z0) / 2))
            out.append((rank, geom.length, [name, cap, rank, cx, cz, r, enc]))
    out.sort(key=lambda e: (-e[0], -e[1]))
    path = Path("web/data/streets.json")
    path.write_text(json.dumps([e[2] for e in out], ensure_ascii=False, separators=(",", ":")))
    names = Counter(e[2][0] for e in out)
    print(len(out), "streets,", len(names), "names,", sum(n > 1 for n in names.values()), "names on more than one street;",
          sum(not e[2][1] for e in out), "without a postcode;", path.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
