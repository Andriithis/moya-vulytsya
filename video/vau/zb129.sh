#!/usr/bin/env bash
# Збирання сценаріїв ZAVDANNYA-129 з випуску на ПК (шляхи dani-edrsr — поруч). Аргумент — --lyshe t1,n3 (необов'язково).
cd "$(dirname "$0")/../.."
DE=../dani-edrsr
PYTHONIOENCODING=utf-8 python video/vau/stsenarii129.py "$DE/data/zolota-zbirka/vykhid/events-2026-11-08.db" \
  --koloda "$DE/data/koloda/koloda-2026-11-08.json" --dani-1551 "$DE/docs/1551-DLIA-ZVITU.md" "$@"
