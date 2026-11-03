"""Inject site_data.json and map.json into template.html.

Usage: python3 -I render_page.py DATADIR OUT_HTML
"""
import os, sys

d, out = sys.argv[1], sys.argv[2]
here = os.path.dirname(os.path.abspath(__file__))
data = open(f"{d}/site_data.json", encoding="utf-8").read().replace("</", "<\\/")
mp = open(f"{d}/map.json", encoding="utf-8").read().replace("</", "<\\/")
metro = open(f"{d}/metro.json", encoding="utf-8").read() if os.path.exists(f"{d}/metro.json") else "[]"
cfg_path = os.path.join(here, "..", "static", "config.json")              # public Supabase address + anon key
config = open(cfg_path, encoding="utf-8").read() if os.path.exists(cfg_path) else "{}"
html = (open(f"{here}/template.html", encoding="utf-8").read()
        .replace("__DATA__", data).replace("__MAP__", mp).replace("__METRO__", metro.replace("</", "<\\/")).replace("__CONFIG__", config.replace("</", "<\\/")))
# The website needs a full HTML document; the claude.ai preview adds its own, so it gets the bare fragment.
head, sep, body = html.partition("<header")
page = ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        + head + "</head>\n<body>\n" + sep + body + "\n</body>\n</html>\n")
open(out, "w", encoding="utf-8").write(page)
open(os.path.join(os.path.dirname(out), "fragment.html"), "w", encoding="utf-8").write(html)
print(out, len(page) // 1024, "KB", file=sys.stderr)
