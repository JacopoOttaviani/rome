"""Layers: historical contexts, each a set of buildings.

A layer has one or more groups; every group takes one bit of a 64-bit mask per building.
Each source function returns {building id: group key} or {building id: (group, note)}, where a note
carries the story behind a building: {"name", "story", "story_it", "source"}. Layers are listed in the
order the viewer shows them within their section.

Sources: Wikidata (CC0) items placed on buildings by pipeline/wikidata.py; the Lazio DBGT 2014 (CC BY 4.0)
for use, type and state; OpenStreetMap (ODbL) for the rioni.
"""
from functools import cache

import geopandas as gpd
import pandas as pd

from .wikidata import dates_its_building, placed

LAYERS = []


def layer(**meta):
    def wrap(fn):
        LAYERS.append(dict(meta, source_fn=fn))
        return fn
    return wrap


# ---------- shared lookups ----------

@cache
def buildings() -> pd.DataFrame:
    return pd.read_parquet("data/buildings.parquet", columns=["id", "kind", "use", "uses", "ty", "state", "istat", "rione",
                                                               "year", "date_flag", "name"])


@cache
def items() -> pd.DataFrame:
    """Placed Wikidata items, the building's own first, then the best known: the first per building speaks for it."""
    it = placed()
    it["own"] = it.classes.map(dates_its_building)
    return it.sort_values(["own", "links"], ascending=False)


def label(r) -> str:
    return r.en or r.it or r.qid


def article(r) -> str:
    return r.wEn or r.wIt or f"https://www.wikidata.org/wiki/{r.qid}"


def by_item(match, story) -> dict:
    """{building: (group, note)} for every placed item that `match` puts in a group; first item per building wins."""
    out = {}
    for r in items().itertuples():
        g = match(r)
        if g and r.bid not in out:
            en, it = story(r)
            out[r.bid] = (g, {"name": label(r), "name_it": r.it or label(r), "story": en, "story_it": it,
                              "source": article(r)})
    return out


# ---------- Architecture ----------

ARCHITECTS = [
    ("bramante", "Bramante", ("Bramante",)),
    ("michelangelo", "Michelangelo", ("Michelangelo",)),
    ("dellaporta", "Giacomo Della Porta", ("Giacomo Della Porta",)),
    ("maderno", "Carlo Maderno", ("Carlo Maderno",)),
    ("bernini", "Gian Lorenzo Bernini", ("Gian Lorenzo Bernini",)),
    ("borromini", "Francesco Borromini", ("Francesco Borromini",)),
    ("fontana", "Carlo Fontana", ("Carlo Fontana",)),
    ("piacentini", "Marcello Piacentini", ("Marcello Piacentini",)),
]


@layer(
    id="architects", section="Architecture", title="Architects", era="1500–1960",
    text=("A handful of names drew the Rome that visitors photograph. Bramante and Michelangelo set the Renaissance "
          "on the Vatican hill; Della Porta and Maderno finished their domes and facades; Bernini and Borromini, "
          "rivals for forty years, made the city Baroque; Carlo Fontana carried it into the 1700s. Three centuries "
          "later Marcello Piacentini drew the university, Via della Conciliazione and much of EUR."),
    caveat="Buildings whose Wikidata item names the architect (P84); a building can have several.",
    source=("Wikidata, architect (P84)", "https://www.wikidata.org/wiki/Property:P84"),
    groups=[(k, l) for k, l, _ in ARCHITECTS],
)
def architects():
    def match(r):
        names = r.architects.split("|") if r.architects else []
        return next((k for k, _, keys in ARCHITECTS if any(any(n.startswith(x) for x in keys) for n in names)), None)

    def story(r):
        names = ", ".join(r.architects.split("|"))
        return f"Designed by {names}.", f"Progettato da {names}."
    return by_item(match, story)


