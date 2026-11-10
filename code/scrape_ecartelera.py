"""Scrape Madrid city showtimes from eCartelera (all cinemas, all listed days).

Usage: python3 -I scrape_ecartelera.py OUTDIR
Writes OUTDIR/showtimes.json
"""
import html, json, re, sys, time, datetime, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
CITY = "https://www.ecartelera.com/cines/0,9,1.html"
DELAY = 0.5
TODAY = datetime.date.today()


def get(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            print("  retry", url, e, file=sys.stderr)
            time.sleep(3)
    return ""


def txt(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).strip()


def day_to_date(label):
    # "Martes 03" -> next date on/after today with that day-of-month
    m = re.search(r"(\d{1,2})", label)
    d = int(m.group(1))
    y, mo = TODAY.year, TODAY.month
    if d < TODAY.day:
        mo += 1
        if mo == 13:
            y, mo = y + 1, 1
    return datetime.date(y, mo, d).isoformat()


def parse_cinema(page):
    info = {}
    m = re.search(r'<h1 class="std-tit">(.*?)</h1>', page, re.S)
    info["name"] = txt(m.group(1)) if m else ""
    m = re.search(r"<b>Direcci.n:</b>(.*?)<span", page, re.S)
    info["address"] = txt(m.group(1)) if m else ""
    m = re.search(r'data-lat="([-\d.]+)" data-long="([-\d.]+)"', page)
    info["lat"], info["lon"] = (float(m.group(1)), float(m.group(2))) if m else (None, None)
    m = re.search(r"<b>Cadena:</b>(.*?)</div>", page, re.S)
    info["chain"] = txt(m.group(1)) if m else ""
    m = re.search(r"<b>Precios:</b>(.*?)</p>", page, re.S)
    info["prices"] = txt(m.group(1)) if m else ""
    m = re.search(r"<b>Reducidos y d.a del espectador:</b>(.*?)</p>", page, re.S)
    info["reduced"] = txt(m.group(1)) if m else ""
    days = re.findall(r'<li[^>]*><a href="([^"]+)" title="Cartelera del ([^"]+)"', page)
    info["days"] = [(u, html.unescape(lbl)) for u, lbl in days]
    return info


def parse_films(page):
    films = []
    blocks = re.split(r'<div class="titem"', page)[1:]
    for b in blocks:
        b = b.split('<div class="pub-box')[0]
        f = {}
        m = re.search(r'<p class="tit"><a href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not m:
            continue
        f["url"], f["title"] = m.group(1), txt(m.group(2))
        m = re.search(r'<img\s+src="([^"]+)"', b)
        f["poster"] = m.group(1) if m else ""
        m = re.search(r'<p class="data">(.*?)</p>', b, re.S)
        spans = [txt(s) for s in re.findall(r"<span>(.*?)</span>", m.group(1))] if m else []
        f["runtime"] = next((int(re.match(r"\d+", s).group()) for s in spans if s.endswith("min.")), None)
        rest = [s for s in spans if not s.endswith("min.")]
        f["age"] = next((s for s in rest if re.fullmatch(r"\+\d+|TP|Apta.*", s)), "")
        rest = [s for s in rest if s != f["age"]]
        f["country"] = rest[0] if rest else ""
        f["genre"] = rest[1] if len(rest) > 1 else ""
        m = re.search(r'<p class="dir">(.*?)</p>', b, re.S)
        f["director"] = ", ".join(txt(a) for a in re.findall(r"<a [^>]*>(.*?)</a>", m.group(1))) if m else ""
        m = re.search(r'<p class="cast">(.*?)</p>', b, re.S)
        f["cast"] = [txt(a) for a in re.findall(r"<a [^>]*>(.*?)</a>", m.group(1))][:3] if m else []
        m = re.search(r'<span class="nota[^"]*">([\d.]+)</span>', b)
        f["ec_score"] = float(m.group(1)) if m else None
        f["times"] = re.findall(r'data-session-time="(\d\d:\d\d)"', b)
        f["urls"] = [u for u, _ in re.findall(r'<a href="([^"]+)"[^>]*data-session-time="(\d\d:\d\d)"', b)]
        f["formats"] = re.findall(r'data-session-format="([^"]*)"', b)
        if f["times"]:
            films.append(f)
    return films


def main(outdir):
    city = get(CITY)
    cinemas = []
    seen = set()
    for url, name in re.findall(r'href="(https://www\.ecartelera\.com/cines/[^"]+)" title="Cartelera de cine ([^"]+)"', city):
        if url not in seen:
            seen.add(url)
            cinemas.append((url, html.unescape(name)))
    print(len(cinemas), "cinemas", file=sys.stderr)

    out_cinemas, films, shows = [], {}, []
    for i, (url, name) in enumerate(cinemas):
        time.sleep(DELAY)
        page = get(url)
        if not page:
            continue
        info = parse_cinema(page)
        cid = len(out_cinemas)
        out_cinemas.append({"id": cid, "name": info["name"] or name, "url": url, "address": info["address"],
                            "lat": info["lat"], "lon": info["lon"], "chain": info["chain"], "prices": info["prices"], "reduced": info["reduced"]})
        days = info["days"] or [(url, "Hoy %02d" % TODAY.day)]
        n = 0
        for j, (durl, lbl) in enumerate(days):
            if j > 0:
                time.sleep(DELAY)
                page = get(durl)
            date = day_to_date(lbl)
            for f in parse_films(page):
                key = f["url"]
                if key not in films:
                    films[key] = {k: f[k] for k in ("title", "url", "poster", "runtime", "age", "country", "genre", "director", "cast", "ec_score")}
                for t, fmt, u in zip(f["times"], f["formats"] + [""] * len(f["times"]), f["urls"] + [""] * len(f["times"])):
                    shows.append({"film": key, "cinema": cid, "date": date, "time": t, "format": fmt, "url": u})
                    n += 1
        print(f"[{i+1}/{len(cinemas)}] {name}: {len(days)} days, {n} shows", file=sys.stderr)

    if sum(1 for s in shows) < 50:
        sys.exit("eCartelera returned almost nothing; keeping the previous file")
    json.dump({"scraped": datetime.datetime.now().isoformat(timespec="minutes"), "cinemas": out_cinemas,
               "films": films, "shows": shows}, open(f"{outdir}/showtimes.json", "w"), ensure_ascii=False)
    print(len(films), "films,", len(shows), "shows", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
