// Форми сайту в базі Cloudflare D1 (ZAVDANNYA-132): «Скоро — залиште пошту», передзамовлення, звернення, чотири числа.
// Сайт на Workers пише сюди замість Supabase (site/zahlushka/nadsylannya.js, режим skhovyshche: 'sait'): той самий акаунт,
// база ззовні недосяжна, не «засинає» після тижня тиші. Перевірки полів — ті самі, що в nadsylannya.js.
// Читає лише партнер: вивантаження /api/admin/vyvantazhennia/<таблиця> з ADMIN_KLIUCH або `wrangler d1 execute`.
import TS from './tsiny.js';
import * as L from './logika.js';
import { nadislaty } from './poshta.js';

export const PODII = ['pryishly', 'adresa', 'peredzamovyty', 'kontakt',
  'hra_start', 'hra_vidpovid', 'hra_kinets', 'hra_podilytysia', 'den_zihrano',
  'vd_start', 'vd_kinets', 'vd_storinka', 'vd_pidpyska', 'vd_podilytysia'];
const SHCHO = ['analiz', 'pidpyska', 'povidomyty', 'kompaniya'];
const SHCHO_NE_TAK = ['mistse', 'opys', 'vydalyty', 'inshe'];
// Що можна «замовити наперед» у режимі «скоро»: усе, що продаватиметься, і «Судова практика» (повідомити про запуск).
export const TOVARY_SKORO = [...new Set([...TS.na_prodazh, 'spdovidka', 'spyurist', 'sudova'])];
export const NAZVA_SUDOVA = 'Судова практика — повідомити про запуск';
const ZAPYSIV_NA_POSHTU = 20;
export const LYSTIV_ZVERNEN = 10;        // листів партнеру про нові звернення — не більше на годину (ZAVDANNYA-156)            // більше рядків «скоро» з однієї пошти не пишемо (захист від засмічення)
export const TABLYTSI = { skoro: 'id, poshta, tovar, budynok, adresa, kanal, stvoreno, napysano',
  zayavka: 'id, shcho, misto, adresa, kontakt, kanal, stvoreno', zvernennya: 'id, posylannya, shcho_ne_tak, poyasnennya, kontakt, stvoreno, zakryto',
  podiya: 'den, nazva, kanal, n',
  prybrani_podii: 'id, kliuch, posylannia, zvernennya_id, prychyna, khto, prybrano, povernuto' };   // журнал прибраних (ZAVDANNYA-161)

export function kanal(d) {
  const k = String(d ?? '').trim().toLowerCase();
  if (!k) return 'priamo';
  return /^[a-z0-9-]{1,40}$/.test(k) ? k : 'inshe';
}

const tekst = (v, n) => { const t = String(v ?? '').trim(); return t ? t.slice(0, n) : null; };

/** «Скоро — залиште пошту»: { ok } або { pomylka }. Будинок — лише існуючий на сайті (адресу беремо з його сторінки). */
export async function zapysatySkoro(env, url, f) {
  const tovar = String(f.tovar || '');
  if (!TOVARY_SKORO.includes(tovar)) return { pomylka: 'Такого товару немає.' };
  const poshta = L.chystaPoshta(f.poshta);
  if (!poshta) return { pomylka: 'Перевірте пошту.' };
  if (f.zghoda !== 'tak') return { pomylka: 'Потрібна згода з політикою конфіденційності.' };
  let budynok = '', adresa = '';
  if (f.budynok) {
    adresa = await L.perevirytyBudynok(env, String(f.budynok), url);
    if (!adresa) return { pomylka: 'Такого будинку на сайті немає.' };
    budynok = String(f.budynok);
  }
  const n = (await L.odyn(env, 'SELECT COUNT(*) AS n FROM skoro WHERE poshta = ?', poshta)).n;
  if (n >= ZAPYSIV_NA_POSHTU) return { ok: true };
  await L.zrobyty(env, `INSERT OR IGNORE INTO skoro (poshta, tovar, budynok, adresa, kanal, stvoreno) VALUES (?, ?, ?, ?, ?, ?)`,
    poshta, tovar, budynok, adresa, kanal(f.dzherelo), L.teper(env));
  return { ok: true };
}

