"""Dates, heights, floors and use per building.

Rome has no register that dates each building, so dates come from four sources, in order of trust:

  wikidata         the building's own Wikidata item gives its inception (P571) or official opening (P1619);
                   a decade, century or millennium is spread across its span (wikidata_approx). A building still
                   being built at the survey takes its opening: its inception is when the works began
  census           the 2011 census counts the residential buildings of each section by period of construction
                   (before 1919, 1919–1945, …, 2006–2011). The section's residential buildings in the DBGT are
                   given those periods in the same proportions, and a year spread across the period. Which
                   building gets which period inside a section is not known; two things steer it:
                   a building already in the 2002–03 survey (DBGT update year 2003) cannot date from after 2005,
                   and buildings the 2014 survey added or redrew take the newest periods first.
  census_old       "before 1919" in the fourteen historic rioni or outside the rioni altogether, where such a
                   building could be Roman or of 1910: no year, shown from 1870. In the eight rioni laid out
                   after 1870 (Esquilino, Prati, Testaccio …) it is spread across 1871–1918.
  ispra            under construction at its survey (2014, or 2003 for a sheet the 2014 pass did not redraw):
                   the first year ISPRA's maps show it as a building, as the end of a window that opens with the
                   survey or the map before (pipeline/ispra.py)
  ispra_new        a building newer than the survey, from OpenStreetMap (s01_load.newer): dated the same way
  estimated        non-residential and minor buildings, and sections without census buildings: the median of the
                   nearest census-dated buildings
  undated          a ruin (DBGT state 'diruto, rudere'), monument or fountain no source dates: year unknown
  construction     under construction at its survey, and ISPRA's maps up to 2021 do not date its completion:
                   the year of that survey
  by_hand          a landmark none of the above dates, or dates wrongly, dated from its history (BY_HAND): when its
                   present building was begun and finished, shown from the year it was finished
  ispra_built      a surveyed building ISPRA's maps show no building on in 2006 and first show later, that the census
                   leaves without a period (finished after October 2011, or not a home): the window between the maps

ISPRA's maps also steer the census: a building they show new since 2006 takes the section's 2006–2011 period first,
and a building standing in 2006 never does. Of the buildings the 2003 survey drew, 99.2% stand on the 2006 map and
0.05% appear only from 2012.
"""
import hashlib
import re

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from .city import CRS, ISTAT, STOREY_M, SURVEY
from .ispra import window
from .periods import PERIODS, UNKNOWN, UNKNOWN_YEAR, period_index
from .wikidata import ancient_ok, dates_its_building, founding_only, labels_of, parse_time, placed, span

(FLAG_WIKIDATA, FLAG_WIKIDATA_APPROX, FLAG_CENSUS, FLAG_CENSUS_OLD, FLAG_ESTIMATED, FLAG_UNDATED, FLAG_CONSTRUCTION,
 FLAG_ISPRA, FLAG_ISPRA_NEW, FLAG_BY_HAND, FLAG_ISPRA_BUILT) = range(11)
FLAGS = ["wikidata", "wikidata_approx", "census", "census_old", "estimated", "undated", "construction", "ispra",
         "ispra_new", "by_hand", "ispra_built"]
MONUMENTS = ("monument", "fountain")
CENSUS = 2011
# Census buckets E8…E16: (variable, first year, last year). The last ends with the census, of October 2011.
BUCKETS = [("E8", None, 1918), ("E9", 1919, 1945), ("E10", 1946, 1960), ("E11", 1961, 1970), ("E12", 1971, 1980),
           ("E13", 1981, 1990), ("E14", 1991, 2000), ("E15", 2001, 2005), ("E16", 2006, CENSUS)]
