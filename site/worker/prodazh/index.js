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
//   GET  /oplata/dyakuiemo/?z=…            «дякуємо» — текст за товаром замовлення (ZAVDANNYA-172)
//   GET  /oplata/zapysaly/                 «Записали» після «скоро — залиште пошту» (обидва режими)
//   GET  /dovidka/<id>/?k=<ключ>           довідка: ключ із листа або вхід у кабінет власника
//   /kabinet/…                             вхід за посиланням на пошту (посилання → сторінка з кнопкою «Увійти» → POST /kabinet/vkhid/uviity), мої довідки, «Стежу», підписка, видалення даних
//   GET  /kabinet/google/…                 вхід через Google — лише з GOOGLE_KLIIENT_ID і GOOGLE_SEKRET (google.js, ZAVDANNYA-142)
//   /api/vnutr/…                           для видавача (site/prodazh/vydavach.py), заголовок Authorization: Bearer VYDACHA_KLIUCH
//   POST /kabinet/obmin                    обмін балів ігор на довідку / місяць підписки — лише з OBMIN_BALIV = 'tak' (ZAVDANNYA-123)
//   /pidpysnyk/…                          карта підписника зі сховища R2 — лише з дійсною підпискою (karta.js, ZAVDANNYA-133)
//   POST /api/admin/vydalyty               видалення даних на запит людини (партнер), Authorization: Bearer ADMIN_KLIUCH
//   /kabinet/zvernennia/                   кабінет звернень партнера (пошта з PARTNERY або POSHTA_PARTNERA): прибрати подію одразу,
//                                          закрити звернення, журнал прибраних (prybrannia.js, ZAVDANNYA-161, п. 5)
//   POST /api/admin/prybraty-podiyu, povernuty-podiyu; GET /api/admin/prybrani  — те саме для скриптів, ключ ADMIN_KLIUCH
//   GET  /api/vnutr/prybrani               список прибраних рішень для видавача й збирання даних (ключ VYDACHA_KLIUCH)
//   POST /api/forma/biznes                 запит «Для бізнесу» зі сторінки /biznes/ — 'skoro' і 'tak' (biznes.js, ZAVDANNYA-157)
//   /api/admin/biznes/…                    клієнти «Для бізнесу», посилання на N днів, вимкнення — ADMIN_KLIUCH (biznes.js)
//   GET  /kopiia/<ключ>/…                  копія бази для компанії за особистим посиланням — 'skoro' і 'tak' (biznes.js)
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
import * as ST from './stezhu.js';
import * as PR from './prybrannia.js';
import * as BZ from './biznes.js';

export const MARSHRUTY = ['/oplata/*', '/api/*', '/kabinet/*', '/dovidka/*', '/prodazh/*', '/pidpysnyk/*', '/kopiia/*'];
const SESIIA_S = 30 * 86400, VKHID_S = 30 * 60, LYSTIV_NA_HODYNU = 5;
export const STEZHU_MAKS = 100;

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

/** Партнер (ZAVDANNYA-161, п. 5): пошта зі списку PARTNERY (через кому) або, без нього, POSHTA_PARTNERA. */
function partnery(env) {
  return String(env.PARTNERY || env.POSHTA_PARTNERA || '').split(',').map((x) => L.chystaPoshta(x)).filter(Boolean);
}
const jePartner = (env, ja) => !!ja && partnery(env).includes(ja.poshta);

/**
 * Ліміт запитів з однієї адреси (ZAVDANNYA-156): прив'язка Cloudflare Rate Limiting OBMEZHENNIA (wrangler.jsonc, «ratelimits»,
 * пише site/khostynh.py). true — забагато, відповісти 429. Без прив'язки (місцевий запуск, тести) — без ліміту.
 * Лише для того, що пишуть люди: форми, замовлення, вхід. Сповіщення платіжного сервісу й видавача — ніколи не обмежуємо.
 */
