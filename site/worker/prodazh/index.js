// Сервер продажу «Моєї вулиці» (ZAVDANNYA-99) — маршрути. Змінна PRODAZH (ZAVDANNYA-132 — один перемикач):
//   'tak'   — справжній продаж (оплата, кабінет, довідки) + форми сайту;
//   'skoro' — оплату не підключено: /oplata/ — «Скоро — залиште пошту» (пошта + товар + будинок у базу), форми сайту;
//   інше    — ці адреси віддають статичний сайт як раніше (сторінка «Оплата скоро»).
// Як увімкнути — docs/ZAPUSK-SAITU.md, docs/PRODAZH-SERVER.md.
//
//   POST /api/skoro                        заявка «скоро» (лише PRODAZH = 'skoro')
//   POST /api/forma/<zayavka|zvernennya|podiya>   форми заглушки й чотири числа (JSON, як у Supabase) — 'skoro' і 'tak'
//   GET  /api/admin/vyvantazhennia/<таблиця>      CSV для партнера, Authorization: Bearer ADMIN_KLIUCH
//   POST /api/admin/perevirka                       прибрати тестові рядки щоденної перевірки форм (канал «perevirka»), той самий ключ
//
//   GET  /oplata/?tovar=…&budynok=…      форма замовлення (ціна — з таблиці)
//   POST /api/zamovlennia                  створити замовлення → платіжний сервіс
//   GET  /oplata/test/<id>/                тестова оплата (лише PLATIZHNYI_SERVIS=test і TESTOVA_OPLATA=tak)
//   POST /api/spovishchennia/<сервіс>      підписане сповіщення про оплату → перевірка підпису й суми → видача
//   GET  /oplata/dyakuiemo/                «дякуємо»
//   GET  /dovidka/<id>/?k=<ключ>           довідка: ключ із листа або вхід у кабінет власника
//   /kabinet/…                             вхід за посиланням на пошту, мої довідки, «Стежу», підписка, видалення даних
//   GET  /kabinet/google/…                 вхід через Google — лише з GOOGLE_KLIIENT_ID і GOOGLE_SEKRET (google.js, ZAVDANNYA-142)
//   /api/vnutr/…                           для видавача (site/prodazh/vydavach.py), заголовок Authorization: Bearer VYDACHA_KLIUCH
//   POST /kabinet/obmin                    обмін балів ігор на довідку / місяць підписки — лише з OBMIN_BALIV = 'tak' (ZAVDANNYA-123)
//   /pidpysnyk/…                          карта підписника зі сховища R2 — лише з дійсною підпискою (karta.js, ZAVDANNYA-133)
//   POST /api/admin/vydalyty               видалення даних на запит людини (партнер), Authorization: Bearer ADMIN_KLIUCH
import TS from './tsiny.js';
import { vypadkovyi, sha256, rivni } from './bezpeka.js';
import { perekhidnyk, pidpysTestu, PomylkaPidpysu, NePidtrymano } from './perekhidnyky.js';
import { nadislaty } from './poshta.js';
import * as L from './logika.js';
import * as S from './storinky.js';
import * as B from './bali.js';
import * as F from './formy.js';
import * as K from './karta.js';
import * as SP from './sudova.js';
import * as G from './google.js';

export const MARSHRUTY = ['/oplata/*', '/api/*', '/kabinet/*', '/dovidka/*', '/prodazh/*', '/pidpysnyk/*'];
const SESIIA_S = 30 * 86400, VKHID_S = 30 * 60, LYSTIV_NA_HODYNU = 5;

const adresaSaitu = (env, url) => (env.ADRESA_SAITU || new URL(url).origin).replace(/\/$/, '');
const pereity = (url, kudy, zaholovky = {}) => new Response(null, { status: 303, headers: { location: new URL(kudy, url).toString(), ...zaholovky } });

function kuky(request) {
  const k = {};
  for (const ch of (request.headers.get('cookie') || '').split(';')) {
    const i = ch.indexOf('=');
    if (i > 0) k[ch.slice(0, i).trim()] = ch.slice(i + 1).trim();
  }
  return k;
}

async function sesiia(request, env) {
  const s = kuky(request).mv_sesiia;
  if (!s) return null;
  return L.odyn(env, `SELECT k.* FROM sesii s JOIN korystuvachi k ON k.id = s.korystuvach_id WHERE s.hash = ? AND s.do_ > ?`, sha256(s), L.teper(env));
}

