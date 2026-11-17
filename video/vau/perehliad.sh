#!/usr/bin/env bash
# Швидкий перегляд: перезібрати сценарії й зняти кадри. Використання: video/vau/perehliad.sh 01,09 "1,4,8,12"
# Шлях до випуску — MV_VYPUSK (за замовчуванням — сусідній dani-edrsr).
set +e
cd "$(dirname "$0")/../.."
DB="${MV_VYPUSK:-../../../../dani-edrsr/data/zolota-zbirka/vykhid/events-2026-11-08.db}"
[ -f "$DB" ] || DB="D:/problem_orienting/dani-edrsr/data/zolota-zbirka/vykhid/events-2026-11-08.db"
KOL="$(dirname "$DB")/../../koloda/koloda-2026-11-08.json"
[ -n "$BEZ_ZBORU" ] || PYTHONIOENCODING=utf-8 python video/vau/stsenarii.py "$DB" --koloda "$KOL" --lyshe "$1" >/dev/null
for n in ${1//,/ }; do
  f=$(ls video/vyhid/kesh/stsenarii/${n}-*.json)
  python video/vau/rushii.py "$f" --kadry "$2"
  id=$(basename "$f" .json)
  python video/vau/montazh.py "video/vyhid/znimky/m-$n.jpg" $(for t in ${2//,/ }; do printf "video/vyhid/znimky/%s-%05.2f.png " "$id" "$t"; done)
done
