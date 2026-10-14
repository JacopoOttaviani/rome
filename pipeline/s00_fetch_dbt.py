"""Fetch the buildings of Rome from the Lazio geotopographic database (DBGT 2014, 1:5,000), CC BY 4.0.

Regione Lazio publishes the DBGT as one zip per IGM 1:50,000 sheet (up to 580 MB each). Only a few members are
needed, so they are read out of the remote zip with HTTP range requests rather than downloading the whole file:

  EDIFC             buildings (use, type, state); EDIFC_CR_EDF_IS their ground footprint; EDIFC_EDIFC_NOME_T names
  EDI_MIN           minor buildings (sheds, kiosks, cabins), with their footprint
  UN_VOL            volume units: a building's parts, each with its height above ground (UN_VOL_AV)
  MN_MAU            monuments and fountains (the Colosseum, arches, columns, obelisks), footprint only
  AB_CDA            water: the wet area of rivers and canals (Tevere, Aniene); SP_ACQ lakes and ponds

A sheet is kept when any of its buildings carries Rome's ISTAT code (058091).
"""
import io
import shutil
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyogrio
import requests

BASE = "https://geoportale.regione.lazio.it/cartografia"
FOLDER = "2014_DBGT_5K_SHP/strati-informativi/Roma"
OUT = Path("data/raw/dbt")
ROMA = "058091"
SHEETS = ["RM354", "RM356", "RM363", "RM364", "RM365", "RM366", "RM367", "RM373", "RM374", "RM375", "RM376",
          "RM386", "RM387", "RM388", "RM389", "RM399", "RM400", "RM401"]
LAYERS = ["EDIFC", "EDIFC_EDIFC_USO", "EDIFC_EDIFC_NOME_T", "EDIFC_CR_EDF_IS", "EDI_MIN", "EDI_MIN_CR_EDF_IS",
          "UN_VOL", "AB_CDA", "AB_CDA_AB_CDA_SUP", "SP_ACQ", "MN_MAU", "MN_MAU_MN_MAU_SUP"]
EXT = (".shp", ".shx", ".dbf", ".prj", ".cpg")


def token():
    """The geoportal's file browser runs without accounts but still wants a session token on each request."""
    for attempt in range(6):
        r = requests.post(f"{BASE}/api/login", json={"username": "", "password": "", "recaptcha": ""}, timeout=60)
        if r.ok and r.text.startswith("ey"):
            return r.text
        time.sleep(15 * (attempt + 1))
    r.raise_for_status()
    raise RuntimeError("the geoportal gave no session token")


class RangeFile(io.RawIOBase):
    """A remote file read with HTTP range requests, enough for zipfile to find and inflate single members."""

    def __init__(self, url, tok):
        self.url, self.pos, self.s = url, 0, requests.Session()
        self.s.headers["X-Auth"] = tok
        r = self.s.get(url, headers={"Range": "bytes=0-0"}, timeout=60)
        r.raise_for_status()
        self.size = int(r.headers["content-range"].split("/")[1])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size or not len(b):
            return 0
        end = min(self.size, self.pos + len(b)) - 1
        for attempt in range(4):
            try:
                r = self.s.get(self.url, headers={"Range": f"bytes={self.pos}-{end}"}, timeout=300)
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 3:
                    raise
        d = r.content
        b[:len(d)] = d
        self.pos += len(d)
        return len(d)


def fetch_sheet(sheet, tok):
    url = f"{BASE}/api/raw/{FOLDER}/DBT_Lazio_{sheet}.zip"
    z = zipfile.ZipFile(io.BufferedReader(RangeFile(url, tok), 1 << 22))
    names = set(z.namelist())
    edifc = f"DBT_Lazio_{sheet}/EDIFC.dbf"
    if edifc not in names:
        return sheet, 0
    out = OUT / sheet
    out.mkdir(parents=True, exist_ok=True)
    if not (out / "EDIFC.dbf").exists():
        (out / "EDIFC.dbf").write_bytes(z.read(edifc))
    codes = pyogrio.read_dataframe(out / "EDIFC.dbf", columns=["COD_ISTAT"], read_geometry=False).COD_ISTAT
    n = int((codes == ROMA).sum())
    if not n:
        shutil.rmtree(out)
        return sheet, 0
    for layer in LAYERS:
        for ext in EXT:
            member = f"DBT_Lazio_{sheet}/{layer}{ext}"
            if member in names and not (out / f"{layer}{ext}").exists():
                (out / f"{layer}{ext}").write_bytes(z.read(member))
    return sheet, n


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tok = token()
    with ThreadPoolExecutor(4) as ex:
        for sheet, n in ex.map(lambda s: fetch_sheet(s, tok), SHEETS):
            print(sheet, f"{n} buildings in Rome" if n else "skipped")


if __name__ == "__main__":
    main()
