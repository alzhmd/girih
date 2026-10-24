"""Render a list of frames: blender -b f.blend -P frames.py -- outdir W H SPP f1,f2,..."""
import os as _os
ROOT = _os.environ.get("GIRIH_ROOT", _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bpy, sys, os
a = sys.argv[sys.argv.index("--") + 1:]
out, W, H, spp, fl = a[0], int(a[1]), int(a[2]), int(a[3]), a[4]
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.cycles.samples = spp
sc.render.image_settings.file_format = "PNG"
os.makedirs(out, exist_ok=True)
frames = []
for part in fl.split(","):
    if ":" in part:
        a0, a1, st = (int(x) for x in part.split(":"))
        frames += list(range(a0, a1 + 1, st))
    else:
        frames.append(int(part))
for f in frames:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, f"f{f:04d}.png")
    bpy.ops.render.render(write_still=True)
