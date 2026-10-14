"""Wikidata items (s00_fetch_wikidata) placed on buildings, shared by the dating, layer and card steps.

An item lands on the building its coordinate falls in. A building-class item whose coordinate falls in a
courtyard or on the street goes to the nearest building within 12 m. Buildings that are gone (P576, P5816
'demolished or destroyed', the class 'destroyed building or structure') are left out: they no longer stand
for what is on their site now.
"""
import csv
import json
import math
from functools import cache

import geopandas as gpd
import pandas as pd
import shapely

from .city import CRS, TO_UTM

RAW = "data/raw/wikidata"
NEAR = 12.0


@cache
def classes() -> dict:
    return json.load(open(f"{RAW}/classes.json"))


def kind_of(item_classes: str) -> str | None:
    """'building' if any class is a building, else 'structure' if any is an architectural structure."""
    kinds = {classes().get(c, {}).get("kind") for c in item_classes.split("|") if c}
    return "building" if "building" in kinds else "structure" if "structure" in kinds else None


# Structures that are buildings in all but Wikidata's class tree; their dates can date what they stand on.
# Organs, fountains, sculptures and tombstones are structures too, inside or beside buildings, and are left out.
DATING_STRUCTURES = ("fort", "fortification", "rocca", "stadium", "sports venue", "arena", "racing venue",
                     "station", "convention center", "observatory", "prison", "gate", "aqueduct", "tower",
                     "mausoleum", "tomb", "theatre", "amphitheatre", "bath", "arch", "column")
# Obelisks carry the date they were carved in Egypt (the Lateran obelisk: 1500 BC), not of their raising in Rome.
NOT_DATING = ("tombstone", "sepulchral monument", "fountain", "organ", "sculpture", "statue", "memorial", "obelisk")
# A building that is gone no longer dates what stands on its site now (the Basilica Porcia burned in 52 BC).
GONE_CLASSES = ("destroyed building or structure", "former place", "former building")
GONE_STATES = {"Q56556915", "Q106959824", "Q107090323"}  # demolished or destroyed; unlocated; backfilled
# An ancient date only stands for a building that is itself ancient or early Christian, not for the barracks
# that took the name of the Castra Praetoria.
ANCIENT_CLASSES = ("roman", "ancient", "archaeolog", "temple", "mausoleum", "tomb", "basilica", "church", "aqueduct",
                   "theatre", "amphitheatre", "bath", "arch", "column", "domus", "catacomb", "baptistery", "ruins")


def labels_of(item_classes: str) -> list[str]:
    return [(classes().get(c, {}).get("label") or "").lower() for c in item_classes.split("|") if c]


def dates_its_building(item_classes: str) -> bool:
    kind = kind_of(item_classes)
    if kind != "structure":
        return kind == "building"
    labels = labels_of(item_classes)
    return (any(k in l for l in labels for k in DATING_STRUCTURES)
            and not any(k in l for l in labels for k in NOT_DATING))


def gone(item_classes: str, state: str) -> bool:
    return (any(k in l for l in labels_of(item_classes) for k in GONE_CLASSES)
            or bool(GONE_STATES & set(state.split("|"))))


def ancient_ok(item_classes: str) -> bool:
    return any(k in l for l in labels_of(item_classes) for k in ANCIENT_CLASSES)


def parse_time(s: str):
    """'+1595-01-01T00:00:00Z/9' → (year, precision); BCE years are negative. None for unparseable values."""
    if not s or "/" not in s:
        return None
    value, prec = s.rsplit("/", 1)
    neg = value.startswith("-")
    try:
        y = int(value.lstrip("+-").split("-")[0])
    except ValueError:
        return None
    return (-y if neg else y), int(prec)


def span(year: int, prec: int) -> tuple[int, int]:
    """The years a Wikidata date covers at its precision: a year, a decade, a century or a millennium.
    Wikidata writes the 16th century as 1501–1600 or 1600 or 1550 alike; all land on 1501–1600."""
    if prec >= 9:
        return year, year
    if prec == 8:
        return year // 10 * 10, year // 10 * 10 + 9
    size = 100 if prec == 7 else 1000
    k = math.floor((year - 1) / size)
    return k * size + 1, k * size + size


@cache
def items() -> pd.DataFrame:
    df = pd.read_csv(f"{RAW}/items.csv", dtype=str, keep_default_na=False)
    df["links"] = df.links.astype(int)
    df["kind"] = df.classes.map(kind_of)
    df = df[(df.demolished == "") & ~pd.Series(map(gone, df.classes, df.state), index=df.index)]
    x, y = TO_UTM.transform(df.lon.astype(float).values, df.lat.astype(float).values)
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(x, y), crs=CRS)


@cache
def placed() -> pd.DataFrame:
    """Items with the id of the building they stand on: columns of items() plus `bid` and `dist`."""
    b = gpd.read_parquet("data/buildings_raw.parquet", columns=["id", "geometry"])
    it = items()
    inside = gpd.sjoin(it, b, predicate="within").rename(columns={"id": "bid"}).drop(columns="index_right")
    inside["dist"] = 0.0
    # A coordinate in a courtyard or an arena (the Colosseum's) belongs to the building around it.
    filled = gpd.GeoDataFrame({"id": b.id}, geometry=[shapely.Polygon(p.exterior) if p.geom_type == "Polygon" else p
                                                       for p in b.geometry], crs=CRS)
    rest = it[~it.index.isin(inside.index) & it.kind.isin(["building", "structure"])]
    court = gpd.sjoin(rest, filled, predicate="within").rename(columns={"id": "bid"}).drop(columns="index_right")
    court = court[~court.index.duplicated()]
    court["dist"] = 0.0
    inside = pd.concat([inside, court])
    rest = it[~it.index.isin(inside.index) & (it.kind == "building")]
    near = gpd.sjoin_nearest(rest, b, max_distance=NEAR, distance_col="dist").rename(columns={"id": "bid"})
    near = near[~near.index.duplicated()].drop(columns="index_right")
    return pd.concat([inside, near])
