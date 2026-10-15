"""The relief of Rome, for the map's hills view: a 40 m elevation grid, and what each cell is (outside, land, water).

Elevations come from the same 2014 survey as the buildings (DBGT, CC BY 4.0): its contour lines (CV_LIV, every
5 m) and, where the contours stop at the built-up city, the base of every building's volumes. Both are thinned to
one mean value per 20 m cell, joined into a triangulated surface, read at the centre of every 40 m cell and
smoothed a little, so the steps between contour lines do not show. The sea lies at 0 m.

terrain.bin (little-endian):
  header  4s magic 'RTER'; u32 nx, nz; f32 x0, z0 (local centre of the first cell, north-west), cell (m),
          zmin (m), zstep (m per unit)
  u16     height[nz * nx], row by row from north to south: zmin + zstep * value
  u8      kind[nz * nx]: 0 outside the comune, 1 land, 2 water
"""
import glob
import struct
from pathlib import Path

import numpy as np
import pyogrio
import shapely
from rasterio import features
from rasterio.transform import from_origin
from scipy.interpolate import LinearNDInterpolator
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

import geopandas as gpd

from .city import ORIGIN
from .s04_water import water_and_land

CELL = 40.0
THIN = 20.0
ZMIN, ZSTEP = -10.0, 0.1
OUT = Path("web/data/terrain.bin")
# A few places to check the surface against what every Roman knows (lon, lat, rough elevation in metres).
CHECKS = [("Palatine", 12.4875, 41.8892, 50), ("Roman Forum", 12.4853, 41.8925, 15), ("Capitoline", 12.4823, 41.8933, 45),
          ("Piazza Navona", 12.4731, 41.8992, 15), ("Janiculum", 12.4614, 41.8915, 80), ("Monte Mario", 12.4500, 41.9330, 135)]


def thin(xyz: np.ndarray) -> np.ndarray:
    """One mean point per THIN-metre cell."""
    key = np.floor(xyz[:, :2] / THIN).astype(np.int64)
    _, inv = np.unique(key[:, 0] * 10_000_000 + key[:, 1], return_inverse=True)
    n = np.bincount(inv)
    return np.c_[[np.bincount(inv, xyz[:, k]) / n for k in range(3)]].T


def contour_points(bounds) -> np.ndarray:
    parts = []
    for f in sorted(glob.glob("data/raw/dbt/*/contours/CV_LIV.shp")):
        g = pyogrio.read_dataframe(f, columns=[], bbox=bounds)
        xyz = shapely.get_coordinates(g.geometry.values, include_z=True)
        parts.append(thin(xyz[np.isfinite(xyz[:, 2])]))
        print(f.split("/")[3], len(g), "contours,", len(xyz), "vertices →", len(parts[-1]), "points")
    return np.concatenate(parts)


def building_points() -> np.ndarray:
    """The base of every surveyed volume: where the city covers the ground, the contours stop."""
    q = gpd.read_parquet("data/parts.parquet", columns=["ground", "geometry"])
    q = q[np.isfinite(q.ground) & (q.ground > -20)]
    c = q.geometry.centroid
    return thin(np.c_[c.x, c.y, q.ground])


def main():
    city, water, land = water_and_land()
    x0, y0, x1, y1 = city.buffer(1000).bounds
    nx, nz = int(np.ceil((x1 - x0) / CELL)), int(np.ceil((y1 - y0) / CELL))
    pts = np.concatenate([contour_points((x0 - 2000, y0 - 2000, x1 + 2000, y1 + 2000)), building_points()])
    pts = thin(pts)
    print(len(pts), "elevation points; triangulating")
    gx = x0 + (np.arange(nx) + 0.5) * CELL
    gy = y1 - (np.arange(nz) + 0.5) * CELL  # north to south
    X, Y = np.meshgrid(gx, gy)
    h = LinearNDInterpolator(pts[:, :2], pts[:, 2])(X, Y)
    gap = ~np.isfinite(h)
    if gap.any():  # past the last contour: the nearest known elevation
        _, nn = cKDTree(pts[:, :2]).query(np.c_[X[gap], Y[gap]])
        h[gap] = pts[nn, 2]

    transform = from_origin(x0, y1, CELL, CELL)
    kind = features.rasterize([(p, 1) for p in [city]] + [(p, 2) for p in water], out_shape=(nz, nx),
                              transform=transform, fill=0, dtype="uint8")
    sea = (kind == 2) & ~features.rasterize([(city, 1)], out_shape=(nz, nx), transform=transform, fill=0, dtype="uint8").astype(bool)
    h[sea] = 0.0
    h = gaussian_filter(h, 0.9)
    h[sea] = 0.0

    q = np.clip(np.round((h - ZMIN) / ZSTEP), 0, 65535).astype("<u2")
    lx, lz = gx[0] - ORIGIN[0], -(gy[0] - ORIGIN[1])
    OUT.write_bytes(struct.pack("<4sII5f", b"RTER", nx, nz, lx, lz, CELL, ZMIN, ZSTEP) + q.tobytes() + kind.tobytes())

    inside = kind > 0
    print(f"{nx}×{nz} cells of {CELL:.0f} m; land from {h[kind == 1].min():.0f} to {h[kind == 1].max():.0f} m;"
          f" {OUT.stat().st_size / 1e6:.1f} MB")
    from .city import TO_UTM
    for name, lon, lat, expect in CHECKS:
        x, y = TO_UTM.transform(lon, lat)
        i, j = int((y1 - y) // CELL), int((x - x0) // CELL)
        print(f"  {name:14s} {h[i, j]:6.1f} m  (about {expect})")
    assert inside.mean() > 0.3


if __name__ == "__main__":
    main()
