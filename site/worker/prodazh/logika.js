// Правила продажу (ZAVDANNYA-99): замовлення, оплата, підписки, лічильник довідок, видача, видалення даних.
// База — Cloudflare D1 (env.BAZA), файли довідок — Cloudflare R2 (env.DOVIDKY). Схема — skhema.sql.
import { shturhnuty } from './vydavach.js';
import TS from './tsiny.js';
import { vypadkovyi, sha256 } from './bezpeka.js';
import { nadislaty } from './poshta.js';
import { budynok as zPachky } from '../budynky.js';
import { nahaduvanniaOsbb, oplatuOtrymano } from './lysty.js';

const dataT = (t) => { const d = new Date(t * 1000); return `${String(d.getUTCDate()).padStart(2, '0')}.${String(d.getUTCMonth() + 1).padStart(2, '0')}.${d.getUTCFullYear()}`; };

export const teper = (env) => (env.__CHAS ? env.__CHAS() : Math.floor(Date.now() / 1000));

const q = (env, sql, ...p) => env.BAZA.prepare(sql).bind(...p);
export const odyn = (env, sql, ...p) => q(env, sql, ...p).first();
export const vsi = async (env, sql, ...p) => (await q(env, sql, ...p).all()).results;
export const zrobyty = (env, sql, ...p) => q(env, sql, ...p).run();
/** Те саме, але таблиці, якої ще немає в старій базі (оновлення skhema-<N>.sql не виконано), не зупиняє дію. */
export async function zrobytyNovu(env, sql, ...p) {
  try { return await zrobyty(env, sql, ...p); } catch (err) {
    if (!/no such table/i.test(err.message)) throw err;
    console.log(`стара база без нової таблиці: ${err.message}`);
    return { meta: { changes: 0 } };
  }
}

export const PIDPYSKY = Object.keys(TS.period_misiatsiv);           // pidpyska, rieltor, osbb
const BEZ_BUDYNKU = ['pidpyska', 'rieltor', ...TS.sudova];          // будинок необов'язковий («Судова практика» — без будинку)
const SUDOVA = TS.sudova;                                            // spdovidka, spyurist (ZAVDANNYA-135)
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
  return m[1].replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&mdash;/g, '—').replace(/&ndash;/g, '–').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
}

export async function korystuvach(env, poshta) {
  await zrobyty(env, 'INSERT OR IGNORE INTO korystuvachi (poshta, stvoreno) VALUES (?, ?)', poshta, teper(env));
  return odyn(env, 'SELECT * FROM korystuvachi WHERE poshta = ?', poshta);
}

/**
 * Нове замовлення. Ціна — лише з таблиці цін (tsiny.js із site/tsiny.py); усе інше з форми ігнорується.
 * Повертає { zam, pidpyska } або { pomylka }.
 */
export async function stvorytyZamovlennia(env, { tovar, budynok, adresa, korystuvach_id, servis, pidpyska_id = null, parametry = null }) {
  const suma = TS.tsiny[tovar];
  if (!Number.isInteger(suma) || suma <= 0) return { pomylka: 'Такого товару немає.' };
  const id = 'z' + vypadkovyi(15);
  const t = teper(env);
  await zrobyty(env, `INSERT INTO zamovlennia (id, korystuvach_id, tovar, budynok, adresa, suma, servis, pidpyska_id, parametry, stvoreno)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`, id, korystuvach_id, tovar, budynok || null, adresa || null, suma, servis, pidpyska_id,
  parametry ? JSON.stringify(parametry) : null, t);
  let pidpyska = null;
  if (PIDPYSKY.includes(tovar)) {
    pidpyska = { id: 'p' + vypadkovyi(15), period_misiatsiv: TS.period_misiatsiv[tovar] };
    await zrobyty(env, `INSERT INTO pidpysky (id, korystuvach_id, tovar, budynok, adresa, zamovlennia_id, stvoreno)
                        VALUES (?, ?, ?, ?, ?, ?, ?)`, pidpyska.id, korystuvach_id, tovar, budynok || null, adresa || null, id, t);
  }
  return { zam: await odyn(env, 'SELECT * FROM zamovlennia WHERE id = ?', id), pidpyska };
}

/** Адреса сторінки будинку з того, що вставила людина: шлях «/budynok/…/…/» або повне посилання на сторінку (з будь-якого
 *  домену беремо лише шлях — будинок однаково перевіряє perevirytyBudynok). Без кінцевої «/» — додаємо. */
