import os as _os
ROOT = _os.environ.get("GIRIH_ROOT", _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bpy, sys
a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
spp = int(a[0]) if a else 32
thr = float(a[1]) if len(a) > 1 else 0.02
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 804, 100
sc.cycles.samples = spp
sc.cycles.adaptive_threshold = thr
sc.render.image_settings.file_format = "OPEN_EXR"
sc.render.image_settings.color_depth = "16"
sc.render.image_settings.exr_codec = "PIZ"
sc.render.filepath = ROOT + "/render/f_####"
sc.render.use_overwrite = False
sc.render.use_placeholder = True
print("FINAL SETUP spp", spp, "thr", thr)
