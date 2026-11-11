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
22. [x] 2026-11-10 **Further ahead**: sessions up to 3 weeks (7 day buttons + "Más adelante" list; "Toda la semana" = 7 days); Cineteca 21 days (cycle names cached); Filmaffinity keeps yesterday's sessions beyond the days today's page shows, "más días" rotates (data/fa_more_log.json, least recently fetched first, FA ≥ 6.5), 20/30-min time budget and stop at the 2nd 429 (runs on 04/11 and 08/11 hit the 60-min timeout). Check the first GitHub run's fa.log.
23. [x] 2026-11-10 **Próximos estrenos + follow by identity**: code/scrape_estrenos.py (eCartelera release calendar, ~78 films a year ahead; film pages cached 14 days, posters embedded) → `upcoming` in site_data (IMDb id for ~95 %, Letterboxd when it exists); "Próximamente" section (6 weeks + "ver más") and pill; search shows releases with their date; followed films stored as {t, o, y, imdb, ec} (old plain titles still work), matched by IMDb id / eCartelera page / title ± 1 year; "Mis películas" says "En cartel" / "Se estrena el …" / "Sin fecha"; email_alerts.py same matching + release-week email (account checkbox, on by default).
24. [~] 2026-11-11 **Irene's picks** built + tested locally (jsdom, mock Supabase: anon / admin / table missing): `supabase/picks.sql` (public read, admin write via is_admin()), keyed by IMDb id → eCartelera slug → FA id, matched like follows so a pick made on an upcoming film carries over; badge + note on cards, "La selección de Irene" strip at the top (showing now, then upcoming), "Solo la selección de Irene" filter, admin editor in the film panel and on Próximamente rows; picks bypass the few-votes rule. **Waiting: Irene runs picks.sql in Supabase, then commits + pushes.** Renamed 2026-11-11 to "Irene's stamp of approval" (ES "El sello de aprobación de Irene", FR "Le sceau d'approbation d'Irene").
26. [x] 2026-11-11 Film page lists every coming date (grouped by day, selected day in red, VOSE switch still applies), not only the day picked in the header.
25. [ ] Live check 2026-11-11: days 4-6 still ~160 sessions/day vs ~1,150 for days 1-3 (FA rotation needs more runs); scheduled run fires ~13:40 UTC, not 05:30 (GitHub delay).

## Done
- 2026-11-02 v2: Doré, Verdi (per-session prices), Cine Estudio, Berlanga, Casa Encendida; prices + personal discounts; favourite cinemas; cinema panel with SVG map; directory; FA/IMDb/Letterboxd/Media switch; filters (above).
- 2026-11-03 renamed "La Butaca" → "Vamos al cine" (working name; site is for the UC3M economists cinema club)
- 2026-11-02 v1 prototype published: https://claude.ai/artifact/8GUPTmZrpnfoiFtrGzVDMz
