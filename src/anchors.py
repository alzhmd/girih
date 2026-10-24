"""Project flying tiles + ball to screen for every frame (no rendering)."""
import os as _os
ROOT = _os.environ.get("GIRIH_ROOT", _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bpy, json
from bpy_extras.object_utils import world_to_camera_view
sc = bpy.context.scene
cam = sc.camera
out = {"frames": {}, "tiles": {}}
movers = [o for o in bpy.data.collections["Tiles"].objects if "t_rel" in o]
for o in movers:
    out["tiles"][o.name] = {"cls": o["cls"], "area": o["area"], "color": list(o.color)[:3]}
for f in range(1, sc.frame_end + 1):
    sc.frame_set(f)
    row = {}
    for o in movers + [bpy.data.objects["ball"]]:
        p = o.matrix_world.translation
        v = world_to_camera_view(sc, cam, p)
        row[o.name] = [round(v.x, 5), round(v.y, 5), round(v.z, 4)]
    out["frames"][f] = row
json.dump(out, open(ROOT + "/anchors.json", "w"))
print("anchors", len(movers), sc.frame_end)
