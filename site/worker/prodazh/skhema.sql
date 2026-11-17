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
  rezhym         TEXT NOT NULL,              -- dovidka | povnyi
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
