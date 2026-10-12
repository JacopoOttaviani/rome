"""Layers: historical contexts, each a set of buildings.

A layer has one or more groups; every group takes one bit of a 64-bit mask per building.
Each source function returns {bag pand id (16 digits): group key}. Layers are listed in
historical order; the viewer shows them in this order.

Sources are fetched by s00_fetch_layers.py. Every one is open (CC0, CC-BY or the open terms of
maps.amsterdam.nl). The last addresses of Holocaust victims are deliberately absent: the only
dataset that links them to buildings (Amsterdam Time Machine / Joods Monument) carries no
licence and asks not to be used without permission.
"""
import csv
import json
import re
from functools import cache

import geopandas as gpd
import pandas as pd
import shapely
from pyproj import Transformer

LAYERS = []
RAW = "data/raw/layers"


def layer(**meta):
    def wrap(fn):
        LAYERS.append(dict(meta, source_fn=fn))
        return fn
    return wrap


# ---------- shared lookups ----------

@cache
def buildings() -> gpd.GeoDataFrame:
    b = gpd.read_parquet("data/buildings.parquet", columns=["identificatie", "year", "geometry"])
    b["bag"] = b.identificatie.str.slice(-16)
    return b


@cache
def monuments() -> list[dict]:
    return json.load(open(f"{RAW}/monuments.json"))


@cache
def wikidata_panden() -> dict[str, set[str]]:
    out = {}
    for r in csv.DictReader(open("data/raw/wd_monuments.csv")):
        if r["bag"]:
            out.setdefault(r["nr"], set()).add(r["bag"].zfill(16))
    return out


def panden_of(nr) -> set[str]:
    """Buildings of a monument: the city register's links, else Wikidata's."""
    nr = str(nr)
    own = {p for m in monuments() if str(m["nr"]) == nr for p in m["panden"]}
    return own or wikidata_panden().get(nr, set())


@cache
def monument_panden() -> dict[str, set[str]]:
    out = {}
    for m in monuments():
        out.setdefault(str(m["nr"]), set()).update(m["panden"])
    for nr, ps in wikidata_panden().items():
        if not out.get(nr):
            out[nr] = set(ps)
    return out


@cache
def rce_texts() -> dict[str, str]:
    return {r["nr"]: r["txt"] for r in csv.DictReader(open("data/raw/rce_descriptions.csv"))}


def by_monument(keyed: dict[str, str]) -> dict[str, str]:
    """{monument nr: group} → {pand: group}."""
    mp = monument_panden()
    return {p: g for nr, g in keyed.items() for p in mp.get(str(nr), ())}


def within(polygons: gpd.GeoDataFrame, key_col: str) -> dict[str, str]:
    """Buildings whose centroid falls inside a polygon, keyed by the polygon's group."""
    b = buildings()
    pts = gpd.GeoDataFrame({"bag": b.bag}, geometry=b.geometry.centroid, crs=28992)
    j = gpd.sjoin(pts, polygons[[key_col, "geometry"]], predicate="within")
    return dict(zip(j.bag, j[key_col]))


def near_points(points: gpd.GeoDataFrame, key_col: str, radius: float) -> dict[str, str]:
    """Buildings within `radius` metres of a point (the building at or around an address)."""
    b = buildings()
    j = gpd.sjoin(b[["bag", "geometry"]], points[[key_col, "geometry"]].set_geometry(points.buffer(radius)),
                  predicate="intersects")
    return dict(zip(j.bag, j[key_col]))


def rd(geom_json) -> shapely.Geometry:
    return shapely.geometry.shape(geom_json if isinstance(geom_json, dict) else json.loads(geom_json))


TO_RD = Transformer.from_crs(4326, 28992, always_xy=True)


# ---------- layers ----------

@layer(
    id="gables", title="Gables", era="1600–1800",
    text=("A canal house shows its age in its top. Stepped gables belong to the early 1600s, neck gables "
          "to the middle of the century, bell gables to the decades around 1700, and the flat cornice "
          "to the 1700s, when the richest owners hid the roof altogether."),
    caveat="Listed houses only: the register of national monuments names the gable of each.",
    source=("Rijksmonumentenregister, RCE", "https://monumentenregister.cultureelerfgoed.nl"),
    groups=[("trap", "Stepped gable"), ("hals", "Neck gable"), ("klok", "Bell gable"), ("lijst", "Cornice")],
)
def gables():
    pats = [("trap", r"trapgevel"), ("hals", r"halsgevel"), ("klok", r"klokgevel"),
            ("lijst", r"rechte lijst|lijstgevel|verhoogde lijst")]
    keyed = {}
    for nr, t in rce_texts().items():
        t = t.lower()
        hits = [(m.start(), k) for k, p in pats for m in [re.search(p, t)] if m]
        if hits:
            keyed[nr] = min(hits)[1]  # the first gable named is the house's own
    return by_monument(keyed)


