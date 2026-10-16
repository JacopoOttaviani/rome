"""Rome's green areas: parks, gardens, woods and meadows, for the map's green button.

Source: OpenStreetMap (ODbL), fetched by s00_fetch_osm (green, which lists the tags it keeps and why farmland and
nature reserves stay out). The areas are joined into one surface, clipped to the comune and kept off the water,
simplified to 3 m, and the slivers under MIN_AREA dropped. On the hills the viewer does not drape these polygons over
the slopes: it draws them once into a mask, and the hills' ground turns green under it.

web/data/green.bin: the layout of water.bin (s04_water).
"""
from pathlib import Path

import geopandas as gpd
import shapely

from .city import CRS
from .s04_water import pack, polygons, water_and_land

MIN_AREA = 400.0


def main():
    city, water, _ = water_and_land()
    g = gpd.read_parquet("data/raw/osm/green.parquet").to_crs(CRS)
    g = g[g.intersects(city)]
    green = shapely.union_all(shapely.make_valid(g.geometry.values))
    green = green.intersection(city).difference(shapely.union_all(water))
    green = green.buffer(0.5).buffer(-0.5).simplify(3)
    parts = [p for p in polygons(green) if p.area > MIN_AREA]
    path = Path("web/data/green.bin")
    path.write_bytes(pack(parts))
    print(f"{len(g)} OSM areas → {len(parts)} green areas, {sum(p.area for p in parts) / 1e6:.1f} km² "
          f"({sum(p.area for p in parts) / city.area:.0%} of the comune); {path.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
