-- ZAVDANNYA-161: оновлення бази, створеної раніше (на новій базі не потрібне — усе вже в skhema.sql).
-- npx wrangler d1 execute moya-vulytsya-prodazh --remote --file=skhema-161.sql   (раз; повтор нічого не змінює)
CREATE TABLE IF NOT EXISTS karta_zavantazhennia (
  korystuvach_id INTEGER NOT NULL,
  den            TEXT NOT NULL,
  n              INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (korystuvach_id, den)
);
