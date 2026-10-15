"""Contour lines of the Lazio geotopographic database (DBGT 2014, 1:5,000), CC BY 4.0: the relief of Rome's hills.

The region publishes them apart from the other layers, one zip per IGM sheet. Only the contour layer itself
(CV_LIV, with its elevation) is read out of each zip, with HTTP range requests, for the sheets that hold Rome's
buildings (the folders s00_fetch_dbt made).
"""
import glob
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .s00_fetch_dbt import BASE, RangeFile, token

RAW = Path("data/raw/dbt")
FOLDER = "2014_DBGT_5K_SHP/curve-di-livello/Roma"
EXT = (".shp", ".shx", ".dbf", ".prj", ".cpg")


def fetch_sheet(sheet, tok):
    out = RAW / sheet / "contours"
    if (out / "CV_LIV.shp").exists():
        return sheet, "kept"
    z = zipfile.ZipFile(io.BufferedReader(RangeFile(f"{BASE}/api/raw/{FOLDER}/DBT_Contours_{sheet}.zip", tok), 1 << 22))
    out.mkdir(parents=True, exist_ok=True)
    for ext in EXT:
        member = f"DBT_Contours_{sheet}/CV_LIV{ext}"
        if member in z.namelist():
            (out / f"CV_LIV{ext}").write_bytes(z.read(member))
    return sheet, f"{(out / 'CV_LIV.shp').stat().st_size / 1e6:.0f} MB"


def main():
    sheets = sorted(Path(p).name for p in glob.glob(str(RAW / "RM*")))
    tok = token()
    with ThreadPoolExecutor(4) as ex:
        for sheet, what in ex.map(lambda s: fetch_sheet(s, tok), sheets):
            print(sheet, what)


if __name__ == "__main__":
    main()
