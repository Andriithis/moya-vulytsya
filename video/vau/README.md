# Рушій роликів «Вау» (ZAVDANNYA-127)

Новий рушій замість зразків ZAVDANNYA-94 (відгук Андрія — `docs/VIDEO-VIDHUK-2026-11-17.md`). Старий `video/rendery.py`
лишається як був; цей — окремо, у `video/vau/`.

## Що вміє

- **Карта як на сайті:** підкладка OpenFreeMap у тон «Індиго й м'ята» (темна й світла), українські назви вулиць і
  станцій метро (більші, ніж на сайті, — дивляться з телефона), 3D-будинки зблизька, межа Києва, **соти H3 у 3D** зі
  шкалою частками сайту (вершини — верхні 12 %, висота залежить від наближення).
- **Тисячі подій одночасно** — власний WebGL-шар (71 тис. точок без гальм): кожна подія «вискакує» з хвилею й спалахом,
  може вилетіти з центру соти («сота розпадається»), зникати за часом (година доби), кілька подій одного місця
  розкладаються «соняшником».
- **Камера-кіно:** ключові кадри з пом'якшенням, переліт «дугою» (зум відступає й повертається), нахил, розворот,
  поштовх і спалах на ударах.
- **Кінетичний текст:** гачок (слова «вбиваються» по одному), лічильники, що біжать, годинник, відлік 3-2-1, варіанти
  відповіді, стовпчики, картка з друкарською машинкою, кінцівка з кнопкою; затемнення під текстом вмикається само.
- **Макети сайту** (намальовані за `docs/STYL.md`, не знімки): пошук, сповіщення, панель вулиці, довідка, звіт ОСББ,
  канал Telegram.
- **Звук — свій:** 6 стилів музики (`puls`, `nich`, `napruha`, `hra`, `epik`, `lofi`) з «дропом» і обривом «зупинка плівки»,
  13 ефектів (поп, клік, тік, вжух, наростання, удар, бас, дзвін, сповіщення, друк, глітч, каса), голос Piper
  (безкоштовний, офлайн; голоси `mykyta`, `tetiana`, `lada`), музика тихішає під голосом, гучність ≈ −14 LUFS.
- **Будь-яка довжина** — 5…65 с (перевірка не пускає довше; довші — за потреби розширити).

## Як запустити

```bash
pip install playwright numpy scipy h3 pillow piper-tts imageio-ffmpeg && playwright install chromium
python video/vau/stsenarii.py <events.db> --koloda <koloda.json>          # → video/vyhid/kesh/stsenarii/*.json
python video/vau/rushii.py video/vyhid/kesh/stsenarii/*.json              # → video/vyhid/*.mp4, lehki/, arkushi/
python video/vau/rushii.py <сценарій.json> --kadry 1,4,8                  # лише знімки — швидка перевірка
python video/vau/sluhaty.py video/vyhid/<id>.mp4 --holos                  # гучність кожні 0,5 с + що каже голос
```

Модель голосу: `~/.cache/mv-holosy/uk_UA-ukrainian_tts-medium.onnx` (+ `.onnx.json`) з
`huggingface.co/rhasspy/piper-voices` (`uk/uk_UA/ukrainian_tts/medium/`). Відеокарта не обов'язкова (`--cpu` —
SwiftShader), але з нею кадр ≈ 0,4 с замість кількох секунд.

## Файли

| Файл | Що робить |
|---|---|
| `dani.py` | події з випуску з правилами (без НАС і чутливих, вулиця без номера), соти H3, кольори груп |
| `stsenarii.py` | 23 сценарії-функції `r_NN` — числа з бази в момент збирання; клас `Rolyk` — доріжки |
| `perevirka.py` | заборонені слова, сліди знеособлення, номер житлового будинку, Київ, кінцівка-посилання |
| `stsena.html/.js/.css` | сцена 1080×1920: `window.kadr(t)` малює кадр |
| `rushii.py` | рендер: кадри → ffmpeg, звук, легка копія ≤ 3 МБ, аркуш кадрів кожні 0,5 с |
| `zvuk.py`, `holos_tekst.py` | музика, ефекти, голос; текст для голосу (числа словами, лише відомі моделі літери) |
| `sluhaty.py`, `montazh.py`, `zshyty.py`, `perehliad.sh` | перевірка звуку й кадрів очима |

