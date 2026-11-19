// Правила продажу (ZAVDANNYA-99): замовлення, оплата, підписки, лічильник довідок, видача, видалення даних.
// База — Cloudflare D1 (env.BAZA), файли довідок — Cloudflare R2 (env.DOVIDKY). Схема — skhema.sql.
import { shturhnuty } from './vydavach.js';
import TS from './tsiny.js';
import { vypadkovyi, sha256 } from './bezpeka.js';
import { nadislaty } from './poshta.js';
import { budynok as zPachky } from '../budynky.js';
import { nahaduvanniaOsbb } from './lysty.js';

export const teper = (env) => (env.__CHAS ? env.__CHAS() : Math.floor(Date.now() / 1000));

const q = (env, sql, ...p) => env.BAZA.prepare(sql).bind(...p);
export const odyn = (env, sql, ...p) => q(env, sql, ...p).first();
export const vsi = async (env, sql, ...p) => (await q(env, sql, ...p).all()).results;
export const zrobyty = (env, sql, ...p) => q(env, sql, ...p).run();

export const PIDPYSKY = Object.keys(TS.period_misiatsiv);           // pidpyska, rieltor, osbb
const BEZ_BUDYNKU = ['pidpyska', 'rieltor'];                         // будинок необов'язковий
const POSHTA = /^[^\s@<>"',;]{1,64}@[^\s@<>"',;]+\.[^\s@<>"',;]{2,}$/;
const BUDYNOK = /^\/budynok\/[a-z0-9-]{1,80}\/[a-z0-9-]{1,40}\/$/;

export function chystaPoshta(p) {
  const t = String(p ?? '').trim().toLowerCase();
  return t.length <= 254 && POSHTA.test(t) ? t : null;
}

export function dodatyMisiatsi(t, n) {
  const d = new Date(t * 1000);
  const den = d.getUTCDate();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() + n);
  const ostannii = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
  d.setUTCDate(Math.min(den, ostannii));
  return Math.floor(d.getTime() / 1000);
}

/** Будинок існує на сайті? Повертає адресу із заголовка його сторінки, інакше null. Адресу з форми не беремо. */
export async function perevirytyBudynok(env, budynok, url) {
  if (!BUDYNOK.test(String(budynok ?? ''))) return null;
  const zapyt = new Request(new URL(budynok, url));
  // Варіант workers — сторінка в пачці (той самий код, що віддає її людям); варіант pages — звичайний файл.
  const r = env.PACHOK ? await zPachky(zapyt, env) : await env.ASSETS.fetch(zapyt);
  if (!r || !r.ok) return null;
  const m = (await r.text()).match(/<h1>([^<]{1,200})<\/h1>/);
  if (!m) return null;
  return m[1].replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
}

export async function korystuvach(env, poshta) {
  await zrobyty(env, 'INSERT OR IGNORE INTO korystuvachi (poshta, stvoreno) VALUES (?, ?)', poshta, teper(env));
  return odyn(env, 'SELECT * FROM korystuvachi WHERE poshta = ?', poshta);
}

/**
 * Нове замовлення. Ціна — лише з таблиці цін (tsiny.js із site/tsiny.py); усе інше з форми ігнорується.
 * Повертає { zam, pidpyska } або { pomylka }.
 */
export async function stvorytyZamovlennia(env, { tovar, budynok, adresa, korystuvach_id, servis, pidpyska_id = null }) {
  const suma = TS.tsiny[tovar];
  if (!Number.isInteger(suma) || suma <= 0) return { pomylka: 'Такого товару немає.' };
  const id = 'z' + vypadkovyi(15);
  const t = teper(env);
  await zrobyty(env, `INSERT INTO zamovlennia (id, korystuvach_id, tovar, budynok, adresa, suma, servis, pidpyska_id, stvoreno)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`, id, korystuvach_id, tovar, budynok || null, adresa || null, suma, servis, pidpyska_id, t);
  let pidpyska = null;
  if (PIDPYSKY.includes(tovar)) {
    pidpyska = { id: 'p' + vypadkovyi(15), period_misiatsiv: TS.period_misiatsiv[tovar] };
    await zrobyty(env, `INSERT INTO pidpysky (id, korystuvach_id, tovar, budynok, adresa, zamovlennia_id, stvoreno)
                        VALUES (?, ?, ?, ?, ?, ?, ?)`, pidpyska.id, korystuvach_id, tovar, budynok || null, adresa || null, id, t);
  }
  return { zam: await odyn(env, 'SELECT * FROM zamovlennia WHERE id = ?', id), pidpyska };
}

