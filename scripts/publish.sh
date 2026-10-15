#!/bin/sh
# Publishes web/, with the generated data, to the gh-pages branch that serves jacopoottaviani.com/rome.
# The branch is rebuilt from scratch each time, so the data never piles up in the history.
# web/data/tiles/ stays out: the map reads the eight packs, not the loose tiles.
set -eu
cd "$(dirname "$0")/.."
test -f web/data/rome.json || { echo "web/data/ is empty: run the pipeline first (see README)." >&2; exit 1; }
remote=$(git remote get-url origin)
rev=$(git describe --always --dirty)
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
rsync -a --exclude /data/tiles/ --exclude .DS_Store web/ "$out/"
touch "$out/.nojekyll"
git -C "$out" init -q -b gh-pages
git -C "$out" add -A
git -C "$out" commit -q -m "Publish web/ at $rev"
git -C "$out" push -q -f "$remote" gh-pages
echo "Published web/ at $rev to gh-pages."
