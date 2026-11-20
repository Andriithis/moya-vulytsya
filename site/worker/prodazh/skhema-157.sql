-- ZAVDANNYA-157: «Для бізнесу» — оновлення бази, створеної раніше (на новій базі не потрібне — усе вже в skhema.sql).
-- npx wrangler d1 execute moya-vulytsya-prodazh --remote --file=skhema-157.sql   (раз; повтор нічого не змінює)
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
