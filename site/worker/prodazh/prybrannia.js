// Позачергове прибрання події (ZAVDANNYA-161, п. 5; MV-173): партнер прибирає подію за зверненням одразу — без перезбірки
// сайту й карти. Сервер тримає список прибраних рішень (таблиця prybrani_podii — вона ж журнал: хто, коли, за яким
// зверненням, чи повернуто) і відфільтровує їх на льоту там, де є опис події:
//   • карта підписника (R2): файли клітинок spravy/<клітинка>.json і «події адреси» (karta.js);
//   • колоди ігор сайту: /ihry/<колода>.json (KOLODY нижче; site/worker/index.js, run_worker_first у site/khostynh.py).
// Сторінки будинків, вулиць і районів подій не показують — лише числа (MV-99, MV-100): там нема що прибирати до наступного
// оновлення даних; число стане меншим із наступним випуском, коли подію внесуть у вилучення конвеєра
// (dani-edrsr/config/vyluchennia.json — список береться з /api/admin/prybrani).
//
// Подію впізнаємо за рішенням суду — так само, як посилання в кожній події (AGENTS.md, розд. 7):
//   h:<32 знаки>  — відбиток файла рішення ЄДРСР (od.reyestr.court.gov.ua/files/<NN>/<відбиток>.rtf; у карті — «NN+відбиток»);
//   n:<цифри>     — номер рішення в реєстрі (reyestr.court.gov.ua/Review/<номер>).
import * as L from './logika.js';

export const KOLODY = ['/ihry/koloda.json', '/ihry/vulytsia-dnia.json', '/ihry/litopys.json', '/ihry/kariera.json',
  '/ihry/detektyv.json', '/ihry/kvalifikuy.json'];

/** Ключ рішення з того, що вставив партнер: посилання на файл рішення, на сторінку Review або сам номер. null — не впізнано. */
export function kliuch(tekst) {
  const t = String(tekst ?? '').trim().toLowerCase();
  if (!t || t.length > 500) return null;
  const h = t.match(/(?:^|[^0-9a-f])([0-9a-f]{32})(?:\.rtf)?(?:$|[^0-9a-f])/);
  if (h) return `h:${h[1]}`;
  const n = t.match(/\/review\/(\d{5,12})(?:\D|$)/) || t.match(/^(\d{5,12})$/);
  return n ? `n:${n[1]}` : null;
}

function zbih(s, kliuchi) {
  const t = s.toLowerCase();
  for (const k of kliuchi) {
    const v = k.slice(2);
    if (k[0] === 'h' ? t.includes(v) : (t === v || new RegExp(`/review/${v}(?!\\d)`).test(t))) return true;
  }
  return false;
}

const konteiner = (x) => x !== null && typeof x === 'object';
/** «Збірка записів»: масив, усі елементи якого — масиви чи об'єкти; або об'єкт, усі значення якого такі (словник за id). */
const zbirka = (x) => konteiner(x) && (Array.isArray(x) ? x.length > 0 && x.every(konteiner)
  : Object.keys(x).length > 0 && Object.values(x).every(konteiner));

/** Чи є рішення з ключів у записі не глибше двох рівнів (запис.url, запис.rishennia.url, рядок[4][0]). */
function blyzko(x, kliuchi, d = 2) {
  if (typeof x === 'string') return zbih(x, kliuchi);
  if (!konteiner(x) || d < 0) return false;
  return Object.values(x).some((v) => blyzko(v, kliuchi, d - 1));
}

/**
 * Прибрати з будь-якого JSON записи (події), що посилаються на прибрані рішення. Запис — член «збірки записів», який сам не є
 * збіркою: подія колоди, рядок справи карти, загадка «Вулиці дня», справа «Детектива». Ключі словника прибраних записів
 * (id подій «Літопису») прибираються й зі списків id. Повертає { dani, prybrano }.
 */
