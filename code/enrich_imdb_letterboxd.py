"""Add IMDb and Letterboxd ratings to site_data.json.

IMDb id: from the cinema (Verdi gives it), else matched on title + year against IMDb's own
datasets (Spanish 'akas' titles, primary and original titles). Letterboxd: /imdb/<tt>/ redirects
to the film page, whose schema.org data holds the average (out of 5) and the count.

Usage: python3 -I enrich_imdb_letterboxd.py DATADIR IMDBDIR
Cache: DATADIR/ext_ratings.json (id -> {imdb, im_r, im_v, lb_r, lb_v, lb_u})
"""
import gzip, json, os, re, sys, time, unicodedata, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
KINDS = {"movie", "tvMovie", "video", "short", "tvSpecial"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"^(the|el|la|los|las|le|les|il|a|an) ", "", s.strip())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode("utf-8", "ignore")


def imdb_match(films, imdbdir):
    want = {}
    for f in films:
        for t in {f["t"], f.get("orig") or ""} - {""}:
            want.setdefault(norm(t), []).append(f)
    cand = {}                                      # tconst -> set of film ids it could be
    def offer(tconst, title):
        for f in want.get(norm(title), []):
            cand.setdefault(tconst, set()).add(f["id"])
    with gzip.open(f"{imdbdir}/title.basics.tsv.gz", "rt", encoding="utf-8") as fh:
        next(fh)
        info, genres = {}, {}
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if p[1] not in KINDS:
                continue
            if norm(p[2]) in want or norm(p[3]) in want:
                offer(p[0], p[2]); offer(p[0], p[3])
            info[p[0]] = None if p[5] == "\\N" else int(p[5])
            genres[p[0]] = [] if p[8] == "\\N" else p[8].split(",")
    print("basics read", file=sys.stderr)
    with gzip.open(f"{imdbdir}/title.akas.tsv.gz", "rt", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            p = line.split("\t", 5)
            if p[0] in info and norm(p[2]) in want:
                offer(p[0], p[2])
    print("akas read", len(cand), "candidates", file=sys.stderr)
    votes = {}
    with gzip.open(f"{imdbdir}/title.ratings.tsv.gz", "rt") as fh:
        next(fh)
        for line in fh:
            t, r, v = line.split("\t")
            votes[t] = (float(r), int(v))
    best = {}
    for tconst, fids in cand.items():
        y = info.get(tconst)
        for fid in fids:
            f = next(x for x in films if x["id"] == fid)
            if f.get("y") and (y is None or abs(y - f["y"]) > 1):
                continue
            v = votes.get(tconst, (None, 0))[1]
            if fid not in best or v > best[fid][1]:
                best[fid] = (tconst, v)
    matched = {fid: b[0] for fid, b in best.items()}
    for f in films:                                 # genres also for ids given by the cinema (Verdi)
        tc = f.get("imdb") or matched.get(f["id"])
        f["g"] = genres.get(tc, []) if tc else []
        if tc and not f.get("y") and info.get(tc):    # year from IMDb when the cinema listing has none
            f["y"] = info[tc]
    return matched, votes


def main(datadir, imdbdir):
    site = json.load(open(f"{datadir}/site_data.json"))
    cache_path = f"{datadir}/ext_ratings.json"
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    films = site["films"]
    ids, votes = imdb_match(films, imdbdir)
    for f in films:
        tc = f.get("imdb") or ids.get(f["id"])
        c = cache.setdefault(f["id"], {})
        if tc and c.get("imdb") != tc:
            c.clear()
            c["imdb"] = tc
        if tc:
            r = votes.get(tc)
            c["im_r"], c["im_v"] = (r if r else (None, 0))
    for i, f in enumerate(films):
        c = cache[f["id"]]
        if not c.get("imdb") or "lb_u" in c:
            continue
        time.sleep(1.5)
        try:
            url, page = get(f"https://letterboxd.com/imdb/{c['imdb']}/")
        except Exception as e:
            print("  lb fail", f["t"], e, file=sys.stderr)
            continue
        r = re.search(r'"ratingValue":\s*([\d.]+)', page)
        n = re.search(r'"ratingCount":\s*(\d+)', page)
        c["lb_u"] = url if "/film/" in url else ""
        c["lb_r"] = float(r.group(1)) if r else None
        c["lb_v"] = int(n.group(1)) if n else 0
        print(f"[{i+1}/{len(films)}] {f['t']} -> {c['imdb']} imdb {c.get('im_r')} lb {c['lb_r']}", file=sys.stderr)
        json.dump(cache, open(cache_path, "w"))
    json.dump(cache, open(cache_path, "w"))
    for f in films:
        c = cache.get(f["id"], {})
        f["imdb"] = c.get("imdb", "")
        f["ir"], f["iv"] = c.get("im_r"), c.get("im_v", 0)
        f["lr"], f["lv"], f["lu"] = c.get("lb_r"), c.get("lb_v", 0), c.get("lb_u", "")
    json.dump(site, open(f"{datadir}/site_data.json", "w"), ensure_ascii=False, separators=(",", ":"))
    n = len(films)
    print(f"imdb {sum(1 for f in films if f['ir'])}/{n}, letterboxd {sum(1 for f in films if f['lr'])}/{n}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
