"""Fracture, ball, speed-ramped time and camera move. Run on top of a built scene:

blender -b scene.blend -P animate.py -- --out anim.blend
Physics is art-directed but physical: every piece is a free rigid body after its release
(ballistic translation + constant spin + gravity), released by a fracture front spreading
from the impact point; the impact star is Voronoi-fractured into shards and glass dust.
"""
import os as _os
ROOT = _os.environ.get("GIRIH_ROOT", _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bpy, bmesh, json, math, random, sys
from mathutils import Vector, Quaternion, Matrix
sys.path.insert(0, ROOT + "/src")
from palette import tile_color

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default

FPS = 30
DUR = float(arg("--dur", "22.0"))
NF = int(round(DUR * FPS))
SILL = 0.90
WIN = json.load(open(ROOT + "/src/window.json"))
IMP2 = (0.012, 0.952)                         # impact point, pattern coords (centre star)
IMP = Vector((IMP2[0], 0.0, IMP2[1] + SILL))
V_BALL = 25.0
R_BALL = 0.022
R_FRAG = 0.075                                # tiles touching this radius are pulverised
R_HOLE = 0.36                                 # tiles inside pop out
T_WAVE = 0.009                                # fracture front reaches R_HOLE after 9 ms
G = Vector((0, 0, -9.81))
S_IMPACT = 4.2                                # screen second of the impact

# --------------------------------------------------------------- time warp
SPEEDS = [  # (screen time, log10 of sim-seconds per screen-second), smoothstep between knots
    (0.0, math.log10(1 / 45)), (3.90, math.log10(1 / 45)), (4.60, math.log10(1 / 150)),
    (9.2, math.log10(1 / 150)), (11.2, math.log10(1 / 4000)), (17.6, math.log10(1 / 4000)),
    (19.6, math.log10(1 / 700)), (DUR + 1, math.log10(1 / 700)),
]

def speed(s):
    for (s0, l0), (s1, l1) in zip(SPEEDS, SPEEDS[1:]):
        if s0 <= s <= s1:
            u = (s - s0) / (s1 - s0) if s1 > s0 else 0.0
            u = u * u * (3 - 2 * u)
            return 10 ** (l0 + (l1 - l0) * u)
    return 10 ** SPEEDS[-1][1]

def build_warp(step=1e-3):
    ts, t = [0.0], 0.0
    n = int((DUR + 0.5) / step)
    for i in range(n):
        s = i * step
        t += 0.5 * (speed(s) + speed(s + step)) * step
        ts.append(t)
    off = ts[int(round(S_IMPACT / step))]
    return [x - off for x in ts], step

WARP, WSTEP = build_warp()

def sim_time(s):
    i = s / WSTEP
    i0 = int(math.floor(i)); u = i - i0
    i0 = max(0, min(len(WARP) - 2, i0))
    return WARP[i0] * (1 - u) + WARP[i0 + 1] * u

# --------------------------------------------------------------- helpers
def look_quat(pos, tgt, roll=0.0):
    q = (tgt - pos).normalized().to_track_quat("-Z", "Y")
    if roll:
        q = q @ Quaternion((0, 0, 1), roll)
    return q

def key_object(ob, frames, locs, quats):
    """Bulk keyframes, linear interpolation (motion blur samples between frames)."""
    ob.rotation_mode = "QUATERNION"
    ad = ob.animation_data_create()
    act = bpy.data.actions.new(ob.name + "_act")
    ad.action = act
    chans = [("location", i, [l[i] for l in locs]) for i in range(3)] + \
            [("rotation_quaternion", i, [q[i] for q in quats]) for i in range(4)]
    for path, idx, vals in chans:
        fc = new_fcurve(ob, act, path, idx)
        n = len(frames)
        fc.keyframe_points.add(n)
        co = []
        for f, v in zip(frames, vals):
            co += [f, v]
        fc.keyframe_points.foreach_set("co", co)
        fc.keyframe_points.foreach_set("interpolation", [1] * n)   # LINEAR
        fc.update()

def new_fcurve(idb, act, path, idx=0):
    if hasattr(act, "fcurve_ensure_for_datablock"):
        return act.fcurve_ensure_for_datablock(idb, path, index=idx)
    return act.fcurves.new(path, index=idx)

def quat_exp(w, t):
    a = w.length * t
    if a < 1e-9:
        return Quaternion()
    return Quaternion(w.normalized(), a)

# --------------------------------------------------------------- shards
def voronoi_shards(poly, centroid, rng, impact2):
    from shapely.geometry import Polygon, MultiPoint, Point
    from shapely.ops import voronoi_diagram
    P = Polygon(poly)
    n = max(6, int(P.area / 0.00045))
    pts = []
    tries = 0
    while len(pts) < n and tries < 20000:
        tries += 1
        # denser close to the impact point
        r = R_FRAG * 1.2 * rng.random() ** 1.7
        a = rng.random() * 2 * math.pi
        x, y = impact2[0] + r * math.cos(a), impact2[1] + r * math.sin(a)
        if P.contains(Point(x, y)):
            pts.append((x, y))
    if len(pts) < 3:
        return [P]
    cells = voronoi_diagram(MultiPoint(pts), envelope=P.buffer(0.05))
    out = []
    for c in cells.geoms:
        piece = c.intersection(P)
        if piece.is_empty:
            continue
        geoms = [piece] if piece.geom_type == "Polygon" else [g for g in getattr(piece, "geoms", []) if g.geom_type == "Polygon"]
        out += [g for g in geoms if g.area > 4e-6]
    return out

def prism_mesh(name, poly2, c2, thick, mat):
    bm = bmesh.new()
    vs = [bm.verts.new((x - c2[0], -thick / 2, y - c2[1])) for x, y in poly2]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=nv, vec=(0, thick, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    return me

def dust_meshes(rng, mat, k=14):
    out = []
    for i in range(k):
        n = rng.choice([3, 3, 4, 4, 5])
        s = 1.0
        pts = []
        for j in range(n):
            a = 2 * math.pi * j / n + rng.uniform(-0.5, 0.5) / n * 2 * math.pi
            r = s * rng.uniform(0.55, 1.0)
            pts.append((r * math.cos(a), r * math.sin(a)))
        out.append(prism_mesh(f"dust_mesh_{i}", pts, (0, 0), 0.5, mat))
    return out

# --------------------------------------------------------------- main
def main():
    rng = random.Random(1979)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, NF
    sc.render.fps = FPS
    glass = bpy.data.materials["Glass"]
    tiles_coll = bpy.data.collections["Tiles"]
    shard_coll = bpy.data.collections.new("Shards"); sc.collection.children.link(shard_coll)

    frames = list(range(1, NF + 1))
    stime = [(f - 1) / FPS for f in frames]
    simt = [sim_time(s) for s in stime]

    ball = bpy.data.objects["ball"]
    cam_pos_at = camera_path()
    # ball aims to pass just left of where the camera is when time freezes
    aim = cam_pos_at(9.2) + Vector((-0.42, 0.0, -0.10))
    bdir = (aim - IMP).normalized()
    B = IMP + bdir * V_BALL * sim_time(14.0)          # where the ball hangs during bullet time
    extend_camera(B)
    cam_pos_at = camera_path()
    n_in = Vector((0, -1, 0))
    burst_axis = (n_in * 0.75 + bdir * 0.25).normalized()

    motions = []   # (object, t_release, v, w)
    imp2 = Vector(IMP2)
    from shapely.geometry import Polygon, Point
    for ob in list(tiles_coll.objects):
        c2 = Vector((ob["cx"], ob["cy"]))
        r = (c2 - imp2).length
        poly = Polygon([tuple(p) for p in WIN["tiles"][int(ob.name.split("_")[1])]["poly"]])
        if poly.distance(Point(IMP2)) < R_FRAG * 0.55:
            # pulverise this tile into shards
            col = ob.color
            pieces = voronoi_shards(list(poly.exterior.coords)[:-1], (ob["cx"], ob["cy"]), rng, IMP2)
            for k, pc in enumerate(pieces):
                cc = pc.centroid
                me = prism_mesh(f"{ob.name}_sh{k}", list(pc.exterior.coords)[:-1], (cc.x, cc.y), 0.004, glass)
                sh = bpy.data.objects.new(me.name, me)
                sh.color = col
                sh.location = (cc.x, 0.0, cc.y + SILL)
                shard_coll.objects.link(sh)
                d2 = Vector((cc.x, cc.y)) - imp2
                rs = d2.length
                rho = Vector((d2.x, 0, d2.y)).normalized() if rs > 1e-6 else Vector((1, 0, 0))
                if rs < R_BALL * 1.1:
                    vax = V_BALL * rng.uniform(1.06, 1.22)
                else:
                    vax = max(5.0, V_BALL * (1.05 - 9.0 * (rs - R_BALL)) * rng.uniform(0.85, 1.05))
                vlat = 2.0 + 55.0 * rs * rng.uniform(0.7, 1.3)
                v = bdir * vax + rho * vlat + Vector((rng.gauss(0, 0.6), rng.gauss(0, 0.6), rng.gauss(0, 0.6)))
                w = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized() * rng.uniform(40, 160)
                motions.append((sh, rs / 1500.0, v, w))
            bpy.data.objects.remove(ob)
            continue
        if r < R_HOLE:
            x = r / R_HOLE
            t_rel = T_WAVE * x ** 1.3 * rng.uniform(0.85, 1.15)
            rho = Vector((c2.x - imp2.x, 0, c2.y - imp2.y)).normalized()
            vn = (2.5 + 11.5 * (1 - x) ** 1.4) * rng.uniform(0.85, 1.15)
            vr = 1.8 * x * (1 - x) * 4 * rng.uniform(0.7, 1.3)
            v = burst_axis * vn + rho * vr + Vector((rng.gauss(0, 0.25), rng.gauss(0, 0.25), rng.gauss(0, 0.25)))
            size = math.sqrt(ob["area"])
            axis = n_in.cross(rho).normalized()
            w = axis * (22.0 * (1 - x) + 5.0) * (0.09 / max(size, 0.03)) * rng.uniform(0.7, 1.3)
            w += Vector((rng.gauss(0, 3), rng.gauss(0, 3), rng.gauss(0, 3)))
            motions.append((ob, t_rel, v, w))

    # glass dust: tiny shards ejected from the impact in a cone
    dm = dust_meshes(rng, glass)
    warm = [tile_color("star", *IMP2), tile_color("hexB", *IMP2), tile_color("small", *IMP2), tile_color("hexA", *IMP2)]
    for i in range(int(arg("--dust", "320"))):
        me = rng.choice(dm)
        ob = bpy.data.objects.new(f"dust_{i:03d}", me)
        sz = rng.uniform(0.0018, 0.0065)
        ob.scale = (sz, sz * rng.uniform(0.5, 0.9), sz)
        c = rng.choice(warm); ob.color = (*[x ** 0.5 for x in c], 1)
        a = rng.random() * 2 * math.pi; rr = 0.03 * math.sqrt(rng.random())
        ob.location = IMP + Vector((rr * math.cos(a), 0, rr * math.sin(a)))
        shard_coll.objects.link(ob)
        cone = math.radians(32) * math.sqrt(rng.random())
        perp = Vector((math.cos(a), 0, math.sin(a)))
        dirv = (bdir * math.cos(cone) + perp * math.sin(cone)).normalized()
        v = dirv * rng.uniform(9.0, 34.0)
        w = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized() * rng.uniform(80, 300)
        motions.append((ob, 0.0, v, w))

    # bake rigid motion
    for ob, t_rel, v, w in motions:
        p0 = ob.location.copy()
        q0 = Quaternion() if ob.rotation_mode != "QUATERNION" else ob.rotation_quaternion.copy()
        locs, quats = [], []
        for t in simt:
            dt = max(0.0, t - t_rel)
            locs.append(p0 + v * dt + 0.5 * G * dt * dt)
            quats.append(quat_exp(w, dt) @ q0)
        key_object(ob, frames, locs, quats)
        ob["t_rel"] = t_rel; ob["v"] = list(v); ob["w"] = list(w)

    # ball: straight line through the impact point
    locs = [IMP + bdir * V_BALL * t for t in simt]
    key_object(ball, frames, locs, [Quaternion()] * len(frames))

    # camera
    cam = bpy.data.objects["cam"]
    clocs, cquats, lens, focus = [], [], [], []
    for s in stime:
        p, tg, ln, fp = camera_state(cam_pos_at, s, sim_time(s), bdir)
        clocs.append(p); cquats.append(look_quat(p, tg)); lens.append(ln); focus.append((fp - p).length)
    key_object(cam, frames, clocs, cquats)
    cd = cam.data
    ad = cd.animation_data_create(); act = bpy.data.actions.new("cam_data"); ad.action = act
    for path, vals in (("lens", lens), ("dof.focus_distance", focus)):
        fc = new_fcurve(cd, act, path)
        fc.keyframe_points.add(len(frames))
        co = []
        for f, v in zip(frames, vals):
            co += [f, v]
        fc.keyframe_points.foreach_set("co", co)
        fc.keyframe_points.foreach_set("interpolation", [1] * len(frames))
        fc.update()

    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    json.dump({"bdir": list(bdir), "imp": list(IMP), "simt": simt, "fps": FPS, "nf": NF},
              open(arg("--meta", ROOT + "/anim_meta.json"), "w"))
    print("moving objects:", len(motions), "frames:", NF)

# --------------------------------------------------------------- camera
CAM_KEYS = [  # screen s, position, target, lens (bullet-time keys are added relative to the ball)
    (0.0,  (1.25, -3.90, 0.55), (0.85, -2.30, 0.00), 30.0),
    (2.6,  (1.40, -4.70, 0.98), (0.35, -0.60, 1.05), 30.0),
    (4.2,  (1.30, -4.45, 1.20), (0.18, 0.00, 1.70), 31.0),
    (9.2,  (1.00, -3.20, 1.36), (0.08, -0.30, 1.78), 34.0),
]

def extend_camera(B):
    V = lambda *a: tuple(B + Vector(a))
    CAM_KEYS.extend([
        (12.4, V(0.40, -0.70, 0.05), V(0.00, 0.30, 0.00), 35.0),
        (15.2, V(-0.10, -0.38, 0.06), V(0.05, 0.60, 0.02), 32.0),
        (18.4, V(-0.35, -0.85, 0.12), V(0.12, 0.60, 0.05), 30.0),
        (DUR,  V(-0.45, -1.25, 0.18), V(0.15, 0.60, 0.05), 30.0),
    ])

def catmull(p0, p1, p2, p3, u):
    u2, u3 = u * u, u * u * u
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u2 + (-p0 + 3 * p1 - 3 * p2 + p3) * u3)

def spline(keys, idx):
    """C2-continuous cubic spline over real key times (no speed jumps at keys)."""
    from scipy.interpolate import CubicSpline
    import numpy as np
    times = np.array([k[0] for k in keys])
    vals = np.array([list(k[idx]) if not isinstance(k[idx], float) else [k[idx]] for k in keys], dtype=float)
    cs = CubicSpline(times, vals, axis=0, bc_type="natural")
    scalar = isinstance(keys[0][idx], float)
    def at(s):
        v = cs(min(times[-1], max(times[0], s)))
        return float(v[0]) if scalar else Vector(v.tolist())
    return at

def camera_path():
    return spline(CAM_KEYS, 1)

def camera_state(pos_at, s, t, bdir):
    tgt_at = spline(CAM_KEYS, 2); lens_at = spline(CAM_KEYS, 3)
    p, tg, ln = pos_at(s), tgt_at(s), lens_at(s)
    ball = IMP + bdir * V_BALL * t
    # focus: window early, then the ball once it is in the room, back to the window at the end
    win = Vector((0.0, 0.0, 1.85))
    floor = Vector((0.9, -2.3, 0.0))
    if t <= 0:
        u = min(1.0, max(0.0, (s - 1.0) / 2.4)); u = u * u * (3 - 2 * u)
        fp = floor.lerp(win, u)
    else:
        u = min(1.0, max(0.0, (s - S_IMPACT) / 1.5)); u = u * u * (3 - 2 * u)
        v = min(1.0, max(0.0, (s - 17.4) / 2.6)); v = v * v * (3 - 2 * v)
        fp = win.lerp(ball, u * (1 - v))
    # subtle hand-held breathing (very low amplitude, low frequency)
    p = p + Vector((0.004 * math.sin(0.9 * s), 0.0, 0.003 * math.sin(1.3 * s + 1.0)))
    return p, tg, ln, fp

if __name__ == "__main__":
    main()
    out = arg("--out", ROOT + "/anim.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("SAVED", out)
