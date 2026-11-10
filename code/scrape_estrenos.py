"""Upcoming Spanish releases ("Próximos estrenos") from eCartelera.

One request to the release calendar (weeks headed "Semana del 13 al 19 de noviembre", one tile per film
with its day, e.g. "Viernes 13"), plus one request per film page the first time a film appears (and every
14 days after) for the original title, year, director, runtime, genres and country. Posters are embedded
as small data URIs (fetched once per film).

Usage: python3 -I scrape_estrenos.py DATADIR
Writes DATADIR/estrenos.json (list); cache DATADIR/estrenos_cache.json (slug -> details).
Keeps the previous file when the page can't be read or looks wrong.
"""
import base64, datetime, html, json, os, re, sys, time, urllib.request

URL = "https://www.ecartelera.com/peliculas/estrenos/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
DELAY, REFRESH_DAYS, MAX_PAGES = 1.5, 14, 80
MONTHS = {m: i + 1 for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}
TODAY = datetime.date.today()


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        b = r.read()
    return b if binary else b.decode("utf-8", "ignore")


def text(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def week_dates(heading, cursor):
    """'Semana del 27 de noviembre al 3 de diciembre' -> (start date, {day number: date}); the year is the first one
    that keeps the calendar moving forward from `cursor` (the page runs from this week into next year)."""
    m = re.search(r"del (\d+)(?: de (\w+))?(?: de (\d{4}))? al (\d+) de (\w+)(?: de (\d{4}))?", heading.lower())
    if not m:
        return None, {}
    d1, m1, y1, d2, m2, y2 = m.groups()
    mo1, mo2 = MONTHS.get(m1 or m2), MONTHS.get(m2)
    if not mo1 or not mo2:
        return None, {}
    for y in ([int(y1 or y2)] if (y1 or y2) else range(cursor.year, cursor.year + 3)):
        try:
            start = datetime.date(y, mo1, int(d1))
        except ValueError:
            continue
        if start >= cursor - datetime.timedelta(days=3):
            break
    else:
        return None, {}
    days = {(start + datetime.timedelta(days=k)).day: start + datetime.timedelta(days=k) for k in range(7)}
    return start, days


def listing(page):
    out, cursor = [], TODAY - datetime.timedelta(days=40)
    for block in re.split(r'<h3 class="fm-team__title">', page)[1:]:
        head = text(block[:block.find("</h3>")])
        start, days = week_dates(head, cursor)
        if not start:
            continue
        cursor = start
        for tile in re.findall(r'<a class="fm-rel[^"]*" href="([^"]+)">(.*?)</a>', block, re.S):
            href, body = tile
            slug = re.search(r"/peliculas/([^/]+)/", href)
            title = re.search(r'fm-rel__title">(.*?)</span>\s*</span>', body, re.S) or re.search(r'fm-rel__title">(.*?)</span>', body, re.S)
            if not slug or not title:
                continue
            day = re.search(r'fm-rel__year">\s*\w+\s+(\d+)', body)
            date = days.get(int(day.group(1)), start) if day else start
            img = re.search(r'srcset="([^" ]+-th\.jpg)', body) or re.search(r'<img src="([^"]+)"', body)
            out.append({"ec": slug.group(1), "t": text(title.group(1)), "u": href, "date": date.isoformat(),
                        "poster": img.group(1) if img else ""})
    return out


def details(page):
    """Film page -> original title, year, director(s), runtime, genres, country, short synopsis."""
    out = {}
    for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            j = json.loads(blob)
        except ValueError:
            continue
        if j.get("@type") != "Movie":
            continue
        out["orig"] = j.get("alternateName") or ""
        out["d"] = ", ".join(p.get("name", "") for p in j.get("director") or [] if isinstance(p, dict))
        rt = re.search(r"PT(?:(\d+)H)?(\d+)M", j.get("duration") or "")
        out["rt"] = (int(rt.group(1) or 0) * 60 + int(rt.group(2))) if rt else None
        out["ge"] = j.get("genre") or []
        c = j.get("countryOfOrigin")
        out["c"] = (c.get("name") if isinstance(c, dict) else c[0].get("name") if isinstance(c, list) and c else "") or ""
        desc = text(j.get("description") or "")
        out["desc"] = desc[:280].rsplit(" ", 1)[0] + "…" if len(desc) > 280 else desc
    y = re.search(r"Año\s*(?:<[^>]+>\s*)*(\d{4})", page)
    out["y"] = int(y.group(1)) if y else None
    return out


def main(d):
    path, cpath = f"{d}/estrenos.json", f"{d}/estrenos_cache.json"
    cache = json.load(open(cpath)) if os.path.exists(cpath) else {}
    try:
        films = listing(get(URL))
    except Exception as e:
        sys.exit(f"estrenos page failed ({e}); keeping the previous file")
    if len(films) < 10:
        sys.exit(f"only {len(films)} releases parsed; keeping the previous file")
    seen, fetched = set(), 0
    for f in films:
        if f["ec"] in seen:
            continue
        seen.add(f["ec"])
        c = cache.setdefault(f["ec"], {})
        stale = not c.get("chk") or (TODAY - datetime.date.fromisoformat(c["chk"])).days >= REFRESH_DAYS
        if stale and fetched < MAX_PAGES:
            time.sleep(DELAY)
            fetched += 1
            try:
                c.update(details(get(f["u"])), chk=TODAY.isoformat())
            except Exception as e:
                print("  film page failed", f["u"], e, file=sys.stderr)
        if not c.get("img") and f["poster"]:
            time.sleep(0.3)
            try:
                c["img"] = "data:image/jpeg;base64," + base64.b64encode(get(f["poster"], binary=True)).decode()
            except Exception as e:
                print("  poster failed", f["poster"], e, file=sys.stderr)
        for k in ("orig", "y", "d", "rt", "ge", "c", "desc", "img"):
            if c.get(k):
                f[k] = c[k]
        f.pop("poster")
        if f.get("orig", "").lower() == f["t"].lower():
            f.pop("orig")
    out = [f for i, f in enumerate(films) if f["ec"] not in {g["ec"] for g in films[:i]}]   # a film listed twice: first date
    cache = {k: v for k, v in cache.items() if k in seen}
    json.dump(cache, open(cpath, "w"), ensure_ascii=False)
    json.dump(out, open(path, "w"), ensure_ascii=False)
    print(len(out), "releases from", out[0]["date"], "to", out[-1]["date"], "|", fetched, "film pages fetched", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
