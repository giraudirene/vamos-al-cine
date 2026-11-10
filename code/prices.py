"""Ticket price rules: the normal price of each session, with día del espectador built in.

A rule is {"n": normal Mon-Fri, "w": weekend/holiday price, "wf": Friday counts as weekend,
           "d": {weekday 0=Mon: [price, label]}  public discount days (día del espectador),
           "m": [price, "HH:MM"]  morning price before that time (optional),
           "src": where it comes from, "chk": date checked (overrides only)}.
Personal discounts (carnet joven, student, member cards) are NOT here: viewers add them on the page.

Sources, in order: static/prices.json (checked by hand on the cinema's own page) >
eCartelera's "Precios" + "Reducidos y día del espectador" lines (scraped daily) > same chain.
"""
import datetime, re

# National + Comunidad de Madrid + Madrid city holidays (BOCM). Update each December for the next year.
HOLIDAYS = {                       # fixed-date ones only; add the movable regional ones when the BOCM publishes them
    "2026-12-08", "2026-12-25",
    "2027-01-01", "2027-01-06", "2027-03-25", "2027-03-26", "2027-05-01", "2027-10-12", "2027-11-01",
    "2027-11-09", "2027-12-06", "2027-12-08", "2027-12-25",
}
DAYS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
NUM = r"(\d+(?:[.,]\d{1,2})?)\s*(?:euros?|€)"


def _n(x):
    return float(x.replace(",", "."))


def _plain(s):
    return (s or "").lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")


WD = r"lunes|martes|miercoles|jueves|viernes|sabados?|domingos?|fines|festivos|laborables|primera"


def _segments(p):
    """Price line -> [(label text, [numbers])]; a number inside brackets gets its own segment,
    a bracket without a number labels the number before it ("8,40 euros (Laborables)")."""
    out = []
    for seg in re.split(r"\||;|(?<=€)\s*,\s*|(?<=euros)\s*,\s*|-\s*(?=(?:%s))" % WD, p):
        label, rest = [], seg
        for paren in re.findall(r"\(([^)]*)\)", seg):
            rest = rest.replace("(" + paren + ")", " ")
            for part in re.split(r"\s-\s", paren):
                if re.search(NUM, part):
                    out.append((part, [_n(x) for x in re.findall(NUM, part)]))
                else:
                    label.append(part)
        nums = [_n(x) for x in re.findall(NUM, rest)]
        if nums:
            out.append((rest + " " + " ".join(label), nums))
    return out


def parse_rule(prices, reduced):
    """eCartelera's two price lines -> rule (None when there is no usable number)."""
    p, r = _plain(prices), _plain(reduced)
    rule = {"n": None, "w": None, "wf": False, "d": {}, "src": "eCartelera"}
    # drop add-ons and special rooms: "+2,50 euros Proyecciones 3D", "Sala Luxury: 14,90€", "9,00 euros en 3D"
    p = re.sub(r"\+\s*" + NUM + r"[^|]*", "", p)
    p = re.sub(r"sala luxury:?\s*" + NUM, "", p)
    p = re.sub(r"-?\s*\d+(?:[.,]\d{1,2})?\s*(?:euros?|€)\s*en 3d", "", p)
    p = re.sub(r"- 3d \([^)]*\)", "", p)
    for label, nums in _segments(p):
        if re.search(r"ninos|menores|antes de las|carnet|matinal|primera sesion|gratis", label):
            continue
        if "dependiendo" in label:
            val, rule["from"] = min(nums), True             # "10,90 a 16,90 euros dependiendo de la película"
        else:
            val = max(nums)                                 # "De 6 a 7,50 euros (Laborables)" -> 7,50
        day = re.fullmatch(r"\s*(lunes|martes|miercoles|jueves)\s*:?\s*" + NUM + r"\s*", label)
        if day:                                             # a cheap weekday inside the price line (mk2 "Jueves: 7,50 €")
            rule["d"][DAYS[day.group(1)]] = [val, "Día del espectador"]
        elif re.search(r"sabado|domingo|festivo|fin(es)? de semana|visperas", label) and "lunes a domingo" not in label:
            rule["w"] = max(rule["w"] or 0, val)
            if re.search(r"viernes|visperas", label):
                rule["wf"] = True
        elif rule["n"] is None:
            rule["n"] = val
    # cheap days for everyone: "Lunes y miércoles (7,30 euros)", "Miércoles: 5,50€", "Miércoles, Carnet Joven (4,50 euros)"
    m = re.match(r"\s*((?:(?:lunes|martes|miercoles|jueves|viernes)[\s,y]*)+)", r)
    price = re.search(NUM, r[m.end():]) if m else None
    if price:
        for day in re.findall(r"lunes|martes|miercoles|jueves|viernes", m.group(1)):
            rule["d"][DAYS[day]] = [_n(price.group(1)), "Día del espectador"]
    base = rule["n"] or rule["w"]
    rule["d"] = {k: v for k, v in rule["d"].items() if base is None or v[0] < base}
    if rule["n"] is None and rule["w"] is None:
        return None
    return rule


def session_price(rule, date, time=""):
    """(price, tag) for one session; tag 'esp' = public discount day, 'm' = morning, 'w' = weekend, '' = normal."""
    if not rule:
        return None, ""
    d = datetime.date.fromisoformat(date)
    dow, iso = d.weekday(), d.isoformat()
    holiday = iso in HOLIDAYS
    eve = (d + datetime.timedelta(days=1)).isoformat() in HOLIDAYS
    dd = rule.get("d", {})
    day = dd.get(dow) or dd.get(str(dow))
    if day and not holiday and not eve:
        return day[0], "esp"
    if rule.get("m") and time and time < rule["m"][1]:
        return rule["m"][0], "m"
    weekend = dow >= 5 or holiday or (rule.get("wf") and (dow == 4 or eve))
    if weekend and rule.get("w"):
        return rule["w"], "w"
    return (rule["n"] if rule.get("n") is not None else rule.get("w")), ""


if __name__ == "__main__":                                 # quick check on a showtimes.json
    import json, sys
    for c in json.load(open(sys.argv[1]))["cinemas"]:
        if c.get("prices"):
            print(c["name"], "|", c["prices"], "||", c.get("reduced", ""), "\n   ->", parse_rule(c["prices"], c.get("reduced", "")))
