"""Scrape smaller arthouse venues that publish their programme as plain HTML.

  Cine Estudio (Círculo de Bellas Artes)  weekly table on /cine-estudio/
  La Casa Encendida                       /cine listing (title, author, "25 nov - 20:30 h", festival tag)
  Sala Berlanga                           WordPress API list of 'actividad' + each activity page ("18 de Noviembre - 20:15h")

Usage: python3 -I scrape_arthouse.py DATADIR   -> DATADIR/arthouse.json (same shape as extra_cinemas.json)
A venue that fails keeps its previous data.
"""
import datetime, html, json, re, sys, time, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MONTHS = {m: i + 1 for i, m in enumerate("ene feb mar abr may jun jul ago sep oct nov dic".split())}
TODAY = datetime.date.today()


def get(url):
    url = urllib.parse.quote(url, safe=":/?&=%#")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def txt(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def to_date(day, month_word):
    mo = MONTHS.get(month_word.strip().lower()[:3])
    if not mo:
        return None
    y = TODAY.year + (1 if mo < TODAY.month - 1 else 0)
    return datetime.date(y, mo, int(day)).isoformat()


def show(title, date, t, director="", year=None, orig="", cycle="", url="", vose=False, runtime=None):
    return {"title": title, "year": year, "orig": orig, "director": director, "date": date, "time": t,
            "vose": vose, "price": None, "cycle": cycle, "url": url, "runtime": runtime}


def cine_estudio():
    base = "https://www.circulobellasartes.com/cine-estudio/"
    page = get(base)
    shows = []
    for day in re.split(r"<div class='cba_cine_table_container'>", page)[1:]:
        dm = re.search(r"cba_cine_table_dia'>\s*\w+,\s*(\d{1,2})\s+(\w+)", day)
        if not dm:
            continue
        date = to_date(dm.group(1), dm.group(2))
        for t, body, tipo, info in re.findall(r"cba_cine_table_hora'>(\d\d:\d\d)</div><div class='cba_cine_table_titulo[^']*'>(.*?)</div>"
                                              r"<div class='cba_cine_table_tipo'>(.*?)</div><div class='cba_cine_table_info'>(.*?)</div>", day, re.S):
            a = re.search(r"<a href='([^']+)'>(.*?)</a>(.*)", body, re.S)
            title, director, url = (txt(a.group(2)), txt(a.group(3)), a.group(1)) if a else (txt(body), "", base)
            extra = txt(tipo) + " " + txt(info)
            shows.append(show(title, date, t, director, url=url, cycle="" if txt(tipo) == "Estreno" else txt(tipo),
                              vose=bool(re.search(r"\bVOS|V\.O\.", extra))))
    dedup = {(s["title"], s["date"], s["time"]): s for s in shows}
    return {"name": "Cine Estudio (Círculo de Bellas Artes)", "url": base, "price": "", "shows": list(dedup.values())}


def casa_encendida():
    base = "https://www.lacasaencendida.es/cine"
    page = get(base)
    shows = []
    for item in page.split('class="results-list__item"')[1:]:
        tm = re.search(r'<h2 class="results-list__title">(.*?)</h2>', item, re.S)
        dm = re.search(r'results-list__date">\s*(\d{1,2})\s+(\w+)\s*-\s*(\d{1,2}):(\d\d)', item)
        if not tm or not dm:
            continue
        link = re.search(r'href="([^"]+)"', item)
        au = re.search(r'results-list__authors">(.*?)</span>', item, re.S)
        tags = [txt(x) for x in re.findall(r'results-list__type mt-1">(.*?)</span>', item, re.S)]
        title = txt(tm.group(1))
        title = title.split("|", 1)[1].strip() if title.upper().startswith(("PLAYLIST", "MÁRGENES", "MARGENES")) and "|" in title else title
        shows.append(show(title, to_date(dm.group(1), dm.group(2)), f"{int(dm.group(3)):02d}:{dm.group(4)}",
                          txt(au.group(1)) if au else "", cycle=", ".join(tags), url=link.group(1) if link else base))
    return {"name": "La Casa Encendida", "url": base, "price": "", "shows": shows}


def berlanga():
    api = "https://salaberlanga.com/wp-json/wp/v2/actividad?per_page=40&orderby=modified&_fields=link,title,class_list"
    acts = json.loads(get(api))
    shows = []
    for a in acts:
        if "categoria-ciclo-cine" not in " ".join(a.get("class_list", [])) and "cine" not in " ".join(a.get("class_list", [])):
            continue
        time.sleep(1)
        page = get(a["link"])
        body = re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>", "", page, flags=re.S)
        x = re.sub(r"\s*\|[\s|]*", "|", html.unescape(re.sub(r"<[^>]+>", "|", body)))
        seg = x[x.find("En cartelera"):] if "En cartelera" in x else x
        title = txt(a["title"]["rendered"])
        after = seg.split("|" + title + "|", 1)
        info = after[1].split("|") if len(after) > 1 else []
        cycle = info[0] if info else ""
        year = next((int(v) for v in info[:6] if re.fullmatch(r"(19|20)\d\d", v)), None)
        runtime = next((int(v[:-1]) for v in info[:8] if re.fullmatch(r"\d{2,3}'", v)), None)
        om = re.search(r"T.tulo original:\|([^|]+)", seg)
        dm = re.search(r"Direcci.n:\|([^|]+)", seg)
        for d, mon, hh, mm in re.findall(r"(\d{1,2}) de (\w+) - (\d{1,2})[:.](\d\d)\s*h", seg.split("|" + title + "|", 1)[0]):
            shows.append(show(title, to_date(d, mon), f"{int(hh):02d}:{mm}", dm.group(1).strip() if dm else "", year,
                              om.group(1).strip() if om else "", cycle, a["link"], runtime=runtime))
    return {"name": "Sala Berlanga", "url": "https://salaberlanga.com/", "price": "", "shows": shows}


if __name__ == "__main__":
    path = f"{sys.argv[1]}/arthouse.json"
    try:
        previous = {c["name"]: c for c in json.load(open(path))}
    except (OSError, ValueError):
        previous = {}
    out = []
    for fn, name in ((cine_estudio, "Cine Estudio (Círculo de Bellas Artes)"), (casa_encendida, "La Casa Encendida"), (berlanga, "Sala Berlanga")):
        try:
            c = fn()
        except Exception as e:
            print(name, "failed:", e, file=sys.stderr)
            c = None
        if (not c or not c["shows"]) and name in previous:
            print(name, "empty; keeping previous data", file=sys.stderr)
            c = previous[name]
        if c:
            out.append(c)
            print(name, len(c["shows"]), "sessions", file=sys.stderr)
    json.dump(out, open(path, "w"), ensure_ascii=False)
