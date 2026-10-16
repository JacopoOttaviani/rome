# Rome, building by building

Every building standing in Rome in 2014, the year of the region's latest survey, 250,000 of them with the Vatican
City inside it, and 708 finished since, by age and historical context: a 3D map built entirely from open data.

**See it:** [jacopoottaviani.com/rome](https://jacopoottaviani.com/rome/). The city turns slowly on its
own until you touch it; add `?spin=0` to the address to keep it still.

Made with 💙 by [Jacopo Ottaviani](https://jacopoottaviani.com), data journalist and computer scientist. If it's useful to you,
[buy me a coffee](https://ko-fi.com/jacopoottaviani).

A Rome adaptation of Alex Barakov's [Amsterdam, building by building](https://github.com/alexbarakov/amsterdam-by-building)
(MIT), itself inspired by Sasha Bogachev's [Paris, building by building](https://paris.bogachev.fr). The architecture is
his: a data pipeline feeding a three.js city with no build step. The sources, the dating method, the periods, the
layers and the Italian translation are new.

**Want to add a layer?** See [CONTRIBUTING.md](CONTRIBUTING.md).

## How it works

```
open data ──► pipeline/ (Python) ──► web/data/ (binary tiles + JSON) ──► web/ (three.js, no build step)
```

| Step | What it does |
|---|---|
| `s00_fetch_dbt` | Buildings, volumes, monuments and water of the Lazio geotopographic database (DBGT 2014), read out of the region's per-sheet zips with HTTP range requests |
| `s00_fetch_istat` | ISTAT 2011 census sections for Lazio, their outlines and building counts by period of construction |
| `s00_fetch_wikidata` | Every Wikidata item with a coordinate in Rome: dates, architects, styles, heritage status, heights, photos |
| `s00_fetch_osm` | The 22 rioni (Nominatim), named streets (Overpass; when the public Overpass servers are busy, as they were in October 2026, Geofabrik's extract of central Italy) building footprints, the addresses that carry a postcode, every named street of the comune for the search, and parks, gardens, woods and meadows (the extract) |
| `s00_fetch_ispra` | ISPRA's land-consumption series for Roma Capitale, 2006–2021: Rome's built-up land, polygon by polygon, with its class each year |
| `s01_load` | DBGT sheets → one row per building and its volume units (LoD1 parts with eaves heights); the buildings finished since, from OpenStreetMap; the year ISPRA's maps first show each unfinished or newer building |
| `s02_attributes` | Dates every building (see below), and its height |
| `s05_layers` | Resolves every context layer to a bit per building; adds Italian texts |
| `s06_wiki` | Names, photos and extracts from Wikidata, Wikipedia and Commons; survey names for the rest |
| `s03_tiles` | Packs 600 m tiles into 8 bundles, writes per-building attributes and the city config |
| `s04_water` | Water, the sea off Ostia, and the city outline |
| `s07_labels` | Street, square and river names placed along their lines |
| `s00_fetch_contours`, `s08_terrain` | The DBGT's contour lines, and from them and the buildings' bases a 40 m elevation grid for the hills view |
| `s09_postcodes` | Rome's 74 postcodes (CAP) for the search box: each at the middle of the addresses OpenStreetMap files under it, with how far they spread. There is no open map of the postcode areas, so the map pins a middle, not a boundary |
| `s10_streets` | Rome's 17,000 named streets, squares and paths for the search box: each line, its middle and its postcode (see below) |
| `s11_green` | The green areas: parks, gardens, woods and meadows, joined, clipped to the comune and kept off the water (see below) |

## Run it

```bash
uv sync     # or: python3 -m venv .venv && .venv/bin/pip install geopandas numpy pandas pyarrow pyogrio pyproj requests scipy shapely
for s in s00_fetch_dbt s00_fetch_contours s00_fetch_istat s00_fetch_wikidata s00_fetch_osm s00_fetch_ispra; do uv run python -m pipeline.$s; done
for s in s01_load s02_attributes s05_layers s06_wiki s03_tiles s04_water s07_labels s08_terrain s09_postcodes s10_streets s11_green; do uv run python -m pipeline.$s; done
python3 -m http.server 8642 --directory web
```

The fetch steps download about 2.8 GB (1.2 GB of DBGT layers, 1.2 GB of ISPRA's maps, 385 MB of OpenStreetMap). Raw downloads (`data/`) and
generated output (`web/data/`) are not in the repository: they are rebuilt by the pipeline.

`scripts/publish.sh` puts `web/`, with its data, on the `gh-pages` branch that GitHub Pages serves at
jacopoottaviani.com/rome. The branch is rebuilt from scratch each time, so the data never piles up in the history.
`node scripts/og-image.mjs` renders the link-preview image that WhatsApp and Slack show (`web/og-image.jpg`) from the
live site with the Chrome on this machine; run it again after the data changes, then publish.

## Data decisions

- **Years.** Rome has no register that dates each building, as the Dutch BAG or the French BDNB do. Dates come from
  four sources, and every building's card says which one dated it:
  - **Wikidata** dates about 700 buildings from their own items (inception, else official opening): monuments,
    churches, palaces. Items that are gone (P576, P5816 'demolished or destroyed', 'destroyed building or
    structure') do not date what stands on their site now; obelisks carry the date they were carved in Egypt and are
    left out; an ancient date on a building the survey names needs the names to agree, or a church or castle in use
    (the survey's 'Santa Maria dei Martiri' is the Pantheon). A building still being built at the 2014 survey takes
    its opening, since its inception is when the works began: one the survey drew as under construction, or one whose
    item began by 2014 and opened after it within 15 years (La Nuvola, 2008–2016; the temple of the Latter-day
    Saints, 2008–2019). Any other date after 2014 belongs to something else on the site and is left out. So does the
    date of a museum, university or academy whose item is not the building itself: it is the institution's founding
    (Palazzo Massimo's 1998 is the museum's, in a palace of the 1880s; the Galleria Borghese's 1903 is when the state
    bought a villa of 1613). A hospital's counts after 1870, when hospitals were built for themselves, not before
    (Santo Spirito's 727). A Roman ruin under a block of flats taller than 15 m does not date the flats. Items land on the building their coordinate falls in; a church's that falls on the
    block beside it moves to the church within 15 m (Sant'Andrea della Valle), unless it fell on a minor building, which
    is how the survey files small chapels (Bramante's Tempietto); a metro station's dates and names no building above it.
  - **The 2011 census** counts the residential buildings of each of Rome's 13,656 sections by period of construction
    (before 1919, 1919–45, 1946–60, 1961–70, 1971–80, 1981–90, 1991–2000, 2001–05, after 2005). Each section's
    residential DBGT buildings are given those periods in the same proportions. Which building gets which period is
    not known; three things steer it. ISPRA's land maps (below) show which buildings are new since 2006: they take the
    2006–2011 period first, a building standing on the 2006 map never takes it, and a building not yet on it takes no
    older period (of the buildings already in the 2003 survey, 99.2% stand on the 2006 map and 0.05% appear only from
    2012; a finished building of the 2014 survey that ISPRA shows only from 2016 is one its maps missed). Buildings already in the
    2002–03 survey cannot date from after 2005. Those the 2014 survey added or redrew come next; hash order breaks the
    ties. Before this, the newest period went to redrawn buildings at random, and three in four of them already stood
    in 2006. The colour is the census's period, the year is
    spread within it for the timeline; "after 2005" ends with the census, in October 2011. 144,000 buildings are dated
    this way, so read the map as the age of a neighbourhood more than of a single house.
  - **ISPRA's land maps.** ISPRA's land-consumption series for Roma Capitale draws the city's built-up land in 2006,
    2012 and every year from 2015 to 2021, each polygon with its class that year (open land, building site, building,
    yard…). A footprint counts as a building from the first map that marks at least half of it as one: that is when
    the finished structure is visible from above, often a year or two before it opens (the AURA mall: 2018, opened
    April 2018; Esselunga on via Prenestina: 2016, opened April 2017). Where the maps skip years the card gives the
    window: 2013–2015, or from the survey to the map. It dates three groups:
    - **Under construction at the survey.** 501 DBGT buildings are drawn as under construction, 188 of them on
      sheets the 2014 pass did not redraw, so as of 2003. Those ISPRA first shows finished after their survey take
      that window (171 of the 2003 ones read 2003–2006). The rest stay "under construction" in the year of their
      survey: ISPRA shows no finished building on the footprint by 2021, or one already stood there before the works.
    - **Newer than the survey.** OpenStreetMap footprints of at least 40 m² that lie less than a fifth under DBGT
      buildings (about 8,800 in Rome; roofs, sheds, greenhouses and stands aside) and that ISPRA first shows as
      buildings in 2015 or later: 708. Those it shows by 2012 (about 4,000) are older buildings the survey left out
      or drew otherwise; those it never shows (about 4,000) are mostly too small for its maps, yards or car parks,
      or still building sites in 2021. Both are left out, as is anything finished after 2021. Their use is
      OpenStreetMap's `building` tag where it names one.
    - **Built after 2006, with no census period.** A surveyed building ISPRA first shows after 2006 that the census
      leaves without a period, because the section's 2006–2011 count is spent on its other new homes (it was finished
      after the census, in October 2011) or because it is not a home, takes the window between the 2006 map and the
      one that shows it, no later than the 2014 survey that drew it finished.
  - **Before 1919.** In the eight rioni laid out after 1870 (Esquilino to Prati) the census's oldest period becomes
    1871–1918. Elsewhere it stays "before 1919 or undated", its own colour, and appears on the timeline in 1870:
    such a building could be Roman or of 1910.
  - **Everything else** (offices, churches without a Wikidata date, schools, sheds) is not counted by the census and
    takes the median year of its twelve nearest census-dated buildings, drawn paler; where those are mostly "before
    1919", so is it, with no circa-year. Ruins, monuments and fountains no source dates join "before 1919 or
    undated", and their cards say "date unknown".
  - **By hand.** Five landmarks no source dates rightly take their years from their history (Italian Wikipedia):
    Roma Termini 1939–1950 (Mazzoni's project approved in 1939, the station inaugurated in December 1950; its Wikidata
    item gives only the 1863 opening of the station it replaced, and its neighbours had dated it to the 1890s), Roma
    Trastevere station 1911, the Palazzo delle Esposizioni 1880–1882 and the MAXXI 2010, whose Wikidata dates are the
    museums' (see below), and the Palazzo dei Conservatori 1568, whose only other date is the glass hall of 2005 inside.
- **Uses.** The survey lists 248 buildings with several uses, in no order of importance (Termini's list starts with
  the Carabinieri post and ends with the station). The use that says most about the building names it: station,
  hospital, ministry or embassy, school, church, culture, military, shop, hotel, industry, farm, other public
  services, homes. A building with homes and another use takes the other one, as most of them already listed it first.
  The churches and embassies layers read every use: a church inside a school is still in the churches layer.
- **Heights.** Every DBGT volume unit carries its eaves height; a building's height is its tallest volume above its
  lowest base. Monuments (the Colosseum, arches, columns) are drawn by the survey without a
  height: they take Wikidata's (P2048) where it has one, else a default of 8 m (3 m for fountains), and their cards
  say so. A building newer than the survey takes its OpenStreetMap height, else its storeys × 3.2 m, else the median
  height of its twelve nearest DBGT buildings (sheds and kiosks aside), on the ground of the nearest; its card says
  which.
- **Hills.** The button under the compass lifts the city onto its relief; the default view stays flat. The relief is the
  2014 survey's own: its contour lines (every 5 m, CC BY 4.0) and, where they stop at the built-up city, the base of
  every building's volumes, thinned to one value per 20 m, triangulated, read every 40 m and lightly smoothed. Heights
  are doubled so the seven hills, the Gianicolo and Monte Mario read beside the buildings (Monte Mario 140 m, the
  Gianicolo 85 m, the Palatine 47 m on the grid); the smallest summits lose a few metres to the 40 m grid (the
  Capitoline: 38 m for 46). Each building stands on the ground at its centre, with a 4 m footing for slopes; the Tiber
  follows its valley, and thin lines mark every 10 m of real height, stronger every 50 m.
- **Search.** The box under "Roma" takes a postcode or a street. Streets are OpenStreetMap's named ways inside the
  comune, roads, paths and steps alike, and its squares; ways of one name are one street unless they lie more than
  1.2 km apart (Via del Corso is in the centre and in Acilia), and each shows the postcode most of its addresses
  carry, else that of the addresses around its middle. OpenStreetMap mostly spells a closing ordinal out (Corso
  Vittorio Emanuele *Secondo*): the search reads "II" and "Secondo" alike. A street found is drawn in red along its
  length, faintly where buildings hide it.
- **Green areas.** The button under Hills lays OpenStreetMap's parks, gardens, golf courses and recreation grounds,
  woods and forests, grass, meadows, scrub and heath on the ground: 276 km², a fifth of the comune. Farmland,
  orchards and vineyards are left out, or the Agro Romano would paint half the city, and so are the outlines of
  nature reserves and protected areas, which take in fields, roads and houses: their woods and meadows show on their
  own. On the hills the ground itself turns green under a mask of these areas, some 13 m to the pixel, so park edges
  are softer there than on the flat map.
- **The Vatican City** has no Italian municipality code in the DBGT (its buildings carry 058000) and is kept, so the
  map has no hole at St Peter's.
- **Not included** from the Amsterdam original: energy labels (Italy publishes none per building; the fourth colouring
  is building use instead), archive photos, street panoramas, quests and the residents layer, which all rest on
  Dutch sources.

## Licence

Code: MIT (see [LICENSE](LICENSE)). Data keeps the licence of its source: Regione Lazio DBGT 2014 CC BY 4.0; ISTAT
census data CC BY 4.0; Wikidata CC0; Wikipedia text CC BY-SA; Wikimedia Commons photos each under their own licence,
credited in the app; OpenStreetMap © OpenStreetMap contributors, ODbL (the rioni, `web/data/labels.json` and the
footprints of the buildings newer than the survey are derived from it and stay under the ODbL). ISPRA's
land-consumption series for Roma Capitale carries no licence on its download page; ISPRA confirmed in October 2026 that
it can be reused for this map (its national land-consumption maps are CC BY 4.0).