export function shliakhBudynku(t) {
  let s = String(t ?? '').trim();
  const m = s.match(/^https?:\/\/[^/]+(\/[^?#]*)/i);
  if (m) s = m[1];
  s = s.split(/[?#]/)[0];
  if (/^\/budynok\/[^/]+\/[^/]+$/.test(s)) s += '/';
  return s.slice(0, 200);
}

// ---------------------------------------------------------------- будинок словами (ZAVDANNYA-150, п. 6)
// ОСББ, рієлтор, «Стежу», пакет: людина пише адресу словами («Оболонський 16», «вул. Хрещатик, 22») — сервер шукає її
// у тому самому файлі пошуку будинків, що й «Мій будинок» (/vulytsi/budynky.json сайту). Посилання на сторінку — теж можна.

const normNazvy = (t) => String(t ?? '').toLowerCase().replace(/[ʼ’'`]/g, '').replace(/ґ/g, 'г').replace(/[-.,«»"]/g, ' ').replace(/\s+/g, ' ').trim();
const normNomera = (t) => String(t ?? '').toLowerCase().replace(/[\s-]/g, '').replace(/\\/g, '/');
const ADRESA = /^(.*?)[\s,]+(?:буд(?:инок)?\.?\s*)?(?:№\s*)?(\d+[^\s,]*(?:\s?[а-яіїєa-z])?)$/i;
let keshBudynkiv = null;        // { env, dani } — файл пошуку в пам'яті скрипта (один на версію сайту)

async function budynkyPoshuku(env, url) {
  if (keshBudynkiv && keshBudynkiv.env === env) return keshBudynkiv.dani;
  let dani = [];
  try {
    const r = await env.ASSETS.fetch(new Request(new URL('/vulytsi/budynky.json', url)));
    if (r && r.ok) dani = await r.json();
  } catch { dani = []; }
  keshBudynkiv = { env, dani };
  return dani;
}

/**
 * Будинок з того, що написала людина: посилання на сторінку або адреса словами.
 * Повертає { budynok, adresa } | { varianty: [{ budynok, adresa }] } (кілька вулиць підходять) | { nemaie: true }.
 */
export async function znaityBudynok(env, url, tekst) {
  const t = String(tekst ?? '').trim().slice(0, 200);
  if (!t) return { nemaie: true };
  if (/^(https?:\/\/|\/budynok\/)/i.test(t)) {
    const budynok = shliakhBudynku(t);
    const adresa = await perevirytyBudynok(env, budynok, url);
    return adresa ? { budynok, adresa } : { nemaie: true };
  }
  const m = ADRESA.exec(t);
  if (!m || !m[1].trim()) return { nemaie: true, bezNomera: true };
  const slova = normNazvy(m[1]).split(' ').filter(Boolean), nn = normNomera(m[2]);
  let vs = [];
  for (const [nazva, , stari, bs] of await budynkyPoshuku(env, url)) {
    const p = normNazvy(`${nazva} ${stari || ''}`);
    if (!slova.every((s) => p.includes(s))) continue;
    for (const [nomer, u] of bs) if (normNomera(nomer) === nn) vs.push({ budynok: u, adresa: `${nazva}, ${nomer}`, tochno: normNazvy(nazva) === normNazvy(m[1]) });
  }
  if (vs.length > 1 && vs.some((v) => v.tochno)) vs = vs.filter((v) => v.tochno);   // обрано з підказки — повна назва
  if (vs.length > 1) return { varianty: vs.slice(0, 6).map(({ budynok, adresa }) => ({ budynok, adresa })) };
  if (!vs.length) return { nemaie: true };
  const adresa = await perevirytyBudynok(env, vs[0].budynok, url);
  return adresa ? { budynok: vs[0].budynok, adresa } : { nemaie: true };
}

/** Що сказати людині, якщо будинок не знайшли (той самий текст у формі замовлення й кабінеті). */
export function chomuNeZnaideno(v) {
  if (v.varianty) return `Підходить кілька адрес: ${v.varianty.map((x) => x.adresa).join('; ')}. Оберіть одну з підказок або впишіть повну назву вулиці.`;
  if (v.bezNomera) return 'Додайте номер будинку: наприклад, «Оболонський 16».';
  return 'Такого будинку в наших даних немає: сторінка будинку є, лише коли є скарги 1551 чи події з рішень. Перевірте назву й номер — або оберіть із підказок.';
}

/** ZAVDANNYA-150, п. 3: скільки довідок людина може взяти на цей будинок без оплати (підписка, пакет «3 довідки»; ОСББ — лише свій будинок). */
export async function zalyshokNaBudynok(env, korystuvach_id, budynok) {
  const { ps, pakety } = await dostupno(env, korystuvach_id);
  return ps.filter((p) => p.tovar !== 'osbb' || p.budynok === budynok).reduce((s, p) => s + p.zalyshok, 0)
    + pakety.reduce((s, z) => s + z.zalyshok, 0);
}

export function potribenBudynok(tovar) {
  return !BEZ_BUDYNKU.includes(tovar);
}

// ---------------------------------------------------------------- довідки й лічильник

/**
 * Поставити довідку в чергу. mezha — з ліміту підписки ({ vid, dovidok }): довідка пишеться, лише якщо цього місяця підписки
 * взято менше за dovidok, — перевірка й запис одним реченням SQL (ZAVDANNYA-156: два одночасні запити не візьмуть 2 з 1).
 * Повертає номер довідки або null (ліміт уже вичерпано).
 */
export async function postavytyDovidku(env, { korystuvach_id, zamovlennia_id, pidpyska_id = null, budynok, adresa, rezhym, parametry = null, poshtovkh = true, mezha = null }) {
  const id = 'd' + vypadkovyi(15);
  const znach = [id, korystuvach_id, zamovlennia_id, pidpyska_id, budynok || '', adresa, rezhym,
    parametry ? (typeof parametry === 'string' ? parametry : JSON.stringify(parametry)) : null, teper(env)];
  const r = mezha
    ? await zrobyty(env, `INSERT INTO dovidky (id, korystuvach_id, zamovlennia_id, pidpyska_id, budynok, adresa, rezhym, parametry, stvoreno)
        SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?
        WHERE (SELECT COUNT(*) FROM dovidky WHERE pidpyska_id = ? AND stvoreno >= ? AND status != 'pomylka') < ?`,
      ...znach, pidpyska_id, mezha.vid, mezha.dovidok)
    : await zrobyty(env, `INSERT INTO dovidky (id, korystuvach_id, zamovlennia_id, pidpyska_id, budynok, adresa, rezhym, parametry, stvoreno)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`, ...znach);
  if (mezha && !r.meta?.changes) return null;
  if (poshtovkh) await shturhnuty(env, 'dovidka');      // видавач у GitHub Actions (ZAVDANNYA-133): довідку ставлять лише після оплати
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
    // Довідка, яку не вдалося зібрати (pomylka), ліміту не з'їдає (ZAVDANNYA-143): її можна взяти знову.
    const vziato = (await odyn(env, `SELECT COUNT(*) AS n FROM dovidky WHERE pidpyska_id = ? AND stvoreno >= ? AND status != 'pomylka'`, p.id, vid)).n;
    p.zalyshok = p.diie ? Math.max(0, TS.dovidok[p.tovar] - vziato) : 0;
    // ZAVDANNYA-143: межі поточного місяця підписки — для кабінету («нові 5 — з …», «наступна довідка ОСББ — …»)
    p.misiats_vid = vid;
    p.misiats_do = dodatyMisiatsi(p.pochatok, k);
    p.vziato = vziato;
    p.dovidok = TS.dovidok[p.tovar];
  }
  return ps;
}

/** Що можна взяти без оплати: довідки про будинок з підписки цього періоду і залишок пакетів «3 довідки».
 *  Підписка юриста («Судова практика») довідок про будинки не дає — її довідки беруться з /pidpysnyk/praktyka/. */
export async function dostupno(env, korystuvach_id) {
  const ps = (await stanPidpysok(env, korystuvach_id)).filter((p) => p.diie && !SUDOVA.includes(p.tovar));
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
      const rezhym = p.tovar === 'osbb' ? 'osbb' : 'dovidka';
      const id = await postavytyDovidku(env, { korystuvach_id, zamovlennia_id: p.zamovlennia_id, pidpyska_id: p.id, budynok, adresa, rezhym,
        mezha: { vid: p.misiats_vid, dovidok: p.dovidok } });
      if (id) return { dovidka: id };      // null — паралельний запит щойно взяв останню: пробуємо далі (пакет, докупити)
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

// Чергове списання раніше, ніж за стільки до кінця оплаченого періоду, — підозра на повтор першої оплати (ZAVDANNYA-156).
export const ZARANO_MIS_S = 10 * 86400, ZARANO_RIK_S = 30 * 86400;

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
      const r = await zrobyty(env, `UPDATE zamovlennia SET status = 'oplacheno', oplacheno = ?, zalyshok = ? WHERE id = ? AND status = 'stvoreno'`,
        t, zam.tovar === 'try' ? TS.dovidok.try - 1 : 0, zam.id);
      // ZAVDANNYA-156: дві різні події «оплачено» одночасно (LiqPay: «subscribed» і «success») — видає лише та, що
      // перша змінила статус; друга нічого не видає (раніше — дві довідки або подвійний початок підписки).
      if (!r.meta?.changes) return { ok: true, prychyna: 'vzhe_oplacheno' };
      await vydaty(env, zam, pidpyska, t);
      await lystOplaty(env, zam, pidpyska ? await odyn(env, 'SELECT diie_do FROM pidpysky WHERE id = ?', pidpyska.id) : null, t, false);
      return { ok: true, prychyna: 'oplacheno' };
    }
    if (pidpyska && zam.status === 'oplacheno' && pidpyska.status !== 'skasovana') { // чергове списання підписки
      // ZAVDANNYA-156: списання задовго до кінця оплаченого періоду — не продовження, а повтор першої оплати (LiqPay шле
      // «subscribed» і «success» на ту саму першу оплату). Не продовжуємо; партнер отримує лист і вирішує сам.
      const period = TS.period_misiatsiv[pidpyska.tovar];
      if (pidpyska.diie_do && t < pidpyska.diie_do - (period >= 12 ? ZARANO_RIK_S : ZARANO_MIS_S)) {
        await zrobyty(env, 'UPDATE spovishchennia SET status = ? WHERE servis = ? AND kliuch = ?', 'zarano', servis, String(p.kliuch));
        if (env.POSHTA_PARTNERA) {
          await nadislaty(env, { komu: env.POSHTA_PARTNERA, tema: 'Списання підписки раніше строку',
            tekst: `Замовлення ${zam.id}: сервіс повідомив оплату ${p.suma} UAH, а оплачений період триває до ${dataT(pidpyska.diie_do)}. ` +
              'Підписку не продовжено. Перевірте в кабінеті сервісу: це повтор першої оплати чи справжнє списання.' });
        }
        return { ok: true, prychyna: 'zarano' };
      }
      const dodo = dodatyMisiatsi(Math.max(pidpyska.diie_do || t, t), period);
      const r = await zrobyty(env, `UPDATE pidpysky SET status = 'aktyvna', pochatok = ?, diie_do = ? WHERE id = ? AND COALESCE(diie_do, 0) = ?`,
        t, dodo, pidpyska.id, pidpyska.diie_do || 0);
      if (r.meta?.changes) await lystOplaty(env, zam, { diie_do: dodo }, t, true);
      return { ok: true, prychyna: r.meta?.changes ? 'prodovzheno' : 'vzhe_prodovzheno' };
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

/** Лист «Оплату отримано» (ZAVDANNYA-161, п. 3). Не вдалося надіслати — оплату однаково зараховано, видачу не зупиняємо. */
async function lystOplaty(env, zam, pidpyska, t, prodovzhennia) {
  const k = zam.korystuvach_id ? await odyn(env, 'SELECT poshta FROM korystuvachi WHERE id = ?', zam.korystuvach_id) : null;
  if (!k?.poshta) return;
  try {
    await nadislaty(env, { komu: k.poshta, ...oplatuOtrymano({ zam, chas: t, diie_do: pidpyska?.diie_do ?? null, prodovzhennia,
      adresaSaitu: (env.ADRESA_SAITU || '').replace(/\/$/, ''), kontakt: env.POSHTA_KONTAKT || '' }) });
  } catch (err) { console.log(`лист «Оплату отримано» не пішов: ${err.message}`); }
}

/** Оплачено → довідка в чергу генератора (і/або підписка активна). «Судова практика»: довідка без будинку — з параметрами. */
async function vydaty(env, zam, pidpyska, t) {
  const rezhym = TS.rezhym[zam.tovar] || (zam.tovar === 'osbb' ? 'osbb' : 'dovidka');
  if (zam.tovar === 'spdovidka' && zam.parametry) {
    await postavytyDovidku(env, { korystuvach_id: zam.korystuvach_id, zamovlennia_id: zam.id, budynok: '', adresa: zam.adresa, rezhym, parametry: zam.parametry });
    return;
  }
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
  const ryadky = await vsi(env, `SELECT d.id, d.budynok, d.adresa, d.rezhym, d.parametry FROM dovidky d JOIN zamovlennia z ON z.id = d.zamovlennia_id
    WHERE z.status = 'oplacheno' AND d.sprob < ? AND (d.status = 'v_cherzi' OR (d.status = 'hotuietsia' AND d.vziato < ?))
    ORDER BY d.stvoreno LIMIT ?`, SPROB, t - ORENDA_S, n);
  const vziato = [];
  for (const r of ryadky) {
    if (r.parametry) r.parametry = JSON.parse(r.parametry); else delete r.parametry;
    const z = await zrobyty(env, `UPDATE dovidky SET status = 'hotuietsia', vziato = ?, sprob = sprob + 1 WHERE id = ? AND status IN ('v_cherzi', 'hotuietsia')`, t, r.id);
    if (z.meta?.changes) vziato.push(r);
  }
  return vziato;
}

/**
 * ZAVDANNYA-172 (ZVIT-167, п. 9): перший висновок довідки («Головне», <ol class="holovne"> генератора dani-edrsr/src/zvit/)
 * одним рядком для листа — щоб у листі було головне число, а не лише посилання. Немає блоку — порожньо (лист як раніше).
 */
export function holovneZDovidky(html) {
  const m = String(html || '').match(/<ol class="holovne">\s*<li>([\s\S]*?)<\/li>/);
  if (!m) return '';
  const t = m[1].replace(/<[^>]*>/g, ' ').replace(/&nbsp;|&#160;/g, '\u00a0').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;|&#x27;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, ' ').replace(/\s([.,;:])/g, '$1').trim();
  return t.length > 300 ? `${t.slice(0, t.lastIndexOf(' ', 297))}…` : t;
}

export async function dovidkaHotova(env, id, html, adresaSaitu) {
  const d = await odyn(env, `SELECT d.*, k.poshta FROM dovidky d LEFT JOIN korystuvachi k ON k.id = d.korystuvach_id WHERE d.id = ?`, id);
  if (!d || d.status !== 'hotuietsia') return false;
  const kliuch = vypadkovyi(24);
  const fail = `dovidky/${d.id}-${vypadkovyi(10)}.html`;
  await env.DOVIDKY.put(fail, html, { httpMetadata: { contentType: 'text/html; charset=utf-8' } });
  await zrobyty(env, `UPDATE dovidky SET status = 'hotova', fail = ?, kliuch_hash = ?, hotovo = ? WHERE id = ?`, fail, sha256(kliuch), teper(env), id);
  if (d.poshta && d.rezhym === 'sp') {
    await nadislaty(env, {
      komu: d.poshta, tema: `Судова практика: ${d.adresa}`,
      tekst: `Готово: довідка «Як закінчуються такі справи» — ${d.adresa}.\n\n` +
        `Відкрити: ${adresaSaitu}/dovidka/${d.id}/?k=${kliuch}\n\n` +
        `Посилання особисте — не пересилайте його. Усі довідки — також у кабінеті: ${adresaSaitu}/kabinet/\n` +
        'Це статистика минулих рішень, а не юридична допомога і не відповідь, чим закінчиться конкретна справа.',
    });
  } else if (d.poshta && d.rezhym === 'osbb') {
    // ZAVDANNYA-143: щомісячна довідка ОСББ (генератор --osbb) — приходить сама щомісяця
    await nadislaty(env, {
      komu: d.poshta, tema: `Щомісячна довідка для ОСББ: ${d.adresa}`,
      tekst: `Готово: щомісячна довідка про будинок ${d.adresa} — звернення мешканців до 1551 за останній місяць і за рік, ` +
        `порівняння з сусідніми будинками, події з рішень судів.\n\n` +
        `Відкрити: ${adresaSaitu}/dovidka/${d.id}/?k=${kliuch}\n\n` +
        `Наступна прийде сама через місяць. Усі довідки — у кабінеті: ${adresaSaitu}/kabinet/\n` +
        'Посилання особисте — не пересилайте його. Це не оцінка безпеки: лише скарги мешканців і події з рішень судів, як їх записано.',
    });
  } else if (d.poshta) {
    const r = d.pidpyska_id ? (await stanPidpysok(env, d.korystuvach_id)).find((p) => p.id === d.pidpyska_id && p.tovar === 'rieltor') : null;
    // ZAVDANNYA-172 (ZVIT-167, п. 9): лічильник — на момент ЦІЄЇ довідки (довідки місяця, взяті не пізніше за неї), а не на
    // момент надсилання листа: інакше три листи поспіль казали «лишилось 1».
    let zalyshok = '';
    if (r) {
      const do_ = (await odyn(env, `SELECT COUNT(*) AS n FROM dovidky WHERE pidpyska_id = ? AND stvoreno >= ? AND status != 'pomylka'
        AND (stvoreno < ? OR (stvoreno = ? AND rowid <= (SELECT rowid FROM dovidky WHERE id = ?)))`, r.id, r.misiats_vid, d.stvoreno, d.stvoreno, d.id)).n;
      zalyshok = `З підписки рієлтора цього місяця лишилось довідок: ${Math.max(0, r.dovidok - do_)} з ${r.dovidok} (нові — з ${dataT(r.misiats_do)}). ` +
        `Усі ваші об'єкти — у кабінеті, «Мої об'єкти».\n`;
    }
    const holovne = holovneZDovidky(html);
    await nadislaty(env, {
      komu: d.poshta, tema: `${d.rezhym === 'povnyi' ? 'Повний звіт' : 'Довідка'}: ${d.adresa}`,
      tekst: `Готово: ${d.rezhym === 'povnyi' ? 'повний звіт' : 'довідка'} про будинок ${d.adresa}.\n\n` +
        (holovne ? `Головне: ${holovne}\n\n` : '') +
        `Відкрити: ${adresaSaitu}/dovidka/${d.id}/?k=${kliuch}\n\n` +
        `Посилання особисте — не пересилайте його. Усі довідки — також у кабінеті: ${adresaSaitu}/kabinet/\n` + zalyshok +
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
  // ZAVDANNYA-172 (ZVIT-167): довідки в черзі знімаються — без адреси видавач падав на них тричі, а партнер отримував лист про невдачу
  await zrobyty(env, `UPDATE dovidky SET status = 'vydaleno' WHERE korystuvach_id = ? AND status IN ('v_cherzi', 'hotuietsia')`, korystuvach_id);
  await zrobyty(env, `UPDATE dovidky SET korystuvach_id = NULL, fail = NULL, kliuch_hash = NULL, adresa = '', budynok = '' WHERE korystuvach_id = ?`, korystuvach_id);
  await zrobyty(env, 'UPDATE zamovlennia SET korystuvach_id = NULL, budynok = NULL, adresa = NULL WHERE korystuvach_id = ?', korystuvach_id);
  await zrobyty(env, 'UPDATE pidpysky SET korystuvach_id = NULL, budynok = NULL, adresa = NULL WHERE korystuvach_id = ?', korystuvach_id);
  await zrobyty(env, 'DELETE FROM stezhu WHERE korystuvach_id = ?', korystuvach_id);
  await zrobyty(env, 'DELETE FROM lysty_stezhu WHERE korystuvach_id = ?', korystuvach_id);   // щомісячний лист «Стежу» (ZAVDANNYA-150)
  await zrobyty(env, 'DELETE FROM bali_rukh WHERE korystuvach_id = ?', korystuvach_id);   // бали ігор (ZAVDANNYA-123)
  await zrobytyNovu(env, 'DELETE FROM karta_zavantazhennia WHERE korystuvach_id = ?', korystuvach_id);   // ліміт карти (ZAVDANNYA-161)
  await zrobyty(env, 'DELETE FROM sp_vyvantazhennia WHERE korystuvach_id = ?', korystuvach_id);
  await zrobyty(env, 'DELETE FROM sesii WHERE korystuvach_id = ?', korystuvach_id);
  await zrobyty(env, 'DELETE FROM vkhody WHERE korystuvach_id = ?', korystuvach_id);
  await zrobyty(env, 'DELETE FROM korystuvachi WHERE id = ?', korystuvach_id);
}

/** Що зникне, якщо людина видалить дані (ZAVDANNYA-172, ZVIT-167 п. 1): для сторінки підтвердження. */
export async function shchoZnykne(env, korystuvach_id) {
  const n = async (q) => (await odyn(env, q, korystuvach_id)).n;
  const dovidok = await n(`SELECT COUNT(*) AS n FROM dovidky WHERE korystuvach_id = ? AND status != 'vydaleno'`);
  const vCherzi = await n(`SELECT COUNT(*) AS n FROM dovidky WHERE korystuvach_id = ? AND status IN ('v_cherzi', 'hotuietsia')`);
  const stezhu = await n('SELECT COUNT(*) AS n FROM stezhu WHERE korystuvach_id = ?');
  const { ps, pakety } = await dostupno(env, korystuvach_id);
  const pidpysky = (await stanPidpysok(env, korystuvach_id)).filter((p) => p.diie);
  return { dovidok, vCherzi, stezhu, pidpysky, zalyshok: ps.reduce((x, p) => x + p.zalyshok, 0) + pakety.reduce((x, z) => x + z.zalyshok, 0) };
}

/** Щоденне прибирання (Cron Trigger): прострочені сесії й посилання входу; файли довідок старші за строк зберігання. */
export async function prybraty(env) {
  const t = teper(env);
  await zrobyty(env, 'DELETE FROM sesii WHERE do_ < ?', t);
  await zrobyty(env, 'DELETE FROM vkhody WHERE do_ < ?', t - 86400);
  const tyzhdenTomu = new Date((t - 7 * 86400) * 1000).toISOString().slice(0, 10);   // лічильники лімітів — лише свіжі
  await zrobytyNovu(env, 'DELETE FROM karta_zavantazhennia WHERE den < ?', tyzhdenTomu);
  await zrobyty(env, 'DELETE FROM sp_vyvantazhennia WHERE den < ?', tyzhdenTomu);
  const dniv = parseInt(env.DOVIDKY_DNIV || '365', 10);
  const stari = await vsi(env, 'SELECT id, fail FROM dovidky WHERE fail IS NOT NULL AND hotovo < ?', t - dniv * 86400);
  for (const d of stari) {
    await env.DOVIDKY.delete(d.fail);
    await zrobyty(env, `UPDATE dovidky SET fail = NULL, kliuch_hash = NULL, status = 'vydaleno' WHERE id = ?`, d.id);
  }
  return stari.length;
}

// ---------------------------------------------------------------- стирання за строками (ZAVDANNYA-161, п. 4; MV-173)

export const NEZAVERSHENE_S = 30 * 86400;       // пошта без жодної покупки (лише незавершені замовлення) — 30 днів
export const ZVERNENNIA_S = 365 * 86400;        // звернення — 1 рік після відповіді (політика, розд. 5)
export const ZAIAVKY_S = 183 * 86400;           // передзамовлення й «скоро» — пів року після запуску (політика, розд. 5)
const KYIV = /ки[їі]в|kyiv|kiev/i;

/**
 * Коли запущено продаж: змінна DATA_ZAPUSKU (РРРР-ММ-ДД) або, без неї, перша справжня оплата (не тестова й не за бали).
 * null — продажу ще не було (режим «скоро»): тоді заявки до запуску не стираються.
 */
export async function chasZapusku(env) {
  const z = String(env.DATA_ZAPUSKU || '').trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(z)) return Math.floor(Date.parse(`${z}T00:00:00Z`) / 1000);
  const r = await odyn(env, `SELECT MIN(oplacheno) AS t FROM zamovlennia WHERE oplacheno IS NOT NULL AND servis NOT IN ('test', 'bali')`);
  return r?.t ?? null;
}

/**
 * Щодня (той самий розклад, що й prybraty; і в режимі «скоро», бо форми пишуться й тоді). Повертає, скільки стерто.
 *  • пошта людини, яка нічого не купила: усі її замовлення незавершені й старші за 30 днів, немає підписки, довідок,
 *    «Стежу», балів і входу за 30 днів — людину стираємо як «Видалити мої дані»; незавершені замовлення лишаються без пошти;
 *  • звернення — через рік після відповіді (zakryto); без відповіді не стираються — партнер ще має відповісти;
 *  • «скоро» — через пів року після листа про запуск (napysano) або після запуску продажу, якщо товар уже продається;
 *  • передзамовлення із заглушки (Київ) — через пів року після запуску; інше місто — лише вручну, коли запустимо там.
 *  Що створено вже після запуску — пів року від створення.
 */
export async function styratyZaStrokom(env) {
  const t = teper(env);
  const v = { korystuvachi: 0, zvernennya: 0, skoro: 0, zayavka: 0 };
  if (env.PRODAZH === 'tak') {
    const mezha = t - NEZAVERSHENE_S;
    const ludy = await vsi(env, `SELECT k.id FROM korystuvachi k WHERE k.stvoreno < ?
      AND NOT EXISTS (SELECT 1 FROM zamovlennia z WHERE z.korystuvach_id = k.id AND (z.status IN ('oplacheno', 'povernuto') OR z.stvoreno >= ?))
      AND NOT EXISTS (SELECT 1 FROM pidpysky p WHERE p.korystuvach_id = k.id AND p.status <> 'ochikuie')
      AND NOT EXISTS (SELECT 1 FROM dovidky d WHERE d.korystuvach_id = k.id)
      AND NOT EXISTS (SELECT 1 FROM stezhu s WHERE s.korystuvach_id = k.id)
      AND NOT EXISTS (SELECT 1 FROM bali_rukh b WHERE b.korystuvach_id = k.id)
      AND NOT EXISTS (SELECT 1 FROM sesii s WHERE s.korystuvach_id = k.id AND s.do_ > ?)
      AND NOT EXISTS (SELECT 1 FROM vkhody x WHERE x.korystuvach_id = k.id AND x.do_ >= ?)
      ORDER BY k.id LIMIT 500`, mezha, mezha, t, mezha);
    for (const k of ludy) await vydalytyDani(env, k.id);
    v.korystuvachi = ludy.length;
  }
  v.zvernennya = (await zrobyty(env, 'DELETE FROM zvernennya WHERE zakryto IS NOT NULL AND zakryto < ?', t - ZVERNENNIA_S)).meta?.changes ?? 0;
  v.skoro = (await zrobyty(env, 'DELETE FROM skoro WHERE napysano IS NOT NULL AND napysano < ?', t - ZAIAVKY_S)).meta?.changes ?? 0;
  const zapusk = await chasZapusku(env);
  if (zapusk !== null && t - zapusk > ZAIAVKY_S) {
    const tovary = TS.prodaietsia;
    v.skoro += (await zrobyty(env, `DELETE FROM skoro WHERE tovar IN (${tovary.map(() => '?').join(', ')}) AND MAX(stvoreno, ?) < ?`,
      ...tovary, zapusk, t - ZAIAVKY_S)).meta?.changes ?? 0;
    const kyiv = await vsi(env, 'SELECT id, misto FROM zayavka WHERE MAX(stvoreno, ?) < ?', zapusk, t - ZAIAVKY_S);
    for (const z of kyiv.filter((x) => KYIV.test(x.misto))) {
      v.zayavka += (await zrobyty(env, 'DELETE FROM zayavka WHERE id = ?', z.id)).meta?.changes ?? 0;
    }
  }
  if (v.korystuvachi + v.zvernennya + v.skoro + v.zayavka) console.log(`стерто за строком: ${JSON.stringify(v)}`);
  return v;
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

// ---------------------------------------------------------------- «Судова практика»: довідка з підписки юриста (ZAVDANNYA-135)

/** Довідка «стаття × суд» з ліміту підписки юриста (3 на місяць). -> { dovidka } або { vycherpano: true } або { nemaie: true }. */
export async function vzyatySpDovidku(env, korystuvach_id, { parametry, opys }) {
  const p = (await stanPidpysok(env, korystuvach_id)).find((x) => x.diie && x.tovar === 'spyurist');
  if (!p) return { nemaie: true };
  if (p.zalyshok <= 0) return { vycherpano: true };
  const id = await postavytyDovidku(env, { korystuvach_id, zamovlennia_id: p.zamovlennia_id, pidpyska_id: p.id, budynok: '', adresa: opys, rezhym: 'sp', parametry,
    mezha: { vid: p.misiats_vid, dovidok: p.dovidok } });
  return id ? { dovidka: id } : { vycherpano: true };
}

// ---------------------------------------------------------------- щомісячна довідка ОСББ (ZAVDANNYA-143; MV-140, S-Зв.5 dani-edrsr)

/**
 * Щодня (той самий Cron Trigger, що й нагадування): кожній чинній підписці ОСББ, у якої в поточному місяці підписки ще немає
 * довідки, — поставити щомісячну довідку свого будинку (режим osbb, генератор --osbb). Перший місяць — довідка з оплати;
 * далі — сама, щомісяця, без жодної дії правління. Скасована, але ще оплачена — теж отримує (рік оплачено).
 * Один поштовх видавачу на всіх. Повертає, скільки довідок поставлено.
 */
export async function shchomisiachnaOsbb(env) {
  const ids = await vsi(env, `SELECT DISTINCT korystuvach_id AS k FROM pidpysky WHERE tovar = 'osbb' AND status IN ('aktyvna', 'skasovana')
    AND diie_do > ? AND korystuvach_id IS NOT NULL AND budynok IS NOT NULL`, teper(env));
  let n = 0;
  for (const { k } of ids) {
    for (const p of await stanPidpysok(env, k)) {
      if (p.tovar !== 'osbb' || !p.diie || p.zalyshok <= 0 || !p.budynok) continue;
      // Цього місяця вже була спроба, що не вдалася, — не ставимо щодня знову: партнер отримав лист і вирішує сам.
      if ((await odyn(env, 'SELECT COUNT(*) AS n FROM dovidky WHERE pidpyska_id = ? AND stvoreno >= ?', p.id, p.misiats_vid)).n) continue;
      await postavytyDovidku(env, { korystuvach_id: k, zamovlennia_id: p.zamovlennia_id, pidpyska_id: p.id, budynok: p.budynok,
        adresa: p.adresa, rezhym: 'osbb', poshtovkh: false });
      n++;
    }
  }
  if (n) await shturhnuty(env, 'osbb');
  return n;
}
