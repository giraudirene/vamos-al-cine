"""Email members when a film they follow (or have on their Letterboxd watchlist) starts showing.

Runs in the daily GitHub job after the page is built. Needs these GitHub secrets:
  SUPABASE_URL, SUPABASE_SERVICE_KEY   read members' saved films and email addresses
  GMAIL_USER, GMAIL_APP_PASSWORD       the club Gmail that sends the messages
One email per member per day at most, listing every film that became available since the last
alert. A film is announced once; if it leaves the listings and comes back, it is announced again.

Usage: python3 -I email_alerts.py DATADIR
State: DATADIR/email_sent.json  (member id -> film keys already announced and still showing)
"""
import datetime, html, json, os, re, smtplib, sys, unicodedata, urllib.request
from email.message import EmailMessage

SITE = os.environ.get("SITE_URL", "https://giraudirene.github.io/vamos-al-cine/")
SB, KEY = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_KEY", "")
GUSER, GPASS = os.environ.get("GMAIL_USER", ""), os.environ.get("GMAIL_APP_PASSWORD", "")
WD = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def api(path):
    headers = {"apikey": KEY}
    if not KEY.startswith("sb_"):                 # legacy service_role JWT also goes in Authorization; new sb_secret_ keys only as apikey
        headers["Authorization"] = f"Bearer {KEY}"
    req = urllib.request.Request(SB + path, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def members():
    """id -> (email, display name, saved state) for members who want alerts and confirmed their email."""
    profiles = {p["id"]: p for p in api("/rest/v1/profiles?select=id,display_name,email_alerts&email_alerts=eq.true")}
    states = {s["user_id"]: s for s in api("/rest/v1/user_state?select=user_id,track,wl,prefs")}
    out, page = {}, 1
    while True:
        users = api(f"/auth/v1/admin/users?page={page}&per_page=500").get("users", [])
        for u in users:
            if u["id"] in profiles and u.get("email") and u.get("email_confirmed_at"):
                out[u["id"]] = (u["email"], profiles[u["id"]]["display_name"], states.get(u["id"], {}))
        if len(users) < 500:
            return out
        page += 1


def film_lines(site, i, showing):
    f = site["films"][i]
    ss = sorted(showing[i], key=lambda s: (s[2], s[3]))
    cines = list(dict.fromkeys(site["cinemas"][s[1]]["n"] for s in ss))
    first = ss[0]
    d = datetime.date.fromisoformat(first[2])
    when = f"{WD[d.weekday()]} {d.day}/{d.month} a las {first[3]} en {site['cinemas'][first[1]]['n']}" + (" (VOSE)" if first[4] else "")
    title = f["t"] + (f" ({f['y']})" if f.get("y") else "")
    where = f"{len(cines)} cine{'s' if len(cines) > 1 else ''}: " + ", ".join(cines[:5]) + ("…" if len(cines) > 5 else "")
    return title, where, when


def main(d):
    if not (SB and KEY and GUSER and GPASS):
        print("email alerts not configured (secrets missing); skipping", file=sys.stderr)
        return
    site = json.load(open(f"{d}/site_data.json"))
    today = datetime.date.today().isoformat()
    showing = {}
    for s in site["shows"]:
        if s[2] >= today:
            showing.setdefault(s[0], []).append(s)
    by_key = {}
    for i in showing:
        f = site["films"][i]
        for t in {f.get("t"), f.get("en"), f.get("orig")} - {None, ""}:
            by_key.setdefault(norm(t), []).append(i)
    path = f"{d}/email_sent.json"
    sent = json.load(open(path)) if os.path.exists(path) else {}
    new_sent, outbox = {}, []
    for uid, (email, name, st) in members().items():
        wanted = [t for t in st.get("track") or [] if isinstance(t, str)]
        if (st.get("prefs") or {}).get("alert_watchlist", True):
            wanted += [w for w in st.get("wl") or [] if isinstance(w, dict)]
        hits = []
        for w in wanted:
            title, year = (w, None) if isinstance(w, str) else (w.get("n", ""), w.get("y"))
            for i in by_key.get(norm(title), []):
                y = site["films"][i].get("y")
                if year and y and abs(int(year) - y) > 1:
                    continue
                if i not in hits:
                    hits.append(i)
        keys = [site["films"][i]["id"] for i in hits]
        new_sent[uid] = keys                                  # films no longer showing drop out, so a return is announced
        fresh = [i for i in hits if site["films"][i]["id"] not in sent.get(uid, [])]
        if fresh:
            outbox.append((uid, email, name, fresh))
    if outbox:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
            smtp.login(GUSER, GPASS)
            for uid, email, name, fresh in outbox:
                rows = [film_lines(site, i, showing) for i in fresh]
                msg = EmailMessage()
                msg["Subject"] = (f"{rows[0][0]} ya está en cartel" if len(rows) == 1
                                  else f"{len(rows)} películas que sigues ya están en cartel")
                msg["From"] = f"Vamos al cine <{GUSER}>"
                msg["To"] = email
                text = [f"Hola {name},", "", "Películas que sigues ya están en cartel en Madrid:", ""]
                for t, where, when in rows:
                    text += [f"• {t}", f"  {where}", f"  Primera sesión: {when}", ""]
                text += [f"Horarios y entradas: {SITE}", "", "Puedes desactivar estos avisos en tu cuenta de Vamos al cine."]
                msg.set_content("\n".join(text))
                items = "".join(f"<li><b>{html.escape(t)}</b><br>{html.escape(where)}<br>Primera sesión: {html.escape(when)}</li>"
                                for t, where, when in rows)
                msg.add_alternative(
                    f"<p>Hola {html.escape(name)},</p><p>Películas que sigues ya están en cartel en Madrid:</p><ul>{items}</ul>"
                    f'<p><a href="{SITE}">Ver horarios y comprar entradas</a></p>'
                    "<p style=\"color:#777;font-size:12px\">Puedes desactivar estos avisos en tu cuenta de Vamos al cine.</p>",
                    subtype="html")
                try:
                    smtp.send_message(msg)
                    print("sent alert", uid, len(rows), "films", file=sys.stderr)
                except Exception as e:
                    print("send failed", uid, e, file=sys.stderr)
                    new_sent[uid] = [k for k in new_sent[uid] if k in sent.get(uid, [])]   # retry tomorrow
    json.dump(new_sent, open(path, "w"))
    print(f"{len(outbox)} alert emails, {len(new_sent)} members checked", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
