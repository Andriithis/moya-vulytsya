# ЗВІТ-162 — Чистка й когерентність: код, файли, документи

Виконавець — хмара, 20.11.2026. Гілка `claude/zealous-fermi-02mgl3` в обох репозиторіях. Нічого не опубліковано, Release
не чіпав, ключів не додавав.

## Коротко

- **Документи звірено з рішеннями до MV-174** — виправлено 17 файлів у продукті й 2 у конвеєрі (старі ціни 599, «компаніям
  на рік», PostgreSQL/Supabase, оплата в Android, ліміт трьох виконавців, тижневий розклад роликів тощо). Аркуш стану
  `docs/08-stan.md` стиснуто з 77 КБ до ≈ 12 КБ — лише «що зараз і що далі».
- **Видалено замінене й мертве:** старий рушій роликів (ZAVDANNYA-11), прототип звіту `zvit_adresy/` (ZAVDANNYA-69), дубль
  скрипта знімків, три модулі конвеєра, які ніде не викликались. Звіти 54 і 107 — з кореня в `docs/`.
- **Тести зелені:** продукт — 592 тести, 1 пропущено з причиною; конвеєр — `check_build` «усе гаразд». Знайшов і виправив
  тест конвеєра, який ніде не запускався й уже падав.
- **Гілки:** з хмари видалити не можна (GitHub відповідає 403 — так і записано в `YAK-PRATSIUIEMO.md`). Злитих гілок без
  нових комітів — **73 у `moya-vulytsya` і 38 у `dani-edrsr`**; готові команди — нижче (може виконати ZAVDANNYA-163 на ПК).
- **Дублів номерів правил S- немає** (78 правил у специфікації; незлиті 137 і 157 беруть вільні S-В.19, S-В.20, S-Д.14).

## 1. Документи ↔ рішення

| Файл | Що було не так | Як тепер |
|---|---|---|
| `AGENTS.md` | компаніям — «на рік»; технології — PostgreSQL з плану передачі; «до налаштування сервера нічого не качаємо»; результат суду — виняток лише для роликів | на місяць або рік (MV-92); Cloudflare Workers, D1, R2 (MV-105, MV-157, MV-159); сервер качає з 10.11; і «Судова практика» (MV-122) |
| `README.md` | ціни без пакета й підписки з довідкою; «що де лежить» без сервера продажу, Android, автопостингу, листа | за MV-100/MV-136; додано теки |
| `docs/STRUKTURA.md` | звіт 599 (MV-70), підписка «звіти по 199», оплата в Google Play, «проблем мало без аналітика», сервер «щотижневі оновлення», етапи з 09.11 | таблиця продуктів за MV-99…MV-170 (199 · 449 · 299 · 399 · 799 · 1 490, «Судова практика», компанії — місяць/рік); проблеми й скупчення (MV-162, MV-163); застосунок без продажу (MV-126, MV-166); сервер — лише тексти (MV-153); етапи до продажу |
| `docs/KOMPAS.md` | судді — «після висновку юриста»; тижневий розклад груп роликів; «Гра «Де це було?»»; Android «план» | юриста не буде — лише рішення Андрія (MV-152); розклад — за MV-161 і `ROLYKY-TYPY.md`; ігри в карті; Android без продажу |
| `docs/ROLYKY-TYPY.md` | 8 типів 138 — «ідея, зараз»; В2–В4 «не виконано»; В8 «чекає»; В9 — без підсумку | прийнято (MV-168); зроблено в рушії (138); kNN-VC і «Голос змінено програмою» (MV-171); 25 виглядів, 8 у тест (MV-166). Рядки 155 («після справжніх продуктів») не чіпав |
| `docs/SPYSOK-DLIA-MYKYTY.md` | оплата в застосунку — «рішення разом з Андрієм»; примітка про неіснуючу гілку | вирішено: не продає (MV-126, MV-166, MV-173); примітку прибрано |
| `docs/AKAUNTY-PAKET.md` | перші ролики «після перемонтажу з новим голосом» (MV-151) | пачка тижня 1 (MV-168), голос Андрія перетворений (MV-156, MV-171), 2 з 3 без голосу (MV-161) |
| `docs/08-stan.md` | 77 КБ, 45 рядків «Оновлено …», закриті пункти як відкриті, «заморожено до «так» на карту» (знято MV-91, MV-100) | один аркуш: у роботі · готово · далі · від Андрія · заморожено · борг коду (MV-37). Історія — коміт `f3f77d4` |
| `docs/05-model-danykh.md`, `docs/PRODAZH-SERVER.md`, `docs/SHCHO-DAIE-PARTNER.md` | база для платного й форми — Supabase | R2 (MV-159), форми — D1 (MV-157) |
| `video/holos/README.md`, `docs/STYL.md`, `video/vau/README.md`, `brend/hrupy.py`, `brend/zrobyty.py`, `video/soty.py` | «Голос згенеровано»; посилання на видалені файли; застарілі коментарі про чутливі (борг MV-34) | за MV-171, MV-102 |
| `dani-edrsr/CLAUDE.md` | «одночасно до трьох виконавців» | MV-160: скільки потрібно, двоє не працюють з одними файлами |
| `dani-edrsr/SPECYFIKATSIYA.md` | S-В.15 — нічна перевірка проблем як основна; S-М.6 — нічний аналітик | S-В.15 «уточнено MV-163» (основна — на ПК); S-М.6 «замінено MV-162, MV-163» |

