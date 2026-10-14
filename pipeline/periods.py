"""Rome periods. The oldest five need a dated source (Wikidata); from 1919 they follow the census's own buckets,
which date most of the city. "Before 1919 or undated" holds the census's oldest bucket inside the fourteen
historic rioni and outside the rioni, where a building could be Roman, medieval or of 1900, and the ruins,
monuments and fountains no source dates: it has no span of its own and the map shows it from 1870, the year the
capital came to Rome."""
PERIODS = [
    # (key, label, start, end, colour) — oxblood for antiquity, through brick and ochre, to green, slate and violet
    ("p1", "Antiquity, before 500",        -800, 499, "#3b0d0a"),
    ("p2", "500–1419 Middle Ages",          500, 1419, "#6e1a12"),
    ("p3", "1420–1599 Renaissance",        1420, 1599, "#9c2416"),
    ("p4", "1600–1750 Baroque",            1600, 1750, "#c0462b"),
    ("p5", "1751–1870 Papal Rome",         1751, 1870, "#d97a2b"),
    ("old", "Before 1919 or undated",      None, None, "#a8665a"),
    ("p6", "1871–1918 Capital of Italy",   1871, 1918, "#e5b13a"),
    ("p7", "1919–1945 Between the wars",   1919, 1945, "#8e9f3c"),
    ("p8", "1946–1960 Reconstruction",     1946, 1960, "#3f8f6b"),
    ("p9", "1961–1970 The boom",           1961, 1970, "#2b8a8f"),
    ("p10", "1971–1980",                   1971, 1980, "#2c6391"),
    ("p11", "1981–2000",                   1981, 2000, "#3a4f9a"),
    ("p12", "Since 2001",                  2001, 2100, "#6a3f8f"),
]
UNKNOWN = next(i for i, p in enumerate(PERIODS) if p[0] == "old")
UNKNOWN_YEAR = 1870


def period_index(year: int) -> int:
    for i, (_, _, a, b, _) in enumerate(PERIODS):
        if a is not None and a <= year <= b:
            return i
    return 0