# A Wikidata item that began before the survey and opened after it was still being built at the survey, as long as
# the works fit in this many years: La Nuvola, 2008–2016. A longer gap is more likely a reopening.
WORKS_YEARS = 15
OLD_RIONI = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV"}
# Dated by hand, by building id: (begun, finished, source). Roma Termini: the census counts no homes there, and
# Wikidata's item gives only the 1863 opening of the station it replaced, so its neighbours dated it to the 1890s.
# Mazzoni's project was approved in 1939 and his side wings built until 1943; the front by Montuori and Vitellozzi
# was finished and the station inaugurated on 20 December 1950.
BY_HAND = {
    "3740001043780": (1939, 1950, "https://it.wikipedia.org/wiki/Stazione_di_Roma_Termini"),
    # Railway stations have no Wikidata date of their building: Roma Trastevere moved here in May 1911.
    "3740001128882": (1911, 1911, "https://it.wikipedia.org/wiki/Stazione_di_Roma_Trastevere"),
    # Museums built for themselves, whose Wikidata date is the museum's (founding_only leaves it out): Palazzo delle
    # Esposizioni, built 1880–1882 and opened in January 1883; the MAXXI, opened in May 2010.
    "3740000996504": (1880, 1882, "https://it.wikipedia.org/wiki/Palazzo_delle_Esposizioni"),
    "3740000986180": (2010, 2010, "https://it.wikipedia.org/wiki/MAXXI_-_Museo_nazionale_delle_arti_del_XXI_secolo"),
    # Palazzo dei Conservatori: the Capitoline Museums' date is the museum's (1471) and the only other is the glass
    # hall of 2005 inside; Michelangelo's rebuilding was finished by Giacomo Della Porta in 1568.
    "3740001136177": (1568, 1568, "https://it.wikipedia.org/wiki/Palazzo_dei_Conservatori"),
}


def unit_hash(ids, salt: str) -> np.ndarray:
    """Deterministic uniform [0,1) per id, so reruns give the same picture."""
    return np.array([int(hashlib.md5((salt + i).encode()).hexdigest()[:8], 16) / 2**32 for i in ids])


def sections() -> gpd.GeoDataFrame:
    s = gpd.read_file("data/raw/istat/R12_11_WGS84.shp")
    s = s[s.PRO_COM == int(ISTAT)].to_crs(CRS)
    v = pd.read_csv("data/raw/istat/R12_indicatori_2011_sezioni.csv", sep=";", encoding="latin1")
    cols = ["E3"] + [b[0] for b in BUCKETS]
    return s[["SEZ2011", "geometry"]].merge(v[["SEZ2011"] + cols], on="SEZ2011", how="left").fillna({c: 0 for c in cols})


def quotas(counts: np.ndarray, n: int) -> np.ndarray:
    """Split n buildings across buckets in the census's proportions (largest remainder)."""
    if counts.sum() == 0:
        return np.zeros_like(counts, dtype=int)
    exact = counts / counts.sum() * n
    q = np.floor(exact).astype(int)
    for k in np.argsort(-(exact - q))[: n - q.sum()]:
        q[k] += 1
    return q


