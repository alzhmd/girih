"""Build the room + Persian girih window scene in Blender (run headless).

blender -b --factory-startup -P build_scene.py -- --out /opt/film/scene.blend
Coordinates: window glass in the plane y=0, room interior is y<0, z up, meters.
"""
import os as _os
ROOT = _os.environ.get("GIRIH_ROOT", _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bpy, bmesh, json, math, sys, random
sys.path.insert(0, ROOT + "/src")
from palette import tile_color
from mathutils import Vector, Matrix, Quaternion

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default

SRC = ROOT + "/src"
WIN = json.load(open(arg("--json", f"{SRC}/window.json")))
SILL = 0.90          # window bottom above floor
GLASS_T = 0.004      # glass thickness
LEAD_W = 0.0026      # visible lead came width per tile edge
WALL_T = 0.36        # wall thickness (deep Persian reveal)
ROOM = dict(x=3.6, y0=-7.0, h=4.6)

# Persian stained glass tints (desired transmitted colour; per-surface tint = sqrt)
TINTS = {
    "star":  (1.00, 0.58, 0.06),
    "hexA":  (0.04, 0.70, 0.72),
    "hexB":  (0.10, 0.24, 0.95),
    "small": (0.95, 0.05, 0.12),
}

def clear():
    for c in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for x in list(c):
            c.remove(x)

def new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out

def principled(nt, **kw):
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    for k, v in kw.items():
        p.inputs[k].default_value = v
    return p

# ---------------------------------------------------------------- materials
def mat_glass():
    m, nt, out = new_mat("Glass")
    L = nt.links
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    p = principled(nt, **{"Roughness": float(arg("--glass_rough", "0.05")), "IOR": 1.52, "Transmission Weight": 1.0})
    L.new(oi.outputs["Color"], p.inputs["Base Color"])
    # hammered "cathedral" glass: low-frequency ripples, per tile random offset
    tc = nt.nodes.new("ShaderNodeTexCoord")
    add = nt.nodes.new("ShaderNodeVectorMath"); add.operation = "ADD"
    rnd = nt.nodes.new("ShaderNodeCombineXYZ")
    L.new(oi.outputs["Random"], rnd.inputs["X"]); L.new(oi.outputs["Random"], rnd.inputs["Z"])
    L.new(tc.outputs["Object"], add.inputs[0]); L.new(rnd.outputs[0], add.inputs[1])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 24.0
    noise.inputs["Detail"].default_value = 2.0
    noise.inputs["Roughness"].default_value = 0.45
    L.new(add.outputs[0], noise.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.22
    bump.inputs["Distance"].default_value = 0.002
    L.new(noise.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], p.inputs["Normal"])
    # thin-glass trick: shadow rays pass straight through, tinted -> coloured light & god rays
    lp = nt.nodes.new("ShaderNodeLightPath")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    L.new(oi.outputs["Color"], tr.inputs["Color"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    L.new(lp.outputs["Is Shadow Ray"], mix.inputs["Fac"])
    L.new(p.outputs[0], mix.inputs[1]); L.new(tr.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    return m

def mat_lead():
    m, nt, out = new_mat("Lead")
    p = principled(nt, **{"Base Color": (0.035, 0.034, 0.033, 1), "Metallic": 0.6, "Roughness": 0.55})
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    return m

def mat_shard():
    """Broken glass pieces: same look, but no lead."""
    return bpy.data.materials["Glass"]

def mat_wood():
    m, nt, out = new_mat("Wood")
    L = nt.links
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.0, 1.0, 22.0)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexNoise"); wave.inputs["Scale"].default_value = 9.0
    wave.inputs["Detail"].default_value = 6.0
    L.new(mp.outputs[0], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.030, 0.014, 0.007, 1)
    ramp.color_ramp.elements[1].color = (0.085, 0.040, 0.018, 1)
    L.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    p = principled(nt, **{"Roughness": 0.32, "Coat Weight": 0.35, "Coat Roughness": 0.08})
    L.new(ramp.outputs["Color"], p.inputs["Base Color"])
    L.new(p.outputs[0], out.inputs["Surface"])
    return m

def mat_plaster():
    m, nt, out = new_mat("Plaster")
    L = nt.links
    noise = nt.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 8.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.46, 0.40, 0.33, 1)
    ramp.color_ramp.elements[1].color = (0.60, 0.54, 0.46, 1)
    L.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    p = principled(nt, **{"Roughness": 0.92})
    L.new(ramp.outputs["Color"], p.inputs["Base Color"])
    n2 = nt.nodes.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 140.0
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.002
    L.new(n2.outputs["Fac"], bump.inputs["Height"]); L.new(bump.outputs["Normal"], p.inputs["Normal"])
    L.new(p.outputs[0], out.inputs["Surface"])
    return m

def mat_floor():
    m, nt, out = new_mat("Floor")
    L = nt.links
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 2.2
    br.inputs["Mortar Size"].default_value = 0.012
    br.inputs["Color1"].default_value = (0.34, 0.22, 0.15, 1)
    br.inputs["Color2"].default_value = (0.28, 0.18, 0.12, 1)
    br.inputs["Mortar"].default_value = (0.10, 0.08, 0.07, 1)
    br.offset = 0.5; br.squash = 1.0
    L.new(tc.outputs["Object"], br.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 6.0
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.18; rough.inputs["To Max"].default_value = 0.45
    L.new(noise.outputs["Fac"], rough.inputs["Value"])
    p = principled(nt, **{})
    L.new(br.outputs["Color"], p.inputs["Base Color"])
    L.new(rough.outputs["Result"], p.inputs["Roughness"])
    L.new(p.outputs[0], out.inputs["Surface"])
    return m

def mat_chrome():
    m, nt, out = new_mat("Chrome")
    p = principled(nt, **{"Base Color": (0.78, 0.78, 0.80, 1), "Metallic": 1.0, "Roughness": 0.12})
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    return m

def mat_haze(density):
    m, nt, out = new_mat("Haze")
    v = nt.nodes.new("ShaderNodeVolumePrincipled")
    v.inputs["Density"].default_value = density
    v.inputs["Anisotropy"].default_value = float(arg("--aniso", "0.35"))
    v.inputs["Color"].default_value = (1, 1, 1, 1)
    nt.links.new(v.outputs[0], out.inputs["Volume"])
    return m

# ---------------------------------------------------------------- geometry
def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj

def to_world(px, py, y=0.0):
    return Vector((px, y, py + SILL))

def make_tile(name, poly, centroid, glass, lead, with_lead=True, thick=GLASS_T):
    """Prism of the tile polygon, origin at centroid; caps inset into lead rim + glass."""
    cx, cy = centroid
    bm = bmesh.new()
    vs = [bm.verts.new((x - cx, -thick / 2, y - cy)) for x, y in poly]
    f = bm.faces.new(vs)
    bmesh.ops.recalc_face_normals(bm, faces=[f])
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=nv, vec=(0, thick, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    caps = [fc for fc in bm.faces if abs(abs(fc.normal.y) - 1) < 1e-4]
    for fc in bm.faces:
        fc.material_index = 1 if with_lead else 0
    if with_lead:
        res = bmesh.ops.inset_individual(bm, faces=caps, thickness=LEAD_W, depth=0.0, use_even_offset=True)
        for fc in caps:
            fc.material_index = 0
            # glass sits slightly recessed inside the came
            for v in fc.verts:
                v.co.y -= math.copysign(0.0006, fc.normal.y)
    for fc in bm.faces:
        fc.smooth = False
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(glass); me.materials.append(lead)
    ob = bpy.data.objects.new(name, me)
    ob.location = to_world(cx, cy)
    return ob

def poly_prism(name, shapely_poly, y0, y1, mat):
    """Extrude a shapely polygon (pattern coords, may have holes) between y0..y1 via triangulation."""
    import bmesh
    from mathutils.geometry import tessellate_polygon
    rings = [list(shapely_poly.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in shapely_poly.interiors]
    bm = bmesh.new()
    flat = []
    for r in rings:
        flat += r
    tris = tessellate_polygon([[Vector((x, yy, 0)) for x, yy in r] for r in rings])
    for yv, flip in ((y0, False), (y1, True)):
        vv = [bm.verts.new((x, yv, yy + SILL)) for x, yy in flat]
        for t in tris:
            a, b, c = (vv[i] for i in t)
            try:
                bm.faces.new((a, c, b) if flip else (a, b, c))
            except ValueError:
                pass
    # side walls for every ring
    for r in rings:
        n = len(r)
        for i in range(n):
            (x0, z0), (x1, z1) = r[i], r[(i + 1) % n]
            q = [bm.verts.new((x0, y0, z0 + SILL)), bm.verts.new((x1, y0, z1 + SILL)),
                 bm.verts.new((x1, y1, z1 + SILL)), bm.verts.new((x0, y1, z0 + SILL))]
            bm.faces.new(q)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    return ob

def box(name, x0, x1, y0, y1, z0, z1, mat, inward=False):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    if inward:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    if mat:
        me.materials.append(mat)
    return bpy.data.objects.new(name, me)

# ---------------------------------------------------------------- build
def build():
    from shapely.geometry import Polygon, box as sbox
    clear()
    sc = bpy.context.scene
    glass, lead = mat_glass(), mat_lead()
    wood, plaster, floor, chrome = mat_wood(), mat_plaster(), mat_floor(), mat_chrome()

    tiles_coll = bpy.data.collections.new("Tiles"); sc.collection.children.link(tiles_coll)
    rng = random.Random(7)
    for i, t in enumerate(WIN["tiles"]):
        ob = make_tile(f"tile_{i:03d}", t["poly"], t["centroid"], glass, lead)
        tint = tile_color(t["cls"], *t["centroid"])
        j = 1.0 + rng.uniform(-0.06, 0.06)
        col = [min(1.0, max(0.0, c * j)) for c in tint]
        ob.color = (*col, 1.0)
        ob["cls"] = t["cls"]; ob["area"] = t["area"]; ob["cx"] = t["centroid"][0]; ob["cy"] = t["centroid"][1]
        link(ob, tiles_coll)

    outline = Polygon(WIN["outline"])
    frame_outer = outline.buffer(0.05, join_style="mitre")
    frame = poly_prism("frame", frame_outer.difference(outline), -0.035, 0.035, wood)
    link(frame)
    # wall with an arch opening (opening = frame outer boundary)
    R = ROOM
    wall_poly = sbox(-R["x"], -SILL, R["x"], R["h"] - SILL).difference(frame_outer)
    wall = poly_prism("wall", wall_poly, -WALL_T / 2, WALL_T / 2, plaster)
    link(wall)
    # reveal: a thin plaster sill/jamb is already the hole side of the wall prism
    room_items = [
        box("floor", -R["x"], R["x"], R["y0"], WALL_T / 2, -0.2, 0.0, floor),
        box("ceiling", -R["x"], R["x"], R["y0"], WALL_T / 2, R["h"], R["h"] + 0.2, plaster),
        box("wall_L", -R["x"] - 0.2, -R["x"], R["y0"], WALL_T / 2, 0, R["h"], plaster),
        box("wall_R", R["x"], R["x"] + 0.2, R["y0"], WALL_T / 2, 0, R["h"], plaster),
        box("wall_B", -R["x"], R["x"], R["y0"] - 0.2, R["y0"], 0, R["h"], plaster),
    ]
    for o in room_items:
        link(o)
    # haze volume filling the room
    haze = box("haze", -R["x"] + 0.01, R["x"] - 0.01, R["y0"] + 0.01, -WALL_T / 2 - 0.005, 0.005, R["h"] - 0.005,
               mat_haze(float(arg("--haze", "0.06"))))
    link(haze)

    # floating dust motes (sunbeam specks; frozen by the slow motion)
    mm, nt2, out2 = new_mat("Mote")
    pm = principled(nt2, **{"Base Color": (0.9, 0.86, 0.8, 1), "Roughness": 0.6})
    nt2.links.new(pm.outputs[0], out2.inputs["Surface"])
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    mme = bpy.data.meshes.new("mote"); bm.to_mesh(mme); bm.free(); mme.materials.append(mm)
    mc = bpy.data.collections.new("Motes"); sc.collection.children.link(mc)
    mr = random.Random(11)
    for i in range(int(arg("--motes", "2200"))):
        o = bpy.data.objects.new(f"mote_{i:04d}", mme)
        o.location = (mr.uniform(-1.6, 2.4), mr.uniform(-4.2, -0.25), mr.uniform(0.4, 2.9))
        r = mr.uniform(0.00025, 0.0009); o.scale = (r, r, r)
        o.visible_shadow = False
        mc.objects.link(o)

    # steel ball (animated later)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=0.022, location=(0, 1.5, 1.8))
    ball = bpy.context.active_object; ball.name = "ball"
    bpy.ops.object.shade_smooth()
    ball.data.materials.append(chrome)
    # the studio card lights only the ball (light linking), so the window keeps clean colours

    # world: CC0 garden HDRI (Poly Haven 'Symmetrical Garden 02'), its sun clamped away
    world = bpy.data.worlds.new("Sky"); sc.world = world
    try:
        world.use_nodes = True
    except Exception:
        pass
    wn = world.node_tree; wn.nodes.clear()
    wo = wn.nodes.new("ShaderNodeOutputWorld")
    tc = wn.nodes.new("ShaderNodeTexCoord")
    mp = wn.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (math.radians(float(arg("--hdri_tilt", "18"))), 0, math.radians(float(arg("--hdri_rot", "-90"))))
    wn.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    env = wn.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(arg("--hdri", ROOT + "/assets/symmetrical_garden_02_4k.exr"))
    wn.links.new(mp.outputs[0], env.inputs["Vector"])
    clamp = wn.nodes.new("ShaderNodeVectorMath"); clamp.operation = "MINIMUM"
    clamp.inputs[1].default_value = (12.0, 12.0, 12.0)
    wn.links.new(env.outputs["Color"], clamp.inputs[0])
    bg = wn.nodes.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = float(arg("--sky", "0.6"))
    wn.links.new(clamp.outputs[0], bg.inputs["Color"]); wn.links.new(bg.outputs[0], wo.inputs["Surface"])
    try:
        world.cycles.sampling_method = "MANUAL"; world.cycles.sample_map_resolution = 2048
    except Exception:
        pass

    # glossy-only kicker strips (motivated by the bright room): glints on glass + steel, room stays dark
    for nm, loc, rot, en in (("kick_L", (-1.6, -2.6, 3.2), (math.radians(55), 0, math.radians(-35)), 160.0),
                             ("kick_R", (2.2, -3.4, 2.4), (math.radians(70), 0, math.radians(40)), 110.0)):
        ld = bpy.data.lights.new(nm, type="AREA"); ld.shape = "RECTANGLE"; ld.size = 2.4; ld.size_y = 0.12
        ld.energy = float(arg("--kick", "0.6")) * en; ld.color = (1.0, 0.92, 0.82)
        lo = bpy.data.objects.new(nm, ld); lo.location = loc; lo.rotation_euler = rot; link(lo)
        lo.visible_camera = False; lo.visible_diffuse = False; lo.visible_volume_scatter = False
    ld = bpy.data.lights.new("card", type="AREA"); ld.shape = "DISK"; ld.size = 9.0
    ld.energy = float(arg("--card", "2000")); ld.color = (1.0, 0.95, 0.88)
    lo = bpy.data.objects.new("card", ld); lo.location = (0.6, -5.2, 2.1); lo.rotation_euler = (math.radians(90), 0, 0); link(lo)
    lo.visible_camera = False; lo.visible_diffuse = False; lo.visible_volume_scatter = False

    # sun: from outside, upper right, streaming into the room
    el, az = math.radians(float(arg("--sun_el", "34"))), math.radians(float(arg("--sun_az", "28")))
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), -math.sin(el)))
    sl = bpy.data.lights.new("sun", type="SUN"); sl.energy = float(arg("--sun", "10.0")); sl.angle = math.radians(0.6)
    sun = bpy.data.objects.new("sun", sl); link(sun)
    sun.rotation_mode = "QUATERNION"; sun.rotation_quaternion = d.to_track_quat("-Z", "Y")

    # camera
    cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd); link(cam)
    sc.camera = cam
    cd.lens = float(arg("--lens", "32")); cd.sensor_width = 36; cd.sensor_fit = "HORIZONTAL"
    cd.clip_start = 0.01; cd.clip_end = 100
    cd.dof.use_dof = True; cd.dof.aperture_fstop = 2.8
    cam.location = Vector([float(v) for v in arg("--cam", "1.4,-4.4,1.25").split(",")])
    tgt = Vector([float(v) for v in arg("--tgt", "0.3,0,1.45").split(",")])
    look_at(cam, tgt)
    cd.dof.focus_distance = (cam.location - Vector((0, 0, 1.8))).length

    only_ball = bpy.data.collections.new("BallOnly"); only_ball.objects.link(bpy.data.objects["ball"])
    bpy.data.objects["card"].light_linking.receiver_collection = only_ball
    # warm floor bounce seen in the lower half of the steel ball
    ld = bpy.data.lights.new("card_low", type="AREA"); ld.shape = "DISK"; ld.size = 3.0
    ld.energy = 220.0; ld.color = (1.0, 0.62, 0.32)
    lo = bpy.data.objects.new("card_low", ld); lo.location = (0.9, -2.6, -0.6); lo.rotation_euler = (math.radians(-20), 0, 0)
    sc.collection.objects.link(lo)
    lo.visible_camera = False; lo.visible_diffuse = False; lo.visible_volume_scatter = False
    lo.light_linking.receiver_collection = only_ball
    setup_render(sc)

def look_at(ob, target, roll=0.0):
    d = (target - ob.location).normalized()
    ob.rotation_mode = "QUATERNION"
    q = d.to_track_quat("-Z", "Y")
    if roll:
        q = q @ Quaternion((0, 0, 1), roll)
    ob.rotation_quaternion = q

def setup_render(sc):
    sc.render.engine = "CYCLES"
    cy = sc.cycles
    cy.device = "CPU"
    cy.samples = int(arg("--spp", "128"))
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    cy.denoiser = "OPENIMAGEDENOISE"
    try:
        cy.denoising_input_passes = "RGB_ALBEDO_NORMAL"
        cy.denoising_prefilter = "ACCURATE"
        cy.denoising_quality = "HIGH"
    except Exception:
        pass
    cy.max_bounces = 12; cy.transmission_bounces = 10; cy.glossy_bounces = 4
    cy.diffuse_bounces = 3; cy.volume_bounces = 0; cy.transparent_max_bounces = 24
    cy.caustics_reflective = False; cy.caustics_refractive = False
    cy.blur_glossy = 0.6
    cy.sample_clamp_indirect = 4.0
    cy.sample_clamp_direct = float(arg("--clampd", "12"))
    cy.adaptive_threshold = float(arg("--adapt", "0.02"))
    sc.render.resolution_x = int(arg("--w", "1920")); sc.render.resolution_y = int(arg("--h", "804"))
    sc.render.resolution_percentage = 100
    sc.render.fps = 30
    sc.view_settings.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast", "AgX - Base Contrast", "None"):
        try:
            sc.view_settings.look = look; break
        except Exception:
            continue
    sc.view_settings.exposure = float(arg("--exposure", "0.0"))
    sc.render.use_persistent_data = True
    sc.render.threads_mode = "AUTO"

if __name__ == "__main__":
    build()
    out = arg("--out", ROOT + "/scene.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("SAVED", out, len(bpy.data.objects), "objects")