async function zabahato(request, env, hrupa) {
  if (!env.OBMEZHENNIA?.limit) return false;
  const ip = request.headers.get('cf-connecting-ip') || 'bez-adresy';
  try {
    return !(await env.OBMEZHENNIA.limit({ key: `${hrupa}:${ip}` })).success;
  } catch (err) {
    console.log(`ліміт запитів: ${err.message}`);
    return false;      // ліміт не відповів — не зупиняємо продаж
  }
}
const ZABAHATO = () => S.povidomlennia('Забагато спроб', 'Забагато запитів з вашої мережі. Зачекайте хвилину й спробуйте ще раз.', 429);

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
  // ZAVDANNYA-150, п. 3: увійшли з пакетом «3 довідки» чи підпискою — спершу «Використати залишок», а не нова оплата
  const ja = await sesiia(request, env);
  const zalyshok = ja && adresa && tovar === 'dovidka' ? await L.zalyshokNaBudynok(env, ja.id, budynok) : 0;
  return S.formaZamovlennia({ tovar, budynok: adresa ? budynok : null, adresa, zalyshok, ...(await vkhidGoogle(request, env, ja)) });
}

/** Для форми замовлення (ZAVDANNYA-142): пошта з сесії (після входу через Google) і чи показувати кнопку Google. */
async function vkhidGoogle(request, env, ja = undefined) {
  if (ja === undefined) ja = await sesiia(request, env);
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
  let budynok = null, adresa = null;
  if (f.budynok) {
    // ZAVDANNYA-150, п. 6: адреса словами або посилання на сторінку будинку
    const v = await L.znaityBudynok(env, url, f.budynok);
    if (!v.budynok) return S.formaZamovlennia({ tovar, budynok: null, adresa: null, pomylka: L.chomuNeZnaideno(v), vvedeno: String(f.budynok).slice(0, 200), poshtaSesii: L.chystaPoshta(f.poshta) || '' });
    ({ budynok, adresa } = v);
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
  // ZAVDANNYA-156: тестові сповіщення — лише коли весь сервер у тестовому режимі, а не поруч із живою оплатою
  if (servis === 'test' && env.PLATIZHNYI_SERVIS !== 'test') return new Response('ні', { status: 404 });
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
      // sandbox (ZAVDANNYA-156): скрипт довідки працює як «чужий» сайт — без кук і без доступу до кабінету на нашому домені,
      // навіть якщо в довідку колись потрапить чужий текст зі скриптом. Дозволено: скрипт, друк (кнопка PDF), посилання на рішення в новій вкладці.
      'content-security-policy': "default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; font-src data:; frame-ancestors 'none'; form-action 'none'; base-uri 'none'; " +
        'sandbox allow-scripts allow-modals allow-popups allow-popups-to-escape-sandbox',
    },
  });
}

// ---------------------------------------------------------------- кабінет

async function nadislatyVkhid(request, env, url) {
  if (!zNashohoSaitu(request, env)) return S.vkhid('Відкрийте кабінет на нашому сайті.', G.uvimkneno(env));
  const poshta = L.chystaPoshta((await forma(request)).poshta);
  const vidpovid = S.vkhid('Якщо ця пошта є в нас, посилання для входу вже в листі. Перевірте й «Спам».', G.uvimkneno(env));
  if (!poshta) return S.vkhid('Перевірте пошту.', G.uvimkneno(env));
  let k = await L.odyn(env, 'SELECT * FROM korystuvachi WHERE poshta = ?', poshta);
  if (!k && partnery(env).includes(poshta)) k = await L.korystuvach(env, poshta);   // партнер — у кабінет звернень і без покупок
  if (!k) return vidpovid;   // не кажемо, чи є така пошта
  const t = L.teper(env);
  const n = (await L.odyn(env, 'SELECT COUNT(*) AS n FROM vkhody WHERE korystuvach_id = ? AND do_ > ?', k.id, t + VKHID_S - 3600)).n;
  if (n >= LYSTIV_NA_HODYNU) return vidpovid;
  const kliuch = vypadkovyi(24);
  await L.zrobyty(env, 'INSERT INTO vkhody (hash, korystuvach_id, do_) VALUES (?, ?, ?)', sha256(kliuch), k.id, t + VKHID_S);
  await nadislaty(env, {
    komu: poshta, tema: 'Вхід у кабінет «Моєї вулиці»',
    tekst: `Відкрийте посилання й натисніть «Увійти» (діє 30 хвилин, один раз):\n${adresaSaitu(env, url)}/kabinet/vkhid/?t=${kliuch}\n\nЯкщо ви не просили — нічого не робіть.`,
  });
  return vidpovid;
}

// ZAVDANNYA-161, п. 1 (MV-173): посилання з листа лише ВІДКРИВАЄ сторінку з кнопкою «Увійти» — нічого не витрачає.
// Поштові сканери (Outlook, корпоративні пошти) самі відкривають посилання з листа запитом GET; раніше вхід згоряв ще до людини.
// Вхід — лише натисканням (POST з нашої сторінки). Заодно чужий «підставний» лист не впустить вас у чужий кабінет без натискання.
const zastarilo = (env) => S.vkhid('Посилання застаріло або вже використане. Надішлемо нове.', G.uvimkneno(env));

