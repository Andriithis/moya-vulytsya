# Автопостинг: як працює і як увімкнути в день Х

ZAVDANNYA-107, 17.11.2026, за MV-91, MV-111, MV-114. Код — `avtopostynh/`, тести — `tests/test_avtopostynh.py`.
Основа — [`ROLYKY-I-SOTSMEREZHI.md`](ROLYKY-I-SOTSMEREZHI.md), розд. 4 (умови мереж перевірено заново — розд. 3 нижче),
[`KOMPAS.md`](KOMPAS.md), розд. 3а (тиждень).

---

## Висновок — головне за хвилину

- **Готово:** сервіс однією командою щогодини: новий випуск → пачка на тиждень → **перевірка правил кожної одиниці** →
  черга → публікує те, чий час настав. Публікує **сам, без схвалення** (MV-114). Андрій дивиться вже опубліковане на
  **сторінці-перегляді** (пароль) і натискає «Прибрати»: сервіс видаляє допис у мережі, пише причину в журнал і більше
  таку подію / ролик / (за галочкою) місце не публікує. Доступу до акаунтів Андрій не має.
- **Telegram** (10 районних каналів) — повністю. **YouTube, Facebook, Instagram, TikTok** — перехідники за офіційними
  інтерфейсами, вмикаються змінною `MV_MEREZHI`, коли партнер отримає дозволи. Справжні запити до мереж **не
  перевірені** (ключів немає) — лише на штучних відповідях у тестах.
- **Пробний режим** (`--probnyi`) — усе те саме, але «публікує» у теку; сторінка-перегляд і «Прибрати» працюють.
  Пройдено наскрізь на заглушці роликів і генераторі дописів з гілки ZAVDANNYA-97.
- **Чого бракує, щоб пішло насправді:** ролики (ZAVDANNYA-94 — генератора ще немає; формат входу описано, розд. 8);
  генератор дописів 97 ще не злитий; **історії з вулиць у 97 — чернетки без переказу ШІ, і перевірка правил їх не
  пропускає (MV-21, MV-25)** — без переказу підуть лише «Цифри тижня». Токени й акаунти — партнер (розд. 7).
- **Змінилось у мережах проти розд. 4 (перевірено 17.11):** YouTube з 02.11.2026 більше не робить завантаження з
  неперевірених проєктів «приватними»; завантажень — 100 на добу окремою квотою. Instagram тепер дає видаляти дописи
  через інтерфейс. Telegram видаляє лише дописи, молодші за 48 год. TikTok до аудиту — лише «бачу тільки я».

## 1. Як працює

```
cron щогодини → servis.py hodyna
   ├─ новий випуск? (поле versiia покажчика indeks.json) або п'ятниця → пачка наступного тижня
   │     дописи Telegram: bot/kanaly.py (97) з покажчика bot/indeks.py
   │     ролики й картки: тека з manifest.json (94, brend/zrobyty.py)
   │     → розклад тижня (розд. 2) → перевірка правил (розд. 4) → черга (SQLite) + тека пачки з perehliad.html
   └─ публікація: усе, чий час настав; по одному на мережу й канал за запуск (без «зливи»);
         помилка → повтор через 1, 2, 4 год (до 4 спроб); 3 помилки підряд → мережа стоїть добу;
         блокування (токен відкликано, бота вигнали, обмеження акаунта) → мережа стоїть до команди vidnovyty;
         допис, що запізнився більше ніж на добу (сервер стояв), — пропускаємо
servis.py perehliad → сторінка для Андрія (за HTTPS-проксі партнера)
```

Стан — тека `MV_AVTOPOSTYNH_TEKA` на сервері: `cherha.db` (черга, журнал, стан мереж, прибране), `pachky/<тиждень>/`
(`pachka.json`, `perehliad.html`), у пробному режимі — `opublikovano/`. Токенів там немає (виняток TikTok — розд. 6).

## 2. Розклад тижня (KOMPAS, розд. 3а — порада, змінюється в `avtopostynh/rozklad.py`)

| Коли (за Києвом) | Що | Куди |
|---|---|---|
| пн 18:00 | «Що болить вулиці» | YouTube, Facebook, Instagram, TikTok |
| вт, пт 18:00 | Історії «під боком» | ті самі 4 |
| ср, сб 18:00 | Ігри | ті самі 4 |
| чт 18:00 | «Що буває за…» | ті самі 4 |
| нд 18:00 | Місто згори (видовищні) | ті самі 4 |
| ср 12:00 | Історії з даних | Facebook |
| вт 12:00, парні тижні | Як це працює | ті самі 4 |
| вт, пт 13:00 | Картка «Вулиця в цифрах» | Facebook, Instagram |
| щодня 09:00–09:18 | допис районного каналу (історія / ср «Вгадай» / пт «Цифри тижня») — розклад 97 | Telegram, 10 каналів по черзі з кроком 2 хв |

