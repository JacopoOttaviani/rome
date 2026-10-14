"""When a building first shows up from above, from ISPRA's land-consumption series for Roma Capitale (s00_fetch_ispra).

The series maps Rome's built-up land in 2006, 2012 and every year from 2015 to 2021, each polygon with its class
that year: 2 open land, 122 building site, 111 a building, 116 a yard or car park, and so on. A footprint is a
building from the first year ISPRA marks at least half of it as 111. That is when the finished structure is
visible in the aerial and satellite images, usually a year or two before the building opens; the maps have gaps
(none for 2007–11 or 2013–14), so the year stands for a window that ends then.
"""
from functools import cache

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely

PATH = "data/raw/ispra/SC_Roma_2021_zur_rep_laea.shp"
YEARS = (2006, 2012, 2015, 2016, 2017, 2018, 2019, 2020, 2021)
BUILDING = 111
SHARE = 0.5


@cache
def series() -> gpd.GeoDataFrame:
    s = pyogrio.read_dataframe(PATH, columns=[f"a_{y}" for y in YEARS])
    for y in YEARS:
        s[f"a_{y}"] = pd.to_numeric(s[f"a_{y}"].str.strip(), errors="coerce").fillna(0).astype(int)
    return s


def first_built(geoms: gpd.GeoSeries) -> np.ndarray:
    """For each footprint, the first map year in which ISPRA marks at least half of it as a building; 0 if none."""
    s = series()
    g = geoms.to_crs(s.crs).reset_index(drop=True)
    j = gpd.sjoin(gpd.GeoDataFrame(geometry=g), s, predicate="intersects")
    j["a"] = shapely.area(shapely.intersection(g.values[j.index.values], s.geometry.values[j.index_right.values]))
    area = g.area.values
    first = np.zeros(len(g), int)
    for y in reversed(YEARS):
        share = j.a.where(j[f"a_{y}"] == BUILDING, 0).groupby(level=0).sum().reindex(range(len(g))).fillna(0).values
        first[share >= SHARE * area] = y
    return first


def window(first: int, since: int = 0) -> tuple[int, int]:
    """The years a first sighting stands for: after the previous map, and not before `since` (the survey that saw the
    building unfinished), up to the map that shows it. 2015 → 2013–2015; 2016 → 2016; 2006, since 2003 → 2003–2006."""
    prev = [y for y in YEARS if y < first]
    lo = prev[-1] + 1 if prev else since or first
    return max(lo, since), first