## 2. Файли — що видалено й чому

| Що | Чому |
|---|---|
| `video/rendery.py`, `video/stsena.html`, `video/stsena.js`, `video/stsena.css` | старий рендер роликів ZAVDANNYA-11; ролики робить `video/vau/` (MV-158). Лишив `video/perevirka.py` (бере бот і автопостинг), `video/stsenarii/` (зразки для її тестів), `video/soty.py` і `video/dani/` (дані для `docs/rolyky-styli`) |
| `zvit_adresy/` (6 файлів) | прототип звіту ZAVDANNYA-69 з цінами 599/199/399; звіт і довідку робить генератор `dani-edrsr/src/zvit/` (MV-94, MV-136) |
| `tests/znimky_zahlushky_06.py` | дубль `tests/znimky_zahlushky.py` (той самий знімок для іншого завдання) |
| `dani-edrsr/src/reyestr_zbii.py` | запобіжник завантаження з карти Києва; ніде не імпортується, тексти качає `src/zavantazhennia.py` |
| `dani-edrsr/src/zolota_perevirka.py` | звірка з живою картою Києва; ніде не викликається |
| `dani-edrsr/src/test_determinizm.py` | ручна перевірка правила карти S-Р.11, якого в нашій специфікації немає; ніде не викликається |

Перенесено: `ZVIT-54.md`, `ZVIT-107.md` → `docs/`. Тести, що згадували видалене, оновлено (`test_video`, `test_vyhliad_mv58` —
шрифти й старі кольори тепер перевіряються в `video/vau/`, `test_hasla`, `test_hrupy`).
`.gitignore` конвеєра: додано винятки для трьох еталонів `*.jsonl`, які вже лежать у git. Великих файлів у git немає:
найбільші — знімки екрана в `docs/znimky-*` (до 1,9 МБ кожен), усі на них посилаються звіти.

## 3. Гілки на GitHub

**З хмари видалити не можна** (GitHub: 403). Порахував так: гілка видаляється, лише якщо її верх **дорівнює** верху злитого
PR (тобто після злиття в неї нічого не дописували). Команда нижче ще раз це перевіряє: якщо гілку хтось оновив, GitHub
відмовить саме для неї, решту видалить.

