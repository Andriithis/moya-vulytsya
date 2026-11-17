// Сервер продажу «Моєї вулиці» (ZAVDANNYA-99) — маршрути. Вмикається змінною PRODAZH = 'tak'; без неї ці адреси
// віддають статичний сайт як раніше (сторінка «Оплата скоро»). Як увімкнути — docs/PRODAZH-SERVER.md.
//
//   GET  /oplata/?tovar=…&budynok=…      форма замовлення (ціна — з таблиці)
//   POST /api/zamovlennia                  створити замовлення → платіжний сервіс
//   GET  /oplata/test/<id>/                тестова оплата (лише PLATIZHNYI_SERVIS=test і TESTOVA_OPLATA=tak)
//   POST /api/spovishchennia/<сервіс>      підписане сповіщення про оплату → перевірка підпису й суми → видача
//   GET  /oplata/dyakuiemo/                «дякуємо»
//   GET  /dovidka/<id>/?k=<ключ>           довідка: ключ із листа або вхід у кабінет власника
//   /kabinet/…                             вхід за посиланням на пошту, мої довідки, «Стежу», підписка, видалення даних
//   /api/vnutr/…                           для видавача (site/prodazh/vydavach.py), заголовок Authorization: Bearer VYDACHA_KLIUCH
//   POST /api/admin/vydalyty               видалення даних на запит людини (партнер), Authorization: Bearer ADMIN_KLIUCH
import TS from './tsiny.js';
import { vypadkovyi, sha256, rivni } from './bezpeka.js';
import { perekhidnyk, pidpysTestu, PomylkaPidpysu, NePidtrymano } from './perekhidnyky.js';
import { nadislaty } from './poshta.js';
import * as L from './logika.js';
import * as S from './storinky.js';

export const MARSHRUTY = ['/oplata/*', '/api/*', '/kabinet/*', '/dovidka/*', '/prodazh/*'];
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
  if (!TS.na_prodazh.includes(tovar)) return pereity(url, tovar === 'biznes' ? '/biznes/' : '/miy-budynok/');
  const budynok = url.searchParams.get('budynok');
  const adresa = budynok ? await L.perevirytyBudynok(env, budynok, url) : null;
  return S.formaZamovlennia({ tovar, budynok: adresa ? budynok : null, adresa });
}

async function stvorytyZamovlennia(request, env, url) {
  if (!zNashohoSaitu(request, env)) return S.povidomlennia('Не вдалося', 'Оформіть замовлення на нашому сайті.', 403);
  const f = await forma(request);
  const tovar = String(f.tovar || '');
  if (!TS.na_prodazh.includes(tovar)) return S.povidomlennia('Не вдалося', 'Такого товару немає.', 400);
  const poshta = L.chystaPoshta(f.poshta);
  let budynok = f.budynok ? String(f.budynok) : null, adresa = null;
  if (budynok) {
    adresa = await L.perevirytyBudynok(env, budynok, url);
    if (!adresa) return S.povidomlennia('Не вдалося', 'Такого будинку на сайті немає.', 400);
  } else if (L.potribenBudynok(tovar)) {
    return S.formaZamovlennia({ tovar, budynok: null, adresa: null });
  }
  if (!poshta) return S.formaZamovlennia({ tovar, budynok, adresa, pomylka: 'Перевірте пошту.' });
  if (f.zghoda !== 'tak') return S.formaZamovlennia({ tovar, budynok, adresa, pomylka: 'Потрібна згода з офертою.' });
  return doOplaty(env, url, { tovar, budynok, adresa, poshta });
}

async function doOplaty(env, url, { tovar, budynok, adresa, poshta, korystuvach_id, pidpyska_id }) {
  const p = perekhidnyk(env);
  if (!p) return S.povidomlennia('Оплата недоступна', 'Оплата тимчасово не працює. Спробуйте пізніше.', 503);
  const k = korystuvach_id ?? (await L.korystuvach(env, poshta)).id;
  const { zam, pidpyska, pomylka } = await L.stvorytyZamovlennia(env, { tovar, budynok, adresa, korystuvach_id: k, servis: p.nazva, pidpyska_id });
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
  if (!zNashohoSaitu(request, env)) return S.vkhid('Відкрийте кабінет на нашому сайті.');
  const poshta = L.chystaPoshta((await forma(request)).poshta);
  const vidpovid = S.vkhid('Якщо ця пошта є в нас, посилання для входу вже в листі. Перевірте й «Спам».');
  if (!poshta) return S.vkhid('Перевірте пошту.');
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
  if (!v || v.vykorystano || v.do_ < zaraz) return S.vkhid('Посилання застаріло або вже використане. Надішлемо нове.');
  const r = await L.zrobyty(env, 'UPDATE vkhody SET vykorystano = ? WHERE hash = ? AND vykorystano IS NULL', zaraz, v.hash);
  if (!r.meta?.changes) return S.vkhid('Посилання вже використане.');
  const s = vypadkovyi(32);
  await L.zrobyty(env, 'INSERT INTO sesii (hash, korystuvach_id, do_) VALUES (?, ?, ?)', sha256(s), v.korystuvach_id, zaraz + SESIIA_S);
  return pereity(url, '/kabinet/', { 'set-cookie': `mv_sesiia=${s}; Path=/; Max-Age=${SESIIA_S}; HttpOnly; Secure; SameSite=Lax` });
}

