"""Tag films 'dirigida por mujeres' and 'cine LGTBIQ+' from Wikidata, via their IMDb ids.

Director gender comes only from Wikidata (P57 director -> P21 sex or gender); it is never guessed
from names. LGTBIQ+ = Wikidata genre/main subject in an LGBTQ set, or (added in the page) a
queer festival/cycle session. Films without an IMDb id or a Wikidata item stay untagged.

Usage: python3 -I enrich_wikidata.py DATADIR
Cache: DATADIR/wikidata.json (imdb id -> {women, queer, dirs})
"""
import json, os, sys, time, urllib.parse, urllib.request

UA = "VamosAlCine/0.1 (personal non-commercial project)"
WDQS = "https://query.wikidata.org/sparql"
WOMEN = {"Q6581072", "Q1052281"}                     # female, trans woman
LGBTQ = {"Q20442589", "Q17884", "Q6636", "Q6649", "Q592", "Q43200", "Q189125", "Q1097630", "Q48270",
         "Q1823134", "Q51415", "Q130359", "Q5480297"}  # LGBT-related film, LGBT, homosexuality, lesbianism, gay, bisexuality,
                                                       # transgender, intersex, non-binary, transsexuality, queer, drag, LGBT rights


def query(ids):
    values = " ".join(f'"{i}"' for i in ids)
    q = f"""SELECT ?imdb ?g ?genre ?subj WHERE {{
      VALUES ?imdb {{ {values} }}
      ?film wdt:P345 ?imdb .
      OPTIONAL {{ ?film wdt:P57 ?d . ?d wdt:P21 ?g . }}
      OPTIONAL {{ ?film wdt:P136 ?genre . }}
      OPTIONAL {{ ?film wdt:P921 ?subj . }}
    }}"""
    url = WDQS + "?" + urllib.parse.urlencode({"query": q, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["results"]["bindings"]


def main(d):
    site = json.load(open(f"{d}/site_data.json"))
    path = f"{d}/wikidata.json"
    cache = json.load(open(path)) if os.path.exists(path) else {}
    todo = sorted({f["imdb"] for f in site["films"] if f.get("imdb")} - set(cache))
    for k in range(0, len(todo), 100):
        batch = todo[k:k + 100]
        rows = None
        for attempt in range(3):
            try:
                rows = query(batch)
                break
            except Exception as e:
                print("wikidata:", e, "- waiting 65 s", file=sys.stderr)
                time.sleep(65)
        if rows is None:
            break
        found = {i: {"women": False, "queer": False, "known": False} for i in batch}
        for r in rows:
            i = r["imdb"]["value"]
            found[i]["known"] = True
            qid = lambda key: r[key]["value"].rsplit("/", 1)[-1] if key in r else None
            if qid("g") in WOMEN:
                found[i]["women"] = True
            if qid("genre") in LGBTQ or qid("subj") in LGBTQ:
                found[i]["queer"] = True
        cache.update(found)
        json.dump(cache, open(path, "w"))
        time.sleep(1)
    for f in site["films"]:
        c = cache.get(f.get("imdb") or "", {})
        f["wo"] = int(bool(c.get("women")))
        f["qu"] = int(bool(c.get("queer")))
    json.dump(site, open(f"{d}/site_data.json", "w"), ensure_ascii=False, separators=(",", ":"))
    n = len(site["films"])
    print(f"wikidata: {sum(1 for f in site['films'] if f.get('imdb') and cache.get(f['imdb'], {}).get('known'))}/{n} found, "
          f"{sum(f['wo'] for f in site['films'])} by women, {sum(f['qu'] for f in site['films'])} LGTBIQ+", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
