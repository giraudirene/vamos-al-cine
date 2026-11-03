"""Inject site_data.json and map.json into template.html.

Usage: python3 -I render_page.py DATADIR OUT_HTML
"""
import os, sys

d, out = sys.argv[1], sys.argv[2]
here = os.path.dirname(os.path.abspath(__file__))
data = open(f"{d}/site_data.json", encoding="utf-8").read().replace("</", "<\\/")
mp = open(f"{d}/map.json", encoding="utf-8").read().replace("</", "<\\/")
metro = open(f"{d}/metro.json", encoding="utf-8").read() if os.path.exists(f"{d}/metro.json") else "[]"
html = (open(f"{here}/template.html", encoding="utf-8").read()
        .replace("__DATA__", data).replace("__MAP__", mp).replace("__METRO__", metro.replace("</", "<\\/")))
open(out, "w", encoding="utf-8").write(html)
print(out, len(html) // 1024, "KB", file=sys.stderr)
