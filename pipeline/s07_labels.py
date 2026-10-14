"""Street, square and river names, placed along their own lines.

Source: named ways from OpenStreetMap (ODbL), fetched by s00_fetch_osm. A street's ways are merged into lines;
a label goes every 350 m along each line, turned along it, where the line runs straight enough to carry it.
Squares get one label at their centre. Tier 1 (the Tiber, the Aniene and the main streets) shows from afar,
tier 2 only up close.
"""
import json
import math
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, Polygon

from .city import ORIGIN, TO_UTM

SPACING = 350.0
# Street width by OSM class, for keeping a name inside its street.
WIDTH = {"motorway": 24, "trunk": 22, "primary": 20, "secondary": 16, "tertiary": 13, "unclassified": 9,
         "residential": 9, "living_street": 7, "pedestrian": 9, "service": 6, "footway": 5, "path": 4, "steps": 4}
SKIP = {"motorway", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "service",
        "track", "path", "cycleway", "bridleway", "corridor", "platform", "construction", "proposed"}
TIER1 = {
    "Tevere", "Fiume Tevere", "Aniene", "Fiume Aniene",
    "Via del Corso", "Via Nazionale", "Via del Tritone", "Corso Vittorio Emanuele II", "Via Cavour",
    "Via dei Fori Imperiali", "Via della Conciliazione", "Via Veneto", "Via Vittorio Veneto", "Via del Babuino",
    "Via Appia Antica", "Via Appia Nuova", "Via Nomentana", "Via Salaria", "Via Flaminia", "Via Cassia",
    "Via Aurelia", "Via Tiburtina", "Via Prenestina", "Via Casilina", "Via Tuscolana", "Via Ostiense",
    "Via Cristoforo Colombo", "Via Marmorata", "Viale Trastevere", "Via Arenula", "Via XX Settembre",
    "Via Merulana", "Viale Manzoni", "Via Giulia", "Via dei Coronari", "Via del Teatro di Marcello",
    "Viale Giulio Cesare", "Via Cola di Rienzo", "Viale delle Milizie", "Corso d'Italia", "Corso di Francia",
    "Piazza Navona", "Piazza di Spagna", "Piazza del Popolo", "Piazza Venezia", "Piazza San Pietro",
    "Piazza della Repubblica", "Piazza del Campidoglio", "Campo de' Fiori", "Piazza della Rotonda",
    "Piazza di San Giovanni in Laterano", "Piazza Vittorio Emanuele II", "Piazza del Colosseo",
}


def local(coords):
    x, y = TO_UTM.transform(*np.array(coords).T)
    return np.c_[x - ORIGIN[0], -(y - ORIGIN[1])]


def angle(dx, dz):
    a = math.degrees(math.atan2(dz, dx))
    return (a + 90) % 180 - 90  # keep text upright


def along(line: LineString, width: float):
    """Placements every SPACING metres, each with the length of straight street around it."""
    n = max(1, int(line.length // SPACING))
    for k in range(n):
        d = (k + 0.5) * line.length / n
        for half in (100, 70, 50, 35):
            a, b = line.interpolate(max(0, d - half)), line.interpolate(min(line.length, d + half))
            chord = math.dist((a.x, a.y), (b.x, b.y))
            arc = min(line.length, d + half) - max(0, d - half)
            if arc > 0 and chord / arc > 0.97:
                p = line.interpolate(d)
                yield [round(p.x, 1), round(p.y, 1), round(angle(b.x - a.x, b.y - a.y), 1), round(chord), width]
                break


def main():
    ways = json.loads(Path("data/raw/osm/streets.json").read_text())
    lines, squares, kinds = {}, {}, {}
    for w in ways:
        t, name = w["tags"], w["tags"].get("name")
        hw = t.get("highway")
        if not name or hw in SKIP or len(w["geom"]) < 2:
            continue
        xy = local(w["geom"])
        if t.get("place") == "square" or (t.get("area") == "yes" and hw == "pedestrian"):
            if len(xy) >= 4:
                squares.setdefault(name, []).append(Polygon(xy))
            continue
        water = t.get("waterway") == "river"
        lines.setdefault(name, []).append(LineString(xy))
        width = 60 if water else float(t["width"]) if t.get("width", "").replace(".", "").isdigit() else WIDTH.get(hw, 8)
        k = kinds.setdefault(name, dict(water=water, width=0, major=False))
        k["width"] = max(k["width"], width)
        k["major"] |= hw in ("trunk", "primary")
    labels = []
    for name, parts in lines.items():
        merged = shapely.line_merge(MultiLineString(parts))
        k = kinds[name]
        pts = [p for g in getattr(merged, "geoms", [merged]) if g.length > 60 for p in along(g, k["width"])]
        if pts:
            labels.append(dict(name=name, water=k["water"], tier=1 if name in TIER1 or k["water"] else 2, pts=pts))
    for name, polys in squares.items():
        p = shapely.union_all([shapely.make_valid(q) for q in polys])
        c = p.representative_point()
        side = math.sqrt(p.area)
        labels.append(dict(name=name, water=False, tier=1 if name in TIER1 else 2,
                           pts=[[round(c.x, 1), round(c.y, 1), 0.0, round(side), round(side * 0.6, 1)]]))
    # One entry per name, placements at least 350 m apart, longest stretches first.
    merged = {}
    for l in labels:
        m = merged.setdefault(l["name"], dict(l, pts=[]))
        m["pts"] += l["pts"]
    out = []
    for m in merged.values():
        kept = []
        for p in sorted(m["pts"], key=lambda p: -p[3]):
            if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 > SPACING ** 2 for q in kept):
                kept.append(p)
        m["pts"] = kept
        out.append(m)
    Path("web/data/labels.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(len(out), "names,", sum(len(l["pts"]) for l in out), "placements,",
          sum(l["tier"] == 1 for l in out), "tier 1;", Path("web/data/labels.json").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
