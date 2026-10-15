"""ISPRA's land-consumption series for Roma Capitale, 2006–2021: about 360,000 polygons, each with its land class
in 2006, 2012 and every year from 2015 to 2021 (class 111: buildings). It dates the buildings the 2014 survey saw
under construction and those it does not have (see pipeline/ispra.py).

ISPRA publishes it in its data library with no licence on the folder, and confirmed in October 2026 that it can be
reused for this map; ISPRA's national land-consumption maps are CC BY 4.0. Files already downloaded are kept.
"""
from pathlib import Path

import requests

OUT = Path("data/raw/ispra")
UA = {"User-Agent": "Mozilla/5.0 (rome-by-building; open-data map of Rome's buildings)"}
BASE = ("https://groupware.sinanet.isprambiente.it/uso-copertura-e-consumo-di-suolo/library/consumo-di-suolo/"
        "consumo-suolo-roma-capitale-dati-2017/edizione-2022/consumo-2006-2021")
NAME = "SC_Roma_2021_zur_rep_laea"
# The library gives every file its own page; the suffixes are its page names.
FILES = {"shp": "", "shx": "-2", "dbf": "-3", "prj": "-4", "cpg": "-1"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for ext, page in FILES.items():
        path = OUT / f"{NAME}.{ext}"
        if path.exists() and path.stat().st_size > 0:
            continue
        url = f"{BASE}/{NAME.lower()}{page}/download/en/1/{NAME}.{ext}"
        with requests.get(url, headers=UA, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(path.with_suffix(".part"), "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        path.with_suffix(".part").rename(path)
        print(path.name, path.stat().st_size // 1_000_000, "MB")
    print("ISPRA Roma Capitale series in", OUT)


if __name__ == "__main__":
    main()