STYLES = [
    ("medieval", "Early Christian and Romanesque", ("early christian", "romanesque architecture", "romanesque art",
                                                    "byzantine architecture", "gothic architecture")),
    ("renaissance", "Renaissance", ("renaissance architecture", "renaissance", "high renaissance")),
    ("mannerism", "Mannerism", ("mannerism", "mannerist")),
    ("baroque", "Baroque and Rococo", ("baroque architecture", "baroque", "italian baroque", "barocchetto", "rococo")),
    ("neoclassical", "Neoclassicism", ("neoclassical", "neoclassicism")),
    ("revival", "Revivals and eclecticism", ("revival", "eclectic", "historicism", "umbertino")),
    ("liberty", "Art Nouveau (Liberty)", ("art nouveau", "liberty")),
    ("modern", "Rationalism and modern", ("rationalism", "fascist", "modern", "brutalis", "novecento",
                                          "postmodern", "contemporary", "deconstructivism")),
]


@layer(
    id="styles", section="Architecture", title="Architecture styles", era="300–today",
    text=("Rome rebuilt itself in every style it invented or borrowed: the basilicas of the first Christians, "
          "Romanesque bell towers, Renaissance palaces, a Baroque that remade whole streets, the revivals and "
          "eclectic palazzi of the new capital, Liberty villas, and the rationalism of the 1930s."),
    caveat="Buildings whose Wikidata item names an architectural style (P149).",
    source=("Wikidata, architectural style (P149)", "https://www.wikidata.org/wiki/Property:P149"),
    groups=[(k, l) for k, l, _ in STYLES],
)
def styles():
    def match(r):
        names = [s.lower() for s in r.styles.split("|")] if r.styles else []
        # Revival first: "Romanesque Revival" is not Romanesque.
        for k, _, keys in [s for s in STYLES if s[0] == "revival"] + [s for s in STYLES if s[0] != "revival"]:
            if any(x in n for n in names for x in keys):
                return k

    def story(r):
        s = ", ".join(r.styles.split("|"))
        return f"Style: {s}.", f"Stile: {s}."
    return by_item(match, story)


@layer(
    id="heritage", section="Architecture", title="Protected heritage", era="All periods",
    text=("Italy protects its cultural property building by building; the historic centre of Rome, the properties "
          "of the Holy See within it and the basilica of Saint Paul are a UNESCO World Heritage Site since 1980."),
    caveat=("Buildings whose Wikidata item records a heritage designation (P1435); far from every protected "
            "building in Rome has one."),
    source=("Wikidata, heritage designation (P1435)", "https://www.wikidata.org/wiki/Property:P1435"),
    groups=[("unesco", "Part of the UNESCO World Heritage Site"), ("national", "National monument"),
            ("bene", "Italian cultural property")],
)
def heritage():
    def match(r):
        h = set(r.heritage.split("|")) if r.heritage else set()
        return ("unesco" if {"Q43113623", "Q9259"} & h else "national" if "Q3323404" in h
                else "bene" if "Q26971668" in h else None)
    text = {"unesco": ("Part of the UNESCO World Heritage Site of Rome.", "Parte del sito UNESCO del centro storico di Roma."),
            "national": ("A national monument of Italy.", "Monumento nazionale."),
            "bene": ("Listed as Italian cultural property.", "Bene culturale tutelato.")}
    return by_item(match, lambda r: text[match(r)])


# ---------- Faith and power ----------

@layer(
    id="faith", section="Faith and power", title="Churches and convents", era="300–today",
    text=("Rome holds more than nine hundred churches: the four papal basilicas, the titular churches of the "
          "cardinals, the national churches of every Catholic nation, and the parish churches the city built as "
          "it grew. Convents and colleges of the religious orders fill whole blocks of the centre."),
    caveat=("Use and type as the 2014 regional survey records them, where a church and its convent are often one "
            "building; basilicas from Wikidata."),
    source=("Regione Lazio, DBGT 2014", "https://dati.lazio.it"),
    groups=[("basilica", "Basilica"), ("church", "Church, convent or bell tower")],
)
def faith():
    b = buildings()
    out = {}
    # Any of the survey's uses: a church inside a school or a convent is still a church; a station's chapel does not
    # make Termini one.
    for i, use, uses, ty in zip(b.id, b.use, b.uses, b.ty):
        if ty in ("06", "07", "11", "22") or (any(u.startswith("05") for u in uses.split("|")) and not use.startswith("06")):
            out[i] = "church"
    for r in items().itertuples():
        if r.bid in out and "basilica" in (r.it or "").lower():
            out[r.bid] = ("basilica", {"name": label(r), "name_it": r.it or label(r), "story": "", "story_it": "",
                                       "source": article(r)})
    return out