/** Форми кабінету й замовлення — лише з нашого сайту (захист від підробки запиту з чужої сторінки). */
function zNashohoSaitu(request, env) {
  const o = request.headers.get('origin');
  return !!o && o === new URL(adresaSaitu(env, request.url)).origin;
}

async function forma(request) {
  try { return Object.fromEntries(await request.formData()); } catch { return {}; }
}

// ---------------------------------------------------------------- замовлення й оплата

async function formaZamovlennia(request, env, url) {
  const tovar = url.searchParams.get('tovar');
  if (!TS.prodaietsia.includes(tovar)) return pereity(url, tovar === 'biznes' ? '/biznes/' : '/miy-budynok/');
  if (tovar === 'spdovidka') {
    return SP.formaDovidky({ d: await SP.dovidnyk(env, url), slug: url.searchParams.get('stattia') || '',
      sud: url.searchParams.get('sud') || '', chastyna: url.searchParams.get('chastyna') || '' });
  }
  const budynok = url.searchParams.get('budynok');
  const adresa = budynok ? await L.perevirytyBudynok(env, budynok, url) : null;
  return S.formaZamovlennia({ tovar, budynok: adresa ? budynok : null, adresa, ...(await vkhidGoogle(request, env)) });
}

/** Для форми замовлення (ZAVDANNYA-142): пошта з сесії (після входу через Google) і чи показувати кнопку Google. */
async function vkhidGoogle(request, env) {
  const ja = await sesiia(request, env);
  return { poshtaSesii: ja?.poshta || '', google: G.uvimkneno(env) && !ja };
}

async function stvorytyZamovlennia(request, env, url) {
  if (!zNashohoSaitu(request, env)) return S.povidomlennia('Не вдалося', 'Оформіть замовлення на нашому сайті.', 403);
  const f = await forma(request);
  const tovar = String(f.tovar || '');
  if (!TS.prodaietsia.includes(tovar)) return S.povidomlennia('Не вдалося', 'Такого товару немає.', 400);
  const poshta = L.chystaPoshta(f.poshta);
  if (tovar === 'spdovidka') {
    // «Судова практика»: стаття, суд і частина — лише з довідника сайту; опис вибору пише сервер, а не форма
    const v = await SP.perevirytyParametry(env, url, f);
    if (!v) return S.povidomlennia('Не вдалося', 'Такої статті, суду чи частини немає. Оберіть зі списку.', 400);
    const znovu = async (pomylka) => SP.formaDovidky({ d: await SP.dovidnyk(env, url), slug: v.slug, sud: v.parametry.sud, chastyna: v.parametry.chastyna, pomylka });
    if (!poshta) return znovu('Перевірте пошту.');
    if (f.zghoda !== 'tak') return znovu('Потрібна згода з офертою.');
    if (f.ne_dopomoga !== 'tak') return znovu('Позначте, що розумієте: це статистика, а не юридична допомога.');
    if (f.odrazu !== 'tak') return znovu('Позначте: «Прошу надіслати одразу…» — без цього оплатити не можна.');
    return doOplaty(env, url, { tovar, budynok: null, adresa: v.opys, poshta, parametry: v.parametry });
  }
  let budynok = f.budynok ? L.shliakhBudynku(f.budynok) : null, adresa = null;
  if (budynok) {
    adresa = await L.perevirytyBudynok(env, budynok, url);
    if (!adresa) return S.formaZamovlennia({ tovar, budynok: null, adresa: null, pomylka: 'Такого будинку на сайті немає. Вставте посилання на сторінку будинку з нашого сайту.' });
  } else if (L.potribenBudynok(tovar)) {
    return S.formaZamovlennia({ tovar, budynok: null, adresa: null });
  }
  if (!poshta) return S.formaZamovlennia({ tovar, budynok, adresa, pomylka: 'Перевірте пошту.' });
  if (f.zghoda !== 'tak') return S.formaZamovlennia({ tovar, budynok, adresa, pomylka: 'Потрібна згода з офертою.' });
  if (f.odrazu !== 'tak') return S.formaZamovlennia({ tovar, budynok, adresa, pomylka: 'Позначте: «Прошу надіслати одразу…» — без цього оплатити не можна.' });
  return doOplaty(env, url, { tovar, budynok, adresa, poshta });
}

