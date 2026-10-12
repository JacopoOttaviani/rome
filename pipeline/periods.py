"""Amsterdam periods. Boundaries follow the city's growth phases, not decades."""
PERIODS = [
    # (key, label, start, end, colour) — oxblood brick for the oldest, through ochre and green, to slate and violet
    ("p1", "Before 1600",              1000, 1599, "#4a1410"),
    ("p2", "1600–1665 Canal ring",     1600, 1665, "#8c1c13"),
    ("p3", "1666–1799",                1666, 1799, "#c0462b"),
    ("p4", "1800–1869",                1800, 1869, "#d97a2b"),
    ("p5", "1870–1913 Nineteenth-century belt", 1870, 1913, "#e5b13a"),
    ("p6", "1914–1940 Amsterdam School", 1914, 1940, "#8e9f3c"),
    ("p7", "1941–1964 Garden cities",  1941, 1964, "#3f8f6b"),
    ("p8", "1965–1984 Bijlmer era",    1965, 1984, "#2c7391"),
    ("p9", "1985–1999 Eastern docks",  1985, 1999, "#3a4f9a"),
    ("p10", "2000– IJburg, Zuidas, Noord", 2000, 2100, "#6a3f8f"),
]

def period_index(year: int) -> int:
    for i, (_, _, a, b, _) in enumerate(PERIODS):
        if a <= year <= b:
            return i
    return 0
