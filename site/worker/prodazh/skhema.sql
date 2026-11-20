-- Сервер продажу «Моєї вулиці» (ZAVDANNYA-99): база замовлень Cloudflare D1 (SQLite).
-- Створення: npx wrangler d1 execute moya-vulytsya-prodazh --remote --file=skhema.sql
-- Тут лише те, без чого не продати й не видати довідку (docs/PRODAZH-SERVER.md, розд. «Що зберігаємо»).
-- Номерів карток, імен, телефонів, адрес проживання — НЕМАЄ. Описів подій — немає: вони лише у файлах довідок (сховище R2).
-- Час — секунди від 1970 (UTC).

CREATE TABLE IF NOT EXISTS korystuvachi (
  id         INTEGER PRIMARY KEY,
  poshta     TEXT NOT NULL UNIQUE,          -- нижнім регістром
  stvoreno   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS zamovlennia (
  id             TEXT PRIMARY KEY,           -- випадковий, не номер по порядку
  korystuvach_id INTEGER,                    -- NULL після видалення даних на запит (замовлення лишається для обліку партнера)
  tovar          TEXT NOT NULL,              -- ключ site/tsiny.py
  budynok        TEXT,                       -- /budynok/<вулиця>/<номер>/ або NULL
  adresa         TEXT,                       -- як у заголовку сторінки будинку (публічна адреса будинку)
  suma           INTEGER NOT NULL,           -- грн, лише з таблиці цін
  valiuta        TEXT NOT NULL DEFAULT 'UAH',
  status         TEXT NOT NULL DEFAULT 'stvoreno',  -- stvoreno | oplacheno | vidmova | povernuto
  servis         TEXT NOT NULL,              -- перехідник: test | liqpay | mono
  pidpyska_id    TEXT,                       -- для «додаткової» і для списань підписки
  parametry      TEXT,                       -- «Судова практика» (ZAVDANNYA-135): JSON {stattia, sud, chastyna}; інакше NULL
  zalyshok       INTEGER NOT NULL DEFAULT 0, -- скільки довідок ще можна взяти з цього замовлення (пакет «3 довідки»)
  stvoreno       INTEGER NOT NULL,
  oplacheno      INTEGER
);
CREATE INDEX IF NOT EXISTS zamovlennia_k ON zamovlennia(korystuvach_id);

CREATE TABLE IF NOT EXISTS pidpysky (
  id             TEXT PRIMARY KEY,
  korystuvach_id INTEGER,
  tovar          TEXT NOT NULL,              -- pidpyska | rieltor | osbb
  budynok        TEXT,                       -- для ОСББ — свій будинок
  adresa         TEXT,
  status         TEXT NOT NULL DEFAULT 'ochikuie',  -- ochikuie | aktyvna | skasovana
  pochatok       INTEGER,                    -- початок поточного оплаченого періоду
  diie_do        INTEGER,                    -- кінець поточного оплаченого періоду
  zamovlennia_id TEXT NOT NULL,              -- перше замовлення (його номер знає платіжний сервіс)
  stvoreno       INTEGER NOT NULL,
  skasovano      INTEGER
);
CREATE INDEX IF NOT EXISTS pidpysky_k ON pidpysky(korystuvach_id);

CREATE TABLE IF NOT EXISTS dovidky (
  id             TEXT PRIMARY KEY,
  korystuvach_id INTEGER,
  zamovlennia_id TEXT NOT NULL,
  pidpyska_id    TEXT,                       -- взято в межах підписки (лічильник місяця)
  budynok        TEXT NOT NULL,
  adresa         TEXT NOT NULL,              -- її й передаємо генератору
  rezhym         TEXT NOT NULL,              -- dovidka | povnyi | sp («Судова практика»: budynok = '', adresa = опис вибору)
  parametry      TEXT,                       -- sp: JSON {stattia, sud, chastyna} — передаємо генератору (dani-edrsr/src/sp_dovidka.py)
  status         TEXT NOT NULL DEFAULT 'v_cherzi', -- v_cherzi | hotuietsia | hotova | pomylka | vydaleno (минув строк)
  kliuch_hash    TEXT,                       -- SHA-256 ключа з посилання в листі (з'являється, коли готова); сам ключ не зберігаємо
  fail           TEXT,                       -- ім'я файла в сховищі
  sprob          INTEGER NOT NULL DEFAULT 0,
  vziato         INTEGER,                    -- коли видавач узяв у роботу
  stvoreno       INTEGER NOT NULL,
  hotovo         INTEGER
);
CREATE INDEX IF NOT EXISTS dovidky_k ON dovidky(korystuvach_id);
CREATE INDEX IF NOT EXISTS dovidky_s ON dovidky(status);

CREATE TABLE IF NOT EXISTS stezhu (
  korystuvach_id INTEGER NOT NULL,
  budynok        TEXT NOT NULL,
  adresa         TEXT NOT NULL,
  stvoreno       INTEGER NOT NULL,
  PRIMARY KEY (korystuvach_id, budynok)
);

-- Сесії кабінету і разові посилання для входу: зберігаємо лише SHA-256, не самі ключі.
CREATE TABLE IF NOT EXISTS sesii (
  hash           TEXT PRIMARY KEY,
  korystuvach_id INTEGER NOT NULL,
  do_            INTEGER NOT NULL
);
-- Разові посилання входу; за ними ж рахуємо листи за годину (не більше 5 — захист від розсилки на чужу пошту).
CREATE TABLE IF NOT EXISTS vkhody (
  hash           TEXT PRIMARY KEY,
  korystuvach_id INTEGER NOT NULL,
  do_            INTEGER NOT NULL,
  vykorystano    INTEGER
);
-- Вхід через Google (ZAVDANNYA-142, google.js): разовий «стан» на 10 хвилин. Хеш стану, nonce, ключ перевірки PKCE і куди
-- повернутися; пошти й даних Google тут немає. Прострочені стираються під час наступного входу.
CREATE TABLE IF NOT EXISTS google_stany (
  hash           TEXT PRIMARY KEY,
  nonce          TEXT NOT NULL,
  perevirka      TEXT NOT NULL,
  kudy           TEXT NOT NULL,
  do_            INTEGER NOT NULL,
  vykorystano    INTEGER
);

-- Журнал сповіщень платіжного сервісу: одне сповіщення обробляється один раз (сервіси повторюють їх днями).
CREATE TABLE IF NOT EXISTS spovishchennia (
  servis         TEXT NOT NULL,
  kliuch         TEXT NOT NULL,              -- номер транзакції сервісу (або замовлення + статус + час)
  zamovlennia_id TEXT,
  status         TEXT,
  suma           INTEGER,
  otrymano       INTEGER NOT NULL,
  PRIMARY KEY (servis, kliuch)
);

-- Бали ігор (ZAVDANNYA-123; MV-130, MV-138) — лише серверні, за акаунтом. Журнал руху: + нараховано, − обміняно.
-- Баланс = сума зміни. Бали з пристрою (localStorage) сюди не переносяться — їх не перевірити (ZVIT-117, розд. 4).
-- Обмін увімкнено лише змінною OBMIN_BALIV = 'tak' (після висновку юриста й кабінету); без неї таблиця порожня.
CREATE TABLE IF NOT EXISTS bali_rukh (
  id             INTEGER PRIMARY KEY,
  korystuvach_id INTEGER NOT NULL,
  zmina          INTEGER NOT NULL,           -- + нараховано (гра), − обмін
  prychyna       TEXT NOT NULL,              -- hra:<гра>:<дата> | obmin:<товар>
  kliuch         TEXT NOT NULL UNIQUE,       -- той самий запит удруге нічого не змінює
  zamovlennia_id TEXT,                       -- для обміну: замовлення з сумою 0 і servis = 'bali'
  stvoreno       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS bali_rukh_k ON bali_rukh(korystuvach_id);

-- ZAVDANNYA-132: нагадування ОСББ за 3 дні до річного списання (MV-155, П7). Один лист на один кінець періоду.
CREATE TABLE IF NOT EXISTS nahaduvannia (
  pidpyska_id    TEXT NOT NULL,
  diie_do        INTEGER NOT NULL,           -- кінець періоду, про який нагадали
  nadislano      INTEGER NOT NULL,
  PRIMARY KEY (pidpyska_id, diie_do)
);

-- ZAVDANNYA-132: сховище форм сайту (замість Supabase, якщо сайт на Workers; docs/ZAPUSK-SAITU.md).
-- «Скоро — залиште пошту» (поки оплату не ввімкнено, PRODAZH = 'skoro'): пошта й що хотіли купити.
CREATE TABLE IF NOT EXISTS skoro (
  id             INTEGER PRIMARY KEY,
  poshta         TEXT NOT NULL,              -- нижнім регістром
  tovar          TEXT NOT NULL,              -- ключ site/tsiny.py
  budynok        TEXT NOT NULL DEFAULT '',   -- /budynok/<вулиця>/<номер>/ (перевірено на сайті) або ''
  adresa         TEXT NOT NULL DEFAULT '',   -- адреса із заголовка сторінки будинку
  kanal          TEXT NOT NULL DEFAULT 'priamo',
  stvoreno       INTEGER NOT NULL,
  napysano       INTEGER,                    -- коли партнер написав про запуск (лист один раз)
  UNIQUE (poshta, tovar, budynok)
);
-- Передзамовлення із заглушки (/zahlushka/#peredzamovlennya) — ті самі поля, що в Supabase (MV-8).
CREATE TABLE IF NOT EXISTS zayavka (
  id             INTEGER PRIMARY KEY,
  shcho          TEXT NOT NULL,
  misto          TEXT NOT NULL,
  adresa         TEXT,
  kontakt        TEXT NOT NULL,
  kanal          TEXT NOT NULL,
  stvoreno       INTEGER NOT NULL
);
-- Звернення «виправити або прибрати подію» (10 робочих днів). Про кожне нове — лист партнеру.
CREATE TABLE IF NOT EXISTS zvernennya (
  id             INTEGER PRIMARY KEY,
  posylannya     TEXT NOT NULL,
  shcho_ne_tak   TEXT NOT NULL,
  poyasnennya    TEXT,
  kontakt        TEXT NOT NULL,
  stvoreno       INTEGER NOT NULL,
  zakryto        INTEGER                     -- коли партнер відповів (ставить вручну)
);
-- Чотири числа (MV-5): лише лічильник за день, назвою події й каналом — без людей, кукі й адрес.
CREATE TABLE IF NOT EXISTS podiya (
  den            TEXT NOT NULL,              -- РРРР-ММ-ДД (UTC)
  nazva          TEXT NOT NULL,
  kanal          TEXT NOT NULL,
  n              INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (den, nazva, kanal)
);

-- ZAVDANNYA-135: «Судова практика» — скільки CSV вивантажив юрист за добу (ліміт — prodazh/sudova.js, VYVANTAZHEN_NA_DEN).
CREATE TABLE IF NOT EXISTS sp_vyvantazhennia (
  korystuvach_id INTEGER NOT NULL,
  den            TEXT NOT NULL,              -- РРРР-ММ-ДД (UTC)
  n              INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (korystuvach_id, den)
);

-- ZAVDANNYA-150, п. 4: щомісячний лист «Стежу» — кому й за який період уже надіслано (повтор розсилки не шле вдруге).
CREATE TABLE IF NOT EXISTS lysty_stezhu (
  korystuvach_id INTEGER NOT NULL,
  period         TEXT NOT NULL,
  nadislano      INTEGER NOT NULL,
  PRIMARY KEY (korystuvach_id, period)
);

-- ZAVDANNYA-157: «Для бізнесу» — запити зі сторінки /biznes/, клієнти за договором, особисті посилання на копію бази
-- (prodazh/biznes.js). У посиланнях — лише хеш ключа; ключ бачить один раз партнер, який його видав.
CREATE TABLE IF NOT EXISTS biznes_zapyty (
  id             INTEGER PRIMARY KEY,
  kompaniia      TEXT NOT NULL,
  kontakt        TEXT NOT NULL,
  meta           TEXT NOT NULL,
  terytoriia     TEXT,
  strok          TEXT NOT NULL,
  komentar       TEXT,
  kanal          TEXT NOT NULL,
  stvoreno       INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS biznes_klienty (
  id             INTEGER PRIMARY KEY,
  nazva          TEXT NOT NULL,
  kontakt        TEXT NOT NULL,
  dohovir        TEXT,
  tarif          TEXT NOT NULL CHECK (tarif IN ('misiats', 'rik')),
  diie_do        INTEGER NOT NULL,
  vymkneno       INTEGER,
  prychyna       TEXT,
  nahadano       INTEGER,
  stvoreno       INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS biznes_posylannia (
  hash           TEXT PRIMARY KEY,
  klient_id      INTEGER NOT NULL REFERENCES biznes_klienty(id),
  do_            INTEGER NOT NULL,
  maks           INTEGER NOT NULL,
  vykorystano    INTEGER NOT NULL DEFAULT 0,
  vymkneno       INTEGER,
  stvoreno       INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS biznes_zavantazhennia (
  id             INTEGER PRIMARY KEY,
  posylannia_hash TEXT NOT NULL,
  klient_id      INTEGER NOT NULL,
  fail           TEXT NOT NULL,
  chas           INTEGER NOT NULL
);