async function doOplaty(env, url, { tovar, budynok, adresa, poshta, korystuvach_id, pidpyska_id, parametry = null }) {
  const p = perekhidnyk(env);
  if (!p) return S.povidomlennia('Оплата недоступна', 'Оплата тимчасово не працює. Спробуйте пізніше.', 503);
  const k = korystuvach_id ?? (await L.korystuvach(env, poshta)).id;
  const { zam, pidpyska, pomylka } = await L.stvorytyZamovlennia(env, { tovar, budynok, adresa, korystuvach_id: k, servis: p.nazva, pidpyska_id, parametry });
  if (pomylka) return S.povidomlennia('Не вдалося', pomylka, 400);
  try {
    const v = await p.stvoryty({ zam, pidpyska, opys: `${TS.nazvy[tovar]}${adresa ? `: ${adresa}` : ''} — Моя вулиця`, adresa: adresaSaitu(env, url), env });
    return v.forma ? S.formaServisu(v.forma) : pereity(url, v.pereity);
  } catch (err) {
    if (err instanceof NePidtrymano) return S.povidomlennia('Не вдалося', err.message, 501);
    console.log(`оплата: ${err.message}`);
    return S.povidomlennia('Не вдалося', 'Платіжний сервіс не відповів. Спробуйте ще раз за хвилину.', 502);
  }
}

async function testovaOplata(env, id) {
  if (!perekhidnyk(env, 'test') || env.PLATIZHNYI_SERVIS !== 'test') return S.nemaie();
  const zam = await L.odyn(env, 'SELECT * FROM zamovlennia WHERE id = ?', id);
  if (!zam) return S.nemaie();
  const chas = String(L.teper(env));
  const knopky = [['oplata', 'Оплата пройшла'], ['vidmova', 'Відмова']];
  if (zam.status === 'oplacheno') {
    if (TS.period_misiatsiv[zam.tovar]) knopky.push(['oplata', 'Списання наступного періоду']);
    knopky.push(['povernennia', 'Повернення']);
  }
  const polia = knopky.map(([podiia, napys], i) => {
    const p = { zamovlennia: zam.id, suma: String(zam.suma), podiia, chas: `${chas}-${i}` };
    return { ...p, napys, pidpys: pidpysTestu(env, p) };
  });
  return S.testovaOplata(zam, polia);
}

async function spovishchennia(request, env, servis) {
  const p = perekhidnyk(env, servis);
  if (!p) return new Response('ні', { status: 404 });
  let v;
  try {
    v = await p.perevirka(request, env);
  } catch (err) {
    if (err instanceof PomylkaPidpysu) {
      console.log(`сповіщення ${servis}: підпис не той — нічого не змінено`);
      return new Response('pidpys', { status: 403 });
    }
    console.log(`сповіщення ${servis}: ${err.message}`);
    return new Response('pomylka', { status: 400 });
  }
  let ok = true;
  for (const podiia of v.podii) ok = (await L.obrobytyPodiiu(env, servis, podiia)).ok && ok;
  return v.vidpovid({ ok });
}

// ---------------------------------------------------------------- довідка

async function vidkrytyDovidku(request, env, url, id) {
  const d = await L.odyn(env, 'SELECT * FROM dovidky WHERE id = ?', id);
  const k = url.searchParams.get('k');
  let svoia = false;
  if (d) {
    if (k && d.kliuch_hash && rivni(sha256(k), d.kliuch_hash)) svoia = true;
    else {
      const ja = await sesiia(request, env);
      svoia = !!ja && d.korystuvach_id === ja.id;
    }
  }
  if (!svoia) return S.nemaie();     // і «немає», і «чужа» — однаково, щоб не вгадувати номери
  if (d.status !== 'hotova' || !d.fail) return S.povidomlennia('Готується', 'Довідка ще готується — посилання прийде на пошту.');
  const o = await env.DOVIDKY.get(d.fail);
  if (!o) return S.nemaie();
  return new Response(o.body, {
    headers: {
      'content-type': 'text/html; charset=utf-8', 'cache-control': 'private, no-store', 'x-robots-tag': 'noindex, nofollow',
      'referrer-policy': 'no-referrer', 'x-content-type-options': 'nosniff', 'x-frame-options': 'DENY',
      // Довідка — один файл із вбудованими стилями, скриптом і картинками (генератор dani-edrsr/src/zvit), без зовнішніх ресурсів.
      'content-security-policy': "default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; font-src data:; frame-ancestors 'none'; form-action 'none'",
    },
  });
}