export function potribenBudynok(tovar) {
  return !BEZ_BUDYNKU.includes(tovar);
}

// ---------------------------------------------------------------- довідки й лічильник

export async function postavytyDovidku(env, { korystuvach_id, zamovlennia_id, pidpyska_id = null, budynok, adresa, rezhym }) {
  const id = 'd' + vypadkovyi(15);
  await zrobyty(env, `INSERT INTO dovidky (id, korystuvach_id, zamovlennia_id, pidpyska_id, budynok, adresa, rezhym, stvoreno)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)`, id, korystuvach_id, zamovlennia_id, pidpyska_id, budynok, adresa, rezhym, teper(env));
  await shturhnuty(env, 'dovidka');      // видавач у GitHub Actions (ZAVDANNYA-133): довідку ставлять лише після оплати
  return id;
}

/** Активна підписка діє (aktyvna або скасована, але ще оплачена) — і скільки довідок цього періоду лишилось. */
export async function stanPidpysok(env, korystuvach_id) {
  const t = teper(env);
  const ps = await vsi(env, `SELECT * FROM pidpysky WHERE korystuvach_id = ? AND status != 'ochikuie' ORDER BY stvoreno`, korystuvach_id);
  for (const p of ps) {
    p.diie = p.diie_do > t && ['aktyvna', 'skasovana'].includes(p.status);
    // Лічильник — за поточний місяць підписки (і в річній ОСББ теж: 1 довідка на місяць).
    let vid = p.pochatok, k = 1;
    while (dodatyMisiatsi(p.pochatok, k) <= t) vid = dodatyMisiatsi(p.pochatok, k++);
    const vziato = (await odyn(env, 'SELECT COUNT(*) AS n FROM dovidky WHERE pidpyska_id = ? AND stvoreno >= ?', p.id, vid)).n;
    p.zalyshok = p.diie ? Math.max(0, TS.dovidok[p.tovar] - vziato) : 0;
  }
  return ps;
}

/** Що можна взяти без оплати: довідки підписки цього періоду і залишок пакетів «3 довідки». */
export async function dostupno(env, korystuvach_id) {
  const ps = (await stanPidpysok(env, korystuvach_id)).filter((p) => p.diie);
  const pakety = await vsi(env, `SELECT id, zalyshok FROM zamovlennia WHERE korystuvach_id = ? AND status = 'oplacheno' AND zalyshok > 0 ORDER BY oplacheno`, korystuvach_id);
  const zPidpysky = ps.reduce((s, p) => s + p.zalyshok, 0);
  const zPaketiv = pakety.reduce((s, z) => s + z.zalyshok, 0);
  const chastyny = [];
  if (zPidpysky) chastyny.push(`${zPidpysky} з підписки`);
  if (zPaketiv) chastyny.push(`${zPaketiv} з пакета «3 довідки»`);
  return { ps, pakety, opys: chastyny.join(', ') || 'немає' };
}

/**
 * Взяти довідку на будинок із кабінету: спершу підписка (ОСББ — лише на свій будинок), далі пакет.
 * Повертає { dovidka } або { dodatkova: pidpyska } (ліміт вичерпано — можна докупити по 99) або { kupyty: true }.
 */
export async function vzyatyDovidku(env, korystuvach_id, budynok, adresa) {
  const { ps, pakety } = await dostupno(env, korystuvach_id);
  for (const p of ps) {
    if (p.zalyshok > 0 && (p.tovar !== 'osbb' || p.budynok === budynok)) {
      return { dovidka: await postavytyDovidku(env, { korystuvach_id, zamovlennia_id: p.zamovlennia_id, pidpyska_id: p.id, budynok, adresa, rezhym: 'dovidka' }) };
    }
  }
  for (const z of pakety) {
    const r = await zrobyty(env, 'UPDATE zamovlennia SET zalyshok = zalyshok - 1 WHERE id = ? AND zalyshok > 0', z.id);
    if (r.meta?.changes) {
      return { dovidka: await postavytyDovidku(env, { korystuvach_id, zamovlennia_id: z.id, budynok, adresa, rezhym: 'dovidka' }) };
    }
  }
  const zDodatkovoiu = ps.find((p) => ['pidpyska', 'rieltor'].includes(p.tovar));
  return zDodatkovoiu ? { dodatkova: zDodatkovoiu } : { kupyty: true };
}

