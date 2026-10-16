"""Names, photos and article extracts for buildings, from the Wikidata items standing on them and the survey's names.

wiki.json: list of {label, label_it, wiki: {lang, url, extract} | null, wiki_it: … | null, architects, styles,
image: {thumb, page, artist, license, licenseUrl} | null}. data/wiki_index.parquet maps each building to its entry.
Where several items stand on one building, its own (a building-class item) speaks for it, then the best known. A building with no
item keeps the name the 2014 survey gives it (Ospedale San Pietro Fatebenefratelli), with no article or photo.
Photos are Wikimedia Commons files with their author and licence, as the Commons API reports them.
"""
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests

from .wikidata import dates_its_building, labels_of, placed

UA = {"User-Agent": "rome-by-building/0.1 (open-data map of Rome's buildings; https://github.com/alexbarakov/amsterdam-by-building fork)"}


CACHE = Path("data/raw/wiki_cache")


def get_json(url, params):
    """GET with backoff: the Wikimedia APIs answer bursts with 429; wait as long as they ask."""
    for attempt in range(8):
        r = requests.get(url, params=params, headers=UA, timeout=60)
        if r.ok and r.headers.get("content-type", "").startswith("application/json"):
            time.sleep(1.0)
            return r.json()
        wait = r.headers.get("retry-after", "")
        time.sleep(int(wait) if wait.isdigit() else 20 * (attempt + 1))
    r.raise_for_status()
    raise RuntimeError(f"{url}: {r.status_code} {r.text[:200]}")


def cached(name, fetch, keys):
    """Results already fetched are kept in data/raw/wiki_cache, so a rerun only asks for what is new."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.json"
    have = json.loads(path.read_text()) if path.exists() else {}
    todo = set(keys) - set(have.get("_asked", []))
    if todo:
        have.update(fetch(todo))
        have["_asked"] = sorted(set(have.get("_asked", [])) | todo)
        path.write_text(json.dumps(have, ensure_ascii=False))
    return {k: v for k, v in have.items() if k != "_asked"}


def batched(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def extracts(lang, titles):
    out = {}
    for chunk in batched(sorted(titles), 20):
        r = get_json(f"https://{lang}.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "prop": "extracts", "exintro": 1, "explaintext": 1,
            "exsentences": 3, "exlimit": 20, "redirects": 1, "titles": "|".join(chunk)})
        norm = {n["to"]: n["from"] for n in r["query"].get("normalized", []) + r["query"].get("redirects", [])}
        for p in r["query"]["pages"].values():
            t = p.get("title")
            while t in norm:
                t = norm[t]
            if p.get("extract"):
                out[t] = p["extract"].strip()
    return out


def strip_html(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or ""))).strip()


def artist_of(meta):
    a = strip_html(meta.get("Artist", {}).get("value"))[:80]
    if not a or re.match(r"^\d{1,2}:\d{2}|^\d{1,2} \w+ \d{4}|^\d{4}-\d{2}-\d{2}|^unknown", a, re.I):
        return None
    return a


def images(files):
    out = {}
    for chunk in batched(sorted(files), 50):
        r = get_json("https://commons.wikimedia.org/w/api.php", {
            "action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|extmetadata",
            "iiurlwidth": 500, "titles": "|".join("File:" + f for f in chunk)})
        norm = {n["to"]: n["from"] for n in r["query"].get("normalized", [])}
        for p in r["query"]["pages"].values():
            ii = (p.get("imageinfo") or [None])[0]
            if not ii:
                continue
            m = ii.get("extmetadata", {})
            key = norm.get(p["title"], p["title"])[5:]
            out[key] = dict(thumb=ii.get("thumburl"), page=ii.get("descriptionurl"),
                            artist=artist_of(m),
                            license=m.get("LicenseShortName", {}).get("value"),
                            licenseUrl=m.get("LicenseUrl", {}).get("value"))
    return out


def title_of(url):
    return unquote(url.rsplit("/wiki/", 1)[1]).replace("_", " ")


def tidy(name):
    """Survey names come in capitals now and then (CASERMA PIAVE): give them a title case."""
    return name.title().replace(" Di ", " di ").replace(" Del ", " del ").replace(" Della ", " della ") \
        if name.isupper() else name


def main():
    # The building's own item first (a church, not the altarpiece inside it), then the best known.
    it = placed()
    # A railway station is not a building to Wikidata, but its item is the station building's own: Roma Termini, not
    # the cinema inside it. (Its date is the first station's, and dates nothing: s02.)
    it["own"] = it.classes.map(lambda c: dates_its_building(c)
                               or any(k in l for l in labels_of(c) for k in ("railway station", "train station")))
    it = it.sort_values(["own", "links"], ascending=False).drop_duplicates("bid")
    file_of = lambda url: unquote(url.rsplit("/", 1)[1]).replace("_", " ") if url else None
    ex_en = cached("extracts_en", lambda t: extracts("en", t), {title_of(u) for u in it.wEn if u})
    ex_it = cached("extracts_it", lambda t: extracts("it", t), {title_of(u) for u in it.wIt if u})
    imgs = cached("images", images, {f for f in map(file_of, it.image) if f})
    print(f"extracts en {len(ex_en)}, it {len(ex_it)}; images {len(imgs)}")

    entries, index = [], {}
    for r in it.itertuples():
        wiki = dict(lang="en", url=r.wEn, extract=ex_en.get(title_of(r.wEn))) if r.wEn else None
        wiki_it = dict(lang="it", url=r.wIt, extract=ex_it.get(title_of(r.wIt))) if r.wIt else None
        img = imgs.get(file_of(r.image)) if r.image else None
        index[r.bid] = len(entries)
        entries.append(dict(label=r.en or r.it, label_it=r.it or r.en, qid=r.qid, wiki=wiki, wiki_it=wiki_it,
                            architects=[a for a in r.architects.split("|") if a],
                            styles=[s for s in r.styles.split("|") if s], image=img))
    b = pd.read_parquet("data/buildings.parquet", columns=["id", "name"])
    named = 0
    for i, name in zip(b.id, b.name):
        if name and i not in index:
            index[i] = len(entries)
            entries.append(dict(label=tidy(name), label_it=tidy(name), wiki=None, wiki_it=None, architects=[],
                                styles=[], image=None))
            named += 1
    print(named, "more buildings named by the survey")
    Path("web/data/wiki.json").write_text(json.dumps(entries, ensure_ascii=False, separators=(",", ":")))
    pd.DataFrame({"id": list(index), "wk": list(index.values())}).to_parquet("data/wiki_index.parquet")
    print(len(entries), "entries for", len(index), "buildings;", Path("web/data/wiki.json").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
