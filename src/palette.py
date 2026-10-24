"""Tile classification + zonal Persian stained-glass palette (desired transmission colours).

A warm 'shamseh' (sun) medallion around the centre, a cool lapis/turquoise field outside; the
zone edge is dithered per tile so every piece keeps one clean colour.
"""
import os as _os
ROOT = _os.environ.get("GIRIH_ROOT", _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import math, random

WARM = {"star": (1.00, 0.60, 0.06), "hexA": (1.00, 0.30, 0.04), "hexB": (0.90, 0.04, 0.10), "small": (1.00, 0.86, 0.40)}
COOL = {"star": (0.04, 0.66, 0.70), "hexA": (0.07, 0.22, 0.95), "hexB": (0.22, 0.10, 0.80), "small": (1.00, 0.62, 0.06)}
CENTER = (0.0, 0.98)       # medallion centre in pattern coords (impact point is here)
R0, R1 = 0.24, 0.42        # warm inside R0, cool outside R1, dithered in between

PALETTE = {"star": WARM["star"], "hexA": COOL["hexA"], "hexB": COOL["hexB"], "small": COOL["small"]}

def classify(face, d, shift):
    c = face.centroid
    gx, gy = (c.x - shift[0]) / d, (c.y - shift[1]) / d
    do = math.hypot(gx - round(gx), gy - round(gy)) * d
    ds = math.hypot(gx - 0.5 - round(gx - 0.5), gy - 0.5 - round(gy - 0.5)) * d
    if do < 0.22 * d:
        return "star"
    if ds < 0.16 * d:
        return "small"
    ox, oy = round(gx), round(gy)
    ang = math.degrees(math.atan2(gy - oy, gx - ox)) % 180.0
    return "hexA" if (ang < 45 or ang >= 135) else "hexB"

def tile_color(cls, cx, cy, seed=0):
    r = math.hypot(cx - CENTER[0], cy - CENTER[1])
    w = min(1.0, max(0.0, (R1 - r) / (R1 - R0)))          # 1 warm .. 0 cool
    rnd = random.Random(f"{abs(cx):.4f},{cy:.4f},{seed}").random()
    return (WARM if rnd < w else COOL)[cls]
