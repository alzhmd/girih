"""Post: linear EXR -> lens glow + vignette -> AgX (Blender's OCIO config) -> titles -> grain -> 16-bit PNG.

python post.py <first> <last> [--preview] [--clean]
"""
import os as _os
ROOT = _os.environ.get("GIRIH_ROOT", _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import sys, os, math
import numpy as np
import OpenEXR, cv2
import PyOpenColorIO as ocio
from scipy.ndimage import gaussian_filter

sys.path.insert(0, ROOT + "/src")
import titles

FPS = 30
NF = 660
W, H = 1920, 804
SRC = ROOT + "/render/f_{:04d}.exr"
OUT = ROOT + "/post/{}/p_{:04d}.png"
CFG = _os.environ.get("BLENDER_OCIO", ROOT + "/blender/5.2/datafiles/colormanagement/config.ocio")

_proc = None
def agx():
    global _proc
    if _proc is None:
        cfg = ocio.Config.CreateFromFile(CFG)
        vp = ocio.LegacyViewingPipeline()
        vp.setDisplayViewTransform(ocio.DisplayViewTransform(src="Linear Rec.709", display="sRGB", view="AgX"))
        vp.setLooksOverride("AgX - Medium High Contrast")
        vp.setLooksOverrideEnabled(True)
        _proc = vp.getProcessor(cfg).getDefaultCPUProcessor()
    return _proc

def read_exr(path):
    ch = OpenEXR.File(path).channels()
    px = ch["RGBA"].pixels if "RGBA" in ch else np.dstack([ch[c].pixels for c in "RGB"])
    return np.ascontiguousarray(px[..., :3].astype(np.float32))

def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)

def glow(img):
    """Lens veiling glare: wide multi-scale blur, energy conserving mix (pure optics, no threshold)."""
    small = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    acc = np.zeros_like(img)
    for sig, w in ((1.5, 0.30), (5.0, 0.30), (14.0, 0.25), (36.0, 0.15)):
        b = np.dstack([gaussian_filter(small[..., c], sig, mode="nearest") for c in range(3)])
        acc += w * cv2.resize(b, (W, H), interpolation=cv2.INTER_LINEAR)
    near = np.dstack([gaussian_filter(img[..., c], 2.0, mode="nearest") for c in range(3)])
    return 0.90 * img + 0.035 * near + 0.065 * acc

_vig = None
def vignette():
    global _vig
    if _vig is None:
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.hypot((x - W / 2) / (W / 2), (y - H / 2) / (W / 2)) / math.hypot(1, H / W)
        _vig = (1.0 - 0.20 * r ** 2.2)[..., None]
    return _vig

def grain(shape, seed, strength=0.011):
    rng = np.random.default_rng(seed)
    g = rng.standard_normal(shape[:2]).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 0.65)
    g /= g.std() + 1e-6
    return g[..., None] * strength

def process(f, clean=False):
    s = (f - 1) / FPS
    lin = read_exr(SRC.format(f))
    lin = glow(lin) * vignette()
    fade_in = smooth(s / 1.4)
    lin *= fade_in
    disp = lin.copy()
    agx().applyRGB(disp)                         # in place, display-referred sRGB 0..1
    disp = np.clip(disp, 0.0, 1.0)
    # end: picture fades to black under the title
    fade_out = 1.0 - smooth((s - 20.6) / 1.2)
    disp *= fade_out
    if not clean:
        layer = titles.overlay(f)                # premultiplied RGBA float (H, W, 4) or None
        if layer is not None:
            a = layer[..., 3:4]
            disp = disp * (1 - a) + layer[..., :3]
    lum = disp.mean(axis=2, keepdims=True)
    disp = disp + grain(disp.shape, 7919 * f) * (0.55 + 0.45 * (1 - lum))
    return np.clip(disp, 0.0, 1.0)

def save16(path, rgb):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, cv2.cvtColor((rgb * 65535 + 0.5).astype(np.uint16), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_PNG_COMPRESSION, 1])

if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    clean = "--clean" in sys.argv
    kind = "clean" if clean else "titled"
    for f in range(a, b + 1):
        if not os.path.exists(SRC.format(f)) or os.path.getsize(SRC.format(f)) == 0:
            print("missing", f); continue
        rgb = process(f, clean)
        if "--preview" in sys.argv:
            os.makedirs(ROOT + "/out/post_prev", exist_ok=True)
            cv2.imwrite(f"{ROOT}/out/post_prev/{kind}_{f:04d}.jpg", cv2.cvtColor((rgb * 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
        else:
            save16(OUT.format(kind, f), rgb)
        print("done", f, flush=True)
