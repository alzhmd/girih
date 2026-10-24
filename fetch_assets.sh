#!/bin/bash
# Fonts (SIL OFL) and the CC0 sky used by the film.
set -e
cd "$(dirname "$0")"
mkdir -p fonts assets
curl -sSL -o /tmp/vz.zip https://github.com/rastikerdar/vazirmatn/releases/download/v33.003/vazirmatn-v33.003.zip
curl -sSL -o /tmp/inter.zip https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip
unzip -qo -j /tmp/vz.zip 'fonts/ttf/Vazirmatn-*.ttf' -d fonts
unzip -qo -j /tmp/inter.zip 'extras/ttf/Inter*.ttf' -d fonts
curl -sSL -o assets/symmetrical_garden_02_4k.exr https://dl.polyhaven.org/file/ph-assets/HDRIs/exr/4k/symmetrical_garden_02_4k.exr
echo ok