@layer(
    id="trade", title="Warehouses and the companies", era="1600–1800",
    text=("Amsterdam stored the goods of the world in its houses. Warehouses with shutters, hoisting beams "
          "and stacked loading doors line the Brouwersgracht, the western islands and the Entrepotdok. "
          "The East and West India Companies ran their trade from a handful of buildings that still stand."),
    source=("Rijksmonumentenregister, RCE", "https://monumentenregister.cultureelerfgoed.nl"),
    groups=[("pakhuis", "Warehouse"), ("company", "VOC and WIC buildings")],
)
def trade():
    keyed = {nr: "pakhuis" for nr, t in rce_texts().items() if re.search(r"\bpakhuis|pakhuizen", t.lower()[:200])}
    # Oost-Indisch Huis, West-Indisch Huis, 's Lands Zeemagazijn, the VOC ropewalk
    keyed.update({nr: "company" for nr in ("2012", "1372", "2205", "3959")})
    return by_monument(keyed)


@layer(
    id="unesco", title="The canal ring", era="1613–1665",
    text=("The seventeenth-century ring of canals, dug in three phases and built up with merchants' houses, "
          "has been a UNESCO World Heritage site since 2010. The buffer zone around it protects the views."),
    source=("Gemeente Amsterdam, UNESCO zones", "https://api.data.amsterdam.nl/v1/monumenten/unesco/"),
    groups=[("Kernzone", "World Heritage site"), ("Bufferzone", "Buffer zone")],
)
def unesco():
    rows = json.load(open(f"{RAW}/unesco.json"))
    g = gpd.GeoDataFrame({"zone": [r["naam"] for r in rows]}, geometry=[rd(r["geometrie"]) for r in rows], crs=28992)
    core = within(g[g.zone == "Kernzone"], "zone")
    buffer = within(g[g.zone == "Bufferzone"], "zone")
    return {**buffer, **core}


@layer(
    id="faith", title="Faith and charity", era="1400–1900",
    text=("Under the Republic, Catholics worshipped in hidden churches behind house fronts, Jews from Portugal "
          "and Central Europe built the city's great synagogues, and wealthy citizens founded hofjes: "
          "courtyards of almshouses for the elderly poor."),
    source=("Gemeente Amsterdam, monuments register", "https://api.data.amsterdam.nl/v1/monumenten/monumenten/"),
    groups=[("worship", "Church"), ("synagogue", "Synagogue"), ("hofje", "Hofje")],
)
def faith():
    keyed = {}
    for m in monuments():
        name = (m["name"] or "").lower()
        if m["function"] == "religie":
            keyed[str(m["nr"])] = "worship"
        if "hofje" in name:
            keyed[str(m["nr"])] = "hofje"
        if "synago" in name:
            keyed[str(m["nr"])] = "synagogue"
    for r in csv.DictReader(open("data/raw/wd_monuments.csv")):
        l = r["label"].lower()
        if "synago" in l:
            keyed[r["nr"]] = "synagogue"
        elif "hofje" in l and r["nr"] not in keyed:
            keyed[r["nr"]] = "hofje"
    return by_monument(keyed)


STYLE_GROUPS = [
    ("neo", "Neo-Renaissance", ("Neo-Renaissance", "Neo-Hollandse Renaissance")),
    ("eclectic", "Eclecticism", ("Eclecticisme",)),
    ("nouveau", "Art Nouveau", ("Art Nouveau",)),
    ("berlage", "Berlage school", ("Berlagianisme", "Rationalisme")),
    ("as", "Amsterdam School", ("Amsterdamse school", "Late Amsterdamse school", "Expressionisme")),
    ("nb", "Nieuwe Bouwen", ("Nieuwe Bouwen", "Functionalisme")),
]