// ---------------------------------------------------------------- кабінет

async function nadislatyVkhid(request, env, url) {
  if (!zNashohoSaitu(request, env)) return S.vkhid('Відкрийте кабінет на нашому сайті.', G.uvimkneno(env));
  const poshta = L.chystaPoshta((await forma(request)).poshta);
  const vidpovid = S.vkhid('Якщо ця пошта є в нас, посилання для входу вже в листі. Перевірте й «Спам».', G.uvimkneno(env));
  if (!poshta) return S.vkhid('Перевірте пошту.', G.uvimkneno(env));
  const k = await L.odyn(env, 'SELECT * FROM korystuvachi WHERE poshta = ?', poshta);
  if (!k) return vidpovid;   // не кажемо, чи є така пошта
  const t = L.teper(env);
  const n = (await L.odyn(env, 'SELECT COUNT(*) AS n FROM vkhody WHERE korystuvach_id = ? AND do_ > ?', k.id, t + VKHID_S - 3600)).n;
  if (n >= LYSTIV_NA_HODYNU) return vidpovid;
  const kliuch = vypadkovyi(24);
  await L.zrobyty(env, 'INSERT INTO vkhody (hash, korystuvach_id, do_) VALUES (?, ?, ?)', sha256(kliuch), k.id, t + VKHID_S);
  await nadislaty(env, {
    komu: poshta, tema: 'Вхід у кабінет «Моєї вулиці»',
    tekst: `Посилання для входу (діє 30 хвилин, один раз):\n${adresaSaitu(env, url)}/kabinet/vkhid/?t=${kliuch}\n\nЯкщо ви не просили — нічого не робіть.`,
  });
  return vidpovid;
}

async function uviity(request, env, url) {
  const t = url.searchParams.get('t') || '';
  const zaraz = L.teper(env);
  const v = await L.odyn(env, 'SELECT * FROM vkhody WHERE hash = ?', sha256(t));
  if (!v || v.vykorystano || v.do_ < zaraz) return S.vkhid('Посилання застаріло або вже використане. Надішлемо нове.', G.uvimkneno(env));
  const r = await L.zrobyty(env, 'UPDATE vkhody SET vykorystano = ? WHERE hash = ? AND vykorystano IS NULL', zaraz, v.hash);
  if (!r.meta?.changes) return S.vkhid('Посилання вже використане.', G.uvimkneno(env));
  const s = vypadkovyi(32);
  await L.zrobyty(env, 'INSERT INTO sesii (hash, korystuvach_id, do_) VALUES (?, ?, ?)', sha256(s), v.korystuvach_id, zaraz + SESIIA_S);
  return pereity(url, '/kabinet/', { 'set-cookie': `mv_sesiia=${s}; Path=/; Max-Age=${SESIIA_S}; HttpOnly; Secure; SameSite=Lax` });
}

const novaSesiia = async (env, korystuvach_id) => {
  const s = vypadkovyi(32);
  await L.zrobyty(env, 'INSERT INTO sesii (hash, korystuvach_id, do_) VALUES (?, ?, ?)', sha256(s), korystuvach_id, L.teper(env) + SESIIA_S);
  return `mv_sesiia=${s}; Path=/; Max-Age=${SESIIA_S}; HttpOnly; Secure; SameSite=Lax`;
};

/** Вхід через Google (google.js): початок і повернення. Без ключів — «сторінки немає». */
async function google(request, env, url) {
  if (!G.uvimkneno(env)) return S.nemaie();
  const adresa = adresaSaitu(env, url);
  if (url.pathname === '/kabinet/google/') return G.pochaty(env, url, adresa);
  if (url.pathname !== '/kabinet/google/povernennia/') return S.nemaie();
  const v = await G.povernennia(env, url, adresa, kuky(request)[G.KUKA]);
  if (v.pomylka) {
    const r = S.vkhid(v.pomylka, true, 400);
    r.headers.append('set-cookie', G.STERTY_KUKU);
    return r;
  }
  const h = new Headers({ location: new URL(v.kudy, url).toString(), 'cache-control': 'no-store' });
  h.append('set-cookie', await novaSesiia(env, v.korystuvach_id));
  h.append('set-cookie', G.STERTY_KUKU);
  return new Response(null, { status: 303, headers: h });
}

