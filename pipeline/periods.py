"""Amsterdam periods. Boundaries follow the city's growth phases, not decades."""
PERIODS = [
    # (key, label, start, end, colour)
    ("p1", "Before 1600",              1000, 1599, "#7a1f3d"),
    ("p2", "1600–1665 Canal ring",     1600, 1665, "#b0304a"),
    ("p3", "1666–1799",                1666, 1799, "#d9603b"),
    ("p4", "1800–1869",                1800, 1869, "#e8963f"),
    ("p5", "1870–1913 Nineteenth-century belt", 1870, 1913, "#e9c46a"),
    ("p6", "1914–1940 Amsterdam School", 1914, 1940, "#a7c957"),
    ("p7", "1941–1964 Garden cities",  1941, 1964, "#52b788"),
    ("p8", "1965–1984 Bijlmer era",    1965, 1984, "#2a9d8f"),
    ("p9", "1985–1999 Eastern docks",  1985, 1999, "#3a86c8"),
    ("p10", "2000– IJburg, Zuidas, Noord", 2000, 2100, "#7b6cd9"),
]

def period_index(year: int) -> int:
    for i, (_, _, a, b, _) in enumerate(PERIODS):
        if a <= year <= b:
            return i
    return 0
