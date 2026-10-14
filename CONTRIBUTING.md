# Adding a context layer

A context layer lights up a set of buildings that share a piece of history, and tells why each one is there.

Add a function to [`pipeline/layers.py`](pipeline/layers.py) with the `@layer(...)` decorator:

```python
@layer(
    id="markets", section="The city", title="Markets", era="1890–today",
    text="Two or three sentences on the history behind the layer.",
    caveat="What the source leaves out.",
    source=("Who publishes the data", "https://link.to/the/dataset"),
    groups=[("covered", "Covered market"), ("open", "Open-air market")],
)
def markets():
    return {building_id: "covered", ...}
```

It returns `{building id: group}`, or `{building id: (group, note)}` where a note tells the story behind a building:
`{"name", "name_it", "story", "story_it", "source"}`. Notes with a name are listed in the layer's panel and fly the map
to their building. Helpers are there for the common joins:

- `buildings()`: every building with its id, DBGT use and type, rione, year and date flag;
- `items()`: the Wikidata items standing on buildings (`bid` is the building's id), the building's own item first;
- `by_item(match, story)`: a layer from Wikidata items, where `match(item)` returns a group or `None`.

A layer can use any openly licensed source. Add a download step in `pipeline/s00_fetch_*.py` and say which licence it
carries.

Rules:

- **Every story rests on a source** that says it: a Wikipedia article, a register, a dataset. Legends are named as legends.
- **Stories are short and plain:** one or two sentences, what happened and when.
- **No personal data about private people.** Public figures are fine.
- **Italian next to English.** Add the Italian version of every new text to [`pipeline/i18n_it.py`](pipeline/i18n_it.py);
  `s05_layers` lists any text still missing a translation.

## Checking your layer

```bash
uv run python -m pipeline.s05_layers    # counts per group, named buildings, missing translations
uv run python -m pipeline.s03_tiles
python3 -m http.server 8642 --directory web
```