async function diisnyiVkhid(env, t) {
  if (!/^[a-z2-7]{10,64}$/.test(t)) return null;
  const v = await L.odyn(env, 'SELECT * FROM vkhody WHERE hash = ?', sha256(t));
  return v && !v.vykorystano && v.do_ >= L.teper(env) ? v : null;
}

async function storinkaVkhodu(env, url) {
  const t = url.searchParams.get('t') || '';
  if (!(await diisnyiVkhid(env, t))) return zastarilo(env);
  return S.knopkaVkhodu(t);
}

async function uviity(request, env, url) {
  if (!zNashohoSaitu(request, env)) return S.vkhid('Відкрийте посилання з листа ще раз і натисніть «Увійти».', G.uvimkneno(env), 403);
  const t = String((await forma(request)).t || '');
  const v = await diisnyiVkhid(env, t);
  if (!v) return zastarilo(env);
  const zaraz = L.teper(env);
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
  const lyst = { pidpyska: pidpysky.some((p) => ['pidpyska', 'rieltor'].includes(p.tovar)), vymkneno: await ST.vymknenyi(env, ja.id) };
  // «Відкрити карту» — коли карту викладено (KARTA) і є підписка, що її відкриває (як K.maieDostup: усе, крім юриста)
  const karta = !!env.KARTA && pidpysky.some((p) => !TS.sudova.includes(p.tovar));
  return S.kabinet({ poshta: ja.poshta, dovidky, stezhu, pidpysky, dostupno: d, povidomlennia, bali, lyst, partner: jePartner(env, ja), karta });
}

