"""Scrape Cines Verdi Madrid (schema.org ScreeningEvent data on each film page) and
Cine Doré / Filmoteca Española (ticket-shop listing pages).

Usage: python3 -I scrape_verdi_dore.py DATADIR   -> DATADIR/extra_cinemas.json
Output: [{name, url, price, shows: [{title, year, director, date, time, vose, price, cycle, url}]}]
"""
import datetime, html, json, re, sys, time, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
VERDI = "https://madrid.cines-verdi.com"
DORE = "https://entradasfilmoteca.sacatuentrada.es/es/busqueda?&pagina={}"
MONTHS = {m: i + 1 for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}
SKIP = {"cartelera", "proximamente", "precios", "contacto", "salas", "noticias", "promos", "reserva", "newsletter", "podcast",
        "colegios", "donde-estamos", "preguntas-frecuentes", "politica-de-cookies", "politica-de-privacidad", "canalverditv",
        "acontraplus", "hojas-publico", "favicon.ico", "fiesta-del-espectador", "jueves-de-imprescindibles",
        "mananas-de-opera-y-ballet", "miercoles-cultural"}


def get(url):
    url = urllib.parse.quote(url, safe=":/?&=%#")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def txt(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def verdi():
    home = get(VERDI)
    slugs = [s for s in dict.fromkeys(re.findall(r'href="/([a-z0-9-]+)"', home)) if s not in SKIP]
    shows = []
    for slug in slugs:
        time.sleep(1)
        page = get(f"{VERDI}/{slug}")
        for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
            try:
                j = json.loads(m.group(1))
            except ValueError:
                continue
            nodes = j.get("@graph", [j]) if isinstance(j, dict) else j
            events = []
            for n in nodes:
                if n.get("@type") == "ScreeningEvent":
                    events.append(n)
                events += [e for e in n.get("event", []) if e.get("@type") == "ScreeningEvent"]
            movie = next((n for n in nodes if n.get("@type") == "Movie"), {})
            for e in events:
                w = e.get("workPresented", {})
                lang = e.get("inLanguage") or w.get("inLanguage") or ""
                start = e["startDate"]
                d = movie.get("director") or w.get("director") or []
                d = d if isinstance(d, list) else [d]
                shows.append({"title": e.get("name") or w.get("name") or movie.get("name"), "year": None,
                              "director": ", ".join(x.get("name", "") for x in d if isinstance(x, dict)),
                              "date": start[:10], "time": start[11:16],
                              "vose": lang not in ("Castellano", "Español", ""), "lang": lang,
                              "price": float(e.get("offers", {}).get("price") or 0) or None,
                              "cycle": "", "url": e.get("offers", {}).get("url", f"{VERDI}/{slug}"),
                              "imdb": (movie.get("sameAs") or "") if isinstance(movie.get("sameAs"), str) else ""})
        print("verdi", slug, len(shows), file=sys.stderr)
    seen, out = set(), []
    for s in shows:
        k = (s["title"], s["date"], s["time"])
        if k not in seen:
            seen.add(k)
            out.append(s)
    return {"name": "Cines Verdi Madrid", "url": VERDI, "price": "", "shows": out}


def dore():
    shows, page_no = [], 1
    while True:
        page = get(DORE.format(page_no))
        blocks = re.split(r'<div class="col s12" data-fecha="', page)[1:]
        if not blocks:
            break
        for b in blocks:
            date = b[:10]
            cat = re.search(r'<div class="categoria row">\s*<p[^>]*>(.*?)</p>', b, re.S)
            tit = re.search(r'<h2 class="titulo[^"]*">(.*?)</h2>', b, re.S)
            sub = re.search(r'<h3 class="subtitulo[^"]*">(.*?)</h3>', b, re.S)
            when = re.search(r"a las (\d{1,2})[:.](\d\d)\s*h\s*\(([^)]*)\)", b)
            link = re.search(r'href="(https://entradasfilmoteca[^"]+/productos/descripcion/[^"]+)"', b)
            if not tit or not when or "bono" in (link.group(1) if link else ""):
                continue
            title = txt(tit.group(1))
            ym = re.search(r"\((?:([^()]*?),\s*)?(\d{4})\)\s*$", title)
            room_cycle = txt(when.group(3))
            shows.append({"title": title[:ym.start()].strip() if ym else title, "year": int(ym.group(2)) if ym else None,
                          "orig": (ym.group(1) or "").strip() if ym else "",
                          "director": txt(sub.group(1)) if sub else "", "date": date,
                          "time": f"{int(when.group(1)):02d}:{when.group(2)}", "vose": None, "price": None,
                          "cycle": txt(cat.group(1)) if cat else "", "room": room_cycle.split(".")[0],
                          "url": link.group(1) if link else ""})
        print("dore page", page_no, len(shows), file=sys.stderr)
        if f"pagina={page_no + 1}" not in page:
            break
        page_no += 1
        time.sleep(1)
    # product pages: VOSE flag and price from the schema.org Event description
    for s in shows:
        if not s["url"]:
            continue
        time.sleep(0.8)
        try:
            p = get(s["url"])
        except Exception as e:
            print("  fail", s["url"], e, file=sys.stderr)
            continue
        m = re.search(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', p, re.S)
        if m:
            try:
                ev = json.loads(m.group(1))[0]
            except (ValueError, IndexError, KeyError):
                continue
            desc = ev.get("description", "")
            s["vose"] = bool(re.search(r"\bVOS[EI]?\b|\bVOSI/E|\bV\.O\.S|\bVO\b", desc))
            pr = float(ev.get("offers", {}).get("price") or 0)
            s["price"] = pr or None
            dm = re.search(r"(\d{2,3})\.?\s*$|\.\s*(\d{2,3})\.\s", desc)
            s["runtime"] = int(next(g for g in dm.groups() if g)) if dm else None
    return {"name": "Cine Doré (Filmoteca Española)", "url": "https://www.cultura.gob.es/cultura/areas/cine/mc/fe/cine-dore.html",
            "price": "", "shows": shows}


if __name__ == "__main__":
    path = f"{sys.argv[1]}/extra_cinemas.json"
    try:
        previous = {c["name"]: c for c in json.load(open(path))}
    except (OSError, ValueError):
        previous = {}
    out = []
    for fn in (verdi, dore):
        try:
            c = fn()
        except Exception as e:
            print(fn.__name__, "failed:", e, file=sys.stderr)
            c = None
        if not c or not c["shows"]:
            name = {"verdi": "Cines Verdi Madrid", "dore": "Cine Doré (Filmoteca Española)"}[fn.__name__]
            if name in previous:
                print(name, "empty; keeping previous data", file=sys.stderr)
                c = previous[name]
        if c:
            out.append(c)
    json.dump(out, open(path, "w"), ensure_ascii=False)
    for c in out:
        print(c["name"], len(c["shows"]), file=sys.stderr)
