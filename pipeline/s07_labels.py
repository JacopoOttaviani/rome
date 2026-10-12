"""Street and canal names, placed along their own outlines.

Source: BAG openbare ruimtes from the Amsterdam city API (polygon per street, CC0). Each polygon is cut
into 300 m cells; every piece longer than it is wide gets one label at its centre, turned along its
long side. Tier 1 (canals and main streets) shows from afar, tier 2 only up close.
"""
import json
import math
from pathlib import Path

import numpy as np
import requests
import shapely
from shapely.geometry import box, shape

from .s03_tiles import DAM

API = "https://api.data.amsterdam.nl/v1/bag/openbareruimtes/"
CELL = 300.0
TIER1 = {
    # canals and rivers
    "Singel", "Herengracht", "Keizersgracht", "Prinsengracht", "Singelgracht", "Amstel", "Brouwersgracht",
    "Lijnbaansgracht", "Bloemgracht", "Egelantiersgracht", "Leidsegracht", "Reguliersgracht", "Lauriergracht",
    "Oudezijds Voorburgwal", "Oudezijds Achterburgwal", "Kloveniersburgwal", "Geldersekade", "Groenburgwal",
    "Nieuwe Herengracht", "Nieuwe Keizersgracht", "Nieuwe Prinsengracht", "Entrepotdok", "Oosterdok",
    "Westerdok", "Amstelkanaal", "Noordhollandsch Kanaal", "Kostverlorenvaart", "Boerenwetering",
    "Het IJ", "IJ", "Nieuwe Meer", "Sloterplas", "Rapenburgwal", "Houtkopersburgwal", "Looiersgracht",
    # main streets and squares
    "Damrak", "Rokin", "Kalverstraat", "Nieuwendijk", "Dam", "Leidsestraat", "Utrechtsestraat", "Vijzelstraat",
    "Weesperstraat", "Wibautstraat", "Overtoom", "Ferdinand Bolstraat", "Van Baerlestraat", "Stadhouderskade",
    "Nassaukade", "Marnixstraat", "Rozengracht", "Raadhuisstraat", "Haarlemmerstraat", "Haarlemmerdijk",
    "Jodenbreestraat", "Plantage Middenlaan", "Sarphatistraat", "Ceintuurbaan", "Albert Cuypstraat",
    "De Clercqstraat", "Kinkerstraat", "Prins Hendrikkade", "Zeedijk", "Warmoesstraat", "Spui", "Rembrandtplein",
    "Leidseplein", "Museumplein", "Beethovenstraat", "Apollolaan", "Amstelveenseweg", "IJburglaan",
    "Van Woustraat", "Linnaeusstraat", "Middenweg", "Admiraal de Ruijterweg", "Jan Evertsenstraat",
    "Bos en Lommerweg", "Klaprozenweg", "Johan Huizingalaan", "Europaboulevard", "Bijlmerdreef",
    "Mr. Visserplein", "Waterlooplein", "Frederiksplein", "Weteringschans", "Mauritskade", "Hobbemakade",
}


def fetch():
    items, url, params = [], API, {"_format": "json", "_pageSize": 1000}
    while url:
        d = requests.get(url, params=params, timeout=120).json()
        items += d["_embedded"]["openbareruimtes"]
        url = d["_links"].get("next", {}).get("href")
        params = None
    return [o for o in items if o.get("geometrie") and not o.get("eindGeldigheid")
            and o["typeOmschrijving"] in ("Weg", "Water")]


def pieces(geom):
    x0, y0, x1, y1 = geom.bounds
    for cx in np.arange(math.floor(x0 / CELL) * CELL, x1, CELL):
        for cy in np.arange(math.floor(y0 / CELL) * CELL, y1, CELL):
            part = geom.intersection(box(cx, cy, cx + CELL, cy + CELL))
            for p in getattr(part, "geoms", [part]):
                if p.geom_type == "Polygon" and p.area > 200:
                    yield p


def placement(p):
    """Centre and angle (degrees, local frame) of a piece, or None if it is not elongated."""
    r = p.minimum_rotated_rectangle
    c = np.array(r.exterior.coords)[:4]
    e1, e2 = c[1] - c[0], c[2] - c[1]
    long, short = (e1, e2) if np.hypot(*e1) >= np.hypot(*e2) else (e2, e1)
    if np.hypot(*long) < 2.2 * np.hypot(*short) or np.hypot(*long) < 60:
        return None
    pt = p.representative_point() if not p.contains(p.centroid) else p.centroid
    ang = math.degrees(math.atan2(-long[1], long[0]))  # local z points south
    ang = (ang + 90) % 180 - 90  # keep text upright
    return [round(pt.x - DAM[0], 1), round(-(pt.y - DAM[1]), 1), round(ang, 1), round(float(np.hypot(*long)))]


def main():
    raw = Path("data/raw/openbareruimtes.json")
    if not raw.exists():
        raw.write_text(json.dumps(fetch()))
    items = json.loads(raw.read_text())
    labels = []
    for o in items:
        g = shapely.make_valid(shape(o["geometrie"] if isinstance(o["geometrie"], dict) else json.loads(o["geometrie"])))
        pts = [pl for p in pieces(g) if (pl := placement(p))]
        if not pts:
            continue
        name = o["naam"]
        labels.append(dict(name=name, water=o["typeOmschrijving"] == "Water",
                           tier=1 if name in TIER1 else 2, pts=pts, origin=o.get("beschrijvingNaam")))
    # One entry per name: a canal is registered both as water and as the street along it; keep the water.
    merged = {}
    for l in sorted(labels, key=lambda l: not l["water"]):
        m = merged.setdefault(l["name"], dict(l, pts=[]))
        m["pts"] += l["pts"]
    labels = []
    for m in merged.values():
        # Keep placements at least 350 m apart, longest stretches first.
        kept = []
        for p in sorted(m["pts"], key=lambda p: -p[3]):
            if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 > 350 ** 2 for q in kept):
                kept.append(p)
        m["pts"] = kept
        labels.append(m)
    Path("web/data/labels.json").write_text(json.dumps(labels, ensure_ascii=False, separators=(",", ":")))
    print(len(labels), "names,", sum(len(l["pts"]) for l in labels), "placements,",
          sum(l["tier"] == 1 for l in labels), "tier 1;", Path("web/data/labels.json").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