export function vidfiltruvaty(dani, kliuchi) {
  if (!kliuchi.length) return { dani, prybrano: 0 };
  let prybrano = 0;
  const ids = new Set();
  const khid = (x) => {
    if (zbirka(x)) {
      if (Array.isArray(x)) {
        return x.filter((m) => { const het = !zbirka(m) && blyzko(m, kliuchi); if (het) prybrano++; return !het; }).map(khid);
      }
      const o = {};
      for (const [k, m] of Object.entries(x)) {
        if (!zbirka(m) && blyzko(m, kliuchi)) { prybrano++; ids.add(k); } else o[k] = khid(m);
      }
      return o;
    }
    if (Array.isArray(x)) return x.map(khid);
    if (konteiner(x)) return Object.fromEntries(Object.entries(x).map(([k, v]) => [k, khid(v)]));
    return x;
  };
  let v = khid(dani);
  if (ids.size) {
    const bez = (x) => {
      if (Array.isArray(x)) return (x.length && x.every((e) => typeof e === 'string') ? x.filter((e) => !ids.has(e)) : x).map(bez);
      if (konteiner(x)) return Object.fromEntries(Object.entries(x).map(([k, y]) => [k, bez(y)]));
      return x;
    };
    v = bez(v);
  }
  return { dani: v, prybrano };
}

// ---------------------------------------------------------------- список (у пам'яті скрипта на хвилину)

let kesh = null;
export async function aktyvni(env) {
  const t = Date.now();
  if (kesh && kesh.env === env && kesh.do_ > t) return kesh.k;
  let k = [];
  try {
    k = (await L.vsi(env, 'SELECT kliuch FROM prybrani_podii WHERE povernuto IS NULL')).map((r) => r.kliuch);
  } catch (err) {
    console.log(`прибрані події: ${err.message}`);      // таблиці ще немає (стара база без skhema-161.sql) — нічого не фільтруємо
  }
  kesh = { env, k, do_: t + 60_000 };
  return k;
}
const skynutyKesh = () => { kesh = null; };

/** Прибрати: { ok, id, kliuch } або { pomylka }. Повтор того самого рішення — те саме прибрання, без дубля. */
export async function prybraty(env, { posylannia, zvernennya_id = null, prychyna = '', khto = '' }) {
  const k = kliuch(posylannia);
  if (!k) return { pomylka: 'Не впізнали рішення. Вставте посилання на рішення суду (reyestr.court.gov.ua/Review/… або od.reyestr.court.gov.ua/files/…) або його номер.' };
  const zv = zvernennya_id ? parseInt(zvernennya_id, 10) || null : null;
  const t = L.teper(env);
  const bulo = await L.odyn(env, 'SELECT * FROM prybrani_podii WHERE kliuch = ?', k);
  if (bulo && bulo.povernuto === null) return { ok: true, id: bulo.id, kliuch: k, vzhe: true };
  if (bulo) {
    await L.zrobyty(env, `UPDATE prybrani_podii SET povernuto = NULL, prybrano = ?, zvernennya_id = COALESCE(?, zvernennya_id),
      prychyna = ?, khto = ? WHERE id = ?`, t, zv, String(prychyna).slice(0, 300), String(khto).slice(0, 120), bulo.id);
  } else {
    await L.zrobyty(env, `INSERT INTO prybrani_podii (kliuch, posylannia, zvernennya_id, prychyna, khto, prybrano) VALUES (?, ?, ?, ?, ?, ?)`,
      k, String(posylannia).trim().slice(0, 500), zv, String(prychyna).slice(0, 300), String(khto).slice(0, 120), t);
  }
  skynutyKesh();
  const r = await L.odyn(env, 'SELECT id FROM prybrani_podii WHERE kliuch = ?', k);
  return { ok: true, id: r.id, kliuch: k };
}

/** Повернути помилково прибрану подію (запис журналу лишається з часом повернення). */
export async function povernuty(env, id, khto = '') {
  const r = await L.zrobyty(env, 'UPDATE prybrani_podii SET povernuto = ?, khto = ? WHERE id = ? AND povernuto IS NULL',
    L.teper(env), String(khto).slice(0, 120), parseInt(id, 10) || 0);
  skynutyKesh();
  return !!r.meta?.changes;
}

export const zhurnal = (env, n = 200) => L.vsi(env, `SELECT id, kliuch, posylannia, zvernennya_id, prychyna, khto, prybrano, povernuto
  FROM prybrani_podii ORDER BY prybrano DESC LIMIT ?`, n);

/** Колода ігор з активів сайту з прибраними подіями. Список порожній — колода як є (без розбору). */
export async function koloda(request, env) {
  const r = await env.ASSETS.fetch(request);
  const k = await aktyvni(env);
  if (!k.length || !r.ok) return r;
  let d;
  try { d = await r.json(); } catch { return new Response('ні', { status: 502 }); }
  const v = vidfiltruvaty(d, k);
  return new Response(JSON.stringify(v.dani), { headers: { 'content-type': 'application/json; charset=utf-8',
    'cache-control': 'public, max-age=300', 'x-content-type-options': 'nosniff' } });
}