## Межі (вшиті в код, не в сценарії)

Подія ≠ проблема — жодних причин, рейтингів небезпеки, прогнозів і порад; номер будинку — лише публічних місць
(`meta['publichni']`); насильство, статеві справи й щодо дітей у ролики не йдуть; колір — вид події, жодного червоного;
кожен ролик закінчується посиланням на конкретне місце (`meta['kudy']`) або є обривом із продовженням.
Великі файли (`video/vyhid/`) — не в git.

## ZAVDANNYA-129: правила монтажу, нові типи, запис сайту, платний голос

```bash
video/vau/zb129.sh [--lyshe t1,n3]                                          # сценарії 129 → video/vyhid/kesh/stsenarii/129-*.json
python video/vau/rushii.py video/vyhid/kesh/stsenarii/129-*.json --vykhid video/vyhid/129
python site/zibraty_sait.py <events.db> video/vyhid/sait --koloda …          # сайт з того самого випуску (для запису екрана)
python video/vau/zapys_saitu.py video/vyhid/sait [--lyshe z1]               # запис екрана справжнього сайту
python video/vau/sluhaty.py video/vyhid/129/<id>.mp4 --stsenarii video/vyhid/kesh/stsenarii/   # С11: голос ↔ текст
video/vau/montazh_kadriv.sh <префікс id> [ширина]                            # знімки --kadry → один рядок для перегляду
```

- `stsenarii129.py` — топ-5 (t1–t5) і нові типи (n1–n8); `zapys_saitu.py` — записи сайту (z1, z2).
- `perevirka.py` з `meta['pravyla'] = 129` не пропускає: кінцівку довше 1 с і нерухому картку (С1), гачок не з кадру 0 (С2),
  паузу без нового довше 2 с і переказ по букві (С4), < 3 компонувань (С6), світлу тему (С7), захисну фразу довше 1,5 с (С8),
  лічильник без узгодження (С10), камеру ближче z 15,3 біля житла і номер рішення в ролику не з однією подією (MV-151).
- Голос: `MV_HOLOS=elevenlabs|azure|teka` + ключ у `MV_HOLOS_KLUCH` (лише змінна середовища) — `holos_servis.py`; без них — Piper.

## ZAVDANNYA-134: «мурашник» (В1) — параметр `styl_sot`

Причина: соти вставлялися «перед першим підписом», а в стилях OpenFreeMap перший підпис — назва води, що йде **до** будинків
і доріг. Тож дороги малювалися **поверх** сот і «їли» заливку. У `R.soty(…, styl_sot=…)`:
`'sait'` — над дорогами, як на сайті; `'sklo'` — рівна напівпрозорість, дороги й будинки приглушені; `'plytka'` — суцільна
мозаїка зі швами кольору тла, дороги й назви вулиць під сотами сховані. Без параметра — як було. Знімки до/після —
`docs/rolyky-v1/`, порада — `docs/ROLYKY-SYSTEMA.md`, розд. 3.

## ZAVDANNYA-138: стилі на вибір, світла тема, адреси, нові типи, пачка тижня

```bash
python video/vau/stsenarii138.py <events.db> --koloda <koloda.json>          # 13 сценаріїв → video/vyhid/kesh/stsenarii/138-*.json
python video/vau/stsenarii138.py <events.db> --pachka                        # лише перевірка чергування пачки (В2)
python video/vau/rushii.py video/vyhid/kesh/stsenarii/138-*.json --vykhid video/vyhid/138 [--cpu]
python video/vau/zapys_saitu.py video/vyhid/sait --lyshe z3 --vykhid video/vyhid/138 [--cpu]   # «POV: застава завтра»
```