Ролика потрібної групи немає — день пропускається, у журналі «пропуск». Позиція з `manifest.json` іде лише раз.

## 3. Мережі — що вміє код і умови (перевірено 17.11.2026)

| Мережа | Публікація | Видалення («Прибрати») | Ліміти й умови | Джерело |
|---|---|---|---|---|
| **Telegram** | текст з кнопкою, вікторина (`sendPoll`, quiz), картинка, ролик до 50 МБ | `deleteMessage` — **лише до 48 год**; пізніше — «прибрати вручну» (партнер) | ≈ 20 повідомлень/хв у групу (для каналів окремої цифри немає); у нас 10 на ранок з кроком 2 хв | [Bot API](https://core.telegram.org/bots/api#deletemessage), [FAQ](https://core.telegram.org/bots/faq) |
| **YouTube** | `videos.insert` із відновленням, вертикальний до 3 хв = Shorts | `videos.delete` | **100 завантажень на добу** окремою квотою (з 01.06.2026); з 02.11.2026 неперевірені проєкти **більше не обмежені «приватними»**; застосунок Google має бути «In production», інакше ключ оновлення живе 7 днів | [квоти](https://developers.google.com/youtube/v3/determine_quota_cost), [історія змін](https://developers.google.com/youtube/v3/revision_history), [OAuth](https://developers.google.com/identity/protocols/oauth2) |
| **Facebook** | Reels у 3 кроки (`video_reels` start → `rupload` → finish), картка (`photos`), текст (`feed`) | `DELETE /{id}` — **документація Meta суперечить сама собі**; не вийде — «прибрати вручну» | 30 Reels за добу, 3–90 с, 9:16; дозволи `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`; Graph API v27.0 | [Reels](https://developers.facebook.com/docs/video-api/guides/reels-publishing), [дописи](https://developers.facebook.com/docs/pages-api/posts) |
| **Instagram** | контейнер (`REELS` або картинка) → чекати обробки → `media_publish` | `DELETE /{ig-media-id}` (з'явилось; дозвіл `instagram_manage_contents`) | 100 дописів за добу; файл Instagram **забирає сам за публічною адресою** (`MV_MEDIA_URL`); лише професійний акаунт, прив'язаний до сторінки Facebook | [публікація](https://developers.facebook.com/docs/instagram-platform/content-publishing), [видалення](https://developers.facebook.com/docs/instagram-platform/reference/instagram-media) |
| **TikTok** | `post/publish/video/init` з публічної адреси, позначка «створено ШІ» (`is_aigc`) | **через інтерфейс не знайдено** — «прибрати вручну» | до аудиту — лише «бачу тільки я» (`SELF_ONLY`); домен `MV_MEDIA_URL` підтвердити в кабінеті TikTok; ≈ 15 прямих публікацій на добу на автора; ключ доступу 2 год, ключ оновлення 180 днів і **змінюється при кожному оновленні** | [пряма публікація](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post), [правила](https://developers.tiktok.com/doc/content-sharing-guidelines), [токени](https://developers.tiktok.com/doc/oauth-user-access-token-management) |

**Позначка ШІ.** Голос у роликах синтезований (MV-93). YouTube вимагає позначку для «реалістичних» підробок — звичайний
диктор, імовірно, не такий (не перевірено), але код ставить її за замовчуванням (`MV_YOUTUBE_SYNTETYCHNYI=1`); TikTok —
`is_aigc`; у Meta поля для позначки в інтерфейсі не знайдено — порада: у підписі ролика рядок «голос синтезований».

**Не перевірено:** жоден справжній запит до мереж (ключів немає) — лише форма запитів і розбір помилок на штучних
відповідях. Перший запуск кожної мережі — під наглядом партнера, на одному дописі.

## 4. Перевірка правил (`avtopostynh/pravyla.py`) — двічі: при складанні пачки й перед публікацією

Не проходить (одиниця стає «не пройшло перевірку», видно на сторінці з причиною): номер житлового будинку в тексті
(номер — лише для публічного місця, MV-25, MV-60); імена, ініціали, «ОСОБА_», «кв.», номери справ; «небезпечн-»,
«безпечн-», рейтинги, «найгірший», «топ-N», «куди не ходити»; чутливі справи (MV-69, MV-102); емодзі; не рівно одне
посилання на сайт, посилання не на сторінку того самого місця або без `?dzherelo=<мережа>` (для каналу —
`telegram-<район>`); подія без номера рішення й «лише те, що дійшло до суду» (MV-60); чернетка без переказу ШІ
(MV-21, MV-25); межі довжини мережі; немає файлу; подія чи місце, які прибирали; подія, що виходила за 90 днів.
Ролик із полем `stsenarii` додатково проходить `video/perevirka.py`.

## 5. Змінні середовища (лише на сервері; у репозиторії й файлах — ніколи)

| Змінна | Що | Хто дає |
|---|---|---|
| `MV_MEREZHI` | які мережі ввімкнено: `telegram,youtube,facebook,instagram,tiktok` (типово `telegram`) | партнер, коли дозволи є |
| `MV_AVTOPOSTYNH_TEKA` | тека стану (черга, журнал, пачки) | партнер (напр. `/srv/mv/avtopostynh`) |
| `MV_INDEKS`, `MV_MEDIA_TEKA` | покажчик для дописів (`bot/indeks.py`) і тека роликів з `manifest.json` | збирання випуску |
| `MV_KANALY` | файл `район → @канал` (не секрет) | партнер |
| `MV_ADRESA_SAITU` | адреса сайту для посилань | партнер |
| `MV_MEDIA_URL` | публічна адреса теки роликів (Instagram і TikTok забирають файл самі) | партнер |
| `MV_PEREHLIAD_PAROL` | пароль сторінки-перегляду (≥ 12 знаків) | партнер → Андрію |
| `MV_TELEGRAM_TOKEN` | токен бота (той самий, що для бота «Мій будинок») | партнер |
| `MV_YOUTUBE_CLIENT_ID`, `MV_YOUTUBE_CLIENT_SECRET`, `MV_YOUTUBE_REFRESH_TOKEN` | вхід Google | партнер |
| `MV_META_PAGE_ID`, `MV_META_PAGE_TOKEN`, `MV_INSTAGRAM_ID`, `MV_META_VERSIA` | сторінка Facebook і Instagram | партнер |
| `MV_TIKTOK_CLIENT_KEY`, `MV_TIKTOK_CLIENT_SECRET`, `MV_TIKTOK_REFRESH_TOKEN`, `MV_TIKTOK_TOKEN_FAIL`, `MV_TIKTOK_PRYVATNIST` | TikTok | партнер |
| `MV_PROBNYI=1` | пробний режим | — |

## 6. Ризики й питання

1. **TikTok змінює ключ оновлення при кожному оновленні** (раз на ≤ 2 год), тому «лише змінні середовища» не працює:
   новий ключ сервіс пише у файл `MV_TIKTOK_TOKEN_FAIL` поза репозиторієм з правами 600. Це виняток з AGENTS, розд. 13 —
   **потрібне «так» центрального чату** або інший шлях (посередник на кшталт Ayrshare).
2. **Telegram: прибрати можна лише в перші 48 год.** Андрію — дивитись сторінку щодня-два; старші — «прибрати вручну».
3. **Історії Telegram без переказу ШІ не підуть** (MV-25). Генератор 97 позначає їх `chernetka`; щоб вийшли, 97 має
   ставити `perepysano: true` після переказу (`dani-edrsr/src/vytiah_shi.py`). Інакше — лише «Цифри тижня».
4. **Мітка каналу:** 97 з ZAVDANNYA-110 пише одразу `?dzherelo=telegram-<район>` (стару `tg-<район>` сервіс і далі переписує на `telegram-<район>`) (як `?dzherelo=telegram`
   на сайті). Варто вирівняти в 97 при злитті.
5. **Публічна адреса файлів** для Instagram і TikTok: тека роликів має бути доступна з інтернету без пароля (лише ролики
   й картки, без черги). Для TikTok домен підтверджують у кабінеті розробника.
6. Facebook: видалення через інтерфейс може не працювати (документація суперечлива) — перевірити на першому дописі.

## 7. День Х — як увімкнути (10 кроків; що робить партнер)

1. **Сервер:** Python 3.12+, копія репозиторію `moya-vulytsya`, тека стану (`/srv/mv/avtopostynh`), часовий пояс будь-який
   (розклад рахується за Києвом).
2. **Telegram:** створити бота в @BotFather і 10 районних каналів; додати бота адміністратором кожного з правами
   «публікувати» і «видаляти повідомлення»; файл `kanaly.json` (`{"Печерський": "@mv_pecherskyi", …}`) →
   `MV_KANALY`; токен → `MV_TELEGRAM_TOKEN`.
3. **Пробний тиждень на сервері:** `MV_PROBNYI=1`, запуск `hodyna` щогодини; Андрій дивиться сторінку-перегляд тиждень.
4. **Сторінка-перегляд:** `servis.py perehliad` як служба (systemd), назовні — лише через HTTPS (Caddy або Nginx з
   сертифікатом); `MV_PEREHLIAD_PAROL` — Андрію окремо, не в чаті з посиланням.
5. **Увімкнути Telegram:** прибрати `MV_PROBNYI`, `MV_MEREZHI=telegram`; перший ранок — партнер дивиться журнал
   (`servis.py zhurnal`).
6. **Тека роликів:** куди генератор 94 кладе `manifest.json` і файли (`MV_MEDIA_TEKA`) і її публічна адреса
   (`MV_MEDIA_URL`, напр. Cloudflare R2 або той самий сервер).
7. **YouTube:** акаунт Google і канал; проєкт у Google Cloud з YouTube Data API v3; екран згоди OAuth у стані
   «In production»; один раз увійти й отримати ключ оновлення → три змінні `MV_YOUTUBE_*`; додати `youtube` у `MV_MEREZHI`.
8. **Facebook та Instagram:** бізнес-портфоліо Meta, сторінка, Instagram — професійний і прив'язаний до сторінки;
   застосунок розробника з дозволами з розд. 3 (і `instagram_content_publish`, `instagram_manage_contents`); безстроковий
   токен сторінки → `MV_META_PAGE_TOKEN`, `MV_META_PAGE_ID`, `MV_INSTAGRAM_ID`; додати `facebook,instagram`.
9. **TikTok:** бізнес-акаунт; застосунок на developers.tiktok.com з Content Posting API (`video.publish`); підтвердити
   домен `MV_MEDIA_URL`; подати аудит. До аудиту — `MV_TIKTOK_PRYVATNIST=SELF_ONLY` (ролики бачить лише акаунт; людина
   ставить їх вручну), після — `PUBLIC_TO_EVERYONE`. Змінні `MV_TIKTOK_*` (розд. 6, п. 1).
10. **Розклад:** рядок cron `5 * * * * cd /srv/mv/moya-vulytsya && python3 avtopostynh/servis.py hodyna >> /srv/mv/avtopostynh/cron.log 2>&1`
    (змінні — у файлі служби, не в crontab у відкритому вигляді). Якщо мережа зупинилась — партнер розбирається і
    `servis.py vidnovyty <мережа>`.

## 8. Пробний режим і формат входу

```
python avtopostynh/zahlushka.py /tmp/mv/media                         # заглушка роликів і карток (поки немає 94)
python avtopostynh/servis.py --teka /tmp/mv/stan --media /tmp/mv/media --probnyi \
       pachka --tyzhden 2026-11-23 --indeks indeks.json --bot-teka <тека з bot/kanaly.py гілки 97>
python avtopostynh/servis.py --teka /tmp/mv/stan --media /tmp/mv/media --probnyi --zaraz 2026-11-23T16:05+00:00 publikuvaty
MV_PEREHLIAD_PAROL=… python avtopostynh/servis.py --teka /tmp/mv/stan --media /tmp/mv/media --probnyi perehliad
```

**`manifest.json` для 94 і `brend/zrobyty.py`** (одна позиція — один готовий файл; посилання сервіс додає сам):

```json
{"nazva": "shcho-bolyt-khreshchatyk-2026-11", "typ": "rolyk", "hrupa": "shcho_bolyt",
 "fail": "rolyky/shcho-bolyt-khreshchatyk.mp4", "zaholovok": "Що болить Хрещатику",
 "pidpys": "Скарги мешканців до 1551 за жовтень і події з рішень судів числом…",
 "mistse": {"shliakh": "/vulytsia/khreshchatyk/", "nazva": "вулиця Хрещатик", "typ_mistsia": null},
 "podii": [], "stsenarii": "stsenarii/shcho-bolyt-khreshchatyk.json", "perepysano": true}
```

Групи (`hrupa`): `shcho_bolyt`, `istorii`, `hry`, `zghory`, `yak_pratsiuie`, `shcho_buvaie`, `istorii_z_danykh` (MV-111);
`typ`: `rolyk` або `kartka`. Генератор дописів — інтерфейс `bot/kanaly.py`: `Henerator(indeks, adresa_saitu).pachka(vid, dniv, vzhe)`.