def assign_census(b: gpd.GeoDataFrame, s: gpd.GeoDataFrame, rione: pd.Series) -> None:
    pts = gpd.GeoDataFrame({"i": np.arange(len(b))}, geometry=b.representative_point().values, crs=CRS)
    sec = gpd.sjoin(pts, s, predicate="within").drop_duplicates("i").set_index("i")
    b["section"] = sec.SEZ2011.reindex(range(len(b))).values
    res = (b.kind == "edifc") & b.use.isin(["01", ""]) & (b.state == "03") & b.section.notna()
    u_order = unit_hash(b.id, "order")
    u_year = unit_hash(b.id, "year")
    counts = s.set_index("SEZ2011")[[k for k, _, _ in BUCKETS]]
    fresh_all = b.updated.values == SURVEY
    # ISPRA's maps (s01): standing in 2006, or first seen later. A building the 2003 survey already drew stood then.
    ispra = b.ispra.to_numpy()
    seen06 = ispra == 2006
    new06 = (ispra > 2006) & (ispra <= 2015) & fresh_all  # finished by 2014: a later first sighting is ISPRA's miss
    bucket = b.bucket.to_numpy().copy()
    for sez, idx in b[res].groupby("section").groups.items():
        c = counts.loc[sez].to_numpy(float)
        if c.sum() == 0:
            continue
        idx = np.asarray(idx)
        # More new buildings than the census's 2006–2011 count: the last ISPRA saw were finished after the census
        # (October 2011). They leave the census to ISPRA's own window (apply_ispra).
        new = idx[new06[idx]]
        n_last = quotas(c, len(idx))[-1]
        if len(new) > n_last:
            idx = np.setdiff1d(idx, new[np.lexsort((u_order[new], -ispra[new]))][:len(new) - n_last])
        q = quotas(c, len(idx))
        # Newest periods first: to the buildings ISPRA first shows after 2006, then to those the 2014 survey added or
        # redrew; after 2005 never to one ISPRA shows standing in 2006, nor to one the 2002–03 survey already saw,
        # and before 2006 never to one ISPRA had not yet seen. Hash order breaks the ties.
        order = idx[np.lexsort((u_order[idx], ~fresh_all[idx], ~new06[idx]))]
        taken = np.zeros(len(order), bool)
        for k in range(len(BUCKETS) - 1, -1, -1):
            cand = np.where(~taken)[0]
            if k == len(BUCKETS) - 1:
                cand = cand[fresh_all[order[cand]] & ~seen06[order[cand]]]
                q[k - 1] += max(0, q[k] - len(cand))  # the surplus falls back a period
            else:
                cand = cand[~new06[order[cand]]]
            pick = cand[:q[k]]
            taken[pick] = True
            bucket[order[pick]] = k
    b["bucket"] = bucket

    year, flag, period = b.year.to_numpy().copy(), b.date_flag.to_numpy().copy(), b.period.to_numpy().copy()
    y0s, y1s = b.y0.to_numpy().copy(), b.y1.to_numpy().copy()
    for k, (_, y0, y1) in enumerate(BUCKETS):
        rows = np.where(bucket == k)[0]
        if y0 is None:
            old = np.array([rione.iat[r] in OLD_RIONI or pd.isna(rione.iat[r]) for r in rows], bool)
            year[rows[old]], flag[rows[old]], period[rows[old]] = UNKNOWN_YEAR, FLAG_CENSUS_OLD, UNKNOWN
            y0s[rows[old]], y1s[rows[old]] = -9999, y1
            rows, y0 = rows[~old], 1871  # the rioni drawn after 1870 grew between 1871 and 1918
        year[rows] = np.round(y0 - 0.5 + u_year[rows] * (y1 - y0 + 1)).astype(int)
        flag[rows], y0s[rows], y1s[rows] = FLAG_CENSUS, y0, y1
    b["year"], b["date_flag"], b["period"], b["y0"], b["y1"] = year, flag, period, y0s, y1s
    print("census:", int((flag == FLAG_CENSUS).sum()), "by period,", int((flag == FLAG_CENSUS_OLD).sum()),
          "before 1919 with no year;", int(res.sum()), "residential buildings in sections")


def same_name(survey: str, label: str) -> bool:
    """A survey name matches a Wikidata label when the label contains it, or they share two longer words.
    'Museo dell'Ara Pacis' is not 'Ara Pacis': the museum is not the altar inside it."""
    norm = lambda s: re.sub(r"[^a-zà-ù0-9 ]", " ", s.lower()).split()
    x, y = norm(survey), norm(label)
    if not x or not y:
        return False
    return " ".join(x) in " ".join(y) or len({w for w in x if len(w) > 3} & {w for w in y if len(w) > 3}) >= 2