- **Вигляди — реєстр, не типовий стиль.** `stsena.js`: `VAU.temy` (тема = основа темна/світла + кольори),
  `VAU.styliSot` (`sait` — напівпрозорі над дорогами, як на сайті; `plytka`; `stovpchyky` — кожна сота стовпчиком за числом,
  крізь них видно вулиці; `stovpchyky_shchilno`; `sklo`), `VAU.styliAdres` (`kola`, `kiltsia`, `svitni`). Свої вигляди
  (ZAVDANNYA-139) — окремим файлом у `S.moduli`: він лише дописує записи в реєстр, рушій не переписується.
- **Правила 138** (`meta['pravyla'] = 138`): стиль сот — лише явний (`styl_sot`), шар ролика названо (`meta['shar']`:
  soty · adresy · tochky · zvit · zapys · ne_karta), в адресах лише число подій; С7 «лише темна» прибрано (MV-158).
- **Точки й межа міста — над дорогами** (`S.nad_dorohamy`, MV-161).
- **Шар адрес** (`R.adresy(…)`): місце → число подій, як карта підписника; номерів будинків немає (MV-25).
- **Поділений екран** (`R.druha(R2, kordon)`, `S.druha.os` 'x' або 'y'): друга сцена зі своєю темою в рамці.
- **Календар року** (`styl: 'kalendar'`), гра без жодних назв на карті (`S.bez_pidpysiv`), без 3D-будинків (`S.bez_3d`).
- **В2:** `perevirka.osi(S, meta)` — тема, шар, рівень наближення; `pereviryty_pachku` — два ролики поспіль різні
  щонайменше за двома осями. Порядок пачки — `PACHKA` у `stsenarii138.py`.

## ZAVDANNYA-139: візуальна лабораторія — теми й вигляди (`tema`, `styl`)

Окремий модуль `vyhliady139.js` + `vyhliady139.css` (сцена вантажить його перед `stsena.js`; у `stsena.js` — лише три гачки:
теми додаються до `KOL`, `dodaty(api)` після шарів карти, `kadr(t)` щокадру). Сценарій без `styl` і з темою `temna`/`svitla`
малюється як раніше.

- **Теми** (`tema`): `nich` (нічне місто), `papir` (папір і чорнило), `vechir` (тепла вечірня), `sontse` (контраст для сонця),
  `monokhrom` (сіре + м'ятний акцент). Кожна має `osnova` — темна чи світла підкладка й стилі тексту.
- **Вигляди** (`styl: [{typ, …}]`): соти — `sklo_kraia`, `neon`, `dykhannia`, `stovpy` (`skliani`, `rist`, `lyshe_vershyny`);
  адреси — `svitni`, `teplo`, `shpyli`, `sonyashnyk`, `khvyli`, `bulbashky` (місце = координата + число, без адреси);
  не карта — `infografika`, `hodynnyk`, `kalendar`, `kartka_zvit`. Наявні `styl_sot` (`sait`, `plytka`) — як були.

```bash
python video/vau/laboratoriia139.py <events.db>                         # 24 вигляди → video/vyhid/kesh/stsenarii/139-*.json
python video/vau/rushii.py video/vyhid/kesh/stsenarii/139-*-temna.json --bez-zvuku --vykhid video/vyhid/139   # кліпи 5 с
python video/vau/rushii.py <сценарій> --kadry 3.6 --vykhid video/vyhid/139                               # кадр
python video/vau/zapys139.py video/vyhid/sait [--tema svitla]           # справжня карта сайту на весь кадр, 3D, рух камери
python video/vau/galereia139.py                                         # → video/vyhid/galereia-139/index.html
```

Що з цього радимо для тесту — `ZVIT-139.md`.