async function diiaKabinetu(request, env, url, ja, dia) {
  const f = await forma(request);
  if (dia === 'stezhu' || dia === 'dovidka') {
    // ZAVDANNYA-150, п. 6: адреса словами («Деміївська 45») або посилання на сторінку будинку
    const z = await L.znaityBudynok(env, url, f.budynok);
    if (!z.budynok) return kabinet(env, ja, L.chomuNeZnaideno(z));
    f.budynok = z.budynok;
    const adresa = z.adresa;
    if (dia === 'stezhu') {
      // ZAVDANNYA-156: межа адрес на людину — щоб один вхід не засмічував базу й щомісячний лист тисячами адрес
      const r = await L.zrobyty(env, `INSERT OR IGNORE INTO stezhu (korystuvach_id, budynok, adresa, stvoreno) SELECT ?, ?, ?, ?
        WHERE (SELECT COUNT(*) FROM stezhu WHERE korystuvach_id = ?) < ?`, ja.id, f.budynok, adresa, L.teper(env), ja.id, STEZHU_MAKS);
      if (!r.meta?.changes && !(await L.odyn(env, 'SELECT 1 AS t FROM stezhu WHERE korystuvach_id = ? AND budynok = ?', ja.id, f.budynok))) {
        return kabinet(env, ja, `У «Стежу» — до ${STEZHU_MAKS} адрес. Приберіть якусь, щоб додати нову.`);
      }
      return kabinet(env, ja, `Стежите: ${adresa}.`);
    }
    // ZAVDANNYA-172 (ZVIT-167): той самий будинок за останню добу — спершу спитати (shche=tak — людина підтвердила)
    if (f.shche !== 'tak') {
      const bula = await L.odyn(env, `SELECT id, status, stvoreno FROM dovidky WHERE korystuvach_id = ? AND budynok = ? AND rezhym != 'sp'
        AND status != 'pomylka' AND stvoreno > ? ORDER BY stvoreno DESC LIMIT 1`, ja.id, f.budynok, L.teper(env) - 86400);
      if (bula) return S.povtorDovidky({ budynok: f.budynok, adresa, dovidka: bula });
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
  if (dia === 'stezhu/lyst') {
    await ST.peremknuty(env, ja.id, f.lyst === 'tak');
    return kabinet(env, ja, f.lyst === 'tak' ? 'Лист «Нове біля дому» знову надсилатимемо раз на місяць.' : 'Лист «Нове біля дому» більше не надсилатимемо.');
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
  // ZAVDANNYA-172 (ZVIT-167, п. 1): без підтвердження зі сторінки «Що зникне» нічого не видаляємо
  if (dia === 'vydalyty' && (f.pidtverdzhuiu !== 'tak' || f.rozumiiu !== 'tak')) return pereity(url, '/kabinet/vydalyty/');
  if (dia === 'vydalyty') {
    if (!(await skasuvatyVsi(env, ja.id))) return kabinet(env, ja, 'Спершу треба скасувати підписку, а сервіс не відповів. Спробуйте ще раз.');
    await L.vydalytyDani(env, ja.id);
    return S.storinka('Дані видалено', `<section class="zaholovok"><h1>Дані видалено</h1>
<p>Пошту, довідки, адреси «Стежу» й вхід видалено. Записи про оплату (сума, дата, товар) партнер зберігає для обліку — без пошти.</p></section>`,
    { zaholovky: { 'set-cookie': 'mv_sesiia=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax' } });
  }
  return S.nemaie();
}

// ---------------------------------------------------------------- кабінет звернень партнера (ZAVDANNYA-161, п. 5)

async function storinkaZvernen(env, povidomlennia = '') {
  const vidkryti = await L.vsi(env, 'SELECT * FROM zvernennya WHERE zakryto IS NULL ORDER BY stvoreno LIMIT 200');
  const zakryti = await L.vsi(env, 'SELECT * FROM zvernennya WHERE zakryto IS NOT NULL ORDER BY zakryto DESC LIMIT 50');
  return S.zvernenniaPartnera({ vidkryti, zakryti, zhurnal: await PR.zhurnal(env), povidomlennia });
}

async function zvernennia(request, env, url, ja) {
  if (!ja) return pereity(url, '/kabinet/');
  if (!jePartner(env, ja)) return S.nemaie();          // для людей цієї сторінки «немає»
  const s = url.pathname.slice('/kabinet/zvernennia/'.length);
  if (request.method === 'GET') return s === '' ? storinkaZvernen(env) : S.nemaie();
  if (request.method !== 'POST') return S.nemaie();
  if (!zNashohoSaitu(request, env)) return S.povidomlennia('Не вдалося', 'Дію можна зробити лише з нашого сайту.', 403);
  const f = await forma(request);
  if (s === 'prybraty') {
    const zv = f.zvernennya ? await L.odyn(env, 'SELECT id FROM zvernennya WHERE id = ?', parseInt(f.zvernennya, 10) || 0) : null;
    const v = await PR.prybraty(env, { posylannia: f.posylannia, zvernennya_id: zv?.id ?? null, prychyna: f.prychyna, khto: ja.poshta });
    if (v.pomylka) return storinkaZvernen(env, v.pomylka);
    return storinkaZvernen(env, v.vzhe ? 'Цю подію вже прибрано.' : 'Подію прибрано: з карти підписника й ігор — одразу (до хвилини). Не забудьте відповісти людині й закрити звернення.');
  }
  if (s === 'zakryty') {
    await L.zrobyty(env, 'UPDATE zvernennya SET zakryto = ? WHERE id = ? AND zakryto IS NULL', L.teper(env), parseInt(f.zvernennya, 10) || 0);
    return storinkaZvernen(env, 'Звернення закрито.');
  }
  if (s === 'povernuty') {
    return storinkaZvernen(env, (await PR.povernuty(env, f.id, ja.poshta)) ? 'Подію повернуто.' : 'Такого прибрання немає або його вже повернуто.');
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
  // ZAVDANNYA-150, п. 4: щомісячний лист «Стежу» — черга й надсилання (скрипт site/prodazh/lyst_stezhu.py)
  if (shliakh === 'stezhu' && request.method === 'GET') {
    const v = await ST.cherha(env, url.searchParams.get('period') || '');
    return v ? Response.json({ pidpysnyky: v }) : new Response('period', { status: 400 });
  }
  m = shliakh.match(/^lyst-stezhu\/(k\d+)$/);
  if (m && request.method === 'POST') {
    let tilo = {};
    try { tilo = await request.json(); } catch { tilo = {}; }
    return new Response(null, { status: (await ST.nadislatyLyst(env, m[1], tilo)).status });
  }
  if (shliakh === 'prybrani' && request.method === 'GET') return Response.json({ prybrani: await PR.aktyvni(env) });
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
  const b = shliakh.match(/^biznes\/(.+)$/);
  if (b) return BZ.admin(request, env, new URL(request.url), b[1]);
  const v = shliakh.match(/^vyvantazhennia\/([a-z_]+)$/);
  if (v && request.method === 'GET') return F.vyvantazhennia(env, v[1]);
  // щоденна перевірка форм прибирає свої тестові рядки (лише канал «perevirka»)
  if (shliakh === 'perevirka' && request.method === 'POST') return Response.json({ prybrano: await F.prybratyPerevirku(env) });
  // позачергове прибрання події (ZAVDANNYA-161, п. 5) — для скриптів; людині-партнеру зручніше /kabinet/zvernennia/
  if (shliakh === 'prybraty-podiyu' && request.method === 'POST') {
    const f = await forma(request);
    const v = await PR.prybraty(env, { posylannia: f.posylannia, zvernennya_id: f.zvernennya, prychyna: f.prychyna, khto: 'admin' });
    return Response.json(v, { status: v.pomylka ? 400 : 200 });
  }
  if (shliakh === 'povernuty-podiyu' && request.method === 'POST') {
    return Response.json({ povernuto: await PR.povernuty(env, (await forma(request)).id, 'admin') });
  }
  if (shliakh === 'prybrani' && request.method === 'GET') return Response.json({ zhurnal: await PR.zhurnal(env, 10000) });
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
  const sp = await vybirSp(env, url, tovar, Object.fromEntries(url.searchParams));
  return S.skoro({ tovar, nazva: tovar === 'sudova' ? F.NAZVA_SUDOVA : TS.nazvy[tovar], budynok: adresa ? budynok : null, adresa,
                   kanal: F.kanal(url.searchParams.get('dzherelo')), kabinet: env.PRODAZH === 'tak', sp });
}

/** Довідка «Судової практики» в «скоро»: стаття, суд і частина — лише якщо є в довіднику (інакше null, сторінка без них). */
async function vybirSp(env, url, tovar, p) {
  if (tovar !== 'spdovidka' || !p.stattia) return null;
  return SP.perevirytyParametry(env, url, { stattia: p.stattia, sud: p.sud, chastyna: p.chastyna });
}

/** «Дякуємо» після оплати: текст за товаром замовлення (?z=…; номер замовлення — випадковий, лише товар, без пошти). */
async function dyakuiemo(env, url) {
  const z = url.searchParams.get('z') || '';
  const zam = /^z[a-z2-7]+$/.test(z) ? await L.odyn(env, 'SELECT tovar FROM zamovlennia WHERE id = ?', z) : null;
  return S.dyakuiemo(zam?.tovar || '');
}

async function skoroZapys(request, env, url) {
  if (!zNashohoSaitu(request, env)) return S.povidomlennia('Не вдалося', 'Залиште пошту на нашому сайті.', 403);
  const f = await forma(request);
  const v = await F.zapysatySkoro(env, url, f);
  if (v.ok) {
    // ZAVDANNYA-172 (ZVIT-169, п. 9): які статті й суди хочуть — знеособлений лічильник за день (skoro_sp, без пошти)
    const sp = await vybirSp(env, url, String(f.tovar || ''), f);
    if (sp) {
      await L.zrobytyNovu(env, `INSERT INTO skoro_sp (den, stattia, sud, chastyna, n) VALUES (?, ?, ?, ?, 1)
        ON CONFLICT (den, stattia, sud, chastyna) DO UPDATE SET n = n + 1`, new Date(L.teper(env) * 1000).toISOString().slice(0, 10),
      sp.parametry.stattia, sp.parametry.sud, sp.parametry.chastyna);
    }
  }
  // ZAVDANNYA-172 (ZVIT-169, п. 1): окрема адреса подяки — і з увімкненою оплатою людина, що лише лишила пошту, бачить
  // «Записали», а не «щойно сервіс підтвердить оплату».
  if (v.ok) return pereity(url, '/oplata/zapysaly/');
  const tovar = F.TOVARY_SKORO.includes(String(f.tovar)) ? String(f.tovar) : null;
  if (!tovar) return S.povidomlennia('Не вдалося', v.pomylka, 400);
  const adresa = f.budynok ? await L.perevirytyBudynok(env, String(f.budynok), url) : null;
  return S.skoro({ tovar, nazva: tovar === 'sudova' ? F.NAZVA_SUDOVA : TS.nazvy[tovar], budynok: adresa ? String(f.budynok) : null,
                   adresa, kanal: F.kanal(f.dzherelo), pomylka: v.pomylka, kabinet: env.PRODAZH === 'tak', sp: await vybirSp(env, url, tovar, f) });
}

/** Спільне для 'skoro' і 'tak': стилі сторінок, форми сайту, вивантаження для партнера. Null — не наша адреса. */
async function spilne(request, env, url) {
  const s = url.pathname;
  if (s === '/prodazh/prodazh.css') return new Response(S.CSS, { headers: { 'content-type': 'text/css; charset=utf-8', 'cache-control': 'public, max-age=3600' } });
  const r = s.match(/^\/api\/forma\/([a-z]+)$/);
  if (r && request.method === 'POST') {
    if (!zNashohoSaitu(request, env)) return new Response('ні', { status: 403 });
    if (await zabahato(request, env, 'forma')) return new Response('zabahato', { status: 429 });
    return r[1] === 'biznes' ? BZ.zapyt(request, env) : F.forma(request, env, r[1]);
  }
  if (s === BZ.KOREN.slice(0, -1) || s.startsWith(BZ.KOREN)) {
    if (await zabahato(request, env, 'kopiia')) return ZABAHATO();
    return BZ.kopiia(request, env, url);
  }
  const a = s.match(/^\/api\/admin\/(.+)$/);
  if (a) return admin(request, env, a[1]);
  return null;
}

/** Відповідь сервера продажу або null (тоді — звичайний сайт). */
// Що обмежуємо (ZAVDANNYA-156): усе, що пише в базу чи шле листи з дії незнайомця, і вгадування ключів.
const OBMEZHENI = [['POST', /^\/api\/(skoro|zamovlennia)$/, 'zapys'], ['POST', /^\/kabinet\/vkhid(\/uviity)?$/, 'vkhid'],
  ['GET', /^\/kabinet\/(vkhid|google)\/$/, 'vkhid'], ['GET', /^\/dovidka\//, 'dovidka'], ['GET', /^\/pidpysnyk\/api\//, 'karta']];

export async function prodazh(request, env) {
  if (env.PRODAZH !== 'tak' && env.PRODAZH !== 'skoro') return null;
  const url = new URL(request.url);
  const s = url.pathname;
  const m = request.method;
  const o = OBMEZHENI.find(([metod, shliakh]) => metod === m && shliakh.test(s));
  if (o && await zabahato(request, env, o[2])) return ZABAHATO();
  const sp = await spilne(request, env, url);
  if (sp) return sp;
  if (env.PRODAZH === 'skoro') {
    if (s === '/oplata/' && m === 'GET') return skoroForma(env, url);
    if (s === '/api/skoro' && m === 'POST') return skoroZapys(request, env, url);
    if ((s === '/oplata/dyakuiemo/' || s === '/oplata/zapysaly/') && m === 'GET') return S.skoroDyakuiemo();
    if (s.startsWith('/api/')) return new Response('ні', { status: 404 });
    return null;     // кабінет, довідки, тестова оплата — у режимі «скоро» їх немає (звичайний сайт, 404)
  }
  // Товари, яких ще немає в продажу («Судова практика»), — «Скоро — залиште пошту» і з увімкненою оплатою.
  const tovar = url.searchParams.get('tovar');
  if (s === '/oplata/' && m === 'GET' && F.TOVARY_SKORO.includes(tovar) && !TS.prodaietsia.includes(tovar)) return skoroForma(env, url);
  if (s === '/api/skoro' && m === 'POST') return skoroZapys(request, env, url);
  if (s === '/oplata/' && m === 'GET') return formaZamovlennia(request, env, url);
  if (s === '/oplata/zapysaly/' && m === 'GET') return S.skoroDyakuiemo();
  if (s === '/oplata/dyakuiemo/' && m === 'GET') return dyakuiemo(env, url);
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
  if (s === '/kabinet/vkhid/' && m === 'GET') return storinkaVkhodu(env, url);
  if (s === '/kabinet/vkhid/uviity' && m === 'POST') return uviity(request, env, url);
  if (s.startsWith('/kabinet/google/') && m === 'GET') return google(request, env, url);
  if (s.startsWith('/kabinet/zvernennia/')) return zvernennia(request, env, url, await sesiia(request, env));
  if (s.startsWith('/kabinet/')) {
    const ja = await sesiia(request, env);
    if (s === '/kabinet/' && m === 'GET') return ja ? kabinet(env, ja) : S.vkhid('', G.uvimkneno(env));
    if (s === '/kabinet/vydalyty/' && m === 'GET') return ja ? S.pidtverdytyVydalennia(await L.shchoZnykne(env, ja.id)) : pereity(url, '/kabinet/');
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
