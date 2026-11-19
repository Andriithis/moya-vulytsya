// Підміни Cloudflare для тестів і місцевого запуску (ZAVDANNYA-99): D1 — справжня SQLite (node:sqlite) зі схемою
// skhema.sql, R2 — словник у пам'яті. Поведінка — як у D1/R2 у тій частині, якою користується сервер (prepare/bind/first/all/run).
import fs from 'node:fs';
import { DatabaseSync } from 'node:sqlite';

const SKHEMA = fs.readFileSync(new URL('../prodazh/skhema.sql', import.meta.url), 'utf8');

export function d1() {
  const db = new DatabaseSync(':memory:');
  db.exec(SKHEMA);
  return {
    db,
    prepare(sql) {
      const st = db.prepare(sql);
      let p = [];
      const o = {
        bind(...x) { p = x.map((v) => (v === undefined ? null : v)); return o; },
        async first() { return st.get(...p) ?? null; },
        async all() { return { results: st.all(...p) }; },
        async run() { const r = st.run(...p); return { meta: { changes: Number(r.changes) } }; },
      };
      return o;
    },
  };
}

export function r2() {
  const m = new Map();
  return {
    m,
    async put(k, v) { m.set(k, String(v)); },
    async get(k) { if (!m.has(k)) return null; const b = m.get(k); return { body: b, async text() { return b; } }; },
    async delete(k) { m.delete(k); },
  };
}


/** R2 з теки на диску (ключі — шляхи файлів): перевірка карти підписника на справжній зібраній карті (karta_proba.mjs). */
export function r2ZTeky(teka) {
  return {
    async get(k) {
      const f = `${teka}/${k}`;
      if (!fs.existsSync(f)) return null;
      const b = fs.readFileSync(f);
      return { body: b, async text() { return b.toString('utf8'); } };
    },
  };
}