@layer(
    id="styles", title="Architecture styles", era="1850–1940",
    text=("Between Cuypers' Rijksmuseum and the white blocks of the Nieuwe Bouwen, Amsterdam tried on a style "
          "a generation. Berlage stripped ornament back to brick; his pupils of the Amsterdam School turned brick "
          "into sculpture across the new housing districts."),
    caveat="Listed buildings only: the register tags the style of about one national monument in three.",
    source=("Rijksmonumentenregister, RCE", "https://linkeddata.cultureelerfgoed.nl"),
    groups=[(k, label) for k, label, _ in STYLE_GROUPS],
)
def styles():
    to_group = {s: k for k, _, names in STYLE_GROUPS for s in names}
    keyed = {}
    for r in json.load(open(f"{RAW}/rce_styles.json")):
        g = to_group.get(r["style"])
        if g:
            keyed.setdefault(r["nr"], g)
    return by_monument(keyed)


ARCHITECTS = [
    ("cuypers", "Cuypers", ("Cuypers, P.J.H.", "Cuypers, Ed.")),
    ("berlage", "Berlage", ("Berlage, H.P.",)),
    ("deklerk", "De Klerk", ("Klerk, M. de",)),
    ("kramer", "Kramer", ("Kramer, P.L.",)),
    ("vangendt", "Van Gendt", ("Gendt, A.L. van",)),
    ("pw", "Public Works", ("Publieke Werken, Dienst der",)),
]


@layer(
    id="architects", title="Architects", era="1870–1940",
    text=("A few names built much of the city that tourists photograph: Cuypers the Rijksmuseum and Centraal "
          "Station, Van Gendt the Concertgebouw, Berlage the Exchange, De Klerk and Kramer the Amsterdam School "
          "housing, and the city's own Public Works department its schools, bridges and bathhouses."),
    caveat="Listed buildings only, by the architect the city's monuments register names.",
    source=("Gemeente Amsterdam, monuments register", "https://api.data.amsterdam.nl/v1/monumenten/monumenten/"),
    groups=[(k, label) for k, label, _ in ARCHITECTS],
)
def architects():
    to_group = {n: k for k, _, names in ARCHITECTS for n in names}
    keyed = {}
    for m in monuments():
        a = m["architect"] or ""
        for name, k in to_group.items():
            if name in a:
                keyed[str(m["nr"])] = k
                break
    return by_monument(keyed)


@layer(
    id="housing", title="Housing Act homes", era="1901–1940",
    text=("The Housing Act of 1901 let housing associations build with public money. Within forty years "
          "they had replaced the slums with whole districts of sound workers' homes, and they still own "
          "these blocks today."),
    caveat="Buildings built 1901–1940 in blocks a housing association owns today; some were bought later.",
    source=("AFWC, housing associations' stock 2025", "https://maps.amsterdam.nl/open_geodata/"),
    groups=[("woningwet", "Housing association, built 1901–1940")],
)
def housing():
    g = gpd.read_file(f"{RAW}/social_housing.geojson").to_crs(28992)
    g["k"] = "woningwet"
    hit = within(g, "k")
    years = dict(zip(buildings().bag, buildings().year))
    return {p: k for p, k in hit.items() if 1901 <= years[p] <= 1940}


PLANNED = [
    ("Plan Zuid", "Plan Zuid"), ("Admiralenbuurt", "Admiralenbuurt"), ("Betondorp", "Betondorp"),
    ("Van Eesteren Museum", "Western garden cities"), ("IJplein", "IJplein"),
    ("Bijlmermuseum", "Bijlmermeer"), ("Plan Van Gool", "Plan Van Gool"),
]


@layer(
    id="planned", title="The planned city", era="1915–1980",
    text=("Twentieth-century Amsterdam grew by plan: Berlage's Plan Zuid, the concrete village of Betondorp, "
          "Van Eesteren's garden cities in the west, the honeycomb high-rise of the Bijlmermeer and the "
          "1980s renewal of IJplein. The city now protects each of them as a cityscape."),
    source=("Gemeente Amsterdam, protected cityscapes", "https://api.data.amsterdam.nl/v1/beschermdestadsdorpsgezichten/"),
    groups=[(name, label) for name, label in PLANNED],
)
def planned():
    rows = json.load(open(f"{RAW}/stadsgezichten.json"))
    g = gpd.GeoDataFrame({"naam": [r["naam"] for r in rows]}, geometry=[rd(r["geometry"]) for r in rows], crs=28992)
    return within(g[g.naam.isin([n for n, _ in PLANNED])], "naam")


