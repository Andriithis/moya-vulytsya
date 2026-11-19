-- ZAVDANNYA-135: оновлення бази, створеної до «Судової практики» (на новій базі не потрібне — усе вже в skhema.sql).
-- npx wrangler d1 execute moya-vulytsya-prodazh --remote --file=skhema-135.sql   (раз; повтор дасть «duplicate column» — це нормально)
ALTER TABLE zamovlennia ADD COLUMN parametry TEXT;
ALTER TABLE dovidky ADD COLUMN parametry TEXT;
CREATE TABLE IF NOT EXISTS sp_vyvantazhennia (
  korystuvach_id INTEGER NOT NULL,
  den            TEXT NOT NULL,
  n              INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (korystuvach_id, den)
);
