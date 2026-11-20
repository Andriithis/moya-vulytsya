# ЗВІТ-167 — Критик: довідка, повний звіт, кабінет, ОСББ і рієлтор

Хмара, 20.11.2026. Незалежний критик: цю частину не робив. Код не змінював — лише звіт і знімки (`docs/znimky-167/`).

> Чернетка: заповнюється по кроках.

## Як перевіряв

- Пробний випуск `vypusk-2026-11-08` з Release `dani-edrsr` (`events-2026-11-08.db`, `koloda-2026-11-08.json`).
- Будинки — `dani-edrsr/src/budynky_sait.py` + скарги 1551 (гілка `dani-1551`, по 2026-10): 19 817 будинків.
- Сайт: `site/zibraty_sait.py … --khostynh workers --oplata tak --platizhnyi-servis test` (5 950 файлів).
- Сервер продажу: `node site/worker/testy/mistsevyi.mjs 8799 <сайт>` — справжній код Workers, тестова оплата, листи — у журнал.
- Довідки — видавач `site/prodazh/vydavach.py` зі справжнім генератором `dani-edrsr/src/zvit/`, карта — вирізка OSM BBBike від 14.11.2026.
