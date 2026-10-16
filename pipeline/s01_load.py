"""Load the DBGT sheets: one row per building in Rome, and its volume units as LoD1 parts.

Buildings are the DBGT's EDIFC (buildings) and EDI_MIN (minor buildings: sheds, kiosks, cabins). Underground
buildings are left out. The Vatican City has no ISTAT comune code; its buildings carry 058000 and are kept,
since the city around them would otherwise have a hole at St Peter's.

Every volume unit (UN_VOL) names its building (CEDIUV) and carries the height of its eaves (UN_VOL_QE) and
of its base. A part's height is its eaves above the lowest base of the building, so parts on a slope keep
their eaves where they are.

Monuments and large fountains (MN_MAU) come in as their own kinds, one part each; see monuments().

Buildings newer than the survey come from OpenStreetMap, dated by ISPRA's maps; see newer(). Every building the
survey saw under construction gets the year ISPRA first shows it finished, for s02 to date it.
"""
import glob
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from scipy.spatial import cKDTree

from .city import CRS, ISTAT, ISTAT_VATICAN, STOREY_M
from .ispra import first_built
from .uses import main_use

RAW = Path("data/raw/dbt")
KEEP = (ISTAT, ISTAT_VATICAN)
DEFAULT_H = {"monument": 8.0, "fountain": 3.0}

OSM = Path("data/raw/osm/buildings.parquet")
NEW_FROM = 2015        # ISPRA's first map after the survey
NEW_MIN_AREA = 40      # m²; smaller footprints are below what ISPRA's maps tell apart
NEW_OVERLAP = 0.2      # a footprint more covered than this by survey buildings is one the survey already has
# OpenStreetMap ids, numbered past the survey's (sheet number + its id, 13 digits from 3…) and below its
# integration pass (9…): ways from 7 000 000 000 000, relations from 7 900 000 000 000.
WAY_ID, RELATION_ID = 7_000_000_000_000, 7_900_000_000_000
# Not buildings for this map: roofs over pumps and platforms, building sites, ruins, greenhouses, stands, sheds.
NOT_NEW = {"roof", "construction", "ruins", "no", "greenhouse", "grandstand", "shed", "carport", "bungalow"}
# OpenStreetMap's building=* in the survey's use codes (uses.py); anything else is "not recorded".
OSM_USE = {
    **dict.fromkeys(["apartments", "residential", "house", "detached", "semidetached_house", "terrace", "dormitory"], "01"),
    "government": "02", "military": "04",
    **dict.fromkeys(["church", "chapel", "cathedral", "mosque", "synagogue", "temple", "religious"], "05"),
    **dict.fromkeys(["train_station", "transportation"], "06"),
    **dict.fromkeys(["retail", "commercial", "supermarket", "kiosk", "mall"], "07"),
    **dict.fromkeys(["industrial", "warehouse", "factory", "service"], "08"),
    **dict.fromkeys(["farm", "barn", "farm_auxiliary", "stable"], "09"),
    **dict.fromkeys(["sports_hall", "sports_centre", "stadium", "theatre", "museum"], "10"),
    **dict.fromkeys(["civic", "public"], "11"),
    "hospital": "0301", **dict.fromkeys(["school", "university", "kindergarten", "college"], "0303"),
    "hotel": "12",
}


def uid(classid: pd.Series, sheet: pd.Series) -> pd.Series:
    """RM374_0001037850 → 3740001037850: the sheet number and the sheet's own id, as one number.
    A few objects added in an integration pass (INTEG2_0000000011) become 9, the sheet, the pass, the id."""
    m = classid.str.extract(r"^([A-Z]+)(\d*)_(\d+)$")
    regular = m[0] == "RM"
    return pd.Series(np.where(regular, m[1] + m[2].str.zfill(10),
                              "9" + sheet.str.slice(2) + m[1].replace("", "0") + m[2].str.zfill(9)), index=classid.index)


def read(sheet, name, **kw):
    path = RAW / sheet / name
    return pyogrio.read_dataframe(path, **kw) if path.exists() else None


