"""Scrape showtimes + ratings for every Madrid-province cinema listed on Filmaffinity.

Usage: python3 -I scrape_filmaffinity.py DATADIR   -> DATADIR/fa_showtimes.json
One page per cinema holds all upcoming days, the Filmaffinity rating and a (VOSE) tag in the session title.
"""
import datetime, html, json, re, sys, time, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
LIST = "https://www.filmaffinity.com/es/theaters.php?state=ES-M"
THEATER = "https://www.filmaffinity.com/es/theater-showtimes.php?id={}"
DELAY = 3.0
AJAX = "https://www.filmaffinity.com/es/theaters.ajax.php"
MORE_MAX = 150          # extra requests per day for days beyond the first ~3
MORE_MIN_RATING = 7.0
MONTHS = {m: i + 1 for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}
TODAY = datetime.date.today()


def get(url):
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            wait = 180 * (attempt + 1) if "429" in str(e) else 10
            print("  retry in", wait, "s", url, e, file=sys.stderr)
            time.sleep(wait)
    return ""


def txt(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def to_date(mday):
    d, _, mon = mday.partition(" de ")
    mo = MONTHS.get(mon.strip().lower())
    if not mo:
        return None
    y = TODAY.year + (1 if mo < TODAY.month else 0)
    return datetime.date(y, mo, int(d)).isoformat()


def parse_rows(block, vose, label):
    """Sessions in one showtimes block: one row per day, times as links titled with the room."""
    shows = []
    for row in re.split(r'<div class="row g-0 mb-2', block)[1:]:
        sd = re.search(r'data-sess-date="(\d{4}-\d\d-\d\d)"', row)
        md = re.search(r'<span class="mday">(.*?)</span>', row)
        date = sd.group(1) if sd else (to_date(txt(md.group(1))) if md and txt(md.group(1)) else None)
        for tag, t in re.findall(r'(<a [^>]*>)\s*(\d\d:\d\d)\s*</a>', row):
            room = re.search(r'title="([^"]*)"', tag)
            href = re.search(r'href="([^"]*)"', tag)
            if date:
                shows.append({"date": date, "time": t, "vose": vose, "label": label, "room": room.group(1) if room else "",
                              "url": html.unescape(href.group(1)) if href else ""})
    return shows


def more_days(out):
    """The theatre page shows ~3 days; 'ver más días' is one request per film and cinema.
    Fetch it only for well-rated films (VOSE first), capped, and stop at the first refusal."""
    todo = []
    for c in out:
        for f in c["films"]:
            for m in f.pop("more", []):
                if (f.get("rating") or 0) >= MORE_MIN_RATING:
                    todo.append((-int(m["vose"]), -(f["rating"] or 0), m, f))
    todo.sort(key=lambda x: (x[0], x[1]))
    done = 0
    for _, _, m, f in todo[:MORE_MAX]:
        time.sleep(DELAY)
        try:
            data = urllib.parse.urlencode({"action": "getMovieTheaterShowtimesBs", "theaterId": m["t"],
                                           "movieId": m["m"], "stId": m["st"]}).encode()
            req = urllib.request.Request(AJAX, data=data, headers={"User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
                                         "Referer": THEATER.format(m["t"]), "Accept-Language": "es-ES,es;q=0.9"})
            with urllib.request.urlopen(req, timeout=30) as r:
                block = json.loads(r.read().decode("utf-8", "ignore")).get("showtimes", "")
        except Exception as e:
            print("  more days stopped:", e, file=sys.stderr)
            break
        have = {(s["date"], s["time"], s["room"]) for s in f["shows"]}
        f["shows"] += [s for s in parse_rows(block, m["vose"], m["label"]) if (s["date"], s["time"], s["room"]) not in have]
        done += 1
    print(f"more days: {done} of {len(todo)} candidate blocks fetched", file=sys.stderr)


def parse_theater(page):
    info = {}
    m = re.search(r"cp=([-\d.]+)~([-\d.]+)", page)
    info["lat"], info["lon"] = (float(m.group(1)), float(m.group(2))) if m else (None, None)
    m = re.search(r'<div class="street">\s*<div>(.*?)</div>\s*([^<,]*)', page, re.S)
    info["address"] = txt(m.group(1)) if m else ""
    info["town"] = txt(m.group(2)) if m else ""
    cards = []
    chunks = page.split('<div class="fs-6 mc-title">')
    for k in range(1, len(chunks)):
        c, prev = chunks[k], chunks[k - 1]
        m = re.search(r'href="https://www\.filmaffinity\.com/es/film(\d+)\.html">(.*?)</a>', c, re.S)
        if not m or "movie-showtimes-n" not in c:
            continue
        f = {"fa_id": m.group(1), "title": txt(m.group(2))}
        posters = re.findall(r'(https://pics\.filmaffinity\.com/[^" ]+-mmed\.jpg)', prev)
        f["poster"] = posters[-1] if posters else ""
        m = re.search(r'class="nflag"[^>]*alt="([^"]*)"', c); f["country"] = m.group(1) if m else ""
        m = re.search(r'mc-year[^"]*">(\d{4})', c); f["year"] = int(m.group(1)) if m else None
        m = re.search(r'mc-director">(.*?)</div></div>', c, re.S)
        f["director"] = ", ".join(txt(a) for a in re.findall(r"<a [^>]*>(.*?)</a>", m.group(1))) if m else ""
        m = re.search(r'mc-cast">(.*?)</div></div>', c, re.S)
        f["cast"] = [txt(a) for a in re.findall(r"<a [^>]*>(.*?)</a>", m.group(1))][:3] if m else []
        m = re.search(r'<div class="avg">\s*([\d,]+)\s*</div>', c); f["rating"] = float(m.group(1).replace(",", ".")) if m else None
        m = re.search(r'<div class="count">.*?([\d.]+)\s*</div>', c, re.S); f["votes"] = int(m.group(1).replace(".", "")) if m else 0
        shows, more = [], []
        for block in c.split('class="movie-showtimes-n')[1:]:
            label = re.search(r'<span class="fs-5">(.*?)</span>', block, re.S)
            label = txt(label.group(1)) if label else ""
            vose = bool(re.search(r"\bV\.?O\.?S?\.?E?\.?\b|\bVOS\b|versi.n original", label, re.I))
            m = re.search(r'class="badge[^"]*runtime">\s*(\d+)', block); f.setdefault("runtime", int(m.group(1)) if m else None)
            m = re.search(r'class="badge[^"]*age-rat"[^>]*>(.*?)<', block); f.setdefault("age", txt(m.group(1)) if m else "")
            shows += parse_rows(block, vose, label)
            ids = re.search(r'data-m-id="(\d+)" data-t-id="(\d+)"', block)
            for st in re.findall(r'data-st-id="(\d+)"', block) if ids and "see-more" in block else []:
                more.append({"m": ids.group(1), "t": ids.group(2), "st": st, "vose": vose, "label": label})
        f["shows"], f["more"] = shows, more
        if shows:
            cards.append(f)
    info["films"] = cards
    return info


def main(datadir):
    lst = get(LIST)
    theaters = list(dict.fromkeys(re.findall(r'theater-showtimes\.php\?id=(\d+)" title="([^"]+)"', lst)))
    print(len(theaters), "cinemas", file=sys.stderr)
    out = []
    for i, (tid, name) in enumerate(theaters):
        time.sleep(DELAY)
        page = get(THEATER.format(tid))
        info = parse_theater(page)
        n = sum(len(f["shows"]) for f in info["films"])
        out.append({"fa_tid": tid, "name": html.unescape(name), "url": THEATER.format(tid), **info})
        print(f"[{i+1}/{len(theaters)}] {html.unescape(name)}: {len(info['films'])} films, {n} shows", file=sys.stderr)
    if sum(1 for c in out if c["films"]) >= 10:
        more_days(out)
    for c in out:
        for f in c["films"]:
            f.pop("more", None)
    if sum(1 for c in out if c["films"]) < 10:
        sys.exit("too few cinemas with sessions; keeping the previous file")
    json.dump({"scraped": datetime.datetime.now().isoformat(timespec="minutes"), "cinemas": out},
              open(f"{datadir}/fa_showtimes.json", "w"), ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1])
