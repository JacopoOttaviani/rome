"""Wikidata items with coordinates inside Rome's bounding box (CC0), and the facts the map uses.

Three passes keep each query under the service's time limit:
  1. every item with a coordinate (P625) in the box;
  2. per batch of items: labels, classes (P31), inception (P571, with its precision), official opening (P1619),
     demolition (P576), state of conservation (P5816), architects (P84), styles (P149), heritage designations
     (P1435), height (P2048), image (P18),
     Italian and English Wikipedia articles, number of sitelinks;
  3. which of their classes are buildings (subclasses of Q41176) or other architectural structures (Q811979).
"""
import csv
import json
import time
from pathlib import Path

import requests

SPARQL = "https://query.wikidata.org/sparql"
UA = {"User-Agent": "rome-by-building/0.1 (open-data map of Rome's buildings; contact via GitHub)",
      "Accept": "application/sparql-results+json"}
BOX = ("Point(12.23 41.65)", "Point(12.86 42.15)")
OUT = Path("data/raw/wikidata")


def query(q):
    for attempt in range(6):
        r = requests.post(SPARQL, data={"query": q}, headers=UA, timeout=120)
        if r.ok:
            time.sleep(0.5)
            return [{k: v["value"] for k, v in b.items()} for b in r.json()["results"]["bindings"]]
        time.sleep(5 * 2 ** attempt)
    r.raise_for_status()


def qid(uri):
    return uri.rsplit("/", 1)[1]


def batched(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def items_in_box():
    rows = query(f"""SELECT ?i ?c WHERE {{ SERVICE wikibase:box {{ ?i wdt:P625 ?c .
      bd:serviceParam wikibase:cornerSouthWest "{BOX[0]}"^^geo:wktLiteral .
      bd:serviceParam wikibase:cornerNorthEast "{BOX[1]}"^^geo:wktLiteral . }} }}""")
    out = {}
    for r in rows:
        lon, lat = map(float, r["c"].removeprefix("Point(").removesuffix(")").split())
        out.setdefault(qid(r["i"]), (lon, lat))
    return out


DETAILS = """SELECT ?i ?it ?en ?descIt ?wIt ?wEn ?links ?image
  (GROUP_CONCAT(DISTINCT ?cls; separator="|") AS ?classes)
  (GROUP_CONCAT(DISTINCT CONCAT(STR(?inc), "/", STR(?incP)); separator="|") AS ?inception)
  (GROUP_CONCAT(DISTINCT STR(?open); separator="|") AS ?opening)
  (GROUP_CONCAT(DISTINCT STR(?gone); separator="|") AS ?demolished)
  (GROUP_CONCAT(DISTINCT ?archL; separator="|") AS ?architects)
  (GROUP_CONCAT(DISTINCT ?styleL; separator="|") AS ?styles)
  (GROUP_CONCAT(DISTINCT ?styleI; separator="|") AS ?styleIds)
  (GROUP_CONCAT(DISTINCT ?herI; separator="|") AS ?heritage)
  (MAX(?h) AS ?height)
  (GROUP_CONCAT(DISTINCT ?stateI; separator="|") AS ?state)
WHERE {
  VALUES ?i { %s }
  OPTIONAL { ?i rdfs:label ?it FILTER(LANG(?it) = "it") }
  OPTIONAL { ?i rdfs:label ?en FILTER(LANG(?en) = "en") }
  OPTIONAL { ?i schema:description ?descIt FILTER(LANG(?descIt) = "it") }
  OPTIONAL { ?wIt schema:about ?i ; schema:isPartOf <https://it.wikipedia.org/> }
  OPTIONAL { ?wEn schema:about ?i ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?i wikibase:sitelinks ?links }
  OPTIONAL { ?i wdt:P18 ?image }
  OPTIONAL { ?i wdt:P31 ?cls }
  OPTIONAL { ?i p:P571/psv:P571 [ wikibase:timeValue ?inc ; wikibase:timePrecision ?incP ] }
  OPTIONAL { ?i wdt:P1619 ?open }
  OPTIONAL { ?i wdt:P576 ?gone }
  OPTIONAL { ?i wdt:P84 ?arch . ?arch rdfs:label ?archL FILTER(LANG(?archL) = "it") }
  OPTIONAL { ?i wdt:P149 ?styleI . ?styleI rdfs:label ?styleL FILTER(LANG(?styleL) = "en") }
  OPTIONAL { ?i wdt:P1435 ?herI }
  OPTIONAL { ?i p:P2048/psn:P2048/wikibase:quantityAmount ?h }
  OPTIONAL { ?i wdt:P5816 ?stateI }
} GROUP BY ?i ?it ?en ?descIt ?wIt ?wEn ?links ?image"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    where = items_in_box()
    print(len(where), "items with coordinates in the box")
    rows = []
    for chunk in batched(sorted(where), 300):
        rows += query(DETAILS % " ".join(f"wd:{q}" for q in chunk))
    seen = {}
    for r in rows:
        seen.setdefault(qid(r["i"]), r)  # an item with two images or labels comes back twice; keep the first
    classes = sorted({qid(c) for r in seen.values() for c in r.get("classes", "").split("|") if c})
    known = json.loads((OUT / "classes.json").read_text()) if (OUT / "classes.json").exists() else {}
    if set(classes) <= set(known):
        write_items(seen, where)
        return
    kind = {}
    for chunk in batched(classes, 200):
        values = " ".join(f"wd:{c}" for c in chunk)
        for root, name in (("Q41176", "building"), ("Q811979", "structure")):
            for r in query(f"SELECT DISTINCT ?c WHERE {{ VALUES ?c {{ {values} }} ?c wdt:P279* wd:{root} }}"):
                kind.setdefault(qid(r["c"]), name)
    labels = {}
    for chunk in batched(classes, 300):
        for r in query(f"""SELECT ?c ?l WHERE {{ VALUES ?c {{ {" ".join(f"wd:{c}" for c in chunk)} }}
                           ?c rdfs:label ?l FILTER(LANG(?l) = "en") }}"""):
            labels[qid(r["c"])] = r["l"]
    (OUT / "classes.json").write_text(json.dumps({c: dict(kind=kind.get(c), label=labels.get(c)) for c in classes},
                                                 ensure_ascii=False, indent=0))
    write_items(seen, where)
    print(len(seen), "items;", len(classes), "classes,", sum(v == "building" for v in kind.values()), "of them buildings")


def write_items(seen, where):
    cols = ["qid", "lon", "lat", "it", "en", "descIt", "wIt", "wEn", "links", "image", "classes", "inception",
            "opening", "demolished", "state", "architects", "styles", "styleIds", "heritage", "height"]
    with open(OUT / "items.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        for q, r in sorted(seen.items()):
            row = {k: r.get(k, "") for k in cols}
            row.update(qid=q, lon=where[q][0], lat=where[q][1],
                       classes="|".join(qid(c) for c in r.get("classes", "").split("|") if c),
                       styleIds="|".join(qid(c) for c in r.get("styleIds", "").split("|") if c),
                       heritage="|".join(qid(c) for c in r.get("heritage", "").split("|") if c),
                       state="|".join(qid(c) for c in r.get("state", "").split("|") if c),
                       links=r.get("links", "0"))
            w.writerow(row)
    print(len(seen), "items written")


if __name__ == "__main__":
    main()