async function kabinet(env, ja, povidomlennia = '') {
  const dovidky = await L.vsi(env, 'SELECT id, budynok, adresa, rezhym, status, pidpyska_id, stvoreno FROM dovidky WHERE korystuvach_id = ? ORDER BY stvoreno DESC', ja.id);
  const stezhu = await L.vsi(env, 'SELECT budynok, adresa FROM stezhu WHERE korystuvach_id = ? ORDER BY stvoreno', ja.id);
  const d = await L.dostupno(env, ja.id);
  const pidpysky = (await L.stanPidpysok(env, ja.id)).filter((p) => p.diie);
  for (const p of pidpysky) p.zaBali = (await L.odyn(env, 'SELECT servis FROM zamovlennia WHERE id = ?', p.zamovlennia_id))?.servis === 'bali';
  const bali = B.uvimkneno(env) ? { balans: await B.balans(env, ja.id), kurs: B.KURS, zapyt: vypadkovyi(16) } : null;
  return S.kabinet({ poshta: ja.poshta, dovidky, stezhu, pidpysky, dostupno: d, povidomlennia, bali });
}

async function diiaKabinetu(request, env, url, ja, dia) {
  const f = await forma(request);
  if (f.budynok) f.budynok = L.shliakhBudynku(f.budynok);      // ZAVDANNYA-143: можна вставити й повне посилання на сторінку
  if (dia === 'stezhu' || dia === 'dovidka') {
    const adresa = await L.perevirytyBudynok(env, f.budynok, url);
    if (!adresa) return kabinet(env, ja, 'Такого будинку на сайті немає. Скопіюйте адресу його сторінки: /budynok/…/…/');
    if (dia === 'stezhu') {
      await L.zrobyty(env, 'INSERT OR IGNORE INTO stezhu (korystuvach_id, budynok, adresa, stvoreno) VALUES (?, ?, ?, ?)', ja.id, f.budynok, adresa, L.teper(env));
      return kabinet(env, ja, `Стежите: ${adresa}.`);
    }
    const v = await L.vzyatyDovidku(env, ja.id, f.budynok, adresa);
    if (v.dovidka) return kabinet(env, ja, `Довідку на ${adresa} готуємо — посилання прийде на пошту.`);
    if (v.dodatkova && f.odrazu !== 'tak') return S.pidtverdytyDodatkovu({ budynok: f.budynok, adresa });   // MV-155, П6
    if (v.dodatkova) return doOplaty(env, url, { tovar: 'dodatkova', budynok: f.budynok, adresa, korystuvach_id: ja.id, pidpyska_id: v.dodatkova.id });
    return pereity(url, `/oplata/?tovar=dovidka&budynok=${encodeURIComponent(f.budynok)}`);
  }
  if (dia === 'obmin') {
    if (!B.uvimkneno(env)) return S.nemaie();
    // Користувач — лише з сесії (ja.id); korystuvach_id чи пошта з форми не читаються взагалі.
    let budynok = null, adresa = null;
    if (f.tovar === 'dovidka') {
      budynok = String(f.budynok || '');
      adresa = await L.perevirytyBudynok(env, budynok, url);
      if (!adresa) return kabinet(env, ja, 'Для довідки за бали оберіть будинок зі списку «Стежу».');
    }
    const v = await B.obminiaty(env, ja.id, { tovar: String(f.tovar || ''), budynok, adresa, zapyt: f.zapyt });
    if (!v.ok) return kabinet(env, ja, v.chomu);
    if (v.povtor) return kabinet(env, ja, 'Цей обмін уже зроблено.');
    return kabinet(env, ja, v.dovidka ? `Обміняно: довідку на ${adresa} готуємо — посилання прийде на пошту.` : 'Обміняно: місяць підписки діє з сьогодні.');
  }
  if (dia === 'stezhu/prybraty') {
    await L.zrobyty(env, 'DELETE FROM stezhu WHERE korystuvach_id = ? AND budynok = ?', ja.id, String(f.budynok || ''));
    return kabinet(env, ja, 'Прибрано.');
  }
  if (dia === 'skasuvaty') {
    const p = await L.odyn(env, `SELECT * FROM pidpysky WHERE id = ? AND korystuvach_id = ? AND status = 'aktyvna'`, String(f.pidpyska || ''), ja.id);
    if (!p) return kabinet(env, ja, 'Такої підписки немає.');
    const zam = await L.odyn(env, 'SELECT * FROM zamovlennia WHERE id = ?', p.zamovlennia_id);
    const servis = perekhidnyk(env, zam.servis);
    let ok = false;
    try { ok = servis ? await servis.skasuvaty({ zamovlennia_id: zam.id, env }) : false; } catch (err) { console.log(`скасування: ${err.message}`); }
    if (!ok) return kabinet(env, ja, 'Платіжний сервіс не підтвердив скасування. Спробуйте ще раз або напишіть партнеру — скасуємо вручну.');
    await L.zrobyty(env, `UPDATE pidpysky SET status = 'skasovana', skasovano = ? WHERE id = ?`, L.teper(env), p.id);
    return kabinet(env, ja, `Підписку скасовано. Нових списань не буде; доступ — до ${S.data(p.diie_do)}.`);
  }
  if (dia === 'vyhid') {
    await L.zrobyty(env, 'DELETE FROM sesii WHERE hash = ?', sha256(kuky(request).mv_sesiia || ''));
    return pereity(url, '/kabinet/', { 'set-cookie': 'mv_sesiia=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax' });
  }
  if (dia === 'vydalyty' && f.pidtverdzhuiu === 'tak') {
    if (!(await skasuvatyVsi(env, ja.id))) return kabinet(env, ja, 'Спершу треба скасувати підписку, а сервіс не відповів. Спробуйте ще раз.');
    await L.vydalytyDani(env, ja.id);
    return S.storinka('Дані видалено', `<section class="zaholovok"><h1>Дані видалено</h1>
<p>Пошту, довідки, адреси «Стежу» й вхід видалено. Записи про оплату (сума, дата, товар) партнер зберігає для обліку — без пошти.</p></section>`,
    { zaholovky: { 'set-cookie': 'mv_sesiia=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax' } });
  }
  return S.nemaie();
}