// ---------------------------------------------------------------- сповіщення про оплату

/**
 * Одна подія від перехідника. Перевірки: подія ще не оброблялась; замовлення є; сума й валюта — рівно ті, що в замовленні.
 * Повертає { ok, prychyna }.
 */
export async function obrobytyPodiiu(env, servis, p) {
  const t = teper(env);
  const zam = await odyn(env, 'SELECT * FROM zamovlennia WHERE id = ?', p.zamovlennia_id);
  const nove = await zrobyty(env, `INSERT OR IGNORE INTO spovishchennia (servis, kliuch, zamovlennia_id, status, suma, otrymano)
                                   VALUES (?, ?, ?, ?, ?, ?)`, servis, String(p.kliuch), zam ? zam.id : null, p.podiia, Math.round(Number(p.suma) * 100) || 0, t);
  if (!nove.meta?.changes) return { ok: true, prychyna: 'povtor' };
  if (!zam || zam.servis !== servis) return { ok: false, prychyna: 'nemaie_zamovlennia' };
  if (p.podiia === 'oplata' && (Number(p.suma) !== zam.suma || p.valiuta !== 'UAH')) {
    await zrobyty(env, 'UPDATE spovishchennia SET status = ? WHERE servis = ? AND kliuch = ?', 'suma_ne_ta', servis, String(p.kliuch));
    if (env.POSHTA_PARTNERA) await nadislaty(env, { komu: env.POSHTA_PARTNERA, tema: 'Оплата з іншою сумою', tekst: `Замовлення ${zam.id}: очікували ${zam.suma} UAH, сервіс повідомив ${p.suma} ${p.valiuta}. Нічого не видано.` });
    return { ok: false, prychyna: 'suma_ne_ta' };
  }
  const pidpyska = await odyn(env, 'SELECT * FROM pidpysky WHERE zamovlennia_id = ?', zam.id);

  if (p.podiia === 'oplata') {
    if (zam.status === 'stvoreno') {
      await zrobyty(env, `UPDATE zamovlennia SET status = 'oplacheno', oplacheno = ?, zalyshok = ? WHERE id = ? AND status = 'stvoreno'`,
        t, zam.tovar === 'try' ? TS.dovidok.try - 1 : 0, zam.id);
      await vydaty(env, zam, pidpyska, t);
      return { ok: true, prychyna: 'oplacheno' };
    }
    if (pidpyska && zam.status === 'oplacheno' && pidpyska.status !== 'skasovana') { // чергове списання підписки
      const dodo = dodatyMisiatsi(Math.max(pidpyska.diie_do || t, t), TS.period_misiatsiv[pidpyska.tovar]);
      await zrobyty(env, `UPDATE pidpysky SET status = 'aktyvna', pochatok = ?, diie_do = ? WHERE id = ?`, t, dodo, pidpyska.id);
      return { ok: true, prychyna: 'prodovzheno' };
    }
    return { ok: true, prychyna: 'vzhe_oplacheno' };
  }
  if (p.podiia === 'vidmova') {
    if (zam.status === 'stvoreno') await zrobyty(env, `UPDATE zamovlennia SET status = 'vidmova' WHERE id = ?`, zam.id);
    return { ok: true, prychyna: 'vidmova' };
  }
  if (p.podiia === 'povernennia') {
    await zrobyty(env, `UPDATE zamovlennia SET status = 'povernuto', zalyshok = 0 WHERE id = ?`, zam.id);
    if (pidpyska) await zrobyty(env, `UPDATE pidpysky SET status = 'skasovana', diie_do = ?, skasovano = ? WHERE id = ?`, t, t, pidpyska.id);
    return { ok: true, prychyna: 'povernuto' };
  }
  if (p.podiia === 'skasuvannia' && pidpyska) {
    await zrobyty(env, `UPDATE pidpysky SET status = 'skasovana', skasovano = COALESCE(skasovano, ?) WHERE id = ?`, t, pidpyska.id);
    return { ok: true, prychyna: 'skasovano' };
  }
  return { ok: true, prychyna: 'ignor' };
}

