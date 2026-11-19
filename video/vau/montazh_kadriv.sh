#!/usr/bin/env bash
# Знімки video/vyhid/znimky/<id>-*.png → один рядок зменшених кадрів (для перегляду очима). Аргумент — префікс id.
cd "$(dirname "$0")/../../video/vyhid/znimky"
FF=$(python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
fs=($(ls "$1"*.png | sort)); n=${#fs[@]}; args=(); f=""
for i in "${!fs[@]}"; do args+=(-i "${fs[$i]}"); f+="[$i]scale=${2:-300}:-1[v$i];"; done
for i in "${!fs[@]}"; do f+="[v$i]"; done
"$FF" -y -loglevel error "${args[@]}" -filter_complex "${f}hstack=$n" "../montazh-$1.jpg"
echo video/vyhid/montazh-$1.jpg