// ---------------------------------------------------------------- «Судова практика»: довідка з підписки юриста

async function spDovidkaZPidpysky(request, env, url) {
  const ja = await sesiia(request, env);
  if (!ja) return pereity(url, '/kabinet/');
  if (!zNashohoSaitu(request, env)) return S.povidomlennia('Не вдалося', 'Дію можна зробити лише з нашого сайту.', 403);
  const v = await SP.perevirytyParametry(env, url, await forma(request));
  if (!v) return S.povidomlennia('Не вдалося', 'Такої статті, суду чи частини немає. Оберіть зі списку.', 400);
  const r = await L.vzyatySpDovidku(env, ja.id, v);
  if (r.nemaie) return pereity(url, SP.KOREN);
  if (r.vycherpano) {
    return S.povidomlennia('Довідки цього місяця використано', `Можна купити окрему довідку — ${S.tsina('spdovidka')}.`, 200,
      `<div class="diyi"><a class="knopka knopka--holovna" href="/oplata/?tovar=spdovidka&amp;stattia=${S.e(v.slug)}">Купити довідку</a><a class="knopka" href="${SP.KOREN}">Назад до практики</a></div>`);
  }
  return kabinet(env, ja, `Довідку «${v.opys}» готуємо — посилання прийде на пошту.`);
}

// ---------------------------------------------------------------- для видавача

async function vnutr(request, env, url, shliakh) {
  const avt = (request.headers.get('authorization') || '').replace(/^Bearer /, '');
  if (!env.VYDACHA_KLIUCH || !rivni(avt, env.VYDACHA_KLIUCH)) return new Response('ні', { status: 401 });
  if (shliakh === 'cherha' && request.method === 'GET') {
    const n = Math.min(10, Math.max(1, parseInt(url.searchParams.get('n') || '1', 10) || 1));
    return Response.json({ dovidky: await L.vziatyZCherhy(env, n) });
  }
  let m = shliakh.match(/^dovidka\/(d[a-z2-7]+)$/);
  if (m && request.method === 'PUT') {
    const html = await request.text();
    if (!html.startsWith('<!') || html.length > 30 * 1024 * 1024) return new Response('ne html', { status: 400 });
    return new Response(null, { status: (await L.dovidkaHotova(env, m[1], html, adresaSaitu(env, url))) ? 204 : 409 });
  }
  m = shliakh.match(/^pomylka\/(d[a-z2-7]+)$/);
  if (m && request.method === 'POST') return new Response(null, { status: (await L.dovidkaPomylka(env, m[1])) ? 204 : 409 });
  return new Response('ні', { status: 404 });
}