/** POST /api/forma/<таблиця> з JSON, як у Supabase. Повертає Response. */
export async function forma(request, env, tablytsia) {
  if (!['zayavka', 'zvernennya', 'podiya'].includes(tablytsia)) return new Response('ні', { status: 404 });
  let d;
  try { d = await request.json(); } catch { return new Response('ne json', { status: 400 }); }
  if (!d || typeof d !== 'object') return new Response('ne json', { status: 400 });
  const t = L.teper(env);
  if (tablytsia === 'podiya') {
    if (!PODII.includes(d.nazva)) return new Response('nazva', { status: 400 });
    const den = new Date(t * 1000).toISOString().slice(0, 10);
    await L.zrobyty(env, `INSERT INTO podiya (den, nazva, kanal, n) VALUES (?, ?, ?, 1)
                          ON CONFLICT (den, nazva, kanal) DO UPDATE SET n = n + 1`, den, d.nazva, kanal(d.kanal));
    return new Response(null, { status: 201 });
  }
  if (d.zghoda !== true) return new Response('zghoda', { status: 400 });
  const kontakt = tekst(d.kontakt, 120);
  if (!kontakt) return new Response('kontakt', { status: 400 });
  if (tablytsia === 'zayavka') {
    const misto = tekst(d.misto, 80);
    if (!misto) return new Response('misto', { status: 400 });
    await L.zrobyty(env, 'INSERT INTO zayavka (shcho, misto, adresa, kontakt, kanal, stvoreno) VALUES (?, ?, ?, ?, ?, ?)',
      SHCHO.includes(d.shcho) ? d.shcho : 'povidomyty', misto, tekst(d.adresa, 200), kontakt, kanal(d.kanal), t);
    return new Response(null, { status: 201 });
  }
  if (tablytsia === 'zvernennya') {
    const posylannya = tekst(d.posylannya, 300);
    if (!posylannya || !SHCHO_NE_TAK.includes(d.shcho_ne_tak)) return new Response('polia', { status: 400 });
    await L.zrobyty(env, 'INSERT INTO zvernennya (posylannya, shcho_ne_tak, poyasnennya, kontakt, stvoreno) VALUES (?, ?, ?, ?, ?)',
      posylannya, d.shcho_ne_tak, tekst(d.poyasnennya, 2000), kontakt, t);
    // Строк — 10 робочих днів (AGENTS.md, розд. 7): партнер має дізнатися одразу, а не з вивантаження.
    // Не більше LYSTIV_ZVERNEN листів на годину (ZAVDANNYA-156): потік підроблених звернень не завалить пошту партнера
    // й не вичерпає ліміт сервісу листів; самі звернення однаково записано — партнер побачить їх у вивантаженні.
    const zaHodynu = (await L.odyn(env, 'SELECT COUNT(*) AS n FROM zvernennya WHERE stvoreno > ?', t - 3600)).n;
    if (env.POSHTA_PARTNERA && zaHodynu <= LYSTIV_ZVERNEN) {
      try {
        await nadislaty(env, { komu: env.POSHTA_PARTNERA, tema: 'Нове звернення: виправити або прибрати подію',
          tekst: `Надійшло звернення (${d.shcho_ne_tak}). Відповісти — протягом 10 робочих днів.\n` +
            'Подробиці — у вивантаженні звернень (docs/ZAPUSK-SAITU.md, «Де читати форми»). Контакт людини в листі не пишемо.' });
      } catch (err) { console.log(`звернення: лист партнеру не пішов: ${err.message}`); }
    }
    return new Response(null, { status: 201 });
  }
  return new Response('ні', { status: 404 });
}

export function csvKlityna(v) {
  if (v === null || v === undefined) return '';
  let s = String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;       // щоб таблиця не виконала вміст клітинки як формулу
  return /[",\n\r;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Вивантаження для партнера (CSV, UTF-8 з BOM — відкривається в Excel і Google Таблицях). */
export async function vyvantazhennia(env, tablytsia) {
  const stovptsi = Object.hasOwn(TABLYTSI, tablytsia) ? TABLYTSI[tablytsia] : null;   // лише свої таблиці (ZAVDANNYA-156)
  if (!stovptsi) return new Response('ні', { status: 404 });
  const ryadky = await L.vsi(env, `SELECT ${stovptsi} FROM ${tablytsia} ORDER BY 1`);
  const nazvy = stovptsi.split(', ');
  const csv = '﻿' + [nazvy.join(','), ...ryadky.map((r) => nazvy.map((k) => csvKlityna(r[k])).join(','))].join('\r\n') + '\r\n';
  return new Response(csv, { headers: { 'content-type': 'text/csv; charset=utf-8', 'cache-control': 'no-store',
    'content-disposition': `attachment; filename="${tablytsia}.csv"` } });
}

/** Щоденна перевірка форм (ZAVDANNYA-133, п. 4; .github/workflows/perevirka-formy.yml): прибрати її тестові рядки — лише з
 *  каналом «perevirka», нічого іншого. Повертає, скільки рядків прибрано в кожній таблиці. */
export const KANAL_PEREVIRKY = 'perevirka';
export async function prybratyPerevirku(env) {
  const v = {};
  for (const t of ['zayavka', 'podiya', 'skoro']) {
    v[t] = (await L.zrobyty(env, `DELETE FROM ${t} WHERE kanal = ?`, KANAL_PEREVIRKY)).meta?.changes ?? 0;
  }
  return v;
}