def load_sheet(sheet):
    e = read(sheet, "EDIFC.dbf", read_geometry=False)
    e = e[e.COD_ISTAT.isin(KEEP) & (e.EDIFC_SOT != "02")]
    uses = read(sheet, "EDIFC_EDIFC_USO.dbf", read_geometry=False)
    # A building can have several uses, listed in no order of importance: uses.main_use picks the one that names it.
    use = uses.groupby("CLASSREF").EDIFC_USO.agg(lambda c: main_use(list(c)))
    all_uses = uses.groupby("CLASSREF").EDIFC_USO.agg("|".join)  # every one, for the layers (a church inside a school)
    names = read(sheet, "EDIFC_EDIFC_NOME_T.dbf", read_geometry=False)
    name = names.drop_duplicates("CLASSREF").set_index("CLASSREF").NOME if names is not None else pd.Series(dtype=str)
    b = pd.DataFrame(dict(classid=e.CLASSID, istat=e.COD_ISTAT, kind="edifc", ty=e.EDIFC_TY, state=e.EDIFC_STAT,
                          monumental=e.EDIFC_MON.astype(int), updated=e.DATA_AGG.astype(str).str[:4].astype(int),
                          use=e.CLASSID.map(use).fillna(""), uses=e.CLASSID.map(all_uses).fillna(""),
                          name=e.CLASSID.map(name).fillna("")))
    m = read(sheet, "EDI_MIN.dbf", read_geometry=False)
    if m is not None:
        m = m[m.COD_ISTAT.isin(KEEP) & (m.EDI_MIN_SO != "02")]
        b = pd.concat([b, pd.DataFrame(dict(classid=m.CLASSID, istat=m.COD_ISTAT, kind="minor", ty=m.EDI_MIN_TY,
                                            state=m.EDI_MIN_ST, monumental=0,
                                            updated=m.DATA_AGG.astype(str).str[:4].astype(int), use="", uses="", name=""))])
    foot = [read(sheet, f) for f in ("EDIFC_CR_EDF_IS.shp", "EDI_MIN_CR_EDF_IS.shp")]
    foot = pd.concat([f for f in foot if f is not None]).drop_duplicates("CLASSREF").set_index("CLASSREF").geometry
    b["geometry"] = b.classid.map(foot)
    b = gpd.GeoDataFrame(b[b.geometry.notna()], geometry="geometry", crs=CRS)

    v = read(sheet, "UN_VOL.shp", columns=["CLASSID", "CEDIUV", "UN_VOL_AV", "UN_VOL_QE", "UN_VOL_POR"])
    v = v[v.CEDIUV.isin(b.classid)]
    v["base"] = [shapely.get_coordinates(g, include_z=True)[:, 2].min() for g in v.geometry.values]
    v["geometry"] = shapely.force_2d(v.geometry.values)
    b["hsrc"] = "survey"

    m, mv = monuments(sheet)
    if m is not None:
        b = pd.concat([b, m], ignore_index=True)
        v = pd.concat([v, mv], ignore_index=True)
    v["sheet"] = sheet
    b["sheet"] = sheet
    return gpd.GeoDataFrame(b, geometry="geometry", crs=CRS), v


def monuments(sheet):
    """Monuments and large fountains (MN_MAU): the Colosseum, the Baths of Diocletian, arches, columns, obelisks.
    The survey drew their footprint but recorded no height; they stand at a default height until s02 finds
    one on Wikidata (P2048)."""
    m = read(sheet, "MN_MAU.dbf", read_geometry=False)
    sup = read(sheet, "MN_MAU_MN_MAU_SUP.shp")
    if m is None or sup is None:
        return None, None
    m = m[m.COD_ISTAT.isin(KEEP) & m.MN_MAU_TY.isin(["01", "02", "04"])]
    sup = sup.drop_duplicates("CLASSREF").set_index("CLASSREF").geometry
    m = m[m.CLASSID.isin(sup.index)]
    geom = gpd.GeoSeries(m.CLASSID.map(sup).values, crs=CRS)
    kind = np.where(m.MN_MAU_TY.values == "01", "fountain", "monument")
    keep = geom.area.values >= np.where(kind == "fountain", 80, 20)
    m, geom, kind = m[keep], geom[keep], kind[keep]
    base = np.array([shapely.get_coordinates(g, include_z=True)[:, 2].min() for g in geom.values])
    flat = shapely.force_2d(geom.values)
    h = np.where(kind == "fountain", DEFAULT_H["fountain"], DEFAULT_H["monument"])
    b = gpd.GeoDataFrame(dict(classid=m.CLASSID.values, istat=m.COD_ISTAT.values, kind=kind, ty=m.MN_MAU_TY.values,
                              state="03", monumental=1, updated=m.DATA_AGG.astype(str).str[:4].astype(int).values,
                              use="", uses="", name="", hsrc="default"), geometry=flat, crs=CRS)
    v = gpd.GeoDataFrame(dict(CLASSID=m.CLASSID.values, CEDIUV=m.CLASSID.values, UN_VOL_AV=h, UN_VOL_QE=base + h,
                              UN_VOL_POR="01", base=base), geometry=flat, crs=CRS)
    return b, v