async function kabinet(env, ja, povidomlennia = '') {
  const dovidky = await L.vsi(env, 'SELECT id, adresa, rezhym, status, stvoreno FROM dovidky WHERE korystuvach_id = ? ORDER BY stvoreno DESC', ja.id);
  const stezhu = await L.vsi(env, 'SELECT budynok, adresa FROM stezhu WHERE korystuvach_id = ? ORDER BY stvoreno', ja.id);
  const d = await L.dostupno(env, ja.id);
  const pidpysky = (await L.stanPidpysok(env, ja.id)).filter((p) => p.diie);
  return S.kabinet({ poshta: ja.poshta, dovidky, stezhu, pidpysky, dostupno: d, povidomlennia });
}

async function diiaKabinetu(request, env, url, ja, dia) {
  const f = await forma(request);
  if (dia === 'stezhu' || dia === 'dovidka') {
    const adresa = await L.perevirytyBudynok(env, f.budynok, url);
    if (!adresa) return kabinet(env, ja, 'Такого будинку на сайті немає. Скопіюйте адресу його сторінки: /budynok/…/…/');
    if (dia === 'stezhu') {
      await L.zrobyty(env, 'INSERT OR IGNORE INTO stezhu (korystuvach_id, budynok, adresa, stvoreno) VALUES (?, ?, ?, ?)', ja.id, f.budynok, adresa, L.teper(env));
      return kabinet(env, ja, `Стежите: ${adresa}.`);
    }
    const v = await L.vzyatyDovidku(env, ja.id, f.budynok, adresa);
    if (v.dovidka) return kabinet(env, ja, `Довідку на ${adresa} готуємо — посилання прийде на пошту.`);
    if (v.dodatkova) return doOplaty(env, url, { tovar: 'dodatkova', budynok: f.budynok, adresa, korystuvach_id: ja.id, pidpyska_id: v.dodatkova.id });
    return pereity(url, `/oplata/?tovar=dovidka&budynok=${encodeURIComponent(f.budynok)}`);
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

/** Відповідь сервера продажу або null (тоді — звичайний сайт). */
export async function prodazh(request, env) {
  if (env.PRODAZH !== 'tak') return null;
  const url = new URL(request.url);
  const s = url.pathname;
  const m = request.method;
  if (s === '/prodazh/prodazh.css') return new Response(S.CSS, { headers: { 'content-type': 'text/css; charset=utf-8', 'cache-control': 'public, max-age=3600' } });
  if (s === '/oplata/' && m === 'GET') return formaZamovlennia(request, env, url);
  if (s === '/oplata/dyakuiemo/' && m === 'GET') return S.dyakuiemo();
  let r = s.match(/^\/oplata\/test\/(z[a-z2-7]+)\/$/);
  if (r && m === 'GET') return testovaOplata(env, r[1]);
  if (s === '/api/zamovlennia' && m === 'POST') return stvorytyZamovlennia(request, env, url);
  r = s.match(/^\/api\/spovishchennia\/([a-z]+)$/);
  if (r && m === 'POST') return spovishchennia(request, env, r[1]);
  r = s.match(/^\/api\/vnutr\/(.+)$/);
  if (r) return vnutr(request, env, url, r[1]);
  r = s.match(/^\/api\/admin\/(.+)$/);
  if (r) return admin(request, env, r[1]);
  r = s.match(/^\/dovidka\/(d[a-z2-7]+)\/?$/);
  if (r && m === 'GET') return vidkrytyDovidku(request, env, url, r[1]);
  if (s === '/kabinet/vkhid' && m === 'POST') return nadislatyVkhid(request, env, url);
  if (s === '/kabinet/vkhid/' && m === 'GET') return uviity(request, env, url);
  if (s.startsWith('/kabinet/')) {
    const ja = await sesiia(request, env);
    if (s === '/kabinet/' && m === 'GET') return ja ? kabinet(env, ja) : S.vkhid();
    if (m === 'POST') {
      if (!ja) return pereity(url, '/kabinet/');
      if (!zNashohoSaitu(request, env)) return S.povidomlennia('Не вдалося', 'Дію можна зробити лише з нашого сайту.', 403);
      return diiaKabinetu(request, env, url, ja, s.slice('/kabinet/'.length));
    }
  }
  if (s.startsWith('/api/')) return new Response('ні', { status: 404 });
  return null;
}
