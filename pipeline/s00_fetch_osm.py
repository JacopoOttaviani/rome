"""OpenStreetMap data (ODbL): the 22 rioni of central Rome, named streets and squares for the map's labels, and
building footprints, the source of the buildings newer than the 2014 survey (s01_load); for the search box, every named
street of the comune and the addresses that carry a postcode; parks, gardens, woods and meadows for the green areas;
the building outlines tagged as churches, hotels, schools, hospitals, cultural venues and stations, for the Use colouring.

Rioni come from Nominatim, one polite request a second; streets from the Overpass API, in tiles, retried when
the public servers are busy, or else read out of Geofabrik's extract of central Italy; buildings from the extract.
"""
import json
import time
from pathlib import Path

import pandas as pd
import requests

OUT = Path("data/raw/osm")
UA = {"User-Agent": "rome-by-building/0.1 (open-data map of Rome's buildings)"}
# The fourteen rioni of papal Rome, then the eight drawn as the capital grew (1874–1921).
RIONI = [
    ("I", "Monti"), ("II", "Trevi"), ("III", "Colonna"), ("IV", "Campo Marzio"), ("V", "Ponte"), ("VI", "Parione"),
    ("VII", "Regola"), ("VIII", "Sant'Eustachio"), ("IX", "Pigna"), ("X", "Campitelli"), ("XI", "Sant'Angelo"),
    ("XII", "Ripa"), ("XIII", "Trastevere"), ("XIV", "Borgo"),
    ("XV", "Esquilino"), ("XVI", "Ludovisi"), ("XVII", "Sallustiano"), ("XVIII", "Castro Pretorio"), ("XIX", "Celio"),
    ("XX", "Testaccio"), ("XXI", "San Saba"), ("XXII", "Prati"),
]
EXTRACT = "https://download.geofabrik.de/europe/italy/centro-latest.osm.pbf"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
# Streets inside the Grande Raccordo Anulare and out to Ostia: where the map's labels are read.
STREET_BOX = (41.70, 12.23, 42.03, 12.66)
# The whole comune, for building footprints.
ROME_BOX = (41.65, 12.23, 42.15, 12.86)


def rioni():
    feats = []
    for num, name in RIONI:
        r = requests.get("https://nominatim.openstreetmap.org/search", headers=UA, timeout=60, params={
            "q": f"{name}, Municipio Roma I, Roma", "format": "jsonv2", "polygon_geojson": 1, "limit": 5})
        hit = next((x for x in r.json() if x.get("type") == "quarter" and x["osm_type"] == "relation"), None)
        if hit is None:
            print("no polygon for rione", name)
        else:
            feats.append(dict(type="Feature", geometry=hit["geojson"],
                              properties=dict(num=num, name=name, osm=f"relation/{hit['osm_id']}")))
        time.sleep(1.1)
    (OUT / "rioni.geojson").write_text(json.dumps(dict(type="FeatureCollection", features=feats), ensure_ascii=False))
    print(len(feats), "rioni")


def overpass(q):
    for attempt in range(4):
        url = OVERPASS[attempt % len(OVERPASS)]
        try:
            r = requests.post(url, data={"data": q}, headers=UA, timeout=120)
            if r.ok and r.headers.get("content-type", "").startswith("application/json"):
                return r.json()["elements"]
        except requests.RequestException:
            pass
        time.sleep(20 * (attempt + 1))
    raise RuntimeError("Overpass is unavailable; try again later")


def streets():
    try:
        ways = streets_overpass()
    except RuntimeError as err:
        print(err, "- reading the Geofabrik extract instead")
        ways = streets_extract()
    (OUT / "streets.json").write_text(json.dumps(ways, ensure_ascii=False))
    print(len(ways), "named ways")