def newer(b: gpd.GeoDataFrame, v: gpd.GeoDataFrame):
    """Buildings finished after the survey: OpenStreetMap footprints the survey does not have (less than a fifth of
    one lies under its buildings) that ISPRA's maps first show as a building in 2015 or later.

    Footprints ISPRA already shows by 2012 are older buildings the survey left out or drew otherwise, and those it
    never shows are mostly too small for its maps, yards or car parks, or still building sites in 2021: all are left
    out. Height comes from the footprint's OpenStreetMap height, else its storeys, else the median height of the
    twelve nearest survey buildings (sheds and kiosks aside); the ground from the nearest of them."""
    o = gpd.read_parquet(OSM).to_crs(CRS)
    o = o[~o.building.isin(NOT_NEW) & (o.area >= NEW_MIN_AREA)].reset_index(drop=True)
    # Inside the comune: its 2011 census sections (s00_fetch_istat).
    s = gpd.read_file("data/raw/istat/R12_11_WGS84.shp", columns=["PRO_COM"])
    rome = gpd.GeoDataFrame(geometry=[s[s.PRO_COM == int(ISTAT)].to_crs(CRS).union_all()], crs=CRS)
    pts = gpd.GeoDataFrame(geometry=o.representative_point(), crs=CRS)
    o = o[o.index.isin(gpd.sjoin(pts, rome, predicate="within").index)].reset_index(drop=True)
    o["i"] = o.index
    inter = gpd.overlay(o[["i", "geometry"]], b[["geometry"]], how="intersection", keep_geom_type=True)
    covered = inter.assign(a=inter.area).groupby("i").a.sum().reindex(o.index).fillna(0) / o.area
    o = o[(covered < NEW_OVERLAP).values].reset_index(drop=True)
    o["ispra"] = first_built(o.geometry)
    print(f"{len(o)} OpenStreetMap footprints the survey does not have; ISPRA first shows them as buildings:",
          o.ispra.value_counts().sort_index().to_dict())
    o = o[o.ispra >= NEW_FROM].reset_index(drop=True)

    kind, num = o.osm.str.split("/", expand=True)[0], o.osm.str.split("/", expand=True)[1].astype("int64")
    ids = (np.where(kind == "way", WAY_ID, RELATION_ID) + num).astype(str)
    number = lambda s: pd.to_numeric(s.str.replace(",", ".").str.extract(r"(\d+(?:\.\d+)?)")[0], errors="coerce")
    h, levels = number(o.height), number(o.levels)
    h = h.where(h.between(2, 250), levels.where(levels.between(1, 70)) * STOREY_M)
    hsrc = np.where(h.notna(), "osm", "neighbours")

    # Neighbours: the survey's buildings with a height, by centre; not its sheds and kiosks.
    tall = (v.UN_VOL_QE - v.ground).clip(lower=2.5).groupby(v.id).max()
    known = b[b.id.isin(tall.index) & (b.kind == "edifc")]
    c = known.geometry.centroid
    tree = cKDTree(np.c_[c.x, c.y])
    oc = o.geometry.centroid
    dist, nn = tree.query(np.c_[oc.x, oc.y], k=12)
    near_h = np.median(known.id.map(tall).to_numpy()[nn], axis=1)
    h = h.fillna(pd.Series(near_h)).to_numpy()
    ground = known.ground.to_numpy()[nn[:, 0]]

    nb = gpd.GeoDataFrame(dict(classid=o.osm, istat=ISTAT, kind="osm", ty="", state="03", monumental=0, updated=0,
                               use=o.building.map(OSM_USE).fillna(""), uses=o.building.map(OSM_USE).fillna(""),
                               name=o.name.fillna(""), hsrc=hsrc,
                               sheet="osm", id=ids, ground=ground, ispra=o.ispra),
                          geometry=o.geometry.values, crs=CRS)
    nv = gpd.GeoDataFrame(dict(id=ids, UN_VOL_AV=h, UN_VOL_QE=ground + h, UN_VOL_POR="01", base=ground, ground=ground),
                          geometry=o.geometry.values, crs=CRS)
    print(f"{len(nb)} newer buildings from OpenStreetMap, {int((hsrc == 'osm').sum())} with their own height")
    return nb, nv