/** Оплачено → довідка в чергу генератора (і/або підписка активна). */
async function vydaty(env, zam, pidpyska, t) {
  const rezhym = TS.rezhym[zam.tovar] || 'dovidka';
  if (pidpyska) {
    await zrobyty(env, `UPDATE pidpysky SET status = 'aktyvna', pochatok = ?, diie_do = ? WHERE id = ?`,
      t, dodatyMisiatsi(t, TS.period_misiatsiv[pidpyska.tovar]), pidpyska.id);
    if (zam.budynok) {
      await postavytyDovidku(env, { korystuvach_id: zam.korystuvach_id, zamovlennia_id: zam.id, pidpyska_id: pidpyska.id, budynok: zam.budynok, adresa: zam.adresa, rezhym });
    }
    return;
  }
  if (zam.budynok) {
    await postavytyDovidku(env, { korystuvach_id: zam.korystuvach_id, zamovlennia_id: zam.id, budynok: zam.budynok, adresa: zam.adresa, rezhym });
  }
}

// ---------------------------------------------------------------- черга видавача

const ORENDA_S = 30 * 60;   // видавач не відзвітував за 30 хв — довідку можна брати знову
const SPROB = 3;

export async function vziatyZCherhy(env, n) {
  const t = teper(env);
  const ryadky = await vsi(env, `SELECT d.id, d.budynok, d.adresa, d.rezhym FROM dovidky d JOIN zamovlennia z ON z.id = d.zamovlennia_id
    WHERE z.status = 'oplacheno' AND d.sprob < ? AND (d.status = 'v_cherzi' OR (d.status = 'hotuietsia' AND d.vziato < ?))
    ORDER BY d.stvoreno LIMIT ?`, SPROB, t - ORENDA_S, n);
  const vziato = [];
  for (const r of ryadky) {
    const z = await zrobyty(env, `UPDATE dovidky SET status = 'hotuietsia', vziato = ?, sprob = sprob + 1 WHERE id = ? AND status IN ('v_cherzi', 'hotuietsia')`, t, r.id);
    if (z.meta?.changes) vziato.push(r);
  }
  return vziato;
}

export async function dovidkaHotova(env, id, html, adresaSaitu) {
  const d = await odyn(env, `SELECT d.*, k.poshta FROM dovidky d LEFT JOIN korystuvachi k ON k.id = d.korystuvach_id WHERE d.id = ?`, id);
  if (!d || d.status !== 'hotuietsia') return false;
  const kliuch = vypadkovyi(24);
  const fail = `dovidky/${d.id}-${vypadkovyi(10)}.html`;
  await env.DOVIDKY.put(fail, html, { httpMetadata: { contentType: 'text/html; charset=utf-8' } });
  await zrobyty(env, `UPDATE dovidky SET status = 'hotova', fail = ?, kliuch_hash = ?, hotovo = ? WHERE id = ?`, fail, sha256(kliuch), teper(env), id);
  if (d.poshta) {
    await nadislaty(env, {
      komu: d.poshta, tema: `${d.rezhym === 'povnyi' ? 'Повний звіт' : 'Довідка'}: ${d.adresa}`,
      tekst: `Готово: ${d.rezhym === 'povnyi' ? 'повний звіт' : 'довідка'} про будинок ${d.adresa}.\n\n` +
        `Відкрити: ${adresaSaitu}/dovidka/${d.id}/?k=${kliuch}\n\n` +
        `Посилання особисте — не пересилайте його. Усі довідки — також у кабінеті: ${adresaSaitu}/kabinet/\n` +
        'Це не оцінка безпеки: лише скарги мешканців і події з рішень судів, як їх записано.',
    });
  }
  return true;
}

export async function dovidkaPomylka(env, id) {
  const d = await odyn(env, 'SELECT * FROM dovidky WHERE id = ?', id);
  if (!d || d.status !== 'hotuietsia') return false;
  const ostannia = d.sprob >= SPROB;
  await zrobyty(env, 'UPDATE dovidky SET status = ? WHERE id = ?', ostannia ? 'pomylka' : 'v_cherzi', id);
  if (ostannia && env.POSHTA_PARTNERA) {
    await nadislaty(env, { komu: env.POSHTA_PARTNERA, tema: 'Довідку не вдалося зібрати', tekst: `Довідка ${id} (${d.adresa}): ${SPROB} спроби без успіху. Покупцю — повернення або повтор.` });
  }
  return true;
}

// ---------------------------------------------------------------- видалення даних на запит

/**
 * Видаляє пошту, сесії, «Стежу», файли довідок. Замовлення лишаються без прив'язки до людини (облік партнера:
 * сума, дата, товар). Активну підписку спершу скасовуємо в сервісі (робить маршрут кабінету).
 */
