# Vamos al cine: to-do

Order chosen 2026-11-02. Tick items off as they ship; add the date.

## In progress
- [x] **v2 published 2026-11-02 (degraded)**: built WITHOUT Filmaffinity (429 block): 23 cinemas from eCartelera + own sites, ratings IMDb/Letterboxd/"Media" only. One Filmaffinity attempt scheduled ~13:50 (`data/fa.log`); when it succeeds: `BUTACA_NO_FA_SEARCH` unset, rerun build_data → enrich → enrich_wikidata → render_page, republish (expect ~50 cinemas, ~4,000 sessions, FA ratings back).

## Reliability first
1. [x] 2026-11-03 **Daily automatic update**: live at https://giraudirene.github.io/vamos-al-cine/ (repo giraudirene/vamos-al-cine, Action 05:30 UTC). First run: 53 cinemas, 97 films, 3,802 sessions; Filmaffinity and Letterboxd both worked from GitHub.
2. [x] **Backup sources** (2026-11-02): every scraper keeps the previous file when its source fails; build_data uses eCartelera for sessions when Filmaffinity data is >36 h old; refuses to write <300 sessions.
3. [ ] **Full week of showtimes**: Filmaffinity shows ~3 days per cinema; the rest sits behind "ver más días" (AJAX, handler in an external FA script). Per film × cinema it would be ~1,800 requests/day = blocked. Test instead a per-film Madrid showtimes page (~100 requests/day for every cinema and day) once the 429 block lifts.

## Choosing a film
4. [x] 2026-11-02 Combined score (FA + IMDb + Letterboxd) and a "critics vs public" badge when they disagree.
5. [ ] Synopsis + trailer link on each film.
6. [x] 2026-11-02 Filters: genre (IMDb genres, Spanish labels), length, country, start-after / finish-before (item 10 partly), **directed by women + LGTBIQ+** (Wikidata P57→P21 / genre+subject; queer festival sessions; never guessed from names).
7. [ ] Tags: "new this week", "last chance" — needs item 3 first (only ~3 days of data, "last chance" would be wrong).

## Personal
8. [ ] Letterboxd watchlist import (username) → highlight watchlist films, hide films already seen.
9. [x] 2026-11-02 Near a metro stop (237 stations from OSM, radius 1/2/4 km, cinemas sorted by distance). Browser location is blocked inside artifacts; revisit on own hosting.
10. [~] Plan an evening: time window + metro area filters exist; a dedicated "plan" view still to do.
11. [ ] Alerts / weekly digest (e.g. rating > 8, VOSE, my cinemas).

## More of Madrid
12. [~] More venues: **done 2026-11-02** Cine Estudio (Círculo, weekly table), Sala Berlanga (WP API + activity pages, incl. QueerCineMad), La Casa Encendida (/cine listing, incl. Festival Márgenes) → `scrape_arthouse.py`. **Still to do**: mk2 Instituto Francés, Academia de Cine, Casa de América (programme URLs 404 or no times in HTML; find the right pages).
13. [ ] Festival calendar (Documenta Madrid, Cine por Mujeres, Semana de Cine Experimental, …) with dates and programmes.
14. [x] 2026-11-02 "Clásico" badge + "Solo clásicos" filter (year < 2000).

## Polish
15. [ ] Own domain (e.g. vamosalcine.es or similar) + installable on phone.
16. [ ] Language switch ES / EN / FR.

## Done
- 2026-11-02 v2: Doré, Verdi (per-session prices), Cine Estudio, Berlanga, Casa Encendida; prices + personal discounts; favourite cinemas; cinema panel with SVG map; directory; FA/IMDb/Letterboxd/Media switch; filters (above).
- 2026-11-03 renamed "La Butaca" → "Vamos al cine" (working name; site is for the UC3M economists cinema club)
- 2026-11-02 v1 prototype published: https://claude.ai/artifact/8GUPTmZrpnfoiFtrGzVDMz