@layer(
    id="war", title="Under fire, 1940–1945", era="1940–1945",
    text=("Amsterdam was spared the destruction of Rotterdam, yet bombs, shells and crashing aircraft still "
          "hit hundreds of addresses. The city archive mapped each incident from the reports of the time."),
    caveat="Buildings within 15 m of a recorded incident; some stand on the site of the building that was hit.",
    source=("Stadsarchief Amsterdam, WWII incidents", "https://maps.amsterdam.nl/open_geodata/"),
    groups=[("bomb", "Bombs, shells and gunfire"), ("crash", "Aircraft crash"), ("damage", "Damage nearby")],
)
def war():
    g = gpd.read_file(f"{RAW}/ww2_damage.geojson").to_crs(28992)
    kind = g.Soort.fillna("").str.lower()
    g["k"] = kind.map(lambda s: "crash" if "vliegtuig" in s else "damage" if "omgeving" in s or "schade" in s else "bomb")
    return near_points(g, "k", 15)


@layer(
    id="noord1943", title="The raid on Noord, 17 July 1943", era="1943",
    text=("Allied bombers aimed at the Fokker aircraft works in Noord and missed: their bombs fell on the "
          "streets around it and killed 185 people. Buildings near the impacts that date from after the war "
          "mark what had to be rebuilt."),
    caveat="Buildings within 40 m of a recorded impact of that day.",
    source=("Gemeente Amsterdam, wartime impacts", "https://api.data.amsterdam.nl/v1/ontplofbare_oorlogsresten/"),
    groups=[("rebuilt", "Built after 1943"), ("stood", "Standing before 1943")],
)
def noord1943():
    rows = [r for r in json.load(open(f"{RAW}/ww2_impacts.json")) if "RAP_19430717" in (r.get("hyperlink") or r.get("pdf") or "")]
    g = gpd.GeoDataFrame({"k": ["hit"] * len(rows)}, geometry=[rd(r["geometrie"]) for r in rows], crs=28992)
    hit = near_points(g, "k", 40)
    years = dict(zip(buildings().bag, buildings().year))
    return {p: ("rebuilt" if years[p] > 1943 else "stood") for p in hit}


@layer(
    id="jewish", title="Jewish Amsterdam and the war", era="1639–1945",
    text=("Before 1940 one Amsterdammer in ten was Jewish; about 60,000 of them were murdered. From the "
          "Hollandsche Schouwburg, the theatre where they were gathered for deportation, to the house on the "
          "Prinsengracht where Anne Frank hid, the places of that history still stand among the synagogues "
          "of the old Jewish quarter."),
    caveat=("The homes of the victims are not shown: the dataset linking the Joods Monument to buildings has "
            "no open licence. joodsmonument.nl lists every person and address."),
    source=("Joods Monument", "https://www.joodsmonument.nl"),
    groups=[("site", "Site of persecution and hiding"), ("synagogue", "Synagogue")],
)
def jewish():
    # Hollandsche Schouwburg, Anne Frank Huis, De Joodsche Invalide, Plancius (Verzetsmuseum)
    keyed = {nr: "site" for nr in ("532241", "4296", "518494", "518400")}
    for r in csv.DictReader(open("data/raw/wd_monuments.csv")):
        if "synago" in r["label"].lower():
            keyed.setdefault(r["nr"], "synagogue")
    for m in monuments():
        if "synago" in (m["name"] or "").lower():
            keyed.setdefault(str(m["nr"]), "synagogue")
    return by_monument(keyed)


@layer(
    id="heritage", title="Protected heritage", era="All periods",
    text=("About one building in twenty is a listed monument: by the State for national significance, "
          "or by the city for local value."),
    source=("Gemeente Amsterdam, monuments register", "https://api.data.amsterdam.nl/v1/monumenten/monumenten/"),
    groups=[("Rijksmonument", "National monument"), ("Gemeentelijk monument", "Municipal monument")],
)
def heritage():
    out = {}
    for m in monuments():
        for p in m["panden"]:
            if m["status"] == "Rijksmonument" or p not in out:
                out[p] = m["status"]
    return out
