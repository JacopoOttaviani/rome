"""Water (DBGT rivers and lakes, and the sea off Ostia) and the city outline, in the viewer's local frame.

The outline is Rome's comune as the 2011 census sections draw it, with the Vatican City filled in.
The sea is what lies within 8 km of the city and is no part of any Lazio census section.

water.bin / land.bin layout (little-endian):
  u32 nPoly, nRing, nVert; u32 ringStart[nPoly+1]; u32 vertStart[nRing+1]; f32 xz[2*nVert]
First ring of each polygon is its exterior, the rest are holes.
"""
import glob
import struct
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Polygon, box

from .city import CRS, ISTAT
from .s03_tiles import to_local

OUT = Path("web/data")


def polygons(geom):
    return [g for g in getattr(geom, "geoms", [geom]) if g.geom_type == "Polygon" and not g.is_empty]


def pack(geoms) -> bytes:
    ring_start, vert_start, verts = [0], [0], []
    for poly in geoms:
        for ring in [poly.exterior, *poly.interiors]:
            c = shapely.get_coordinates(ring)[:-1]
            if len(c) < 3:
                continue
            verts.append(to_local(c).astype("<f4"))
            vert_start.append(vert_start[-1] + len(c))
        ring_start.append(len(vert_start) - 1)
    V = np.concatenate(verts)
    return (struct.pack("<3I", len(ring_start) - 1, len(vert_start) - 1, len(V))
            + np.array(ring_start, "<u4").tobytes() + np.array(vert_start, "<u4").tobytes() + V.tobytes())


def city_outline():
    s = gpd.read_file("data/raw/istat/R12_11_WGS84.shp").to_crs(CRS)
    rome = shapely.make_valid(s[s.PRO_COM == int(ISTAT)].union_all()).buffer(1).buffer(-1)
    # The Vatican is a hole in the comune; fill every hole, keep the mainland and Ostia.
    rome = shapely.MultiPolygon([Polygon(p.exterior) for p in polygons(rome) if p.area > 1e4])
    near = s[s.intersects(rome.buffer(8000))]
    lazio = shapely.make_valid(near.union_all()).buffer(5).buffer(-5)
    sea = box(*rome.buffer(8000).bounds).difference(lazio).difference(rome)
    sea = max(polygons(sea), key=lambda p: p.area)  # the Tyrrhenian, not slivers between sections
    return rome, sea


def water_and_land():
    """The city outline, and its water (rivers, lakes, the sea) and land as lists of polygons; s08_terrain reuses them."""
    city, sea = city_outline()
    frames = []
    for f in glob.glob("data/raw/dbt/*/AB_CDA_AB_CDA_SUP.shp") + glob.glob("data/raw/dbt/*/SP_ACQ.shp"):
        frames.append(gpd.read_file(f).set_crs(CRS, allow_override=True)[["geometry"]])
    w = gpd.GeoDataFrame(pd.concat(frames), crs=CRS)
    w["geometry"] = shapely.force_2d(w.geometry.values)
    water = shapely.make_valid(w.union_all()).intersection(city.buffer(200))
    water = water.union(sea).buffer(0.5).buffer(-0.5).simplify(1.0)
    water = [p for p in polygons(water) if p.area > 30]
    land = city.difference(shapely.MultiPolygon(water)).simplify(1.0)
    land = [p for p in polygons(land) if p.area > 30]
    return city, water, land


def main():
    city, water, land = water_and_land()
    (OUT / "water.bin").write_bytes(pack(water))
    (OUT / "land.bin").write_bytes(pack(land))
    gpd.GeoDataFrame(geometry=[city], crs=CRS).to_parquet("data/outline.parquet")
    print(f"water {len(water)} polys {sum(p.area for p in water)/1e6:.1f} km², {(OUT/'water.bin').stat().st_size/1e6:.2f} MB;"
          f" land {len(land)} polys {city.area/1e6:.0f} km², {(OUT/'land.bin').stat().st_size/1e6:.2f} MB")


if __name__ == "__main__":
    main()