def extract() -> Path:
    pbf = OUT / "centro-latest.osm.pbf"
    if not pbf.exists():
        with requests.get(EXTRACT, headers=UA, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(pbf, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    return pbf


def tags(other) -> dict:
    """GDAL keeps the tags it has no column for as '"k"=>"v","k2"=>"v2"'."""
    other = other if isinstance(other, str) else ""
    return dict(kv.split('"=>"', 1) for kv in other.strip('"').split('","') if '"=>"' in kv)


def buildings():
    """Every building footprint in the comune's box, with the tags s01_load reads: kind, name, height, storeys."""
    import pyogrio
    s, w, n, e = ROME_BOX
    b = pyogrio.read_dataframe(extract(), layer="multipolygons", bbox=(w, s, e, n),
                               columns=["osm_id", "osm_way_id", "name", "building", "other_tags"],
                               where="building IS NOT NULL")
    t = b.other_tags.map(tags)
    way, rel = pd.to_numeric(b.osm_way_id), pd.to_numeric(b.osm_id)
    b["osm"] = [f"way/{int(x)}" if x == x else f"relation/{int(r)}" for x, r in zip(way, rel)]
    b["height"] = t.map(lambda d: d.get("height", ""))
    b["levels"] = t.map(lambda d: d.get("building:levels", ""))
    b = b[["osm", "building", "name", "height", "levels", "geometry"]]
    b.to_parquet(OUT / "buildings.parquet")
    print(len(b), "building footprints")


def postcodes():
    """Every address in the comune's box that carries a postcode (addr:postcode), nodes and building outlines alike,
    for the postcode search (s09_postcodes)."""
    import geopandas as gpd
    import pyogrio
    s, w, n, e = ROME_BOX
    where = "other_tags LIKE '%addr:postcode%'"
    pts = pyogrio.read_dataframe(extract(), layer="points", bbox=(w, s, e, n), columns=["other_tags"], where=where)
    areas = pyogrio.read_dataframe(extract(), layer="multipolygons", bbox=(w, s, e, n), columns=["other_tags"], where=where)
    areas["geometry"] = areas.geometry.representative_point()
    a = pd.concat([pts, areas], ignore_index=True)
    t = a.other_tags.map(tags)
    a["cap"] = t.map(lambda d: d.get("addr:postcode", "").strip())
    a["street"] = t.map(lambda d: d.get("addr:street", "").strip())
    gpd.GeoDataFrame(a[["cap", "street"]], geometry=a.geometry, crs=4326).to_parquet(OUT / "postcodes.parquet")
    print(len(a), "addresses with a postcode")


# Ways that are not streets one can look up: unbuilt, platforms, corridors inside buildings, motorway services.
NOT_STREETS = {"construction", "proposed", "abandoned", "razed", "platform", "corridor", "elevator", "bus_stop",
               "raceway", "rest_area", "services", "emergency_bay"}


def search_streets():
    """Every named street, path and square in the comune's box, for the street search (s10_streets): the ways with their
    highway class, and the squares drawn as areas."""
    import geopandas as gpd
    import pyogrio
    s, w, n, e = ROME_BOX
    lines = pyogrio.read_dataframe(extract(), layer="lines", bbox=(w, s, e, n), columns=["osm_id", "name", "highway"],
                                   where="name IS NOT NULL AND highway IS NOT NULL")
    lines = lines[~lines.highway.isin(NOT_STREETS)]
    polys = pyogrio.read_dataframe(extract(), layer="multipolygons", bbox=(w, s, e, n),
                                   columns=["osm_way_id", "name", "place", "other_tags"], where="name IS NOT NULL")
    hw = polys.other_tags.map(lambda o: tags(o).get("highway", ""))
    polys = polys[(polys.place == "square") | (hw == "pedestrian")].copy()
    polys["highway"] = "square"
    polys["geometry"] = polys.geometry.boundary
    polys["osm_id"] = polys.osm_way_id
    a = pd.concat([lines, polys[["osm_id", "name", "highway", "geometry"]]], ignore_index=True)
    a["name"] = a.name.str.strip()
    gpd.GeoDataFrame(a, geometry="geometry", crs=4326).to_parquet(OUT / "search_streets.parquet")
    print(len(lines), "named ways and", len(polys), "squares,", a.name.nunique(), "names")


# What the green areas show, by OSM tag: parks, gardens and woods, and the grass and meadows between them. Farmland,
# orchards and vineyards stay out (the Agro Romano would paint half the comune), and so do nature reserves and protected
# areas, whose outlines take in fields, roads and houses: their woods and meadows show on their own.
GREEN = {
    "leisure": ["park", "garden", "golf_course", "recreation_ground"],
    "landuse": ["forest", "grass", "meadow", "village_green", "recreation_ground"],
    "natural": ["wood", "grassland", "scrub", "heath"],
}


def green():
    """The parks, gardens, woods and meadows in the comune's box (GREEN), for the green areas (s10_green)."""
    import geopandas as gpd
    import pyogrio
    s, w, n, e = ROME_BOX
    where = " OR ".join(f"{k} IN ({', '.join(repr(v) for v in vs)})" for k, vs in GREEN.items())
    g = pyogrio.read_dataframe(extract(), layer="multipolygons", bbox=(w, s, e, n),
                               columns=["osm_id", "osm_way_id", "name", "leisure", "landuse", "natural"], where=where)
    g["kind"] = g.leisure.fillna(g.landuse).fillna(g.natural)
    gpd.GeoDataFrame(g[["name", "kind"]], geometry=g.geometry, crs=4326).to_parquet(OUT / "green.parquet")
    print(len(g), "green areas:", g.kind.value_counts().to_dict())


def building_uses():
    """The building outlines in the comune's box whose tags name a strong use (osm_uses: a church, a hotel, a school,
    a hospital, a cultural venue, a station), for the Use colouring's correction of the survey's homes (s01_load)."""
    import geopandas as gpd
    import pyogrio
    from .osm_uses import BUILT_AS, KEYS, USE_TAGS
    s, w, n, e = ROME_BOX
    values = {}
    for _, keys in USE_TAGS:
        for k, vs in keys.items():
            values.setdefault(k, set()).update(vs)
    values["building"] = set().union(*(vs for _, vs in BUILT_AS))
    columns = ["amenity", "tourism", "leisure", "aeroway", "building"]  # the extract's own columns; the rest are in other_tags
    where = [f"{k} IN ({', '.join(repr(v) for v in sorted(vs))})" for k, vs in values.items() if k in columns]
    where += [f"other_tags LIKE '%\"{k}\"=>\"{v}\"%'" for k, vs in values.items() if k not in columns for v in sorted(vs)]
    b = pyogrio.read_dataframe(extract(), layer="multipolygons", bbox=(w, s, e, n),
                               columns=["osm_id", "osm_way_id", "name", *columns, "other_tags"],
                               where=f"building IS NOT NULL AND ({' OR '.join(where)})")
    t = b.other_tags.map(tags)
    for k in KEYS:
        if k not in columns:
            b[k] = t.map(lambda d: d.get(k))
    way, rel = pd.to_numeric(b.osm_way_id), pd.to_numeric(b.osm_id)
    b["osm"] = [f"way/{int(x)}" if x == x else f"relation/{int(r)}" for x, r in zip(way, rel)]
    gpd.GeoDataFrame(b[["osm", "name", "building", *KEYS]], geometry=b.geometry, crs=4326).to_parquet(OUT / "building_uses.parquet")
    print(len(b), "building outlines with a use tag")


def streets_extract():
    import pyogrio
    pbf = extract()
    s, w, n, e = STREET_BOX
    ways = []
    lines = pyogrio.read_dataframe(pbf, layer="lines", bbox=(w, s, e, n),
                                   columns=["osm_id", "name", "highway", "waterway", "other_tags"])
    lines = lines[lines.name.notna() & (lines.highway.notna() | (lines.waterway == "river"))]
    for r in lines.itertuples():
        t = {k: v for k, v in dict(tags(r.other_tags), name=r.name, highway=r.highway, waterway=r.waterway).items()
             if isinstance(v, str)}
        for g in getattr(r.geometry, "geoms", [r.geometry]):
            ways.append(dict(id=int(r.osm_id), tags=t, geom=[tuple(c) for c in g.coords]))
    polys = pyogrio.read_dataframe(pbf, layer="multipolygons", bbox=(w, s, e, n),
                                   columns=["osm_way_id", "name", "place", "other_tags"])
    polys = polys[polys.name.notna() & (polys.place == "square")]
    for r in polys.itertuples():
        for g in getattr(r.geometry, "geoms", [r.geometry]):
            ways.append(dict(id=int(r.osm_way_id) if r.osm_way_id == r.osm_way_id else 0, tags=dict(name=r.name, place="square"),
                             geom=[tuple(c) for c in g.exterior.coords]))
    return ways


def streets_overpass():
    s, w, n, e = STREET_BOX
    elements, step = [], 0.11
    for lat in [s + i * step for i in range(round((n - s) / step))]:
        for lon in [w + i * step for i in range(round((e - w) / step) + 1)]:
            box = f"{lat},{lon},{lat + step},{lon + step}"
            elements += overpass(f"""[out:json][timeout:300];
              (way["highway"]["name"]({box}); way["place"="square"]["name"]({box});
               way["waterway"="river"]["name"]({box}););
              out tags geom;""")
    seen, ways = set(), []
    for el in elements:
        if el["id"] not in seen:
            seen.add(el["id"])
            ways.append(dict(id=el["id"], tags=el["tags"], geom=[(p["lon"], p["lat"]) for p in el["geometry"]]))
    return ways


def main():
    import sys
    OUT.mkdir(parents=True, exist_ok=True)
    for step in sys.argv[1:] or ["rioni", "streets", "buildings", "postcodes", "search_streets", "green",
                                     "building_uses"]:
        globals()[step]()


if __name__ == "__main__":
    main()
