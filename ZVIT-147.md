# ЗВІТ-147 — Незалежний критик: шлях покупця на пробних даних (чернетка, пишеться)

## Крок 1. Що зібрано (хмара, 19.11.2026)

- Пробний випуск `vypusk-2026-11-08` з Release `dani-edrsr`: `events-2026-11-08.db`, `koloda-2026-11-08.json`.
- Будинки — `dani-edrsr/src/budynky_sait.py` на тому самому випуску + скарги 1551 (гілка `dani-1551`): 19 817 будинків.
- «Судова практика» — **штучне зведення з тестів** (`tests/test_sudova_praktyka.py`, 3 статті): справжнього файла в хмарі немає.
- Сайт: `site/zibraty_sait.py … --khostynh workers --oplata tak --platizhnyi-servis test` (≈ 4 хв, 5 976 файлів).
- Сервер продажу: `node site/worker/testy/mistsevyi.mjs 8799 <сайт>` — справжній код Workers, тестова оплата, листи в журнал.
- Для довідок після оплати — видавач `site/prodazh/vydavach.py` зі справжнім генератором, OSM — вирізка BBBike (19.11).
