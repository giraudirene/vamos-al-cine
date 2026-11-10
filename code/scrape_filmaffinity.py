"""Scrape showtimes + ratings for every Madrid-province cinema listed on Filmaffinity.

Usage: python3 -I scrape_filmaffinity.py DATADIR   -> DATADIR/fa_showtimes.json
One page per cinema holds ~3 days, the Filmaffinity rating and a (VOSE) tag in the session title.
Later days come from the capped "ver más días" requests, which rotate (least recently fetched first),
and from yesterday's file: sessions beyond the days today's page shows are kept, so the weeks fill in over runs.
Time budget: theatre pages stop after THEATER_BUDGET, extra days after TOTAL_BUDGET; a second HTTP 429 stops everything.
"""
import datetime, html, json, re, sys, time, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
LIST = "https://www.filmaffinity.com/es/theaters.php?state=ES-M"
THEATER = "https://www.filmaffinity.com/es/theater-showtimes.php?id={}"
DELAY = 3.0
AJAX = "https://www.filmaffinity.com/es/theaters.ajax.php"
MORE_MAX = 150          # extra requests per day for days beyond the first ~3
MORE_MIN_RATING = 6.5
THEATER_BUDGET = 20 * 60   # seconds
TOTAL_BUDGET = 30 * 60
START = time.time()
BLOCKED = False            # set after Filmaffinity refused twice: no more requests this run
MONTHS = {m: i + 1 for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}
TODAY = datetime.date.today()


def elapsed():
    return time.time() - START


def get(url):
    """One page; on HTTP 429 wait 3 min once, and if refused again stop all Filmaffinity requests this run."""
    global BLOCKED
    refused = 0
    for attempt in range(3):
        if BLOCKED:
            return ""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            if "429" in str(e):
                refused += 1
                if refused >= 2:
                    BLOCKED = True
                    print("  refused twice (429): stopping Filmaffinity for this run", file=sys.stderr)
                    return ""
                wait = 180
            else:
                wait = 10
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


def more_days(out, log):
    """The theatre page shows ~3 days; 'ver más días' is one request per film and cinema.
    Fetch it only for well-rated films, capped; least recently fetched first (then VOSE, rating),
    so the cap covers different films each day. Stops at the first refusal or when the time budget is spent."""
    todo = []
    for c in out:
        for f in c["films"]:
            for m in f.pop("more", []):
                if (f.get("rating") or 0) >= MORE_MIN_RATING:
                    key = f'{m["t"]}|{m["m"]}|{m["st"]}'
                    todo.append((log.get(key, ""), -int(m["vose"]), -(f["rating"] or 0), key, m, f))
    todo.sort(key=lambda x: x[:3])
    done = 0
    for _, _, _, key, m, f in todo[:MORE_MAX]:
        if BLOCKED or elapsed() > TOTAL_BUDGET:
            print("  more days: time budget spent" if not BLOCKED else "  more days: blocked", file=sys.stderr)
            break
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
        log[key] = TODAY.isoformat()
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


def keep_previous(out, prev):
    """Add yesterday's sessions that today's pages could not show: for each cinema, sessions dated after the
    last day today's page covers (they came from 'ver más días'); for a cinema not fetched today, all of them."""
    today = TODAY.isoformat()
    by_tid = {c["fa_tid"]: c for c in out}
    kept = 0
    for pc in prev.get("cinemas", []):
        c = by_tid.get(pc["fa_tid"])
        if c is None:                                   # not fetched today (budget or refusal): keep it whole
            c = dict(pc, films=[])
            out.append(c)
            by_tid[pc["fa_tid"]] = c
            covered = today
            c["films"] = []
        else:
            covered = max((s["date"] for f in c["films"] for s in f["shows"]), default=today)
        films = {f["fa_id"]: f for f in c["films"]}
        for pf in pc["films"]:
            old = [s for s in pf["shows"] if s["date"] > covered or (s["date"] >= today and not c.get("fetched"))]
            if not old:
                continue
            f = films.get(pf["fa_id"])
            if f is None:
                f = dict(pf, shows=[])
                c["films"].append(f)
                films[pf["fa_id"]] = f
            have = {(s["date"], s["time"], s["room"]) for s in f["shows"]}
            new = [s for s in old if (s["date"], s["time"], s["room"]) not in have]
            f["shows"] += new
            kept += len(new)
    print(f"kept {kept} sessions from the previous run", file=sys.stderr)


def main(datadir):
    path = f"{datadir}/fa_showtimes.json"
    try:
        prev = json.load(open(path))
    except (OSError, ValueError):
        prev = {"cinemas": []}
    log_path = f"{datadir}/fa_more_log.json"
    try:
        log = json.load(open(log_path))
    except (OSError, ValueError):
        log = {}
    lst = get(LIST)
    theaters = list(dict.fromkeys(re.findall(r'theater-showtimes\.php\?id=(\d+)" title="([^"]+)"', lst)))
    print(len(theaters), "cinemas", file=sys.stderr)
    out = []
    for i, (tid, name) in enumerate(theaters):
        if BLOCKED or elapsed() > THEATER_BUDGET:
            print(f"stopped after {i} cinemas ({'blocked' if BLOCKED else 'time budget'})", file=sys.stderr)
            break
        time.sleep(DELAY)
        page = get(THEATER.format(tid))
        if not page:
            continue
        info = parse_theater(page)
        n = sum(len(f["shows"]) for f in info["films"])
        out.append({"fa_tid": tid, "name": html.unescape(name), "url": THEATER.format(tid), "fetched": True, **info})
        print(f"[{i+1}/{len(theaters)}] {html.unescape(name)}: {len(info['films'])} films, {n} shows", file=sys.stderr)
    fresh = sum(1 for c in out if c["films"])
    if fresh >= 10:
        more_days(out, log)
    for c in out:
        for f in c["films"]:
            f.pop("more", None)
    if fresh < 10:
        sys.exit("too few cinemas with sessions; keeping the previous file")
    keep_previous(out, prev)
    for c in out:
        c.pop("fetched", None)
    log = {k: v for k, v in log.items() if v >= (TODAY - datetime.timedelta(days=14)).isoformat()}
    json.dump(log, open(log_path, "w"))
    json.dump({"scraped": datetime.datetime.now().isoformat(timespec="minutes"), "cinemas": out},
              open(path, "w"), ensure_ascii=False)
    days = {}
    for c in out:
        for f in c["films"]:
            for s_ in f["shows"]:
                days[s_["date"]] = days.get(s_["date"], 0) + 1
    print(f"done in {elapsed() / 60:.1f} min; sessions per day:", sorted(days.items()), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