**Лишаються:** `main`, `server-stan`, `ispyt`; гілки переглядів `rolyky-*`, `hra-*`, `holos-*`; відкриті PR (157 — #147 і
`dani-edrsr` #94, 161 — #148, 137 — `dani-edrsr` #88, 151 — `dani-edrsr` #93, 158 — `dani-edrsr` #92); гілки без PR, що
можуть бути в роботі (`claude/eloquent-cannon-fqvjc2` — 154, `claude/nifty-dirac-0cexn8`, `claude/clever-pasteur-02fi6a`).

**На рішення Андрія (не злиті, не порожні — не видаляв):**
- `moya-vulytsya`: `maket-m7` (історія макетів М1–М7, ZVIT-67 — лишити); `ccr-aaa20c4e-3bqxye-94` (PR #113 закрито — ZAVDANNYA-94
  замінено); `claude/zavdannya-129` (65 комітів, злито через #121/#122 іншими гілками); `claude/quirky-franklin-86j8ft` (16.11);
  `claude/compassionate-heisenberg-mrof74` (друга спроба 153 з тестами `tests/test_vkhody.py`; 153 злито через #142);
  `claude/zvit-137` (звіт 137 — лишити, доки 137 не закінчить); `rolyky-127-rushiy` (злита #118, але назва «перегляду»).
- `dani-edrsr`: зразки до звітів `zvit-72`, `zvit-73`, `zvit-74`, `zvit-76`, `zvit-84`, `zvit-109`, `zvit-112`, `zvity-71`,
  `znimky-87`, `znimky-89`; макети `claude/zavdannya-77-b4c82c`, `-79-lilwd5`, `-80-gymkpu`; прототипи `ccr-2e58f026-lrw0z1` (92),
  `ccr-bffc03c5-imcl5o` (91, «Для медіа»); `rolyky-94-zrazky` (94 замінено); `dani-1551`. На більшість посилаються звіти й
  `RISHENNYA.md` як «зразки — гілка …», тож порада — лишити, доки звіт живий.

**Видалити — `moya-vulytsya` (73):** `ccr-0f042df5-jit0tv` (#98), `ccr-1b1e79ab-w9kba5` (#89), `ccr-1b1e79ab-w9kba5-105` (#96), `ccr-1b1e79ab-w9kba5-106` (#97), `ccr-1d3addb6-i7grs9` (#109), `ccr-2931df0f-w6kd6r` (#83), `ccr-2e58f026-lrw0z1` (#91), `ccr-35866528-6vhmjl` (#86), `ccr-396d16fa-nigvlm` (#124), `ccr-39e14437-pd23ey` (#103), `ccr-3c335638-xsshcp` (#99), `ccr-3f28823b-q91hob` (#127), `ccr-549a3308-zn7mhc` (#76), `ccr-5a0dc3dd-dnrz2i` (#105), `ccr-69f1964c-l7b658` (#85), `ccr-74e6ffd6-7rxf8s` (#126), `ccr-773c94d1-aan27k` (#104), `ccr-8c90d307-n4ax94` (#117), `ccr-9d4a0c4f-gtxwci` (#107), `ccr-9d4a0c4f-gtxwci-113` (#110), `ccr-aaa20c4e-3bqxye` (#108), `ccr-b784e793-2kma5p` (#106), `ccr-bb843a57-oiuod6` (#75), `ccr-bffc03c5-imcl5o` (#88), `ccr-c685d2ea-1bwsto` (#81), `ccr-cba1726d-6zp4xj` (#77), `ccr-ce09b009-sn0du8` (#94), `ccr-ce09b009-sn0du8-102` (#101), `ccr-ce09b009-sn0du8-103` (#102), `ccr-e6b3614e-5tddrg` (#92), `ccr-e87a69bd-nggfz6` (#82), `ccr-f3918343-yej79e` (#114), `ccr-f3918343-yej79e-124` (#115), `ccr-f3918343-yej79e-125` (#116), `claude/awesome-feynman-z4a655` (#130), `claude/beautiful-curie-29wob9` (#136), `claude/charming-hypatia-khn0q2` (#145), `claude/clever-allen-abbicp` (#134), `claude/clever-pasteur-02fi6a` (#140), `claude/ecstatic-archimedes-95i9cg` (#142), `claude/friendly-keller-alfupn` (#78), `claude/friendly-volta-883c3d` (#138), `claude/gallant-sagan-uvucan` (#128), `claude/happy-sagan-cyqne2` (#74), `claude/intelligent-goodall-fe5ujn` (#139), `claude/kind-cannon-xh1ixp` (#129), `claude/lucid-albattani-hl7coj` (#141), `claude/magical-clarke-2rls71` (#144), `claude/moya-vulytsya-zavdannya-134-h5h3oq` (#125), `claude/nifty-edison-wqfb3y` (#133), `claude/optimistic-volta-t4jo2g` (#135), `claude/peaceful-wright-vvmlfb` (#123), `claude/pensive-cori-vzp61z` (#132), `claude/pensive-lovelace-uiddqf` (#146), `claude/sharp-meitner-41deyx` (#131), `claude/sleepy-hawking-5h30lc` (#137), `claude/upbeat-sagan-zdffo4` (#120), `claude/wizardly-thompson-5nxuh8` (#143), `claude/zavdannya-111-m0q7t2` (#112), `claude/zavdannya-117-lytq9a` (#111), `claude/zavdannya-129-numpy` (#122), `claude/zavdannya-130-5uq62e` (#119), `claude/zavdannya-67-115dc9` (#71), `claude/zavdannya-71-jev1ar` (#73), `claude/zavdannya-79-lilwd5` (#79), `claude/zavdannya-80-gymkpu` (#80), `claude/zavdannya-85-vzkiqm` (#84), `claude/zavdannya-89-dqaqtf` (#87), `claude/zavdannya-95-8gvcv2` (#93), `claude/zavdannya-96-95-8gvcv2` (#90), `claude/zavdannya-97-98-7l09e3` (#95), `claude/zavdannya-98-7l09e3` (#100), `zavdannya-69` (#72).

**Видалити — `dani-edrsr` (38):** `ccr-0f042df5-jit0tv` (#66), `ccr-1d3addb6-i7grs9` (#71), `ccr-1d3addb6-i7grs9-119` (#76), `ccr-1d5f8ef4-u0zery` (#58), `ccr-35866528-6vhmjl` (#60), `ccr-396d16fa-nigvlm` (#85), `ccr-39e14437-pd23ey` (#67), `ccr-3f28823b-q91hob` (#87), `ccr-5a0dc3dd-dnrz2i` (#69), `ccr-69f1964c-l7b658` (#59), `ccr-74e6ffd6-7rxf8s` (#86), `ccr-773c94d1-aan27k` (#68), `ccr-9d4a0c4f-gtxwci` (#72), `ccr-9d4a0c4f-gtxwci-113` (#77), `ccr-aaa20c4e-3bqxye` (#74), `ccr-e6b3614e-5tddrg` (#80), `ccr-f329b91f-5ak75b` (#61), `ccr-f3918343-yej79e` (#82), `ccr-f3918343-yej79e-124` (#84), `claude/amazing-hamilton-2aed3i` (#55), `claude/beautiful-curie-29wob9` (#90), `claude/intelligent-goodall-fe5ujn` (#91), `claude/pensive-cori-vzp61z` (#89), `claude/quirky-franklin-86j8ft` (#56), `claude/serene-goldberg-grdapr` (#54), `claude/zavdannya-111-m0q7t2` (#79), `claude/zavdannya-115-116-cqsum8` (#70), `claude/zavdannya-116-cqsum8` (#73), `claude/zavdannya-117-lytq9a` (#78), `claude/zavdannya-120-kaolzf` (#75), `claude/zavdannya-121-4plw2r` (#81), `claude/zavdannya-122-9bvjc9` (#83), `claude/zavdannya-137` (#88), `claude/zavdannya-85-vzkiqm` (#57), `claude/zavdannya-89-dqaqtf` (#62), `claude/zavdannya-95-8gvcv2` (#64), `claude/zavdannya-96-95-8gvcv2` (#63), `claude/zavdannya-97-98-7l09e3` (#65).

Команди (Git Bash на ПК; шлях — `D:\problem_orienting\…`). Перевірено на пробному сховищі: видаляє лише гілки з тим самим
верхом, змінену — відмовляє.

<details><summary>moya-vulytsya — 73 гілок</summary>

```bash
git -C D:/problem_orienting/moya-vulytsya push origin \
  --force-with-lease=refs/heads/ccr-0f042df5-jit0tv:adeed68e80c387b1d1e38ba19b67ec7fe7fae661 :refs/heads/ccr-0f042df5-jit0tv \
  --force-with-lease=refs/heads/ccr-1b1e79ab-w9kba5:7610b464f0c2b9811f8868acf4f3e25954f5eafa :refs/heads/ccr-1b1e79ab-w9kba5 \
  --force-with-lease=refs/heads/ccr-1b1e79ab-w9kba5-105:4a7bf6246e2c4ec0a77e3a51b1971e9cd4fdd01d :refs/heads/ccr-1b1e79ab-w9kba5-105 \
  --force-with-lease=refs/heads/ccr-1b1e79ab-w9kba5-106:6ab7e9b974e602e41fa0ad968bb4ec2e69f1e780 :refs/heads/ccr-1b1e79ab-w9kba5-106 \
  --force-with-lease=refs/heads/ccr-1d3addb6-i7grs9:e7211d5210f5d6385bde81b6a82534bb695650f9 :refs/heads/ccr-1d3addb6-i7grs9 \
  --force-with-lease=refs/heads/ccr-2931df0f-w6kd6r:af81c891f15bba18b1a1717d67cca38865f63e20 :refs/heads/ccr-2931df0f-w6kd6r \
  --force-with-lease=refs/heads/ccr-2e58f026-lrw0z1:133826db05583536279465ede0b405d2e7b53f0e :refs/heads/ccr-2e58f026-lrw0z1 \
  --force-with-lease=refs/heads/ccr-35866528-6vhmjl:cd2eb3672edcf86547b1014421e79979a2b4bca7 :refs/heads/ccr-35866528-6vhmjl \
  --force-with-lease=refs/heads/ccr-396d16fa-nigvlm:ffe4454ef83803a2eca68915ec0b5df182f53e4a :refs/heads/ccr-396d16fa-nigvlm \
  --force-with-lease=refs/heads/ccr-39e14437-pd23ey:0be369dfc0cb30ff03db84522de39df7f1976b28 :refs/heads/ccr-39e14437-pd23ey \
  --force-with-lease=refs/heads/ccr-3c335638-xsshcp:d217ab319459ce1eb75b589ebd553c9c93be042c :refs/heads/ccr-3c335638-xsshcp \
  --force-with-lease=refs/heads/ccr-3f28823b-q91hob:9f5ca32f57a938c26c203a1075cfbf59f569570d :refs/heads/ccr-3f28823b-q91hob \
  --force-with-lease=refs/heads/ccr-549a3308-zn7mhc:d3354e38b922656d6ce55300dfdc78dfd8d476f4 :refs/heads/ccr-549a3308-zn7mhc \
  --force-with-lease=refs/heads/ccr-5a0dc3dd-dnrz2i:2c8e517b5788f8bd0570c319ca9336219d155de2 :refs/heads/ccr-5a0dc3dd-dnrz2i \
  --force-with-lease=refs/heads/ccr-69f1964c-l7b658:8bf8c3acad76cdb74041dfd1e83047c1d7c75376 :refs/heads/ccr-69f1964c-l7b658 \
  --force-with-lease=refs/heads/ccr-74e6ffd6-7rxf8s:f76ee9bbb415da9f35175927fd0475f38f8a72f8 :refs/heads/ccr-74e6ffd6-7rxf8s \
  --force-with-lease=refs/heads/ccr-773c94d1-aan27k:0cdffb8d4a0d8ca5c646bac45d2ef6b5c103a396 :refs/heads/ccr-773c94d1-aan27k \
  --force-with-lease=refs/heads/ccr-8c90d307-n4ax94:3ad453673c8defe8feadb3c9ec77b3959a132552 :refs/heads/ccr-8c90d307-n4ax94 \
  --force-with-lease=refs/heads/ccr-9d4a0c4f-gtxwci:b731a7b991abc36748b982cdcf3b85929dc33c77 :refs/heads/ccr-9d4a0c4f-gtxwci \
  --force-with-lease=refs/heads/ccr-9d4a0c4f-gtxwci-113:8cce50d09b518477fbcb46955839405301ab96ef :refs/heads/ccr-9d4a0c4f-gtxwci-113 \
  --force-with-lease=refs/heads/ccr-aaa20c4e-3bqxye:1919b380556521ddc6fba8cf2f33504c2cda0125 :refs/heads/ccr-aaa20c4e-3bqxye \
  --force-with-lease=refs/heads/ccr-b784e793-2kma5p:c3aff98fbd39a52475ff3f91bb9adae94255180b :refs/heads/ccr-b784e793-2kma5p \
  --force-with-lease=refs/heads/ccr-bb843a57-oiuod6:924a7990af62ef4c9eed9e15f4bef93c4ddf6b12 :refs/heads/ccr-bb843a57-oiuod6 \
  --force-with-lease=refs/heads/ccr-bffc03c5-imcl5o:8a08f0f04d03e4549a108c4085e17ac189ff839b :refs/heads/ccr-bffc03c5-imcl5o \
  --force-with-lease=refs/heads/ccr-c685d2ea-1bwsto:b40b5587c29181702c77a7bd5a666fa163b0fb3e :refs/heads/ccr-c685d2ea-1bwsto \
  --force-with-lease=refs/heads/ccr-cba1726d-6zp4xj:0c3f249deb87fe7f458847ec6a3b551180f06131 :refs/heads/ccr-cba1726d-6zp4xj \
  --force-with-lease=refs/heads/ccr-ce09b009-sn0du8:97238677f72dbf2c5fa74187343d8afd7e2dcd87 :refs/heads/ccr-ce09b009-sn0du8 \
  --force-with-lease=refs/heads/ccr-ce09b009-sn0du8-102:b841abf06cc52eac137aff36608c66cb4d3aa050 :refs/heads/ccr-ce09b009-sn0du8-102 \
  --force-with-lease=refs/heads/ccr-ce09b009-sn0du8-103:a3f85ba99fa86b61c81d7f7feff101ed7707a99d :refs/heads/ccr-ce09b009-sn0du8-103 \
  --force-with-lease=refs/heads/ccr-e6b3614e-5tddrg:24849333f5b24896d41b6f865364eee88021c255 :refs/heads/ccr-e6b3614e-5tddrg \
  --force-with-lease=refs/heads/ccr-e87a69bd-nggfz6:c2745bee3e6e648494b6fb71ae71d1246ca8045f :refs/heads/ccr-e87a69bd-nggfz6 \
  --force-with-lease=refs/heads/ccr-f3918343-yej79e:738257dfe1270777914c1f3554a55620f3c51326 :refs/heads/ccr-f3918343-yej79e \
  --force-with-lease=refs/heads/ccr-f3918343-yej79e-124:7e402fb544b1ebe24d4e0639c2e63b14179c0d39 :refs/heads/ccr-f3918343-yej79e-124 \
  --force-with-lease=refs/heads/ccr-f3918343-yej79e-125:02833482ad2abc7986701822b404ac63af6ed22b :refs/heads/ccr-f3918343-yej79e-125 \
  --force-with-lease=refs/heads/claude/awesome-feynman-z4a655:783e917a339813cfa80a472abf6397f05623060f :refs/heads/claude/awesome-feynman-z4a655 \
  --force-with-lease=refs/heads/claude/beautiful-curie-29wob9:bcd1872c669087f14f4bda50d942da2e3d2d213e :refs/heads/claude/beautiful-curie-29wob9 \
  --force-with-lease=refs/heads/claude/charming-hypatia-khn0q2:8bf207388785233792e4291c57cb16a8f488fdd7 :refs/heads/claude/charming-hypatia-khn0q2 \
  --force-with-lease=refs/heads/claude/clever-allen-abbicp:c0527e92a63fde9bacfbe5706716e3bdcf2291b8 :refs/heads/claude/clever-allen-abbicp \
  --force-with-lease=refs/heads/claude/clever-pasteur-02fi6a:0e4c615235f65ae07526072af35d439228a72189 :refs/heads/claude/clever-pasteur-02fi6a \
  --force-with-lease=refs/heads/claude/ecstatic-archimedes-95i9cg:fd42b1d8b04b91e0e7f4ec26245f5e4bf9cab64a :refs/heads/claude/ecstatic-archimedes-95i9cg \
  --force-with-lease=refs/heads/claude/friendly-keller-alfupn:1d49d4800c49c52647b70e8b24b39b538996a4ca :refs/heads/claude/friendly-keller-alfupn \
  --force-with-lease=refs/heads/claude/friendly-volta-883c3d:c453068b3fdfbc33d84790f17d532ae37242052c :refs/heads/claude/friendly-volta-883c3d \
  --force-with-lease=refs/heads/claude/gallant-sagan-uvucan:3060eaa5d343430c12c9c12b676407a125de97ef :refs/heads/claude/gallant-sagan-uvucan \
  --force-with-lease=refs/heads/claude/happy-sagan-cyqne2:120307c8c4f9e8a173c2caa2d308f5a066863641 :refs/heads/claude/happy-sagan-cyqne2 \
  --force-with-lease=refs/heads/claude/intelligent-goodall-fe5ujn:89bf345e59ca782b74a812d6c34fbb00a29f0936 :refs/heads/claude/intelligent-goodall-fe5ujn \
  --force-with-lease=refs/heads/claude/kind-cannon-xh1ixp:4679654ee913033d65c27d7fbe9bdc09be9229c2 :refs/heads/claude/kind-cannon-xh1ixp \
  --force-with-lease=refs/heads/claude/lucid-albattani-hl7coj:c3be35be1c297d2197ebe9787f29bf7a9e9e36ea :refs/heads/claude/lucid-albattani-hl7coj \
  --force-with-lease=refs/heads/claude/magical-clarke-2rls71:6c2653e7e335439382c269778ed0c5d7cafc2e98 :refs/heads/claude/magical-clarke-2rls71 \
  --force-with-lease=refs/heads/claude/moya-vulytsya-zavdannya-134-h5h3oq:d4a9e87807a6675ee683ea262d1c7ba784137c51 :refs/heads/claude/moya-vulytsya-zavdannya-134-h5h3oq \
  --force-with-lease=refs/heads/claude/nifty-edison-wqfb3y:59edcefae5f9595ad7416e03ee4a429dd50f927d :refs/heads/claude/nifty-edison-wqfb3y \
  --force-with-lease=refs/heads/claude/optimistic-volta-t4jo2g:2b8e91037130c6bdd77214e89f991a3860c960dc :refs/heads/claude/optimistic-volta-t4jo2g \
  --force-with-lease=refs/heads/claude/peaceful-wright-vvmlfb:cb882398d799c9b64cd9522c9d80e261e58ce937 :refs/heads/claude/peaceful-wright-vvmlfb \
  --force-with-lease=refs/heads/claude/pensive-cori-vzp61z:bca7f5f55e728cc1af925d7d3d7da3d2fd5560ff :refs/heads/claude/pensive-cori-vzp61z \
  --force-with-lease=refs/heads/claude/pensive-lovelace-uiddqf:57ec3b831471edbe7441745feff26a86f10b6195 :refs/heads/claude/pensive-lovelace-uiddqf \
  --force-with-lease=refs/heads/claude/sharp-meitner-41deyx:c95e50fccb403cb27989e121e5e5cb349b71bf1c :refs/heads/claude/sharp-meitner-41deyx \
  --force-with-lease=refs/heads/claude/sleepy-hawking-5h30lc:bbd04d7c69745a78876a189c79150d8ef7a9d3a1 :refs/heads/claude/sleepy-hawking-5h30lc \
  --force-with-lease=refs/heads/claude/upbeat-sagan-zdffo4:9927dca0b2bf468140c643a233b611e9bd4116cc :refs/heads/claude/upbeat-sagan-zdffo4 \
  --force-with-lease=refs/heads/claude/wizardly-thompson-5nxuh8:faf5cccf5348bcbfbbd44694af6b3153e8deb793 :refs/heads/claude/wizardly-thompson-5nxuh8 \
  --force-with-lease=refs/heads/claude/zavdannya-111-m0q7t2:f7d8119868aa08fa0256c1ffaa82bdbd49017b9d :refs/heads/claude/zavdannya-111-m0q7t2 \
  --force-with-lease=refs/heads/claude/zavdannya-117-lytq9a:a4b7fcc85f273dc2015d647fb77b6dff441b1c8f :refs/heads/claude/zavdannya-117-lytq9a \
  --force-with-lease=refs/heads/claude/zavdannya-129-numpy:e55871fe848b105f45e66181ab8614e3841f14fd :refs/heads/claude/zavdannya-129-numpy \
  --force-with-lease=refs/heads/claude/zavdannya-130-5uq62e:50774a565793c89293fa09c7035c462f5f300f4b :refs/heads/claude/zavdannya-130-5uq62e \
  --force-with-lease=refs/heads/claude/zavdannya-67-115dc9:c29f4d1a46634c4ef0970ce9fa6f912b27591a08 :refs/heads/claude/zavdannya-67-115dc9 \
  --force-with-lease=refs/heads/claude/zavdannya-71-jev1ar:b7767a7421b5929622972c79e1ca2b138f44e422 :refs/heads/claude/zavdannya-71-jev1ar \
  --force-with-lease=refs/heads/claude/zavdannya-79-lilwd5:75d564bde36af70d44f33e38178315e9ac3feeb8 :refs/heads/claude/zavdannya-79-lilwd5 \
  --force-with-lease=refs/heads/claude/zavdannya-80-gymkpu:d6601d1df3682140b9e16104b78510cb17e1af22 :refs/heads/claude/zavdannya-80-gymkpu \
  --force-with-lease=refs/heads/claude/zavdannya-85-vzkiqm:36d81ad3d917f4b59438fa43f5cde0e75d6aabcf :refs/heads/claude/zavdannya-85-vzkiqm \
  --force-with-lease=refs/heads/claude/zavdannya-89-dqaqtf:4b4498ca619610338489acbd22f142edc27bfc44 :refs/heads/claude/zavdannya-89-dqaqtf \
  --force-with-lease=refs/heads/claude/zavdannya-95-8gvcv2:deffcf79ba63c800f39643ac6abc56502ab519ce :refs/heads/claude/zavdannya-95-8gvcv2 \
  --force-with-lease=refs/heads/claude/zavdannya-96-95-8gvcv2:115c5338c67810ff379a3fcc76413239379930df :refs/heads/claude/zavdannya-96-95-8gvcv2 \
  --force-with-lease=refs/heads/claude/zavdannya-97-98-7l09e3:a880e02d83abcdf48054091844620a4905ac1904 :refs/heads/claude/zavdannya-97-98-7l09e3 \
  --force-with-lease=refs/heads/claude/zavdannya-98-7l09e3:575e25fd7a38ba5c0908b688c21eb7469275c3ea :refs/heads/claude/zavdannya-98-7l09e3 \
  --force-with-lease=refs/heads/zavdannya-69:ce4dd4eaeba3a5e133d25336749daa1ad57c9bf9 :refs/heads/zavdannya-69
```
</details>

<details><summary>dani-edrsr — 38 гілок</summary>

```bash
git -C D:/problem_orienting/dani-edrsr push origin \
  --force-with-lease=refs/heads/ccr-0f042df5-jit0tv:fb6c4b21cf77b505ca4daaa2a250c20a2e6183b2 :refs/heads/ccr-0f042df5-jit0tv \
  --force-with-lease=refs/heads/ccr-1d3addb6-i7grs9:2c144ffb50798cb1029dca962e70abf04d2f7873 :refs/heads/ccr-1d3addb6-i7grs9 \
  --force-with-lease=refs/heads/ccr-1d3addb6-i7grs9-119:3e5bc478683b64a01ab4550ed7f59bda3adc9758 :refs/heads/ccr-1d3addb6-i7grs9-119 \
  --force-with-lease=refs/heads/ccr-1d5f8ef4-u0zery:fef4f1a358dca1a800f9aea3caf47a62a90f557c :refs/heads/ccr-1d5f8ef4-u0zery \
  --force-with-lease=refs/heads/ccr-35866528-6vhmjl:b0f26d2a48bb3f54268f5fd63ca0025e72174b89 :refs/heads/ccr-35866528-6vhmjl \
  --force-with-lease=refs/heads/ccr-396d16fa-nigvlm:be59a1fa1e893ce40d47da2904a1f767fe9a7bd8 :refs/heads/ccr-396d16fa-nigvlm \
  --force-with-lease=refs/heads/ccr-39e14437-pd23ey:ac82f09cf2e12ce5513594d8e9f2af3608604907 :refs/heads/ccr-39e14437-pd23ey \
  --force-with-lease=refs/heads/ccr-3f28823b-q91hob:6bd654a901a100c5ea7e911eb633a75075ecb007 :refs/heads/ccr-3f28823b-q91hob \
  --force-with-lease=refs/heads/ccr-5a0dc3dd-dnrz2i:01f4bd940e2edda863795edb9f9480adfdd38159 :refs/heads/ccr-5a0dc3dd-dnrz2i \
  --force-with-lease=refs/heads/ccr-69f1964c-l7b658:5b9498bd05e7e2d3710bef69f4bb18d63b6f82b9 :refs/heads/ccr-69f1964c-l7b658 \
  --force-with-lease=refs/heads/ccr-74e6ffd6-7rxf8s:3c5865c0c603381633868512c50f5c4e509be073 :refs/heads/ccr-74e6ffd6-7rxf8s \
  --force-with-lease=refs/heads/ccr-773c94d1-aan27k:302029838d5290c51d78efdbc94cb031289874da :refs/heads/ccr-773c94d1-aan27k \
  --force-with-lease=refs/heads/ccr-9d4a0c4f-gtxwci:c5280b3434a1809f874fc12f1e79b5d7c67223fe :refs/heads/ccr-9d4a0c4f-gtxwci \
  --force-with-lease=refs/heads/ccr-9d4a0c4f-gtxwci-113:8cb84f6b731d37d4bfc8d2ccd4f7b642b3eebddb :refs/heads/ccr-9d4a0c4f-gtxwci-113 \
  --force-with-lease=refs/heads/ccr-aaa20c4e-3bqxye:15475cc5bd5f1aef04b9cd0829eecf66378b1174 :refs/heads/ccr-aaa20c4e-3bqxye \
  --force-with-lease=refs/heads/ccr-e6b3614e-5tddrg:571e9ad6e046ca98cf3373854b48f2a39a598c5e :refs/heads/ccr-e6b3614e-5tddrg \
  --force-with-lease=refs/heads/ccr-f329b91f-5ak75b:ce9d81dabceabf43404734e5c2ea36b476b103f7 :refs/heads/ccr-f329b91f-5ak75b \
  --force-with-lease=refs/heads/ccr-f3918343-yej79e:b502d367146931ee66e896a5447a2e71024d2002 :refs/heads/ccr-f3918343-yej79e \
  --force-with-lease=refs/heads/ccr-f3918343-yej79e-124:77b6920db579b306fd3f1b12972669f957505acd :refs/heads/ccr-f3918343-yej79e-124 \
  --force-with-lease=refs/heads/claude/amazing-hamilton-2aed3i:d19c328d9c5c13944a5ed4c790d1e3c0175ff8bb :refs/heads/claude/amazing-hamilton-2aed3i \
  --force-with-lease=refs/heads/claude/beautiful-curie-29wob9:91850722624d63a86d044883a25c8637946c0c27 :refs/heads/claude/beautiful-curie-29wob9 \
  --force-with-lease=refs/heads/claude/intelligent-goodall-fe5ujn:f8bee900c34b53c765ac47115bcce785bf1efedd :refs/heads/claude/intelligent-goodall-fe5ujn \
  --force-with-lease=refs/heads/claude/pensive-cori-vzp61z:b2b4ed2686861f87bf408c8cd4c9ef4c8d0f7917 :refs/heads/claude/pensive-cori-vzp61z \
  --force-with-lease=refs/heads/claude/quirky-franklin-86j8ft:7dad23c58329a04abeb61ee9592c4c8c52d5a463 :refs/heads/claude/quirky-franklin-86j8ft \
  --force-with-lease=refs/heads/claude/serene-goldberg-grdapr:a25ef7a5a7d2024ec06003fb3b09f6550339c568 :refs/heads/claude/serene-goldberg-grdapr \
  --force-with-lease=refs/heads/claude/zavdannya-111-m0q7t2:97f05f1afe5aa056563a2f78a4dc72c3faaae489 :refs/heads/claude/zavdannya-111-m0q7t2 \
  --force-with-lease=refs/heads/claude/zavdannya-115-116-cqsum8:d6e970ce0cf620cc16b6be8bf0482073c62653d4 :refs/heads/claude/zavdannya-115-116-cqsum8 \
  --force-with-lease=refs/heads/claude/zavdannya-116-cqsum8:e17b83438668b5fe224ccb895bc410da7936f686 :refs/heads/claude/zavdannya-116-cqsum8 \
  --force-with-lease=refs/heads/claude/zavdannya-117-lytq9a:f140673ef50f96b19172484020a62b1d125653a6 :refs/heads/claude/zavdannya-117-lytq9a \
  --force-with-lease=refs/heads/claude/zavdannya-120-kaolzf:270082c9f7995fd38faebe674d33cff3e759934a :refs/heads/claude/zavdannya-120-kaolzf \
  --force-with-lease=refs/heads/claude/zavdannya-121-4plw2r:8d183574321471fbdfb34f91211a9a5c529eb54d :refs/heads/claude/zavdannya-121-4plw2r \
  --force-with-lease=refs/heads/claude/zavdannya-122-9bvjc9:93a3e39baff3e4ee0a683ae2d01162d5cf12980c :refs/heads/claude/zavdannya-122-9bvjc9 \
  --force-with-lease=refs/heads/claude/zavdannya-137:e34d88daec2ae6189c4a3e9e2456bdd483081268 :refs/heads/claude/zavdannya-137 \
  --force-with-lease=refs/heads/claude/zavdannya-85-vzkiqm:a0f75df2265f67a05f3f1fee5b4f01609475a49b :refs/heads/claude/zavdannya-85-vzkiqm \
  --force-with-lease=refs/heads/claude/zavdannya-89-dqaqtf:5c9e7227beccdd8bc40f261a300be20bde1502f2 :refs/heads/claude/zavdannya-89-dqaqtf \
  --force-with-lease=refs/heads/claude/zavdannya-95-8gvcv2:ae5f499009e51acb81facc4f9253d78ebee42d39 :refs/heads/claude/zavdannya-95-8gvcv2 \
  --force-with-lease=refs/heads/claude/zavdannya-96-95-8gvcv2:4ff98b36c25f067fc82088098d69cc0ce65be651 :refs/heads/claude/zavdannya-96-95-8gvcv2 \
  --force-with-lease=refs/heads/claude/zavdannya-97-98-7l09e3:eb22baceb945d5c9772edba36f01311146530b57 :refs/heads/claude/zavdannya-97-98-7l09e3
```
</details>

## 4. Тести

- **Продукт:** `python -m unittest discover -s tests` — 592 тести, усе гаразд, 1 пропущено: `test_litopys.Temp.test_60_dniv`
  — потрібен зібраний `litopys.json` (з колоди, поза git) — причина справжня. Інші пропуски в коді (`skipUnless` на Node,
  Chrome, h3) тут не спрацьовують — усе є. Тести сервера продажу (`site/worker/testy/*.test.mjs`) запускає `test_prodazh.py`.
- **Конвеєр:** `python src/check_build.py` — «усе гаразд». `tests/test_pokaz_fabuly.py` **ніде не запускався й падав**:
  перевірка «Особа N» застаріла після ZAVDANNYA-150 (тепер після ролі «водій ОСОБА_1» мітка прибирається зовсім). Перевірку
  оновлено, файл тепер запускає `check_build` (у `fabuly_pokaz`, S-П.1) — більше не «осиротіє». Інші файли `tests/`
  конвеєра запускає `check_build`, `test_koloda.py` пропускає 2 тести без справжньої колоди (змінна `KOLODA`) — причина є.
- **Дублі:** однакових назв тестів в одному класі (пізніший тихо перекриває ранній) — немає в обох репозиторіях.
  `tests/test_pokaz_fabuly.py` частково повторює `fabuly_pokaz` у `check_build`, але перевіряє більше (укази, хвіст
  кваліфікації, межа речення) — лишив обидва.

## 5. Що не чіпав (файли інших виконавців) — лише позначив у боргу `docs/08-stan.md`

- `video/vau/` і `docs/HOLOS-TEKSTY.md` (155) — позначка ще «Голос згенеровано», а MV-171 — «Голос змінено програмою».
- `dani-edrsr/.github/workflows/problemy-nich.yml` — щоночі за розкладом, хоча MV-163 переніс перевірку на ПК; тест
  `problemy_nich` вимагає розклад; 137 зараз працює з проблемами. Порада: після злиття 137 лишити лише ручний запуск.
- Сайт, сервер продажу, карта підписника, автопостинг — не рухав (151, 154, 155, 157, 161).

## 6. Суперечність для центрального чату

`YAK-PRATSIUIEMO.md` (розд. 7) і `dani-edrsr/CLAUDE.md`: «виконані завдання й звіти видаляємо». На практиці: 100+ звітів у
`moya-vulytsya/docs/` і 8 у корені `dani-edrsr`, на них посилаються `RISHENNYA.md`, аркуш стану й навіть код
(`dani-edrsr/src/kyiv_povnyi.py` бере оцінки з ZVIT-100). Звіти — ще й доказ методики (AGENTS, розд. 10.5). Я **не
видаляв** звітів. Порада: записати правило «звіти лишаються в `docs/` (продукт) і в корені (`dani-edrsr`); видаляються лише
`ZAVDANNYA-*` після приймання» — або «так» Андрія на видалення з переліком.

## Не перевірено

- Команди видалення гілок на справжньому GitHub не запускались (лише на пробному сховищі).
- Пункти боргу коду «паспорт рішення, ланцюжок справи…» (MV-33…MV-43) лишив як були — що з них уже в коді, не перевіряв.
- Звірка — пошуком за словами й номерами рішень; сторонньої людини, яка прочитала б усе, не було.