def date_of(inception: str, opening: str, unfinished_at: int = 0):
    """(year, precision, building) from an item's inceptions, the most precise one first; else its official opening.

    A building still being built at the survey takes its opening year, and `building` is True: one the survey saw
    unfinished (`unfinished_at`, the survey's year), or one whose item began by the survey and opened after it. An
    inception up to an unfinished building's survey is when the works began, and dates nothing."""
    # Coarser than a century says little about a building (the Vittoriano carries "2nd millennium").
    ts = [t for t in (parse_time(x) for x in inception.split("|") if x) if t and t[1] >= 7]
    ys = [int(o[:4]) for o in opening.split("|") if o[:4].isdigit()]
    began = min(ts, key=lambda t: (-t[1], t[0])) if ts else None
    opened = min(ys) if ys else None
    if opened and (unfinished_at or (began and began[0] <= SURVEY < opened <= began[0] + WORKS_YEARS)):
        return opened, 9, True
    if began and not (unfinished_at and began[0] <= unfinished_at):
        return began[0], began[1], False
    return (opened, 9, False) if opened else None


def apply_wikidata(b: gpd.GeoDataFrame, height: pd.Series) -> None:
    """A building's own Wikidata item wins over the census: inception, else official opening (see date_of).
    Where several items stand on one building, the best known (most sitelinks) speaks for it."""
    it = placed()
    it = it[it.classes.map(dates_its_building)].copy()
    # The survey that saw a building unfinished: its own, or 2014 for a building newer than the survey.
    unfinished_at = dict(zip(b.id, np.where(b.kind == "osm", SURVEY, np.where(b.state == "01", b.updated, 0))))
    it["t"] = [date_of(inc, op, unfinished_at.get(i, 0)) for inc, op, i in zip(it.inception, it.opening, it.bid)]
    it = it[it.t.notna()]
    it = it[[t[0] >= 500 or ancient_ok(c) for t, c in zip(it.t, it.classes)]]
    # A museum's, a hospital's or a university's date is its founding, not its building's (wikidata.founding_only).
    it = it[[not founding_only(c, t[0]) for t, c in zip(it.t, it.classes)]]
    # A fountain is dated by a fountain only: the Stadium of Domitian is not the Four Rivers.
    fountains = set(b.id[b.kind == "fountain"])
    it = it[~it.bid.isin(fountains)]
    # Where the survey names the building, the item of that name speaks for it (the Museo dell'Ara Pacis of 2006,
    # not the altar inside it), and an ancient date needs that match: the Fatebenefratelli hospital stands on the
    # site of a temple, it is not the temple.
    name = dict(zip(b.id, b.name))
    it["match"] = [same_name(name.get(i, ""), x) or same_name(name.get(i, ""), y) for i, x, y in zip(it.bid, it.it, it.en)]
    # ... unless the item is a church or a castle still standing in use: the survey's 'Santa Maria dei Martiri'
    # is the Pantheon.
    it["in_use"] = it.classes.map(lambda c: any(k in l for l in labels_of(c) for k in ("church", "basilica", "castle")))
    it = it[[t[0] >= 500 or m or u or not name.get(i) for t, m, u, i in zip(it.t, it.match, it.in_use, it.bid)]]
    # Nor does a ruin under a block of flats date the flats (the Curia of Pompey, under a 26 m palazzo by
    # Sant'Andrea della Valle): an ancient date on a home taller than 15 m needs a church still in use.
    flats = set(b.id[(b.use == "01") & (b.id.map(height) > 15)])
    it = it[[t[0] >= 500 or u or i not in flats for t, u, i in zip(it.t, it.in_use, it.bid)]]
    it = it.sort_values(["match", "links"], ascending=False).drop_duplicates("bid")
    row_of = {k: i for i, k in enumerate(b.id)}
    u = unit_hash(b.id, "wikidata")
    n = 0
    for bid, (y, prec, building), q, label in zip(it.bid, it.t, it.qid, it.en):
        # A later date belongs to something else on the site (a museum opened in an old palace), unless it is the
        # opening of a building still being built at the survey, or the building is newer than the survey.
        if y > SURVEY and not (building or unfinished_at.get(bid)):
            continue
        i = row_of[bid]
        if building:
            print(f"  wikidata: {label or q} ({q}) still being built at the survey, dated by its opening, {y}")
        lo, hi = span(y, prec)
        b.at[i, "year"] = lo if lo == hi else int(round(lo - 0.5 + u[i] * (hi - lo + 1)))
        b.at[i, "y0"], b.at[i, "y1"] = lo, hi
        b.at[i, "date_flag"] = FLAG_WIKIDATA if lo == hi else FLAG_WIKIDATA_APPROX
        b.at[i, "period"] = period_index(int(b.at[i, "year"]))
        b.at[i, "qid_date"] = q
        n += 1
    print("wikidata:", n, "buildings dated by their own item")


