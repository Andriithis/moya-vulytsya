# ZVIT-67. Прибирання ПК і GitHub (доробка ZAVDANNYA-54)

Виконавець — Claude Code на ПК Андрія. 16.11.2026. **Чернетка — пишеться по кроках.**

## 1. Віддалені гілки GitHub — перелік перед видаленням

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
