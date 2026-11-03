"""Turn the OpenStreetMap extract into compact SVG path data (km from Puerta del Sol, y down).

Usage: python3 -I build_map.py OSM_JSON OUT_JSON
"""
import json, math, sys

LAT0, LON0 = 40.4168, -3.7038
KX, KY = math.cos(math.radians(LAT0)) * 111.32, 110.54
RADIUS_KM = 40


def proj(lat, lon):
    return ((lon - LON0) * KX, -(lat - LAT0) * KY)


def simplify(pts, tol):
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy) or 1e-9
    dmax, idx = 0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * pts[i][0] - dx * pts[i][1] + x2 * y1 - y2 * x1) / norm
        if d > dmax:
            dmax, idx = d, i
    if dmax <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[:idx + 1], tol)[:-1] + simplify(pts[idx:], tol)


def path(lines, tol):
    out = []
    for g in lines:
        pts = simplify([proj(p["lat"], p["lon"]) for p in g], tol)
        if len(pts) >= 2:
            out.append("M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in pts))
    return "".join(out)


def centroid(lines):
    pts = [proj(p["lat"], p["lon"]) for g in lines for p in g]
    return round(sum(p[0] for p in pts) / len(pts), 2), round(sum(p[1] for p in pts) / len(pts), 2)


def main(src, dst):
    els = json.load(open(src))["elements"]
    out = {"districts": [], "munis": [], "m30": "", "river": ""}
    m30, river = [], []
    for e in els:
        t = e.get("tags", {})
        if e["type"] == "relation":
            lines = [m["geometry"] for m in e.get("members", []) if m.get("type") == "way" and m.get("geometry")]
            if not lines:
                continue
            cx, cy = centroid(lines)
            if t.get("admin_level") == "9":
                out["districts"].append({"n": t.get("name", ""), "d": path(lines, 0.03), "x": cx, "y": cy})
            elif t.get("admin_level") == "8" and math.hypot(cx, cy) < RADIUS_KM:
                out["munis"].append({"n": t.get("name", ""), "d": path(lines, 0.12), "x": cx, "y": cy})
        elif t.get("highway") == "motorway":
            m30.append(e["geometry"])
        elif t.get("waterway") == "river":
            river.append(e["geometry"])
    out["m30"] = path(m30, 0.03)
    out["river"] = path(river, 0.03)
    json.dump(out, open(dst, "w"), ensure_ascii=False, separators=(",", ":"))
    print(len(out["districts"]), "districts", len(out["munis"]), "municipalities",
          len(json.dumps(out)) // 1024, "KB", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
