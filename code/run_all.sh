#!/usr/bin/env bash
# Full daily pipeline: scrape -> merge -> ratings -> page. Run from anywhere.
# Each scraper keeps the previous file if its source fails, so a bad day shows yesterday's data.
set -u
P="$(cd "$(dirname "$0")/.." && pwd)"
C="$P/code"; D="$P/data"
mkdir -p "$D" "$P/site"
cp -n "$P"/static/*.json "$D"/ 2>/dev/null || true      # map + metro stations (static)
python3 -I "$C/scrape_filmaffinity.py" "$D" 2> "$D/fa.log" || echo "Filmaffinity failed, keeping previous data"
python3 -I "$C/scrape_ecartelera.py"   "$D" 2> "$D/ec.log" || echo "eCartelera failed"
python3 -I "$C/scrape_verdi_dore.py"   "$D" 2> "$D/extra.log" || echo "Verdi/Doré failed"
python3 -I "$C/scrape_arthouse.py"     "$D" 2> "$D/arthouse.log" || echo "Arthouse venues failed"
python3 -I "$C/scrape_cineteca.py"     "$D" 2> "$D/cineteca.log" || echo "Cineteca failed"
python3 -I "$C/scrape_estrenos.py"     "$D" 2> "$D/estrenos.log" || echo "Upcoming releases failed"
[ -f "$D/map.json" ] || python3 -I "$C/build_map.py" "$P/cache/osm/osm.json" "$D/map.json"
python3 -I "$C/build_data.py" "$D" 2> "$D/build.log" && \
python3 -I "$C/enrich_imdb_letterboxd.py" "$D" "$P/cache/imdb" 2> "$D/enrich.log" && \
python3 -I "$C/enrich_wikidata.py" "$D" 2> "$D/wikidata.log"; \
python3 -I "$C/render_page.py" "$D" "$P/site/index.html"
python3 -I "$C/email_alerts.py" "$D" 2> "$D/email.log" || echo "Email alerts failed"
