#!/usr/bin/env bash
# Нічний рендер усіх сценаріїв двома потоками (відеокарта тягне два браузери). Лог — video/vyhid/log-render.txt.
#   video/vau/vse.sh            — усі;   video/vau/vse.sh 05 07  — лише ці
cd "$(dirname "$0")/../.."
if [ $# -gt 0 ]; then
  fs=(); for n in "$@"; do fs+=(video/vyhid/kesh/stsenarii/${n}-*.json); done
else
  fs=(video/vyhid/kesh/stsenarii/[0-9]*.json)
fi
a=(); b=(); i=0
for f in "${fs[@]}"; do if (( i % 2 == 0 )); then a+=("$f"); else b+=("$f"); fi; i=$((i+1)); done
log=video/vyhid/log-render.txt
echo "старт $(date +%H:%M) — ${#fs[@]} роликів" >> "$log"
[ ${#a[@]} -gt 0 ] && PYTHONIOENCODING=utf-8 python video/vau/rushii.py "${a[@]}" >> "$log" 2>&1 &
[ ${#b[@]} -gt 0 ] && PYTHONIOENCODING=utf-8 python video/vau/rushii.py "${b[@]}" >> "$log" 2>&1 &
wait
echo "кінець $(date +%H:%M)" >> "$log"