@layer(
    id="holysee", section="Faith and power", title="The Vatican and the embassies", era="1929–today",
    text=("Since the Lateran Treaty of 1929 the Vatican City is a state of its own inside Rome. Rome is also the "
          "only city with two diplomatic corps: embassies to Italy and embassies to the Holy See, many of them in "
          "palaces of the centre and villas of Parioli."),
    caveat="The Vatican's buildings carry no Italian municipality code in the regional survey; embassies are its use 'sede ambasciata o consolato'.",
    source=("Regione Lazio, DBGT 2014", "https://dati.lazio.it"),
    groups=[("vatican", "Vatican City"), ("embassy", "Embassy or consulate")],
)
def holysee():
    b = buildings()
    out = {i: "vatican" for i in b.id[b.istat == "058000"]}
    out.update({i: "embassy" for i in b.id[b.uses.map(lambda us: any(u.startswith("0204") for u in us.split("|")))]})
    return out


# ---------- The city ----------

@layer(
    id="rioni", section="The city", title="The rioni", era="1000s–1921",
    text=("Papal Rome was divided into fourteen rioni, a name from the regiones of Augustus. When the city "
          "became Italy's capital in 1871 it filled the vineyards inside the Aurelian walls and spilled beyond "
          "them; eight new rioni were drawn between 1874 and 1921, from Esquilino to Prati."),
    caveat="Rioni boundaries from OpenStreetMap.",
    source=("OpenStreetMap contributors, ODbL", "https://www.openstreetmap.org"),
    groups=[("papal", "The fourteen rioni of papal Rome"), ("capital", "The eight rioni of the new capital")],
)
def rioni():
    old = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV"}
    b = buildings()
    return {i: ("papal" if r in old else "capital") for i, r in zip(b.id, b.rione) if isinstance(r, str)}


# ---------- Ancient Rome ----------

@layer(
    id="ancient", section="Ancient Rome", title="Monuments and ruins", era="Antiquity–today",
    text=("Ancient Rome still stands among the houses: the Colosseum, the Pantheon, the Theatre of Marcellus, "
          "tombs along the consular roads, aqueduct arches in the eastern suburbs. Alongside them are the "
          "monuments and fountains the popes and the kings of Italy added."),
    caveat=("Dated to antiquity: a Wikidata item says so. Ruins and monuments as the 2014 survey draws them; "
            "a ruin can also be a farmhouse abandoned last century."),
    source=("Regione Lazio, DBGT 2014; Wikidata", "https://dati.lazio.it"),
    groups=[("ancient", "Standing since antiquity"), ("monument", "Monument"), ("ruin", "Ruin"),
            ("fountain", "Fountain")],
)
def ancient():
    b = buildings()
    out = {}
    for i, kind, state, year, flag in zip(b.id, b.kind, b.state, b.year, b.date_flag):
        if flag in (0, 1) and year < 500:
            out[i] = "ancient"
        elif kind == "monument":
            out[i] = "monument"
        elif kind == "fountain":
            out[i] = "fountain"
        elif state == "02":
            out[i] = "ruin"
    for r in items().itertuples():
        if r.bid in out and isinstance(out[r.bid], str):
            out[r.bid] = (out[r.bid], {"name": label(r), "name_it": r.it or label(r), "story": "", "story_it": "",
                                       "source": article(r)})
    return out
