"""Merge all sources into one compact JSON for the page.

Sources (all in DATADIR):
  fa_showtimes.json   Filmaffinity: cinemas (coords, address), films (rating), sessions (VOSE tag)
  showtimes.json      eCartelera: cinemas Filmaffinity lacks + per-cinema price text and coords
  extra_cinemas.json  Cines Verdi (per-session prices) and Cine Doré
  arthouse.json       Cine Estudio (Círculo), La Casa Encendida, Sala Berlanga
  cineteca.json       Cineteca Madrid programme (festivals and cycles)
Writes DATADIR/site_data.json (posters embedded). Run enrich_imdb_letterboxd.py afterwards.

Usage: python3 -I build_data.py DATADIR
"""
import base64, datetime, json, os, re, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ratings_filmaffinity import get as fa_get, norm, parse_film_page, parse_search, SEARCH
from prices import parse_rule, session_price

TODAY = datetime.date.today().isoformat()
LAST = (datetime.date.today() + datetime.timedelta(days=20)).isoformat()     # 3 weeks of sessions
FEST_LAST = (datetime.date.today() + datetime.timedelta(days=60)).isoformat()
FEST_RE = re.compile(r"festival|queercinemad|muestra|semana de|m.rgenes|documenta|animadrid|cine por mujeres", re.I)
CHAINS = ["Cinesa", "Yelmo", "Renoir", "Ocine", "Kinépolis", "mk2", "Verdi", "Conde Duque", "Golem",
          "Embajadores", "Artistic", "Odeon", "Zoco", "Cine Doré", "Cineteca"]
STOP = {"cine", "cines", "de", "del", "la", "el", "3d", "madrid", "sala", "multicines", "cinemes", "filmoteca", "espanola"}


def toks(name):
    return {w for w in norm(name).split() if w not in STOP}


def same_cinema(a, b):
    ta, tb = toks(a), toks(b)
    return bool(ta and tb) and (ta <= tb or tb <= ta)


def chain_of(name):
    n = norm(name)
    for c in CHAINS:
        if norm(c) in n:
            return c
    return ""


def load_overrides():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static", "prices.json")
    try:
        return {k: v for k, v in json.load(open(path)).items() if not k.startswith("_")}
    except (OSError, ValueError):
        return {}


def fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Chrome/130.0", "Referer": "https://www.filmaffinity.com/"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main(d):
    def load(name, empty):
        try:
            return json.load(open(f"{d}/{name}"))
        except (OSError, ValueError):
            print(f"{name} missing: continuing without it", file=sys.stderr)
            return empty
    fa = load("fa_showtimes.json", {"scraped": "2000-01-01T00:00", "cinemas": []})
    ec = load("showtimes.json", {"cinemas": [], "films": {}, "shows": []})
    extra = load("extra_cinemas.json", []) + load("arthouse.json", [])
    ct = load("cineteca.json", [])
    search_cache_path = f"{d}/fa_search_cache.json"
    search_cache = json.load(open(search_cache_path)) if os.path.exists(search_cache_path) else {}

    films, cinemas, shows = {}, [], {}
    overrides = load_overrides()
    fest = []                                    # festival sessions up to 60 days ahead (calendar)
    title_index = {}

    def best(pool, key, name):
        return (next((c for c in pool if toks(c[key]) == toks(name)), None)
                or next((c for c in pool if same_cinema(c[key], name)), None))

    def ec_cinema(name):
        return best(ec["cinemas"], "name", name)

    def fa_cinema(name):
        return best(fa["cinemas"], "name", name)

    def add_cinema(name, url, src, lat=None, lon=None, address="", town=""):
        e = ec_cinema(name)
        if lat is None and e:
            lat, lon = e["lat"], e["lon"]
        if not address and e:
            address = re.sub(r",?\s*CP\d+.*$", "", e["address"])
        price_txt = " · ".join(x for x in ((e or {}).get("prices", ""), (e or {}).get("reduced", "")) if x)
        rule = next((v for k, v in overrides.items() if toks(k) == toks(name)), None) \
            or (parse_rule(e.get("prices", ""), e.get("reduced", "")) if e else None)
        if rule and rule.get("note"):
            price_txt = rule["note"]
        cinemas.append({"n": name, "u": url, "src": src, "lat": lat, "lon": lon, "a": address, "town": town or "Madrid",
                        "ch": chain_of(name), "pt": price_txt, "pr": rule, "p": rule and (rule["n"] if rule.get("n") is not None else rule.get("w"))})
        return len(cinemas) - 1

    def add_film(fid, f):
        if fid not in films:
            films[fid] = {"id": fid, "t": f["title"], "y": f.get("year"), "c": f.get("country", ""),
                          "d": f.get("director", ""), "cast": f.get("cast", []), "r": f.get("rating"),
                          "v": f.get("votes", 0), "rt": f.get("runtime"), "age": f.get("age", ""),
                          "img": f.get("poster", ""), "u": f"https://www.filmaffinity.com/es/film{fid}.html",
                          "orig": f.get("orig", ""), "imdb": f.get("imdb", "")}
            title_index.setdefault(norm(f["title"]), fid)
        else:
            for k, src in (("rt", "runtime"), ("age", "age"), ("img", "poster"), ("imdb", "imdb"), ("orig", "orig")):
                if not films[fid][k] and f.get(src):
                    films[fid][k] = f[src]
        return fid

    def add_show(fid, cid, date, t, vose, price=None, cycle="", url=""):
        if TODAY <= date <= LAST:                 # url: the session's ticket page, when the source gives one
            shows[(fid, cid, date, t)] = [fid, cid, date, t, int(bool(vose)), price, cycle, url or ""]

    def lookup(title, year=None, director="", country=""):
        """Filmaffinity id for a film not already in the Filmaffinity cinema data (cached search)."""
        key = norm(title)
        if key in title_index and (not year or not films[title_index[key]]["y"] or abs(films[title_index[key]]["y"] - year) <= 1):
            return title_index[key], None
        ck = f"{key}|{year or ''}"
        if ck not in search_cache and os.environ.get("BUTACA_NO_FA_SEARCH"):
            return None, None
        if ck not in search_cache:
            time.sleep(4)
            try:
                url, page = fa_get(SEARCH.format(urllib.parse.quote_plus(title)))
            except Exception as e:
                print("  search fail", title, e, file=sys.stderr)
                return None, None
            if "/es/film" in url:
                res = parse_film_page(url, page)
            else:
                cards = parse_search(page)
                exact = [c for c in cards if norm(c["fa_title"]) == key] or cards
                if year:
                    exact = [c for c in exact if c["fa_year"] and abs(c["fa_year"] - year) <= 1]
                res = max(exact, key=lambda c: c["fa_votes"]) if exact else None
            search_cache[ck] = res
            json.dump(search_cache, open(search_cache_path, "w"), ensure_ascii=False)
        res = search_cache[ck]
        if not res or not res.get("fa_url"):
            return None, None
        return re.search(r"film(\d+)", res["fa_url"]).group(1), res

    # 1. Filmaffinity cinemas with sessions (skipped when the file is older than 36 h:
    #    then eCartelera supplies the sessions and Filmaffinity only ratings via search)
    fa_age_h = (datetime.datetime.now() - datetime.datetime.fromisoformat(fa["scraped"])).total_seconds() / 3600
    fa_fresh = fa_age_h < 36
    if not fa_fresh:
        print(f"Filmaffinity data is {fa_age_h:.0f} h old: using eCartelera for sessions", file=sys.stderr)
    own_site = [x["name"] for x in extra if x["shows"]]          # venues scraped from their own site win
    for c in fa["cinemas"]:
        if not c["films"] or not fa_fresh or any(same_cinema(c["name"], n) for n in own_site):
            continue
        cid = add_cinema(c["name"], c["url"], "Filmaffinity", c.get("lat"), c.get("lon"), c.get("address", ""), c.get("town", ""))
        for f in c["films"]:
            add_film(f["fa_id"], f)
            for s in f["shows"]:
                add_show(f["fa_id"], cid, s["date"], s["time"], s["vose"], url=s.get("url", ""))

    # 2. Verdi and Doré from their own sites
    for x in extra:
        if any(same_cinema(c["n"], x["name"]) for c in cinemas):
            continue
        fc = fa_cinema(x["name"])
        cid = add_cinema(x["name"], x["url"], "web del cine", fc.get("lat") if fc else None, fc.get("lon") if fc else None,
                         fc.get("address", "") if fc else "", fc.get("town", "") if fc else "")
        for s in x["shows"]:
            if not s["title"]:
                continue
            fid, res = lookup(s["title"], s.get("year"))
            if fid and fid not in films:
                add_film(fid, {"title": s["title"], "year": (res or {}).get("fa_year") or s.get("year"),
                               "director": s.get("director", ""), "rating": (res or {}).get("fa_rating"),
                               "votes": (res or {}).get("fa_votes", 0), "runtime": s.get("runtime"),
                               "country": (res or {}).get("country", ""), "orig": s.get("orig", ""),
                               "imdb": re.sub(r".*/(tt\d+).*", r"\1", s.get("imdb", "")) if s.get("imdb") else ""})
            elif not fid:
                fid = add_film("x-" + norm(s["title"]).replace(" ", "-"),
                               {"title": s["title"], "year": s.get("year"), "director": s.get("director", ""),
                                "runtime": s.get("runtime"), "orig": s.get("orig", "")})
                films[fid]["u"] = s.get("url", "")
            elif s.get("imdb") and not films[fid]["imdb"]:
                films[fid]["imdb"] = re.sub(r".*/(tt\d+).*", r"\1", s["imdb"])
            add_show(fid, cid, s["date"], s["time"], s["vose"], s.get("price"), s.get("cycle", ""), s.get("url", ""))
            if s.get("cycle") and FEST_RE.search(s["cycle"]) and TODAY <= s["date"] <= FEST_LAST:
                fest.append({"date": s["date"], "time": s["time"], "t": s["title"], "u": s.get("url", ""),
                             "cyc": s["cycle"], "w": x["name"]})
        sp = sorted({s["price"] for s in x["shows"] if s.get("price")})
        if sp and not cinemas[cid]["pr"]:          # per-session prices only when the cinema has no price rule
            cinemas[cid]["p"] = sp[0]
            cinemas[cid]["pt"] = "Según la web del cine: " + " / ".join(f"{p:.2f}".replace(".", ",") + " €" for p in sp) + " según sesión"

    # 3. eCartelera cinemas still missing
    ec_count = {}
    for s in ec["shows"]:
        ec_count[s["cinema"]] = ec_count.get(s["cinema"], 0) + 1
    ec_cid = {}
    for c in ec["cinemas"]:
        if ec_count.get(c["id"]) and not any(same_cinema(x["n"], c["name"]) for x in cinemas):
            ec_cid[c["id"]] = add_cinema(c["name"], c["url"], "eCartelera", c["lat"], c["lon"])
    for s in ec["shows"]:
        if s["cinema"] in ec_cid:
            f = ec["films"][s["film"]]
            fid, res = lookup(f["title"])
            if fid and fid not in films:
                add_film(fid, {"title": f["title"], "year": (res or {}).get("fa_year"), "country": f["country"],
                               "director": f["director"], "cast": f["cast"], "rating": (res or {}).get("fa_rating"),
                               "votes": (res or {}).get("fa_votes", 0), "runtime": f["runtime"], "age": f["age"]})
            elif not fid:
                fid = add_film("x-" + norm(f["title"]).replace(" ", "-"), {"title": f["title"], "country": f["country"],
                               "director": f["director"], "cast": f["cast"], "runtime": f["runtime"], "age": f["age"],
                               "poster": f.get("poster", "")})
                films[fid]["u"] = f["url"]
            add_show(fid, ec_cid[s["cinema"]], s["date"], s["time"], 0, url=s.get("url", ""))

    # 4. Cineteca: festival / cycle programme, listed separately (no ratings)
    fc = fa_cinema("Cineteca")
    cineteca = {"n": "Cineteca Madrid (Matadero)", "lat": fc.get("lat") if fc else None, "lon": fc.get("lon") if fc else None,
                "a": fc.get("address", "") if fc else "Plaza de Legazpi, 8"}
    events = [{"date": e["date"], "times": e["times"], "t": e["title"], "u": e["url"], "rt": e["runtime"],
               "sec": e["section"], "cyc": e.get("cycle", ""), "desc": e["desc"], "w": "Cineteca"}
              for e in ct if TODAY <= e["date"] <= LAST]

    for e in ct:
        if (e.get("cycle") or FEST_RE.search(e.get("section", ""))) and TODAY <= e["date"] <= FEST_LAST:
            for t in e["times"]:
                fest.append({"date": e["date"], "time": t, "t": e["title"], "u": e["url"],
                             "cyc": e.get("cycle") or e["section"], "w": "Cineteca Madrid"})

    # same chain: cinemas eCartelera has no price for take the chain's most common rule
    chain_rules = {}
    for c in ec["cinemas"]:
        ch = chain_of(c["name"]) or chain_of(c.get("chain", ""))
        r = parse_rule(c.get("prices", ""), c.get("reduced", "")) if ch else None
        if r:
            chain_rules.setdefault(ch, []).append(json.dumps(r, sort_keys=True))
    for c in cinemas:
        if not c["pr"] and c["ch"] in chain_rules:
            rs = chain_rules[c["ch"]]
            c["pr"] = dict(json.loads(max(set(rs), key=rs.count)), src="eCartelera (misma cadena)")
            c["p"] = c["pr"].get("n") or c["pr"].get("w")
    # the normal price of each session (día del espectador and weekend built in); slot 8 = tag
    for k, s in shows.items():
        rule = cinemas[s[1]]["pr"]
        if rule:
            s[5], tag = session_price(rule, s[2], s[3])
        else:
            tag = ""
        s.append(tag)

    # first time each film was seen (for "new this week"); the first run seeds everything as old
    fs_path = f"{d}/first_seen.json"
    first_seen = load("first_seen.json", None)
    seeding = first_seen is None
    first_seen = first_seen or {}

    used = {s[0] for s in shows.values()}
    films = {k: v for k, v in films.items() if k in used}
    for f in films.values():
        if f["img"] and not f["img"].startswith("data:"):
            try:
                f["img"] = "data:image/jpeg;base64," + base64.b64encode(fetch_bytes(f["img"].replace("-mmed.jpg", "-msmall.jpg"))).decode()
            except Exception as e:
                print("poster fail", f["t"], e, file=sys.stderr)
                f["img"] = ""
            time.sleep(0.3)

    for fid, f in films.items():
        key = f"{norm(f['t'])}|{f['y'] or ''}"
        if key not in first_seen:
            first_seen[key] = "seed" if seeding else TODAY
        f["fs"] = "" if first_seen[key] == "seed" else first_seen[key]
    json.dump(first_seen, open(fs_path, "w"), ensure_ascii=False)

    # complete week? (Filmaffinity only lists ~3 days unless the extra-days fetch worked)
    later = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
    fa_cids = {i for i, c in enumerate(cinemas) if c["src"] == "Filmaffinity"}
    with_later = {s[1] for s in shows.values() if s[1] in fa_cids and s[2] >= later}
    full_week = bool(fa_cids) and len(with_later) >= 0.6 * len(fa_cids)

    # upcoming releases (eCartelera): released in the last week or later, and not already in the listings
    showing_years = {}                           # title -> years of showing films with that title
    for f in films.values():
        for t in {f["t"], f.get("orig")} - {None, ""}:
            showing_years.setdefault(norm(t), []).append(f.get("y"))
    def is_showing(u):
        return any(not u.get("y") or not y or abs(u["y"] - y) <= 1
                   for t in {u["t"], u.get("orig")} - {None, ""} for y in showing_years.get(norm(t), []))
    week_ago = (datetime.date.today() - datetime.timedelta(days=6)).isoformat()
    upcoming = [dict(u, id="u:" + u["ec"]) for u in load("estrenos.json", []) if u["date"] >= week_ago and not is_showing(u)]

    fid_list = list(films)
    pos = {k: i for i, k in enumerate(fid_list)}
    out = {"scraped": fa["scraped"], "today": TODAY, "films": [films[k] for k in fid_list], "cinemas": cinemas,
           "shows": sorted([[pos[s[0]]] + s[1:] for s in shows.values()], key=lambda x: (x[2], x[3])),
           "events": events, "cineteca": cineteca, "full_week": full_week, "upcoming": upcoming,
           "fest": sorted(fest, key=lambda e: (e["date"], e["time"]))}
    if len(out["shows"]) < 300:
        sys.exit(f"only {len(out['shows'])} sessions; keeping the previous site_data.json")
    json.dump(out, open(f"{d}/site_data.json", "w"), ensure_ascii=False, separators=(",", ":"))
    print(len(out["films"]), "films", len(cinemas), "cinemas", len(out["shows"]), "shows", len(events), "events,",
          sum(1 for c in cinemas if c["lat"]), "with coords,", sum(1 for c in cinemas if c["pr"]), "with price rule", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
