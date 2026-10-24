"""Persian girih window: Hankin star pattern on the 4.8.8 tiling, clipped to a pointed arch.

Exports tiles as polygons (meters, window plane x=right, y=up, origin at window centre-bottom).
"""
import os as _os
ROOT = _os.environ.get("GIRIH_ROOT", _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import json, math, sys
import numpy as np
from shapely.geometry import LineString, Polygon, Point, box
from shapely.ops import unary_union, polygonize

def arch_outline(W, H_rect, r_fac=0.78, n=64):
    """Pointed two-centred arch: rectangle W x H_rect + arch on top."""
    r = r_fac * W
    cxL, cxR = -W / 2 + r, W / 2 - r        # left arc centred right of axis and vice versa
    # left side arc: centre (cxL, H_rect), from angle pi (point (-W/2,H)) up to crown at x=0
    crown_y = H_rect + math.sqrt(r * r - cxL * cxL)
    a0 = math.pi; a1 = math.atan2(crown_y - H_rect, 0 - cxL)
    left = [(cxL + r * math.cos(a), H_rect + r * math.sin(a)) for a in np.linspace(a0, a1, n)]
    right = [(-x, y) for (x, y) in reversed(left)]
    pts = [(-W / 2, 0.0)] + left + right[1:] + [(W / 2, 0.0)]
    return Polygon(pts), crown_y

def tiling_488(a, xr, yr):
    d = a * (1 + math.sqrt(2))
    R = a / (2 * math.sin(math.pi / 8))
    polys = []
    for i in range(int(xr[0] / d) - 2, int(xr[1] / d) + 3):
        for j in range(int(yr[0] / d) - 2, int(yr[1] / d) + 3):
            cx, cy = i * d, j * d
            octa = [(cx + R * math.cos(math.radians(22.5 + 45 * k)), cy + R * math.sin(math.radians(22.5 + 45 * k))) for k in range(8)]
            polys.append(("oct", (i, j), octa))
            sx, sy = cx + d / 2, cy + d / 2
            h = a / math.sqrt(2)
            polys.append(("sq", (i, j), [(sx + h, sy), (sx, sy + h), (sx - h, sy), (sx, sy - h)]))
    return polys, d

def rot(v, ang):
    c, s = math.cos(ang), math.sin(ang)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]])

def hankin(poly, theta):
    P = [np.array(p, float) for p in poly]
    n = len(P); segs = []
    for k in range(n):
        vp, v, vn = P[k - 1], P[k], P[(k + 1) % n]
        ma, mb = (vp + v) / 2, (v + vn) / 2
        da = rot((v - ma) / np.linalg.norm(v - ma), theta)
        db = rot((v - mb) / np.linalg.norm(v - mb), -theta)
        # solve ma + s*da = mb + t*db
        A = np.array([da, -db]).T
        s, t = np.linalg.solve(A, mb - ma)
        X = ma + s * da
        segs.append([tuple(ma), tuple(X)]); segs.append([tuple(X), tuple(mb)])
    return segs

def build(W=1.0, H_rect=1.15, a=0.068, theta_deg=67.5, shift=(0.0, 0.0)):
    outline, crown = arch_outline(W, H_rect)
    polys, d = tiling_488(a, (-W - 0.3, W + 0.3), (-0.6 - shift[1], crown + 0.6 - shift[1]))
    th = math.radians(theta_deg)
    lines = []
    for kind, ij, poly in polys:
        poly = [(x + shift[0], y + shift[1]) for (x, y) in poly]
        for s in hankin(poly, th):
            lines.append(LineString(s))
    lines.append(outline.exterior)
    import shapely
    merged = shapely.set_precision(unary_union(lines), 1e-7)
    faces = [f for f in polygonize(merged) if f.representative_point().within(outline) and f.area > 1e-7]
    faces = merge_slivers(faces, min_area=2.5e-4)
    return outline, crown, faces, d

def merge_slivers(faces, min_area):
    """Fold tiny boundary slivers into the neighbour they share the longest edge with."""
    faces = list(faces)
    while True:
        small = [i for i, f in enumerate(faces) if f.area < min_area]
        if not small:
            return faces
        i = min(small, key=lambda k: faces[k].area)
        f = faces[i]
        best, best_len = None, 0.0
        for j, g in enumerate(faces):
            if j == i:
                continue
            l = f.boundary.intersection(g.boundary).length
            if l > best_len:
                best, best_len = j, l
        if best is None:
            faces.pop(i); continue
        merged = unary_union([faces[best], f]).buffer(0)
        if merged.geom_type != "Polygon":
            merged = max(merged.geoms, key=lambda p: p.area)
        faces[best] = merged.simplify(1e-6)
        faces.pop(i)

def classify(face, d, shift):
    c = face.centroid
    n = len(face.exterior.coords) - 1
    # distance to nearest octagon centre / square centre
    gx, gy = (c.x - shift[0]) / d, (c.y - shift[1]) / d
    do = math.hypot(gx - round(gx), gy - round(gy)) * d
    ds = math.hypot(gx - 0.5 - round(gx - 0.5), gy - 0.5 - round(gy - 0.5)) * d
    return n, do, ds

def _preview():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    theta = float(sys.argv[1]) if len(sys.argv) > 1 else 67.5
    shift = (0.0, 0.62)
    outline, crown, faces, d = build(theta_deg=theta, shift=shift)
    fig, ax = plt.subplots(figsize=(6, 10), dpi=110)
    fig.patch.set_facecolor("#111")
    areas = [f.area for f in faces]
    for f in faces:
        n, do, ds = classify(f, d, shift)
        col = "#e8a317" if do < 0.2 * d else ("#1b4fd8" if ds < 0.2 * d else ("#1aa3b5" if n == 6 else "#c0122a"))
        x, y = f.exterior.xy
        ax.fill(x, y, color=col, ec="#111", lw=1.2)
    x, y = outline.exterior.xy; ax.plot(x, y, color="w", lw=1)
    ax.set_aspect("equal"); ax.axis("off")
    out = f"{ROOT}/out/tests/pattern_{theta:g}.png"
    plt.savefig(out, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(out, "faces:", len(faces), "crown:", round(crown, 3), "d:", round(d, 4), "area min/max:", round(min(areas), 5), round(max(areas), 5))


def export(path, W=1.0, H_rect=1.15, shift=(0.0, 0.62)):
    from palette import classify, PALETTE
    outline, crown, faces, d = build(W=W, H_rect=H_rect, shift=shift)
    tiles = []
    for f in faces:
        f = f.simplify(1e-6)
        coords = list(f.exterior.coords)[:-1]
        # CCW orientation
        if Polygon(coords).exterior.is_ccw is False:
            coords = coords[::-1]
        k = classify(f, d, shift)
        c = f.centroid
        tiles.append({"poly": [[round(x, 6), round(y, 6)] for x, y in coords], "cls": k,
                      "centroid": [c.x, c.y], "area": f.area})
    data = {"W": W, "H_rect": H_rect, "crown": crown, "d": d, "shift": shift,
            "outline": [[x, y] for x, y in outline.exterior.coords][:-1], "tiles": tiles}
    json.dump(data, open(path, "w"))
    return data


if __name__ == "__main__":
    d = export(ROOT + "/src/window.json")
    print(len(d["tiles"]), "tiles ->", ROOT + "/src/window.json")