// ---------------------------------------------------------------- для партнера: видалення на запит

async function skasuvatyVsi(env, korystuvach_id) {
  for (const p of (await L.stanPidpysok(env, korystuvach_id)).filter((x) => x.status === 'aktyvna')) {
    const zam = await L.odyn(env, 'SELECT * FROM zamovlennia WHERE id = ?', p.zamovlennia_id);
    let ok = false;
    try { ok = await perekhidnyk(env, zam.servis)?.skasuvaty({ zamovlennia_id: zam.id, env }); } catch { ok = false; }
    if (!ok) return false;
    await L.zrobyty(env, `UPDATE pidpysky SET status = 'skasovana', skasovano = ? WHERE id = ?`, L.teper(env), p.id);
  }
  return true;
}

async function admin(request, env, shliakh) {
  const avt = (request.headers.get('authorization') || '').replace(/^Bearer /, '');
  if (!env.ADMIN_KLIUCH || !rivni(avt, env.ADMIN_KLIUCH)) return new Response('ні', { status: 401 });
  const v = shliakh.match(/^vyvantazhennia\/([a-z]+)$/);
  if (v && request.method === 'GET') return F.vyvantazhennia(env, v[1]);
  // щоденна перевірка форм прибирає свої тестові рядки (лише канал «perevirka»)
  if (shliakh === 'perevirka' && request.method === 'POST') return Response.json({ prybrano: await F.prybratyPerevirku(env) });
  if (shliakh === 'vydalyty' && request.method === 'POST') {
    const poshta = L.chystaPoshta((await forma(request)).poshta);
    const k = poshta && await L.odyn(env, 'SELECT * FROM korystuvachi WHERE poshta = ?', poshta);
    if (!k) return Response.json({ vydaleno: false, prychyna: 'takoi poshty nemaie' });
    if (!(await skasuvatyVsi(env, k.id))) return Response.json({ vydaleno: false, prychyna: 'servis ne skasuvav pidpysku' }, { status: 502 });
    await L.vydalytyDani(env, k.id);
    return Response.json({ vydaleno: true });
  }
  return new Response('ні', { status: 404 });
}

// ---------------------------------------------------------------- вхід

// ---------------------------------------------------------------- «скоро» і форми (ZAVDANNYA-132)

async function skoroForma(env, url) {
  const tovar = url.searchParams.get('tovar') || '';
  if (tovar === 'biznes') return pereity(url, '/biznes/');
  if (!F.TOVARY_SKORO.includes(tovar)) return pereity(url, '/miy-budynok/');
  const budynok = url.searchParams.get('budynok');
  const adresa = budynok ? await L.perevirytyBudynok(env, budynok, url) : null;
  return S.skoro({ tovar, nazva: tovar === 'sudova' ? F.NAZVA_SUDOVA : TS.nazvy[tovar], budynok: adresa ? budynok : null, adresa,
                   kanal: F.kanal(url.searchParams.get('dzherelo')), kabinet: env.PRODAZH === 'tak' });
}

async function skoroZapys(request, env, url) {
  if (!zNashohoSaitu(request, env)) return S.povidomlennia('Не вдалося', 'Залиште пошту на нашому сайті.', 403);
  const f = await forma(request);
  const v = await F.zapysatySkoro(env, url, f);
  if (v.ok) return pereity(url, '/oplata/dyakuiemo/');
  const tovar = F.TOVARY_SKORO.includes(String(f.tovar)) ? String(f.tovar) : null;
  if (!tovar) return S.povidomlennia('Не вдалося', v.pomylka, 400);
  const adresa = f.budynok ? await L.perevirytyBudynok(env, String(f.budynok), url) : null;
  return S.skoro({ tovar, nazva: tovar === 'sudova' ? F.NAZVA_SUDOVA : TS.nazvy[tovar], budynok: adresa ? String(f.budynok) : null,
                   adresa, kanal: F.kanal(f.dzherelo), pomylka: v.pomylka, kabinet: env.PRODAZH === 'tak' });
}

