"""Scrape the next 21 days of Cineteca Madrid (Matadero) programme, incl. festival/cycle labels.

Usage: python3 -I scrape_cineteca.py DATADIR   -> DATADIR/cineteca.json
"""
import datetime, html, json, re, sys, time, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
BASE = "https://www.cinetecamadrid.com"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def txt(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def main(datadir):
    items = []
    today = datetime.date.today()
    empty = 0
    for k in range(21):
        date = (today + datetime.timedelta(days=k)).isoformat()
        page = get(f"{BASE}/programacion-home/nojs/{date}")
        n0 = len(items)
        for row in page.split('<div class="views-row">')[1:]:
            t = re.search(r'<h2 class="title">\s*<a href="([^"]+)"[^>]*>(.*?)</a>', row, re.S)
            p = re.search(r"<strong>PASES</strong>:(.*?)</div>", row, re.S)
            if not t or not p:
                continue
            sec = re.search(r'<span class="fCategory">(.*?)</span>', row, re.S)
            dur = re.search(r"field-duration\">.*?\((\d+)'\)", row, re.S)
            img = re.search(r'<img[^>]+src="([^"]+)"', row)
            desc = re.search(r'field-description">(.*?)</div>', row, re.S)
            items.append({"date": date, "times": re.findall(r"\d\d:\d\d", p.group(1)),
                          "title": txt(t.group(2)), "url": BASE + t.group(1),
                          "section": txt(sec.group(1)).title() if sec else "",
                          "runtime": int(dur.group(1)) if dur else None,
                          "image": BASE + img.group(1) if img else "",
                          "desc": txt(desc.group(1)) if desc else ""})
        print(date, len(items), file=sys.stderr)
        empty = empty + 1 if len(items) == n0 else 0
        if empty >= 3 and k >= 7:                      # programme not published that far yet
            break
        time.sleep(1)
    # festival / cycle name from each item's own page (one fetch per distinct item)
    cache_path = f"{datadir}/cineteca_cycles.json"
    try:
        cycles = json.load(open(cache_path))
    except (OSError, ValueError):
        cycles = {}
    for it in items:
        if it["url"] not in cycles:
            time.sleep(1)
            c = re.search(r'href="/ciclo/[^"]+" hreflang="es">(.*?)</a>', get(it["url"]))
            cycles[it["url"]] = txt(c.group(1)).title() if c else ""
        it["cycle"] = cycles[it["url"]]
    json.dump({u: cycles[u] for u in {it["url"] for it in items}}, open(cache_path, "w"), ensure_ascii=False)
    json.dump(items, open(f"{datadir}/cineteca.json", "w"), ensure_ascii=False)


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except Exception as e:
        sys.exit(f"Cineteca failed ({e}); keeping the previous file")
