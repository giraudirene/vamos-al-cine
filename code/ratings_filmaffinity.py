"""Attach Filmaffinity ratings to the films in showtimes.json.

Usage: python3 -I ratings_filmaffinity.py DATADIR
Reads DATADIR/showtimes.json, writes DATADIR/ratings.json (cached: films already rated are skipped)
"""
import html, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
SEARCH = "https://www.filmaffinity.com/es/search.php?stext={}&stype=title"
DELAY = 1.0


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode("utf-8", "ignore")


def norm(s):
    s = unicodedata.normalize("NFKD", html.unescape(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def num(s):
    s = (s or "").replace(".", "").replace(",", ".").strip()
    return float(s) if s else None


def parse_film_page(url, page):
    m = re.search(r'id="movie-rat-avg" itemprop="ratingValue" content="([\d.]+)"', page)
    c = re.search(r'itemprop="ratingCount" content="(\d+)"', page)
    y = re.search(r'itemprop="datePublished">(\d{4})', page)
    t = re.search(r'<h1[^>]*>\s*<span itemprop="name">(.*?)</span>', page, re.S)
    o = re.search(r"T.tulo original</dt>\s*<dd>(.*?)</dd>", page, re.S)
    return {"fa_url": url, "fa_title": html.unescape(t.group(1)).strip() if t else "",
            "fa_original": re.sub(r"<[^>]+>|\s+", " ", html.unescape(o.group(1))).strip() if o else "",
            "fa_year": int(y.group(1)) if y else None,
            "fa_rating": float(m.group(1)) if m else None, "fa_votes": int(c.group(1)) if c else 0}


def parse_search(page):
    cards = []
    for chunk in page.split('class="fs-6 mc-title">')[1:]:
        chunk = chunk.split('class="fs-6 mc-title">')[0]
        m = re.search(r'href="(https://www\.filmaffinity\.com/es/film\d+\.html)">(.*?)</a>', chunk, re.S)
        if not m:
            continue
        y = re.search(r'mc-year[^"]*">(\d{4})', chunk)
        co = re.search(r'class="nflag"[^>]*alt="([^"]*)"', chunk)
        a = re.search(r'class="avg[^"]*">\s*([\d,]*)', chunk)
        n = re.search(r'class="count[^"]*">\s*([\d.]+)', chunk)
        cards.append({"fa_url": m.group(1), "fa_title": html.unescape(m.group(2)).strip(),
                      "fa_year": int(y.group(1)) if y else None, "country": co.group(1) if co else "",
                      "fa_rating": num(a.group(1)) if a else None, "fa_votes": int(num(n.group(1))) if n else 0})
    return cards


def pick(cards, film):
    t = norm(film["title"])
    exact = [c for c in cards if norm(c["fa_title"]) == t]
    pool = exact or cards
    same_country = [c for c in pool if film["country"] and norm(c["country"]) == norm(film["country"])]
    pool = same_country or pool
    pool = sorted(pool, key=lambda c: (c["fa_year"] or 0), reverse=True)
    if not pool:
        return None
    best = dict(pool[0])
    best["match"] = "exact" if exact else "loose"
    return best


def main(datadir):
    data = json.load(open(f"{datadir}/showtimes.json"))
    path = f"{datadir}/ratings.json"
    ratings = json.load(open(path)) if os.path.exists(path) else {}
    todo = [k for k in data["films"] if k not in ratings]
    print(len(todo), "films to rate", file=sys.stderr)
    for i, key in enumerate(todo):
        film = data["films"][key]
        time.sleep(DELAY)
        try:
            url, page = get(SEARCH.format(urllib.parse.quote_plus(film["title"])))
        except Exception as e:
            print("  fail", film["title"], e, file=sys.stderr)
            continue
        if "/es/film" in url:
            res = parse_film_page(url, page)
            res["match"] = "direct"
        else:
            res = pick(parse_search(page), film)
        ratings[key] = res
        print(f"[{i+1}/{len(todo)}] {film['title']} -> {res and (res['fa_title'], res['fa_year'], res['fa_rating'], res['match'])}", file=sys.stderr)
        if i % 20 == 0:
            json.dump(ratings, open(path, "w"), ensure_ascii=False)
    json.dump(ratings, open(path, "w"), ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1])
