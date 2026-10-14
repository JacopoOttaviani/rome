"""ISTAT 2011 census sections for Lazio: their outlines and the census variables (CC BY 4.0).

The 2011 census is the last to count buildings by section: E3 residential buildings, E8–E16 the same by
period of construction (before 1919, 1919–1945, 1946–1960, 1961–1970, 1971–1980, 1981–1990, 1991–2000,
2001–2005, after 2005), E17–E20 by number of floors. The 2021 census releases population only.
"""
import io
import zipfile
from pathlib import Path

import requests

OUT = Path("data/raw/istat")
SECTIONS = "https://www.istat.it/storage/cartografia/basi_territoriali/WGS_84_UTM/2011/R12_11_WGS84.zip"
VARIABLES = "https://www.istat.it/storage/cartografia/variabili-censuarie/dati-cpa_2011.zip"


def get(url):
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    return zipfile.ZipFile(io.BytesIO(r.content))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    z = get(SECTIONS)
    for n in z.namelist():
        if "R12_11_WGS84." in n and not n.endswith(".xls"):
            (OUT / Path(n).name).write_bytes(z.read(n))
    z = get(VARIABLES)
    for n in ("Sezioni di Censimento/R12_indicatori_2011_sezioni.csv", "Sezioni di Censimento/tracciato_2011_sezioni.csv"):
        (OUT / Path(n).name).write_bytes(z.read(n))
    print(sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
