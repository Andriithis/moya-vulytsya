-- ZAVDANNYA-150: оновлення бази, створеної раніше (на новій базі не потрібне — усе вже в skhema.sql).
-- npx wrangler d1 execute moya-vulytsya-prodazh --remote --file=skhema-150.sql   (раз; повтор нічого не змінює)
CREATE TABLE IF NOT EXISTS lysty_stezhu (
  korystuvach_id INTEGER NOT NULL,
  period         TEXT NOT NULL,
  nadislano      INTEGER NOT NULL,
  PRIMARY KEY (korystuvach_id, period)
);
