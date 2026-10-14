"""Rome: the constants every step shares.

Coordinates are ETRS89 / UTM zone 33N (EPSG:25833), the frame of the Lazio geotopographic database.
The viewer's local frame is metres from Piazza Venezia, x east, z south.
"""
from pyproj import Transformer

CRS = 25833
ISTAT = "058091"          # Roma Capitale
ISTAT_VATICAN = "058000"  # the DBGT's code for buildings outside any Italian comune: the Vatican City
LONLAT = (12.48254, 41.89578)  # Piazza Venezia
TO_UTM = Transformer.from_crs(4326, CRS, always_xy=True)
TO_LONLAT = Transformer.from_crs(CRS, 4326, always_xy=True)
ORIGIN = tuple(round(v, 1) for v in TO_UTM.transform(*LONLAT))
SURVEY = 2014     # the year of the DBGT's latest survey
STOREY_M = 3.2    # metres per storey, for storeys from heights and heights from storeys
