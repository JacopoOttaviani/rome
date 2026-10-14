"""What a building is for, from the DBGT's use (EDIFC_USO) and type (EDIFC_TY) codes.

Rome's fourth colouring, in place of Amsterdam's energy labels: Italy publishes no energy label per building,
but the 2014 survey records every building's use. Codes follow the national specification for geotopographic
databases (AgID, Specifiche di contenuto per i DB Geotopografici).
"""
USES = [
    # (key, label, colour)
    ("none", "Not recorded", "#efeee9"),
    ("home", "Homes", "#e8c39e"),
    ("office", "Government and embassies", "#7b3fa0"),
    ("school", "Schools and universities", "#d99a12"),
    ("health", "Hospitals and care", "#d6336c"),
    ("public", "Other public services", "#b07aa1"),
    ("military", "Military", "#5b6b3a"),
    ("worship", "Churches and convents", "#ec0000"),
    ("transport", "Stations and transport", "#1f4e8c"),
    ("shop", "Shops and markets", "#00909a"),
    ("industry", "Industry and utilities", "#6f6f6f"),
    ("farm", "Farms", "#8cb369"),
    ("culture", "Culture and sport", "#2e8b57"),
    ("hotel", "Hotels", "#8c5a2b"),
    ("minor", "Sheds and minor buildings", "#cfd3d6"),
    ("monument", "Monuments and fountains", "#4a1410"),
]
INDEX = {k: i for i, (k, _, _) in enumerate(USES)}
WORSHIP_TYPES = {"06", "07", "11", "15", "16", "20", "22"}  # baptistery, bell tower, church, mosque, temple, synagogue, cathedral


def use_of(kind: str, use: str, ty: str) -> int:
    if kind == "minor":
        return INDEX["minor"]
    if kind in ("monument", "fountain"):
        return INDEX["monument"]
    if ty in WORSHIP_TYPES or use.startswith("05"):
        return INDEX["worship"]
    if use.startswith("0301"):
        return INDEX["health"]
    if use.startswith("0303"):
        return INDEX["school"]
    return INDEX[{"01": "home", "02": "office", "03": "public", "04": "military", "06": "transport", "07": "shop",
                  "08": "industry", "09": "farm", "10": "culture", "11": "public", "12": "hotel"}.get(use[:2], "none")]