def apply_by_hand(b: gpd.GeoDataFrame) -> None:
    """The buildings in BY_HAND take their dates from there, over every other source."""
    for bid, (begun, finished, _) in BY_HAND.items():
        i = b.index[b.id == bid]
        b.loc[i, ["year", "y0", "y1", "date_flag", "qid_date"]] = finished, begun, finished, FLAG_BY_HAND, ""
        b.loc[i, "period"] = period_index(finished)
    print("by hand:", int(b.id.isin(BY_HAND).sum()), "buildings")


def apply_ispra(b: gpd.GeoDataFrame) -> None:
    """Buildings under construction at their survey, the newer ones from OpenStreetMap, and the surveyed ones ISPRA
    first shows after 2006 that nothing else dates: the first year ISPRA's maps show them as a building (s01_load),
    when that comes after their survey; a finished building the 2014 survey drew is no later than 2014."""
    new = (b.kind == "osm").to_numpy()
    unfinished = (b.state == "01").to_numpy()
    # Finished by the 2014 survey, so on the 2012 or the 2015 map: one ISPRA shows only later is one it missed.
    built = ((b.kind == "edifc").to_numpy() & ~unfinished & (b.updated.to_numpy() == SURVEY)
             & (b.ispra.to_numpy() > 2006) & (b.ispra.to_numpy() <= 2015))
    since = np.where(new | built, 0, b.updated.to_numpy())
    undated = b.date_flag.to_numpy() == -1
    todo = np.where(undated & (b.ispra.to_numpy() > since) & (new | unfinished | built))[0]
    for i in todo:
        lo, hi = window(int(b.ispra.iat[i]), int(since[i]))
        if built[i]:
            lo, hi = min(lo, SURVEY), min(hi, SURVEY)
        b.iat[i, b.columns.get_loc("year")] = hi
        b.iat[i, b.columns.get_loc("y0")], b.iat[i, b.columns.get_loc("y1")] = lo, hi
        b.iat[i, b.columns.get_loc("date_flag")] = FLAG_ISPRA_NEW if new[i] else FLAG_ISPRA_BUILT if built[i] else FLAG_ISPRA
    print("ispra:", int(unfinished[todo].sum()), "buildings unfinished at their survey,", int(new[todo].sum()),
          "newer than it,", int(built[todo].sum()), "surveyed ones first seen after 2006, dated by the year ISPRA first shows them")


