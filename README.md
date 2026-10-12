# Amsterdam, building by building

A static 3D map of every building in Amsterdam, coloured by construction year.
Architecture after paris.bogachev.fr: offline Python pipeline → binary 600 m tiles → three.js.

## Run

```bash
uv sync
uv run python -m pipeline.s01_load        # 3D BAG tiles → data/panden.parquet, data/parts.parquet
uv run python -m pipeline.s02_attributes  # dates, floors, heights → data/buildings.parquet
uv run python -m pipeline.s03_tiles       # → web/data/
python3 -m http.server 8642 --directory web
```

Raw inputs (not in git): `data/raw/boundary.json` (PDOK bestuurlijke gebieden, gemeente Amsterdam),
`data/raw/tile_index.fgb` and `data/raw/3dbag/*.gpkg` (3D BAG v20250903, 202 tiles).

## Data decisions

- Source of footprints, years, heights, LoD1.3 parts: 3D BAG (CC BY 4.0), which carries BAG `oorspronkelijkbouwjaar`.
- Year flags: `exact` (BAG), `faint` (pre-1800 round year in excess of its neighbours, spread across the rounding step),
  `estimated` (BAG placeholder 1005, median of 12 nearest dated buildings within 1 km).
- Round years after 1800 are not inflated (11% end in 0), so smoothing applies only before 1800.
- Floors: `b3_bouwlagen` when below its cap of 5, otherwise height ÷ 3.2 m.
- Ground is flat (base 0); heights are roof 70th percentile minus `b3_h_maaiveld`.

## Next

1. Water from BGT `waterdeel`; city outline.
2. Rijksmonumenten (RCE) as second date source for rebuilt canal houses.
3. Addresses and streets from BAG: search, street selection, street elevation view.
4. Phone tile set (coarser simplification), LOD by distance.
5. Wikidata / Wikipedia / Commons enrichment for named buildings.
6. About page with the imprecision section written for Amsterdam.
