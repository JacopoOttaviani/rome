"""Where the 2014 survey says homes and OpenStreetMap clearly says otherwise.

The survey codes most buildings as homes (use 01), and many that are not: matched to OpenStreetMap's outlines, it calls
homes 100 of OpenStreetMap's 110 hotels, a sixth of its churches, a quarter of its schools, nearly a third of its
hospitals. Where a survey building of homes and an OpenStreetMap outline cover each other by at least MUTUAL, one to
one, and the outline's tags name one of six strong categories, the Use colouring follows OpenStreetMap; the survey's
use is kept beside it, and the card says which tag moved it.

Only these categories, and only from these tags: what a building is used for (amenity, tourism, leisure, healthcare,
railway, public_transport, aeroway) first, then what it was built as (building=*). Never shops, industry, farms or
offices: building=commercial on a block of flats with shops below says little. A sports centre is left out too: in
Rome the tag marks gyms, bocce and shooting clubs and a police unit's grounds. An outline whose own building=* says
homes is left alone, since its tag is about a part of it (a B&B in a block of flats).
"""
import geopandas as gpd
import pandas as pd

from .city import CRS
from .uses import INDEX, use_of

OSM = "data/raw/osm/building_uses.parquet"
MUTUAL = 0.6  # each covers at least this much of the other
# (category, {key: values}) in the order of uses.PRIORITY: a station with a chapel is a station.
USE_TAGS = [
    ("transport", dict(railway={"station"}, public_transport={"station"}, amenity={"bus_station"},
                       aeroway={"terminal"})),
    ("health", dict(amenity={"hospital", "clinic"}, healthcare={"hospital", "clinic"})),
    ("school", dict(amenity={"school", "university", "college", "kindergarten"})),
    ("worship", dict(amenity={"place_of_worship", "monastery"})),
    ("culture", dict(tourism={"museum", "gallery"}, amenity={"theatre", "cinema", "arts_centre", "library"},
                     leisure={"sports_hall", "stadium"})),
    ("hotel", dict(tourism={"hotel", "hostel", "motel"})),
]
BUILT_AS = [
    ("transport", {"train_station", "transportation"}),
    ("health", {"hospital"}),
    ("school", {"school", "university", "college", "kindergarten"}),
    ("worship", {"church", "chapel", "cathedral", "basilica", "mosque", "synagogue", "temple", "shrine", "monastery",
                 "convent", "religious"}),
    ("culture", {"museum", "theatre", "stadium", "sports_hall"}),
    ("hotel", {"hotel"}),
]
HOMES = {"apartments", "residential", "house", "detached", "semidetached_house", "terrace", "dormitory"}
KEYS = sorted({k for _, keys in USE_TAGS for k in keys})


def category(tags: dict):
    """(category, 'key=value') that names an outline, or (None, None)."""
    if tags.get("building") in HOMES:
        return None, None
    for cat, keys in USE_TAGS:
        for k, values in keys.items():
            if tags.get(k) in values:
                return cat, f"{k}={tags[k]}"
    for cat, values in BUILT_AS:
        if tags.get("building") in values:
            return cat, f"building={tags['building']}"
    return None, None


def correct(b: gpd.GeoDataFrame) -> pd.DataFrame:
    """For the survey buildings the Use colouring calls homes: OpenStreetMap's category (use_osm), the tag that names
    it (use_osm_tag) and the outline (use_osm_ref, way/… or relation/…), where an outline matches one to one."""
    o = gpd.read_parquet(OSM).to_crs(CRS)
    cats = [category(t) for t in o[["building", *KEYS]].to_dict("records")]
    o["cat"], o["tag"] = [c for c, _ in cats], [t for _, t in cats]
    o = o[o.cat.notna() & (o.area > 0)]
    h = b[[k == "edifc" and use_of(k, u, t) == INDEX["home"] for k, u, t in zip(b.kind, b.use, b.ty)]]
    x = gpd.overlay(gpd.GeoDataFrame({"id": h.id.values, "ba": h.area.values}, geometry=h.geometry.values, crs=CRS),
                    gpd.GeoDataFrame({"osm": o.osm.values, "oa": o.area.values}, geometry=o.geometry.values, crs=CRS),
                    how="intersection", keep_geom_type=True)
    x["a"] = x.area
    x = x.groupby(["id", "osm"], as_index=False).agg(a=("a", "sum"), ba=("ba", "first"), oa=("oa", "first"))
    x = x[(x.a >= MUTUAL * x.ba) & (x.a >= MUTUAL * x.oa)]
    x = x[~x.id.duplicated(keep=False) & ~x.osm.duplicated(keep=False)]
    x = x.merge(o[["osm", "cat", "tag"]], on="osm")
    out = pd.DataFrame(index=b.index, data=dict(use_osm="", use_osm_tag="", use_osm_ref=""))
    row = pd.Series(b.index, index=b.id)
    out.loc[row[x.id].values, ["use_osm", "use_osm_tag", "use_osm_ref"]] = x[["cat", "tag", "osm"]].values
    print(f"OpenStreetMap names {len(x)} of the survey's homes otherwise:", x.cat.value_counts().to_dict())
    return out
