# ZVIT-67. Прибирання ПК і GitHub (доробка ZAVDANNYA-54)

Виконавець — Claude Code на ПК Андрія. 16.11.2026.

## Коротко

- **GitHub:** видалено 31 гілку в `moya-vulytsya` і 26 у `dani-edrsr` — сам, правило безпеки цього разу не заблокувало,
  команди Андрію не потрібні. Лишились: `moya-vulytsya` — `main`, `maket-m7`; `dani-edrsr` — `main`, `ispyt`, `server-stan`, `dani-1551`.
  З гілкою `maket-m1` GitHub закрив старий відкритий PR #30 (вміст є в `maket-m7`).
- **ПК:** видалено 5 старих робочих копій (≈ 300 МБ разом із тимчасовими файлами в них), 25 злитих локальних гілок,
  ≈ 450 МБ у `moya-vulytsya\tmp\` (було 471 МБ, лишилось 22 МБ). `dani-edrsr\data\` не чіпав (перевірено: 254 записи на місці).
- **Що лишилось поза `main`:** лише гілка `maket-m7` (сторінки макетів М1–М7, звіти й оцінки макетів) — не видаляв.
- `docs/08-stan.md` виправлено (рядки 4, 4д, 4е, 4є); у `docs/MAKET-M9.md` — позначка, що клікабельні сторінки M9 видалено.

## 1. Віддалені гілки GitHub — видалено (перелік складено до видалення)

Перевірка 16.11 після `git fetch --prune`: для кожної гілки — чи вона вже в історії `main`, і чи злиття її
в `main` (`git merge-tree`) не дає нічого нового. Для гілок, злитих «одним комітом» (squash), різниця лишалась лише там,
де `main` уже пішов далі (новіші записи MV, новіші рядки стану) — тобто їхній вміст у `main` є.

### `moya-vulytsya` — видалити (31)

| Гілка | Чому |
|---|---|
| `borh-mv49`, `mv-48`, `mv-50`, `mv-52`, `mv-54`, `mv-55`, `pravyla-8`, `prybraty-27`, `stan-vyhliad` | злита (усі коміти в `main`) |
| `zavdannya-26`, `zavdannya-26b`, `zavdannya-27`, `zavdannya-28`, `zavdannya-54` | злита |
| `zavdannya-45` (сайт у вигляді М7) | злита — у `main` є |
| `zavdannya-60` (макет M9) | злита — у `main` є (`docs/MAKET-M9.md`) |
| `zavdannya-63` (дослідження звіту) | злита — у `main` є |
| `zavdannya-64` (оформлення звіту) | злита через squash (PR #70); залишок — лише старіші версії рядків `AGENTS.md`, `RISHENNYA.md`, `08-stan.md`, які в `main` уже новіші |
| `claude/eager-cray-b0jfrj`, `claude/great-johnson-um287f`, `claude/zavdannya-26-completion-2sou6g`, `claude/zavdannya-27-completion-nep6ca`, `claude/zavdannya-47-weieh3`, `claude/zavdannya-50-689468`, `claude/zavdannya-51-i9xh0h` | злита |
| `claude/happy-mccarthy-wnfmnr` | замінена: хмарна чернетка ZVIT-54, у `main` — версія з ПК |
| `maket-m1`, `maket-m3`, `maket-m4`, `maket-m5`, `maket-m6` | замінені: кожен коміт цих гілок є в `maket-m7` (послідовний ланцюжок М1→М7). **Увага:** з `maket-m1` закриється старий відкритий PR #30 «Макет М1» |

### `moya-vulytsya` — лишити

- `main`.
- **`maket-m7` — не в `main`.** Поза `main` лише в цій гілці (і в її предках М1–М6): сторінки макетів
  `maket/m1`, `maket/m4`, `maket/m5`, `maket/m6`, `maket/m7` зі шрифтами й скриптами знімків, тести
  `tests/test_maket_m1.py`, `test_maket_m4.py`…, знімки `znimky/m1…`, звіти `ZVIT-M1`, `ZVIT-M3`, `ZVIT-28`, `ZVIT-32`,
  `ZVIT-36`, `ZVIT-42`, `docs/OTSINKA-M5.md`, `docs/OTSINKA-M7.md`, `docs/NASTRII-M7.md`. Сам сайт у вигляді М7 —
  у `main` (`zavdannya-45`), тож гілка — лише історія макетів.

### `dani-edrsr` — видалити (26)

| Гілка | Чому |
|---|---|
| `ccr-762a9487-0oi3oe`, `mv-48`, `zavdannya-22`, `-23`, `-24`, `-29`, `-30`, `-31`, `-34`, `-35`, `-37`, `-38`, `-39`, `-41`, `-44` | злита |
| `claude/admiring-brown-67iwc1`, `claude/gallant-cray-aqtr3g`, `claude/zavdannya-43-qsh1cd`, `claude/zavdannya-53-mctatp`, `claude/zavdannya-59-0xrk5x`, `claude/zavdannya-62-owvv2u` | злита |
| `claude/nice-meitner-oen12g` (ZAVDANNYA-55) | злита через squash (`b1dc936`); `ZVIT-55` потім свідомо прибрано з `main` |
| `zavdannya-57` | злита через squash (PR #49); `ZVIT-57` свідомо прибрано (`561a341`) |
| `claude/zavdannya-61-tp903u` | злита через squash (PR #51, MV-78) |
| `claude/zavdannya-65-a9bz62` | злита через squash (PR #53, MV-81) |
| `claude/bold-planck-4jw8j3` (ZAVDANNYA-66) | злита через squash (PR #52, MV-80) |

Залишок різниці в цих squash-гілках — лише рядки, яких у них ще не було (новіші MV і тести в `main`).

### `dani-edrsr` — лишити

`main`, `ispyt`, `server-stan`, `dani-1551` (за завданням).

### `karta-kyiv` (репозиторій `karta-kyiv-kod`) — не чіпав (за межами завдання).

## 2. ПК

### Робочі копії

| Репозиторій | Робоча копія | Що в ній було | Чи збережено вміст |
|---|---|---|---|
| `moya-vulytsya` | `zavdannya-28-0c2226` (гілка `maket-m4`) | 93 МБ, у т. ч. `tmp\` 29 МБ знімків М4 | коміти — у `maket-m7` |
| `moya-vulytsya` | `zavdannya-63-eed105` | 14 МБ | коміт у `main` |
| `moya-vulytsya` | `zavdannya-64-b85a1e` | 23 МБ, `tmp\zvit-v64\` | злито squash; `tmp\zvit-v64\` — точна копія тієї, що лишилась у головній теці |
| `dani-edrsr` | `zavdannya-41-d4f341` | 9 МБ | коміт у `main` |
| `dani-edrsr` | `zavdannya-44-3f24ac` | 158 МБ, з них `data\` 147 МБ — проміжні файли OSM (`osm_risks_raw_pbf.json` тощо), які `perevirka/diahnostyka.py` сам створює знову | коміт ZAVDANNYA-57 злито squash (PR #49) |

У `zavdannya-44` в `data\` були **посилання** на справжні `dani-edrsr\data\osm`, `server`, `teksty-arkhiv` — спершу
прибрав самі посилання, потім робочу копію; оригінали цілі. `git worktree prune` — в обох.

**Не вдалося:** порожня тека `moya-vulytsya\.claude\worktrees\zavdannya-64-b85a1e` — її тримає запущений сервер
`python -m http.server 8765` (процес 17500). Сервер не зупиняв: можливо, Андрій ним користується. Файлів у теці вже
немає. Після зупинки сервера — видалити теку вручну.

### Локальні гілки (25)

- `moya-vulytsya` (12): `claude/zavdannya-54-b9cef7`, `claude/zavdannya-63-eed105`, `claude/zavdannya-64-b85a1e`,
  `zavdannya-54`, `zavdannya-60`, `zavdannya-63`, `zavdannya-64` — злиті; `maket-m1`, `-m3`, `-m4`, `-m5`, `-m6` — є в `maket-m7`.
- `dani-edrsr` (13): `claude/zavdannya-41-d4f341`, `claude/zavdannya-57-0e803c`, `codex/editor-pilot-recovery`,
  `etalon-mv45`, `zavdannya-15`, `-15b`, `-22`, `-29`, `-34`, `-41`, `-44`, `zvit-09` — злиті; `zavdannya-57` — злито squash.

**Лишив (не злиті в `main`, завдання їх не називає):** у `moya-vulytsya` — 10 гілок `codex/*` (26–29.09) і
`zberezhennya-2026-10-08`, `maket-m7`; у `dani-edrsr` — 11 гілок `codex/*` (27–29.09), `zavdannya-03`, `ispyt`. Гілки
`codex/*` і `zavdannya-03`, `zberezhennya-2026-10-08` — старі, на GitHub їх уже немає; якщо не потрібні — видалити окремим «так».

### `moya-vulytsya\tmp\` — було 471 МБ, стало 22 МБ

| Видалено | Розмір |
|---|---|
| 66 файлів у корені `tmp\` (старі скрипти `*.py` і нотатки codex `0006…0008-*.md`, вересень) | 0,5 МБ |
| `maket-m9\` (клікабельний макет M9; знімки лишились у `docs/znimky-m9/`) | 38 МБ |
| `sait-m8\` (зібраний сайт; сам сайт — у `main`, `site/`) | 38 МБ |
| `znimky\m5\`, `m6\`, `m7\` | 93 + 73 + 155 МБ |
| `znimky\kyiv_*`, `m1_*`, `m3_*` (96 знімків) і `znimky\opys.md` (опис саме цих знімків) | 55 МБ |
| **Разом** | **≈ 452 МБ** |

Лишилось: `tmp\zvit-v64\` (1,6 МБ, MV-79) і `tmp\znimky\m8\` (21 МБ).

### `dani-edrsr`

Тимчасових тек поза `data\` немає; робочі копії — див. вище; порожню теку `.claude\worktrees` прибрано. `data\` не чіпав.

### `D:\problem_orienting`

Лише `karta-kyiv`, `dani-edrsr`, `moya-vulytsya`. `karta-kyiv` не змінював.

## 3. Що лишилось і чому

- `maket-m7` на GitHub і локально — у `main` немає сторінок макетів і звітів М1–М7 (перелік у розділі 1).
- `moya-vulytsya\private\` (106 МБ, аудити codex з вересня–жовтня, у git не йде) — завдання не називає, лишив
  (так само відзначено в ZVIT-54). Видалити — окремим «так».
- Головна тека `dani-edrsr` стоїть на старому `main` (відстає на 65 комітів, змін немає) — не оновлював, бо це не
  прибирання; `git pull` там безпечний.
- Тека `zavdannya-64-b85a1e` (порожня) — тримає сервер на порту 8765.
- **Моя робоча копія** `.claude\worktrees\kyiv-map-screenshots-5b73db` (гілка `claude/zavdannya-67-115dc9`) — лишається
  до злиття PR цього звіту; потім `git worktree remove` з головної теки й видалити гілку.