def main():
    sheets = sorted(Path(p).name for p in glob.glob(str(RAW / "RM*")))
    bs, vs = zip(*(load_sheet(s) for s in sheets))
    b = pd.concat(bs, ignore_index=True)
    v = pd.concat(vs, ignore_index=True)

    # A building on the edge of two sheets is drawn on both, under two ids. Keep the copy with more volume units.
    b["id"] = uid(b.classid, b.sheet)
    nparts = v.CEDIUV.value_counts()
    b["nparts"] = b.classid.map(nparts).fillna(0).astype(int)
    b = gpd.GeoDataFrame(b, geometry="geometry", crs=CRS)
    pts = gpd.GeoDataFrame({"i": b.index, "sheet": b.sheet}, geometry=b.representative_point(), crs=CRS)
    j = gpd.sjoin(pts, b[["sheet", "nparts", "geometry"]], predicate="within")
    j = j[j.sheet_left != j.sheet_right]
    drop = set()
    for i, k in zip(j.i, j.index_right):
        if i in drop or k in drop:
            continue
        a, c = b.loc[i], b.loc[k]
        if a.geometry.intersection(c.geometry).area > 0.5 * min(a.geometry.area, c.geometry.area):
            drop.add(i if (a.nparts, a.geometry.area) < (c.nparts, c.geometry.area) else k)
    b = b.drop(index=list(drop))
    print(f"{len(drop)} buildings drawn on two sheets kept once")

    # A monument the survey also drew as a building (the Vittoriano, a church on a monument's base) stays a building.
    mon = b[b.kind.isin(["monument", "fountain"])]
    bld = b[~b.kind.isin(["monument", "fountain"])]
    j = gpd.sjoin(mon[["geometry"]], bld[["geometry"]], predicate="intersects")
    covered = {i for i, k in zip(j.index, j.index_right)
               if b.geometry[i].intersection(b.geometry[k]).area > 0.5 * b.geometry[i].area}
    b = b.drop(index=list(covered))
    print(f"{len(mon) - len(covered)} monuments and fountains; {len(covered)} already drawn as buildings")

    v = v[v.CEDIUV.isin(b.classid)].copy()
    v["id"] = v.CEDIUV.map(dict(zip(b.classid, b.id)))
    ground = v[v.UN_VOL_POR == "01"].groupby("id").base.min()
    v["ground"] = v.id.map(ground).fillna(v.base)
    b["ground"] = b.id.map(v.groupby("id").ground.min())
    b = b.drop(columns=["nparts"])

    # The year ISPRA first shows each building the survey saw unfinished as a building (0: never, up to 2021).
    b["ispra"] = 0
    unfinished = (b.state == "01").to_numpy()
    b.loc[unfinished, "ispra"] = first_built(b.geometry[unfinished])
    print(f"{int(unfinished.sum())} buildings under construction at their survey; ISPRA first shows them finished:",
          b.ispra[unfinished].value_counts().sort_index().to_dict())
    nb, nv = newer(b, v)
    b = pd.concat([b, nb], ignore_index=True)
    v = pd.concat([v, nv], ignore_index=True)
    assert b.id.is_unique

    gpd.GeoDataFrame(b, geometry="geometry", crs=CRS).to_parquet("data/buildings_raw.parquet")
    gpd.GeoDataFrame(v[["id", "UN_VOL_AV", "UN_VOL_QE", "UN_VOL_POR", "base", "ground", "geometry"]],
                     geometry="geometry", crs=CRS).to_parquet("data/parts.parquet")
    print(len(b), "buildings:", b.kind.value_counts().to_dict(), "| Vatican", int((b.istat == ISTAT_VATICAN).sum()),
          "|", len(v), "volume units;", int(b.ground.isna().sum()), "buildings without a volume unit")


if __name__ == "__main__":
    main()
