# girih: the story starts here

<p align="center"><b>داستان از اینجا شروع شد</b> · a 22-second slow-motion film made entirely in code</p>

A dark room, sunlight through a Persian *girih* stained-glass window, coloured god-rays in the dust.
A steel ball breaks through. Time slows to 1/150, then almost stops (1/4000); the camera flies through
the floating glass while each piece carries the name of a project.

**Watch:** https://alzhmd.github.io · **Download:** see [Releases](https://github.com/alzhmd/alzhmd/releases/latest)

## How it is made

| Stage | What happens | File |
|---|---|---|
| Pattern | 8-fold girih stars from **Hankin's method** on the 4.8.8 tiling, clipped to a pointed Persian arch and noded with Shapely (403 pieces). A warm *shamseh* (sun) medallion sits in a turquoise/lapis field. | `src/pattern.py`, `src/palette.py` |
| Scene | Blender (headless) builds the room, the 36 cm-deep wall, the walnut frame and every tile: a glass core inside a lead came. The haze is a homogeneous volume. Coloured beams are physical: shadow rays pass the thin glass tinted by its colour. | `src/build_scene.py` |
| Physics | Every tile is a free rigid body: ballistic flight, constant spin and gravity, released by a fracture front spreading from the impact point. The central star is Voronoi-fractured into shards and glass dust. | `src/animate.py` |
| Time | A smooth speed ramp maps screen time to physics time: 1/45 → 1/150 at the impact → 1/4000 (bullet time) → 1/700. Every frame is rendered; nothing is interpolated. | `src/animate.py` |
| Render | Cycles path tracing, 1920×804 (2.39:1), 30 fps, motion blur, OpenImageDenoise, linear EXR. | `render.sh` |
| Post | Lens glare and vignette in linear light, Blender's AgX view (OCIO), labels tracked to the flying tiles, film grain. | `src/post.py`, `src/titles.py`, `src/anchors.py` |
| Sound | Fully synthesised: sub impact, modal glass resonances slowed down with a tape-stop, and a Karplus-Strong **santur** playing Dastgah-e Shur (with the *koron* quarter-tone), one note per project. | `src/sound.py` |

## Reproduce

Needs Blender 5.2 and Python 3.12 or newer with `numpy scipy shapely pillow opencolorio OpenEXR opencv-python-headless soundfile pyloudnorm`.

```bash
python src/pattern.py                       # writes window.json
blender -b -P src/build_scene.py -- --out scene.blend
blender -b scene.blend -P src/animate.py -- --out anim.blend
blender -b anim.blend -P src/anchors.py     # label tracking data
./render.sh                                  # 660 frames, about 11 h on 8 CPU cores
python src/sound.py && python src/post.py 1 660
```

## Credits

- Sky: [Symmetrical Garden 02](https://polyhaven.com/a/symmetrical_garden_02) HDRI, Poly Haven (CC0)
- Fonts: [Vazirmatn](https://github.com/rastikerdar/vazirmatn) and [Inter](https://github.com/rsms/inter) (SIL OFL)

Code: MIT. Film: © alzhmd.