export async function vydalytyDani(env, korystuvach_id) {
  const faily = await vsi(env, 'SELECT fail FROM dovidky WHERE korystuvach_id = ? AND fail IS NOT NULL', korystuvach_id);
  for (const f of faily) await env.DOVIDKY.delete(f.fail);
  await zrobyty(env, `UPDATE dovidky SET korystuvach_id = NULL, fail = NULL, kliuch_hash = NULL, adresa = '', budynok = '' WHERE korystuvach_id = ?`, korystuvach_id);
  await zrobyty(env, 'UPDATE zamovlennia SET korystuvach_id = NULL, budynok = NULL, adresa = NULL WHERE korystuvach_id = ?', korystuvach_id);
  await zrobyty(env, 'UPDATE pidpysky SET korystuvach_id = NULL, budynok = NULL, adresa = NULL WHERE korystuvach_id = ?', korystuvach_id);
  await zrobyty(env, 'DELETE FROM stezhu WHERE korystuvach_id = ?', korystuvach_id);
  await zrobyty(env, 'DELETE FROM bali_rukh WHERE korystuvach_id = ?', korystuvach_id);   // бали ігор (ZAVDANNYA-123)
  await zrobyty(env, 'DELETE FROM sesii WHERE korystuvach_id = ?', korystuvach_id);
  await zrobyty(env, 'DELETE FROM vkhody WHERE korystuvach_id = ?', korystuvach_id);
  await zrobyty(env, 'DELETE FROM korystuvachi WHERE id = ?', korystuvach_id);
}

/** Щоденне прибирання (Cron Trigger): прострочені сесії й посилання входу; файли довідок старші за строк зберігання. */
export async function prybraty(env) {
  const t = teper(env);
  await zrobyty(env, 'DELETE FROM sesii WHERE do_ < ?', t);
  await zrobyty(env, 'DELETE FROM vkhody WHERE do_ < ?', t - 86400);
  const dniv = parseInt(env.DOVIDKY_DNIV || '365', 10);
  const stari = await vsi(env, 'SELECT id, fail FROM dovidky WHERE fail IS NOT NULL AND hotovo < ?', t - dniv * 86400);
  for (const d of stari) {
    await env.DOVIDKY.delete(d.fail);
    await zrobyty(env, `UPDATE dovidky SET fail = NULL, kliuch_hash = NULL, status = 'vydaleno' WHERE id = ?`, d.id);
  }
  return stari.length;
}

// ---------------------------------------------------------------- нагадування ОСББ (MV-155, П7; ZAVDANNYA-132)

export const NAHADATY_ZA_S = 3 * 86400;

/**
 * Щодня (той самий Cron Trigger): активним річним підпискам ОСББ, у яких період закінчується протягом 3 днів, — один лист
 * на кінець періоду (таблиця nahaduvannia). Скасовані не отримують: списання не буде. Повертає, скільки листів надіслано.
 */
export async function nahadatyOsbb(env, adresaSaitu) {
  const t = teper(env);
  const ps = await vsi(env, `SELECT p.id, p.adresa, p.diie_do, k.poshta FROM pidpysky p JOIN korystuvachi k ON k.id = p.korystuvach_id
    WHERE p.tovar = 'osbb' AND p.status = 'aktyvna' AND p.diie_do > ? AND p.diie_do <= ?
      AND NOT EXISTS (SELECT 1 FROM nahaduvannia n WHERE n.pidpyska_id = p.id AND n.diie_do = p.diie_do)`, t, t + NAHADATY_ZA_S);
  let n = 0;
  for (const p of ps) {
    const r = await zrobyty(env, 'INSERT OR IGNORE INTO nahaduvannia (pidpyska_id, diie_do, nadislano) VALUES (?, ?, ?)', p.id, p.diie_do, t);
    if (!r.meta?.changes) continue;
    try {
      await nadislaty(env, { komu: p.poshta, ...nahaduvanniaOsbb({ adresa: p.adresa, diie_do: p.diie_do, adresaSaitu }) });
      n++;
    } catch (err) {
      // Лист не пішов — прибираємо позначку, щоб завтра спробувати ще раз (до списання лишається ≥ 2 дні).
      await zrobyty(env, 'DELETE FROM nahaduvannia WHERE pidpyska_id = ? AND diie_do = ?', p.id, p.diie_do);
      console.log(`нагадування ОСББ: ${err.message}`);
    }
  }
  return n;
}