/** Спільне для 'skoro' і 'tak': стилі сторінок, форми сайту, вивантаження для партнера. Null — не наша адреса. */
async function spilne(request, env, url) {
  const s = url.pathname;
  if (s === '/prodazh/prodazh.css') return new Response(S.CSS, { headers: { 'content-type': 'text/css; charset=utf-8', 'cache-control': 'public, max-age=3600' } });
  const r = s.match(/^\/api\/forma\/([a-z]+)$/);
  if (r && request.method === 'POST') {
    if (!zNashohoSaitu(request, env)) return new Response('ні', { status: 403 });
    return F.forma(request, env, r[1]);
  }
  const a = s.match(/^\/api\/admin\/(.+)$/);
  if (a) return admin(request, env, a[1]);
  return null;
}

/** Відповідь сервера продажу або null (тоді — звичайний сайт). */
export async function prodazh(request, env) {
  if (env.PRODAZH !== 'tak' && env.PRODAZH !== 'skoro') return null;
  const url = new URL(request.url);
  const s = url.pathname;
  const m = request.method;
  const sp = await spilne(request, env, url);
  if (sp) return sp;
  if (env.PRODAZH === 'skoro') {
    if (s === '/oplata/' && m === 'GET') return skoroForma(env, url);
    if (s === '/api/skoro' && m === 'POST') return skoroZapys(request, env, url);
    if (s === '/oplata/dyakuiemo/' && m === 'GET') return S.skoroDyakuiemo();
    if (s.startsWith('/api/')) return new Response('ні', { status: 404 });
    return null;     // кабінет, довідки, тестова оплата — у режимі «скоро» їх немає (звичайний сайт, 404)
  }
  // Товари, яких ще немає в продажу («Судова практика»), — «Скоро — залиште пошту» і з увімкненою оплатою.
  const tovar = url.searchParams.get('tovar');
  if (s === '/oplata/' && m === 'GET' && F.TOVARY_SKORO.includes(tovar) && !TS.prodaietsia.includes(tovar)) return skoroForma(env, url);
  if (s === '/api/skoro' && m === 'POST') return skoroZapys(request, env, url);
  if (s === '/oplata/' && m === 'GET') return formaZamovlennia(request, env, url);
  if (s === '/oplata/dyakuiemo/' && m === 'GET') return S.dyakuiemo();
  let r = s.match(/^\/oplata\/test\/(z[a-z2-7]+)\/$/);
  if (r && m === 'GET') return testovaOplata(env, r[1]);
  if (s === '/api/zamovlennia' && m === 'POST') return stvorytyZamovlennia(request, env, url);
  r = s.match(/^\/api\/spovishchennia\/([a-z]+)$/);
  if (r && m === 'POST') return spovishchennia(request, env, r[1]);
  r = s.match(/^\/api\/vnutr\/(.+)$/);
  if (r) return vnutr(request, env, url, r[1]);
  r = s.match(/^\/dovidka\/(d[a-z2-7]+)\/?$/);
  if (r && m === 'GET') return vidkrytyDovidku(request, env, url, r[1]);
  if (s === '/kabinet/vkhid' && m === 'POST') return nadislatyVkhid(request, env, url);
  if (s === '/kabinet/vkhid/' && m === 'GET') return uviity(request, env, url);
  if (s.startsWith('/kabinet/google/') && m === 'GET') return google(request, env, url);
  if (s.startsWith('/kabinet/')) {
    const ja = await sesiia(request, env);
    if (s === '/kabinet/' && m === 'GET') return ja ? kabinet(env, ja) : S.vkhid('', G.uvimkneno(env));
    if (m === 'POST') {
      if (!ja) return pereity(url, '/kabinet/');
      if (!zNashohoSaitu(request, env)) return S.povidomlennia('Не вдалося', 'Дію можна зробити лише з нашого сайту.', 403);
      return diiaKabinetu(request, env, url, ja, s.slice('/kabinet/'.length));
    }
  }
  if (s === `${SP.KOREN}dovidka` && m === 'POST') return spDovidkaZPidpysky(request, env, url);
  if (s.startsWith(SP.KOREN.slice(0, -1))) {
    const r = await SP.praktyka(request, env, url, await sesiia(request, env));
    if (r) return r;
  }
  if (s === '/pidpysnyk' || s.startsWith('/pidpysnyk/')) {
    const k = await K.karta(request, env, url, await sesiia(request, env));
    if (k) return k;
  }
  if (s.startsWith('/api/')) return new Response('ні', { status: 404 });
  return null;
}
