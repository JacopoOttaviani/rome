"""Verify the curated entries against their Wikipedia articles and geocode them to BAG buildings."""
import json
import re
from functools import cache
from urllib.parse import quote

import geopandas as gpd
import requests
from shapely.geometry import Point

from .curated import CURATED

UA = {"User-Agent": "amsterdam-by-building/0.1 (https://stop-token.com/lab/amsterdam/)"}


@cache
def article(ref):
    lang, title = ref.split(":", 1)
    r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", headers=UA, timeout=60, params={
        "action": "query", "prop": "extracts|info", "inprop": "url", "explaintext": 1, "redirects": 1,
        "format": "json", "titles": title}).json()
    page = next(iter(r["query"]["pages"].values()))
    return (page.get("extract") or ""), page.get("fullurl")


@cache
def buildings():
    b = gpd.read_parquet("data/buildings.parquet", columns=["identificatie", "geometry"])
    b["bag"] = b.identificatie.str.slice(-16)
    return b


def geocode(address):
    r = requests.get("https://api.pdok.nl/bzk/locatieserver/search/v3_1/free", headers=UA, timeout=60, params={
        "q": address, "fq": ["type:adres", "woonplaatsnaam:Amsterdam"], "rows": 5,
        "fl": "weergavenaam,centroide_rd"}).json()
    # Exact address only: the first result must start with the street and house number as written.
    exact = re.compile(re.escape(address) + r"(?:[A-Za-z]|-\w+)?,", re.I)  # 444, 444A, 444-1
    docs = [d for d in r["response"]["docs"] if exact.match(d["weergavenaam"])]
    if not docs:
        return None, None
    x, y = map(float, docs[0]["centroide_rd"][6:-1].split())
    b = buildings()
    hit = b[b.contains(Point(x, y))]
    if hit.empty:
        d = b.distance(Point(x, y))
        hit = b[d == d.min()] if d.min() < 15 else hit
    return (hit.bag.iloc[0] if not hit.empty else None), docs[0]["weergavenaam"]


def main():
    out, dropped = [], []
    for L in CURATED:
        entries = []
        for name, address, story, ref, checks, *group in L["entries"]:
            text, url = article(ref)
            missing = [c for c in checks if c not in text]
            bag, found = geocode(address)
            if missing or not bag:
                dropped.append((L["id"], name, missing, found))
                continue
            entries.append(dict(name=name, address=address, bag=bag, story=story, source=url,
                                group=group[0] if group else L["id"]))
        out.append(dict({k: v for k, v in L.items() if k != "entries"}, entries=entries))
        print(f'{L["id"]:10s} {len(entries)}/{len(L["entries"])}')
    for d in dropped:
        print("dropped:", d)
    json.dump(out, open("data/curated.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
