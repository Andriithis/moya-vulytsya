-- ZAVDANNYA-172: оновлення бази, створеної раніше (на новій базі не потрібне — усе вже в skhema.sql).
-- npx wrangler d1 execute moya-vulytsya-prodazh --remote --file=skhema-172.sql   (раз; повтор нічого не змінює)
-- Без цього файла сервер працює: лічильник «скоро» для «Судової практики» просто не пишеться (zrobytyNovu).
-- ZAVDANNYA-172 (ZVIT-169, п. 9): «скоро» для довідки «Судової практики» — які статті, суди й частини люди хочуть.
-- Лише лічильник за день, без пошти й без зв'язку з рядком skoro: персональних даних тут немає, стирати нічого.
CREATE TABLE IF NOT EXISTS skoro_sp (
  den            TEXT NOT NULL,              -- РРРР-ММ-ДД, UTC
  stattia        TEXT NOT NULL,              -- як у довіднику «Судової практики»: «ст. 130 КУпАП»
  sud            TEXT NOT NULL DEFAULT '',   -- назва району суду або '' (усі суди)
  chastyna       TEXT NOT NULL DEFAULT '',
  n              INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (den, stattia, sud, chastyna)
);