def estimate_rest(b: gpd.GeoDataFrame) -> None:
    c = b.geometry.centroid
    pts = np.c_[c.x, c.y]
    known = (b.date_flag.isin([FLAG_CENSUS, FLAG_CENSUS_OLD])).values
    tree = cKDTree(pts[known])
    years, old = b.year.values[known], (b.date_flag.values[known] == FLAG_CENSUS_OLD)
    todo = np.where(b.date_flag.values == -1)[0]
    dist, nn = tree.query(pts[todo], k=12, distance_upper_bound=600)
    seen06 = b.ispra.to_numpy() == 2006
    for row, d, n in zip(todo, dist, nn):
        ok = np.isfinite(d)
        if seen06[row]:  # standing on ISPRA's 2006 map: dated by its neighbours of 2006 or earlier
            ok &= np.where(ok, years[np.where(ok, n, 0)] <= 2006, False)
        if b.state.iat[row] == "02" or b.kind.iat[row] in MONUMENTS:
            b.iat[row, b.columns.get_loc("date_flag")] = FLAG_UNDATED
            b.iat[row, b.columns.get_loc("year")], b.iat[row, b.columns.get_loc("period")] = UNKNOWN_YEAR, UNKNOWN
            continue
        if b.state.iat[row] == "01":
            b.iat[row, b.columns.get_loc("date_flag")] = FLAG_CONSTRUCTION
            b.iat[row, b.columns.get_loc("year")] = b.updated.iat[row]
            continue
        b.iat[row, b.columns.get_loc("date_flag")] = FLAG_ESTIMATED
        if ok.any() and old[n[ok]].mean() > 0.5:
            b.iat[row, b.columns.get_loc("year")], b.iat[row, b.columns.get_loc("period")] = UNKNOWN_YEAR, UNKNOWN
        else:
            b.iat[row, b.columns.get_loc("year")] = int(np.median(years[n[ok]])) if ok.any() else 1970


def monument_heights(b: gpd.GeoDataFrame, q: gpd.GeoDataFrame) -> None:
    """A monument with a height on Wikidata (P2048) stands at that height; the rest keep the default."""
    it = placed()
    it = it[(it.height != "") & it.bid.isin(b.id[b.kind.isin(MONUMENTS)])]
    it = it.sort_values("links", ascending=False).drop_duplicates("bid")
    h = dict(zip(it.bid, it.height.astype(float).clip(1, 200)))
    hit = q.id.isin(h)
    q.loc[hit, "UN_VOL_QE"] = q.ground[hit] + q.id[hit].map(h)
    b.loc[b.id.isin(h), "hsrc"] = "wikidata"
    q.to_parquet("data/parts.parquet")
    print("monuments:", len(h), "heights from Wikidata;", int((b.hsrc == "default").sum()), "at the default height")


def main():
    b = gpd.read_parquet("data/buildings_raw.parquet").reset_index(drop=True)
    q = gpd.read_parquet("data/parts.parquet")

    b["year"], b["date_flag"], b["period"], b["bucket"] = 0, -1, -1, -1
    b["y0"], b["y1"], b["qid_date"] = 0, 0, ""
    rioni = gpd.read_file("data/raw/osm/rioni.geojson").to_crs(CRS)
    pts = gpd.GeoDataFrame({"i": np.arange(len(b))}, geometry=b.representative_point().values, crs=CRS)
    r = gpd.sjoin(pts, rioni[["num", "geometry"]], predicate="within").drop_duplicates("i").set_index("i").num
    b["rione"] = r.reindex(range(len(b))).values
    assign_census(b, sections(), b.rione)
    apply_wikidata(b, (q.UN_VOL_QE - q.ground).groupby(q.id).max())  # heights, for ruins under flats
    apply_by_hand(b)
    apply_ispra(b)
    estimate_rest(b)
    dated = b.period < 0
    b.loc[dated, "period"] = b.year[dated].map(period_index)
    b["period"] = b.period.astype(np.uint8)
    b["date_flag"] = b.date_flag.astype(np.uint8)

    monument_heights(b, q)
    # Height: the tallest volume unit's eaves above the building's lowest base.
    q["h"] = (q.UN_VOL_QE - q.ground).clip(lower=2.5)
    b["height"] = b.id.map(q.groupby("id").h.max()).fillna(2.5)
    b["floors"] = np.clip(np.round(b.height / STOREY_M), 1, 99).astype(np.uint8)

    b = b.sort_values("id").reset_index(drop=True)
    b.to_parquet("data/buildings.parquet")
    print({f: int((b.date_flag == i).sum()) for i, f in enumerate(FLAGS)})
    print({PERIODS[k][1]: int(n) for k, n in b.groupby("period").size().items()})


if __name__ == "__main__":
    main()
