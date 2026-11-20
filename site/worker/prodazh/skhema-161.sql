-- ZAVDANNYA-161: оновлення бази, створеної раніше (на новій базі не потрібне — усе вже в skhema.sql).
-- npx wrangler d1 execute moya-vulytsya-prodazh --remote --file=skhema-161.sql   (раз; повтор нічого не змінює)
CREATE TABLE IF NOT EXISTS karta_zavantazhennia (
  korystuvach_id INTEGER NOT NULL,
  den            TEXT NOT NULL,
  n              INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (korystuvach_id, den)
);

-- ZAVDANNYA-161, п. 5 (MV-173): позачергово прибрані події — список, який сервер застосовує одразу (карта підписника,
-- колоди ігор; prodazh/prybrannia.js), і водночас журнал: коли, хто з партнерів, за яким зверненням, чи повернуто.
-- Людських даних тут немає: лише рішення суду (ключ і посилання) і номер звернення. Журнал не стирається.
CREATE TABLE IF NOT EXISTS prybrani_podii (
  id             INTEGER PRIMARY KEY,
  kliuch         TEXT NOT NULL UNIQUE,       -- h:<відбиток файла рішення> | n:<номер рішення в реєстрі>
  posylannia     TEXT NOT NULL,              -- що вставив партнер
  zvernennya_id  INTEGER,                    -- звернення, за яким прибрано (NULL — за листом чи з власної ініціативи)
  prychyna       TEXT,
  khto           TEXT,                       -- пошта партнера з кабінету або «admin» (ключ ADMIN_KLIUCH)
  prybrano       INTEGER NOT NULL,
  povernuto      INTEGER                     -- NULL — діє; інакше коли повернули
);
