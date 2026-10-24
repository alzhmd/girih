#!/bin/bash
# opening + window (haze-heavy) at higher quality, the rest at 32 spp; resumable (existing frames are skipped)
cd "$(dirname "$0")"
nice -n 5 blender -b render_master.blend -P src/final_setup.py -s 1 -e 110 -a -- 64 0.012
nice -n 5 blender -b render_master.blend -P src/final_setup.py -s 111 -e 660 -a -- 32 0.02
echo RENDER-DONE
