"""Layers: historical contexts, each a set of buildings.

A layer has one or more groups; every group takes one bit of a 64-bit mask per building.
Each source function returns {bag pand id (16 digits): group key}.
"""
import csv
import re

LAYERS = []


def layer(**meta):
    def wrap(fn):
        LAYERS.append(dict(meta, source_fn=fn))
        return fn
    return wrap


def _monument_texts():
    """BAG pand id → RCE description, through the Wikidata P359 → P5208 link."""
    text = {r["nr"]: r["txt"] for r in csv.DictReader(open("data/raw/rce_descriptions.csv"))}
    out = {}
    for r in csv.DictReader(open("data/raw/wd_monuments.csv")):
        if r["bag"] and r["nr"] in text:
            out[r["bag"].zfill(16)] = text[r["nr"]]
    return out


@layer(
    id="gables",
    title="Gables",
    era="1600–1800",
    text=("A canal house shows its age in its top. Stepped gables belong to the early 1600s, neck gables "
          "to the middle of the century, bell gables to the decades around 1700, and the flat cornice "
          "to the 1700s, when the richest owners hid the roof altogether. The register of national "
          "monuments names the gable of each listed house."),
    source=("Rijksmonumentenregister, RCE", "https://monumentenregister.cultureelerfgoed.nl"),
    groups=[("trap", "Stepped gable"), ("hals", "Neck gable"), ("klok", "Bell gable"), ("lijst", "Cornice")],
)
def gables():
    first = [("trap", r"trapgevel"), ("hals", r"halsgevel"), ("klok", r"klokgevel"),
             ("lijst", r"rechte lijst|lijstgevel|verhoogde lijst")]
    out = {}
    for bag, t in _monument_texts().items():
        t = t.lower()
        hits = [(m.start(), key) for key, pat in first for m in [re.search(pat, t)] if m]
        if hits:
            out[bag] = min(hits)[1]  # the first gable named is the house's own
    return out


@layer(
    id="warehouses",
    title="Warehouses",
    era="1600–1900",
    text=("Amsterdam stored the goods of the world in its houses. Warehouses line the Brouwersgracht, "
          "the islands west of Centraal Station and the Entrepotdok, recognisable by their shutters, "
          "hoisting beams and loading doors stacked above each other."),
    source=("Rijksmonumentenregister, RCE", "https://monumentenregister.cultureelerfgoed.nl"),
    groups=[("pakhuis", "Warehouse")],
)
def warehouses():
    return {bag: "pakhuis" for bag, t in _monument_texts().items() if re.search(r"\bpakhuis|pakhuizen", t.lower()[:200])}


@layer(
    id="amsterdam_school",
    title="Amsterdam School",
    era="1910–1930",
    text=("Brick as sculpture: rounded corners, towers, ornament built from the bricks themselves. "
          "Michel de Klerk, Piet Kramer and Jan Gratama gave Amsterdam's new public housing this "
          "expressive style, most of it in Plan Zuid and the Spaarndammerbuurt."),
    source=("Rijksmonumentenregister, RCE", "https://monumentenregister.cultureelerfgoed.nl"),
    groups=[("as", "Amsterdam School")],
)
def amsterdam_school():
    return {bag: "as" for bag, t in _monument_texts().items() if "amsterdamse school" in t.lower()}
