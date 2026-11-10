# Vamos al cine: to-do

Order chosen 2026-11-02. Tick items off as they ship; add the date.

## In progress
- [x] **v2 published 2026-11-02 (degraded)**: built WITHOUT Filmaffinity (429 block): 23 cinemas from eCartelera + own sites, ratings IMDb/Letterboxd/"Media" only. One Filmaffinity attempt scheduled ~13:50 (`data/fa.log`); when it succeeds: `BUTACA_NO_FA_SEARCH` unset, rerun build_data → enrich → enrich_wikidata → render_page, republish (expect ~50 cinemas, ~4,000 sessions, FA ratings back).

## Reliability first
1. [x] 2026-11-03 **Daily automatic update**: live at https://giraudirene.github.io/vamos-al-cine/ (repo giraudirene/vamos-al-cine, Action 05:30 UTC). First run: 53 cinemas, 97 films, 3,802 sessions; Filmaffinity and Letterboxd both worked from GitHub.
2. [x] **Backup sources** (2026-11-02): every scraper keeps the previous file when its source fails; build_data uses eCartelera for sessions when Filmaffinity data is >36 h old; refuses to write <300 sessions.
3. [~] 2026-11-03 **Full week**: capped "ver más días" fetch (≤150 requests/day, FA ≥ 7, VOSE first; stops at first refusal) in scrape_filmaffinity.py — first real test is the next GitHub run (local IP still 429).

## Choosing a film
4. [x] 2026-11-02 Combined score (FA + IMDb + Letterboxd) and a "critics vs public" badge when they disagree.
5. [ ] Synopsis + trailer link on each film.
6. [x] 2026-11-02 Filters: genre (IMDb genres, Spanish labels), length, country, start-after / finish-before (item 10 partly), **directed by women + LGTBIQ+** (Wikidata P57→P21 / genre+subject; queer festival sessions; never guessed from names).
7. [x] 2026-11-03 "Nuevo" (first seen ≤ 7 days, first run seeds all as old) and "Últimos días" (only when the data covers the week) badges + "Solo novedades" filter.

## Personal
8. [x] 2026-11-03 Letterboxd watchlist import (export .zip or watchlist.csv, read in the browser; matched on Spanish/English/original title ± 1 year) + "Solo mi watchlist" filter + badge.
9. [x] 2026-11-02 Near a metro stop (237 stations from OSM, radius 1/2/4 km, cinemas sorted by distance). Browser location is blocked inside artifacts; revisit on own hosting.
10. [~] Plan an evening: time window + metro area filters exist; a dedicated "plan" view still to do.
11. [ ] **Email alerts + accounts** (decided 2026-11-03: Supabase auth email+password, anyone can sign up; club Gmail sends mail; comments/stars public to read, members write). Follow button + "Mis películas" panel already work locally (this browser only).

## More of Madrid
12. [x] 2026-11-03 More venues: Cine Estudio, Sala Berlanga, La Casa Encendida, **Academia de Cine** (public sessions only), **Casa de América** (free). Institut français: page only lists 2025 events — revisit.
13. [x] 2026-11-03 Festival calendar (next 60 days, grouped by festival across venues: Cine por Mujeres, QueerCineMad, Márgenes, Mi Primer Festival…).
14. [x] 2026-11-02 "Clásico" badge + "Solo clásicos" filter (year < 2000).

## Polish
15. [ ] Own domain (e.g. vamosalcine.es or similar) + installable on phone.
16. [x] 2026-11-03 Language switch ES / EN / FR (all UI text; browser language by default).

## Next (asked 2026-11-03)
17. [ ] Search: works for any title; unknown titles can be followed.  ✔ done in page
18. [ ] Accounts (Supabase): save favourite cinemas, followed films, watchlist, discounts across devices.
19. [ ] Film page: click a film → details, sessions, club stars + comments (public), your stars/comment.
20. [ ] Email alerts when a followed film starts showing (daily job, club Gmail).

## Asked 2026-11-10 (plan: ~/.claude/plans/lively-sniffing-crane.md)
21. [x] 2026-11-10 **Normal prices + día del espectador**: per-session normal price (weekday / weekend+holidays / discount day) from eCartelera's two price lines (parsed daily, code/prices.py) + hand-checked overrides in static/prices.json (Verdi, Cine Estudio, Casa de América); chain fallback; personal discounts only on top.
22. [ ] Further ahead: sessions up to 3 weeks, Filmaffinity sessions kept across days + rotating "más días", time budget so runs stop being cancelled.
23. [ ] Próximos estrenos (eCartelera) + follow a film by id, alerts on release.
24. [ ] Irene's picks (Supabase table, admin edits from the film page; badge, note, top strip, filter).

## Done
- 2026-11-02 v2: Doré, Verdi (per-session prices), Cine Estudio, Berlanga, Casa Encendida; prices + personal discounts; favourite cinemas; cinema panel with SVG map; directory; FA/IMDb/Letterboxd/Media switch; filters (above).
- 2026-11-03 renamed "La Butaca" → "Vamos al cine" (working name; site is for the UC3M economists cinema club)
- 2026-11-02 v1 prototype published: https://claude.ai/artifact/8GUPTmZrpnfoiFtrGzVDMz
