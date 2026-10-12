# Amsterdam, building by building

A static 3D map of every building in Amsterdam, coloured by construction year.
Architecture after paris.bogachev.fr: offline Python pipeline → binary 600 m tiles → three.js.

## Run

```bash
uv sync
uv run python -m pipeline.s00_fetch_water # BGT waterdeel → data/raw/bgt_waterdeel.geojson
uv run python -m pipeline.s01_load        # 3D BAG tiles → data/panden.parquet, data/parts.parquet
uv run python -m pipeline.s02_attributes  # dates, floors, heights → data/buildings.parquet
uv run python -m pipeline.s03_tiles       # → web/data/tiles, attrs.bin, amsterdam.json
uv run python -m pipeline.s04_water       # → web/data/water.bin, land.bin
python3 -m http.server 8642 --directory web
```

Raw inputs (not in git): `data/raw/boundary.json` (PDOK bestuurlijke gebieden, gemeente Amsterdam),
`data/raw/tile_index.fgb` and `data/raw/3dbag/*.gpkg` (3D BAG v20250903, 202 tiles),
`data/raw/rce_descriptions.csv` (RCE linked data SPARQL, rijksmonument descriptions, Amsterdam),
`data/raw/wd_monuments.csv` (Wikidata SPARQL: P359 rijksmonument → P5208 BAG pand).

## Data decisions

- Source of footprints, years, heights, LoD1.3 parts: 3D BAG (CC BY 4.0), which carries BAG `oorspronkelijkbouwjaar`.
- Year flags: `exact` (BAG), `faint` (pre-1800 round year in excess of its neighbours, spread across the rounding step),
  `estimated` (placeholder, median of 12 nearest dated buildings within 1 km), `monument` / `monument approx` (RCE).
- Placeholders: 1005 (official, 729 panden) and 1905 (unofficial: 1,184 within 1.5 km of the Dam vs ~100 for 1904/1906).
  The 1905 excess over the neighbouring years' average is estimated, nearest the Dam first.
- Rijksmonumenten: the first date in the RCE description (Roman century ± quarter/half, year, or Dutch ordinal)
  dates the building. RCE replaces BAG only when BAG is more than 10 years later than the RCE span; when BAG is earlier,
  BAG stays, because RCE often dates a later facade. Linked through Wikidata P5208 (93% of Amsterdam's 7,679 monuments).
  Checks: Westerkerk BAG 1761 → 1627; Munttoren BAG 1886 → 1486; Zuiderkerk, Noorderkerk, Trippenhuis unchanged.
- Wikidata inception (P571) is not used: it often records a restoration (Rembrandthuis: 1907).
- Round years after 1800 are not inflated (11% end in 0), so smoothing applies only before 1800.
- Floors: `b3_bouwlagen` when below its cap of 5, otherwise height ÷ 3.2 m.
- Ground is flat (base 0); heights are roof 70th percentile minus `b3_h_maaiveld`.

## Next

1. Addresses and streets from BAG: search, street selection, street elevation view.
2. Phone tile set (coarser simplification), LOD by distance.
3. Wikidata / Wikipedia / Commons enrichment for named buildings.
4. About page with the imprecision section written for Amsterdam.
5. Monuments without a Wikidata BAG link (~7%): match through the RCE address (`ceo:volledigAdres`).
6. Gemeentelijke monumenten Amsterdam as a third date source.
