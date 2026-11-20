// Незалежна перевірка безпеки сервера продажу перед грошима (ZAVDANNYA-156). Кожен тест відтворює одну знахідку
// (до виправлення падав) або закріплює те, що вже було захищено. Таблиця знахідок — docs/ZVIT-156.md.
// Запуск: node --test site/worker/testy/  (Node 22+: node:sqlite). Справжній код Workers на справжній схемі (skhema.sql).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import worker from '../index.js';
import { pidpysTestu } from '../prodazh/perekhidnyky.js';
import * as L from '../prodazh/logika.js';
import TS from '../prodazh/tsiny.js';
import { d1, r2 } from './pidminy.mjs';

const SAIT = 'https://mv.test';
const DEN = 86400;
const BUDYNKY = { '/budynok/zhylianska/5/': 'вулиця Жилянська, 5', '/budynok/obolonskyi/16/': 'проспект Оболонський, 16' };

function seredovyshche(dod = {}) {
  let chas = 1_790_000_000;
  const env = {
    PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 'test-kliuch', VYDACHA_KLIUCH: 'vydacha-kliuch',
    ADMIN_KLIUCH: 'admin-kliuch', ADRESA_SAITU: SAIT, POSHTA_PARTNERA: 'partner@mv.test',
    BAZA: d1(), DOVIDKY: r2(), __LYSTY: [],
    __CHAS: () => chas,
    ASSETS: {
      async fetch(req) {
        const p = new URL(req.url).pathname;
        if (BUDYNKY[p]) return new Response(`<!doctype html><main><h1>${BUDYNKY[p]}</h1></main>`, { status: 200 });
        if (p === '/vulytsi/budynky.json') return Response.json([]);
        return new Response('немає', { status: 404 });
      },
    },
    ...dod,
  };
  env.krok = (s) => { chas += s; };
  return env;
}

async function zapyt(env, metod, shliakh, { forma, kuka, origin = SAIT, zaholovky = {}, tilo } = {}) {
  const h = { ...zaholovky };
  if (origin) h.origin = origin;
  if (kuka) h.cookie = kuka;
  const body = forma ? new URLSearchParams(forma) : tilo;
  const r = await worker.fetch(new Request(SAIT + shliakh, { method: metod, headers: h, body, redirect: 'manual' }), env);
  return { r, text: await r.text(), kudy: r.headers.get('location') };
}

const sql = (env, s, ...p) => env.BAZA.db.prepare(s).all(...p);

async function zamovyty(env, tovar, budynok, poshta = 'ana@poshta.ua') {
  const f = { tovar, poshta, zghoda: 'tak', odrazu: 'tak' };
  if (budynok) f.budynok = budynok;
  const { r, kudy, text } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: f });
  if (r.status === 303) return new URL(kudy).pathname.match(/\/oplata\/test\/(z[a-z2-7]+)\//)[1];
  return text;    // форма платіжного сервісу (LiqPay)
}

/** Підписане тестовим ключем сповіщення (той самий шлях, що кнопки сторінки тестової оплати). */
function podiiaTestu(env, zam, podiia, chas) {
  const p = { zamovlennia: zam.id, suma: String(zam.suma), podiia, chas: String(chas) };
  return { ...p, pidpys: pidpysTestu(env, p) };
}
const spovistyty = (env, forma) => zapyt(env, 'POST', '/api/spovishchennia/test', { forma, origin: null });

async function uviity(env, poshta = 'ana@poshta.ua') {
  env.__LYSTY.length = 0;
  await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta } });
  const lyst = env.__LYSTY.find((l) => l.komu === poshta);
  assert.ok(lyst, 'лист входу');
  const { r } = await zapyt(env, 'GET', new URL(lyst.tekst.match(/https:\S+/)[0]).pathname + new URL(lyst.tekst.match(/https:\S+/)[0]).search);
  return r.headers.get('set-cookie').split(';')[0];
}

// ---------------------------------------------------------------- 1. оплата: повтор, гонка, підробка

test('оплата: дві різні події «оплачено» одночасно — товар видано один раз', async () => {
  const env = seredovyshche();
  const zam = sql(env, 'SELECT * FROM zamovlennia WHERE id = ?', await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/'))[0];
  await Promise.all([spovistyty(env, podiiaTestu(env, zam, 'oplata', 'a')), spovistyty(env, podiiaTestu(env, zam, 'oplata', 'b'))]);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 1, 'одна оплата — одна довідка');
});

test('оплата: той самий підписаний лист удруге — нічого нового (повтор зворотного виклику)', async () => {
  const env = seredovyshche();
  const zam = sql(env, 'SELECT * FROM zamovlennia WHERE id = ?', await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/'))[0];
  const f = podiiaTestu(env, zam, 'oplata', 'x');
  await spovistyty(env, f);
  await spovistyty(env, f);
  await spovistyty(env, f);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 1);
});

test('оплата: підробка — інший підпис, інша сума, чуже замовлення — нічого не видано', async () => {
  const env = seredovyshche();
  const zam = sql(env, 'SELECT * FROM zamovlennia WHERE id = ?', await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/'))[0];
  const f = podiiaTestu(env, zam, 'oplata', 'x');
  let v = await spovistyty(env, { ...f, pidpys: f.pidpys.replace(/^./, (c) => (c === 'a' ? 'b' : 'a')) });
  assert.equal(v.r.status, 403, 'чужий підпис');
  // сума 1 грн з правильним підписом (ключ знає лише сервер — тут перевіряємо саму звірку суми)
  const deshevo = { zamovlennia: zam.id, suma: '1', podiia: 'oplata', chas: 'y' };
  v = await spovistyty(env, { ...deshevo, pidpys: pidpysTestu(env, deshevo) });
  assert.equal(sql(env, `SELECT status FROM zamovlennia`)[0].status, 'stvoreno', 'сума не та — не оплачено');
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 0);
  assert.match(env.__LYSTY.at(-1).tema, /іншою сумою/, 'партнер дізнався');
});

test('оплата: тестові сповіщення не працюють, коли ввімкнено справжній сервіс', async () => {
  const env = seredovyshche();
  const zam = sql(env, 'SELECT * FROM zamovlennia WHERE id = ?', await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/'))[0];
  env.PLATIZHNYI_SERVIS = 'liqpay';        // перемкнули на живу оплату, а TESTOVA_OPLATA і TEST_KLIUCH забули прибрати
  const v = await spovistyty(env, podiiaTestu(env, zam, 'oplata', 'x'));
  assert.equal(v.r.status, 404);
  assert.equal(sql(env, `SELECT status FROM zamovlennia`)[0].status, 'stvoreno');
});

test('оплата: невідомий сервіс у адресі («constructor», «__proto__») — 404, а не помилка', async () => {
  const env = seredovyshche();
  for (const s of ['constructor', 'proto', 'valueof', 'hasownproperty']) {
    const { r } = await zapyt(env, 'POST', `/api/spovishchennia/${s}`, { tilo: 'x', origin: null });
    assert.equal(r.status, 404, s);
  }
});

function liqpay(env, data) {
  const d = Buffer.from(JSON.stringify(data)).toString('base64');
  const signature = createHash('sha1').update(env.LIQPAY_PRIVATE_KEY + d + env.LIQPAY_PRIVATE_KEY).digest('base64');
  return zapyt(env, 'POST', '/api/spovishchennia/liqpay', { forma: { data: d, signature }, origin: null });
}

test('підписка LiqPay: «subscribed» і «success» на першу оплату — один місяць, а не два', async () => {
  const env = seredovyshche({ PLATIZHNYI_SERVIS: 'liqpay', TESTOVA_OPLATA: '', LIQPAY_PUBLIC_KEY: 'pub', LIQPAY_PRIVATE_KEY: 'priv' });
  await zamovyty(env, 'pidpyska', null);
  const zam = sql(env, 'SELECT * FROM zamovlennia')[0];
  const t = env.__CHAS();
  const spilne = { order_id: zam.id, amount: zam.suma, currency: 'UAH' };
  await liqpay(env, { ...spilne, status: 'subscribed', payment_id: 1, end_date: t });
  const pershyi = sql(env, 'SELECT diie_do FROM pidpysky')[0].diie_do;
  env.krok(60);
  await liqpay(env, { ...spilne, status: 'success', payment_id: 2, end_date: t + 60 });
  assert.equal(sql(env, 'SELECT diie_do FROM pidpysky')[0].diie_do, pershyi, 'друге «оплачено» того ж дня не дає ще місяць');
  assert.match(env.__LYSTY.at(-1).tema, /раніше строку/, 'партнер дізнався');
  // справжнє чергове списання наприкінці місяця — продовжує
  env.krok(30 * DEN);
  await liqpay(env, { ...spilne, status: 'success', payment_id: 3, end_date: env.__CHAS() });
  assert.ok(sql(env, 'SELECT diie_do FROM pidpysky')[0].diie_do > pershyi, 'чергове списання продовжує');
});

// ---------------------------------------------------------------- 2. залишок: подвійне списання (гонка)

test('гонка: два одночасні «Використати залишок» з підписки (1 на місяць) — одна довідка, друга — до оплати', async () => {
  const env = seredovyshche();
  const id = await zamovyty(env, 'pidpyska', null);
  const zam = sql(env, 'SELECT * FROM zamovlennia WHERE id = ?', id)[0];
  await spovistyty(env, podiiaTestu(env, zam, 'oplata', 'x'));
  const kuka = await uviity(env);
  const forma = { budynok: '/budynok/zhylianska/5/' };
  await Promise.all([1, 2, 3].map(() => zapyt(env, 'POST', '/kabinet/dovidka', { kuka, forma })));
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 1, 'з підписки — лише одна довідка на місяць');
});

test('гонка: пакет «3 довідки» — п\'ять одночасних запитів дають рівно 3', async () => {
  const env = seredovyshche();
  const zam = sql(env, 'SELECT * FROM zamovlennia WHERE id = ?', await zamovyty(env, 'try', '/budynok/zhylianska/5/'))[0];
  await spovistyty(env, podiiaTestu(env, zam, 'oplata', 'x'));
  const kuka = await uviity(env);
  await Promise.all([1, 2, 3, 4, 5].map(() => zapyt(env, 'POST', '/kabinet/dovidka', { kuka, forma: { budynok: '/budynok/obolonskyi/16/' } })));
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 3);
  assert.equal(sql(env, 'SELECT zalyshok FROM zamovlennia')[0].zalyshok, 0);
});

test('гонка: ліміт юриста (3 на місяць) — шість одночасних запитів дають рівно 3', async () => {
  const env = seredovyshche();
  const k = await L.korystuvach(env, 'yurist@poshta.ua');
  const { zam } = await L.stvorytyZamovlennia(env, { tovar: 'spyurist', korystuvach_id: k.id, servis: 'test' });
  await spovistyty(env, podiiaTestu(env, zam, 'oplata', 'x'));
  const v = { parametry: { stattia: 'ст. 130 КУпАП', sud: '', chastyna: '' }, opys: 'ст. 130' };
  const r = await Promise.all([1, 2, 3, 4, 5, 6].map(() => L.vzyatySpDovidku(env, k.id, v)));
  assert.equal(r.filter((x) => x.dovidka).length, TS.dovidok.spyurist);
  assert.equal(r.filter((x) => x.vycherpano).length, 6 - TS.dovidok.spyurist);
});

// ---------------------------------------------------------------- 3. чужий кабінет, чужа довідка (IDOR), XSS, CSRF, пошти

async function hotovaDovidka(env, poshta) {
  const zam = sql(env, 'SELECT * FROM zamovlennia WHERE id = ?', await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/', poshta))[0];
  await spovistyty(env, podiiaTestu(env, zam, 'oplata', poshta));
  const AVT = { authorization: 'Bearer vydacha-kliuch' };
  const { text } = await zapyt(env, 'GET', '/api/vnutr/cherha?n=10', { zaholovky: AVT });
  for (const d of JSON.parse(text).dovidky) await zapyt(env, 'PUT', `/api/vnutr/dovidka/${d.id}`, { zaholovky: AVT, tilo: '<!doctype html><p>опис</p>' });
  const lyst = env.__LYSTY.find((l) => l.komu === poshta && /Готово/.test(l.tekst));
  return new URL(lyst.tekst.match(/https:\S+\/dovidka\/\S+/)[0]);
}

test('чужа довідка за номером: без ключа, з чужим ключем, з чужим входом — «сторінки немає», як і неіснуюча', async () => {
  const env = seredovyshche();
  const moia = await hotovaDovidka(env, 'ana@poshta.ua');
  const id = moia.pathname;
  assert.equal((await zapyt(env, 'GET', moia.pathname + moia.search)).r.status, 200, 'своя з ключем — так');
  const chuzha = await uviity(env, 'ana@poshta.ua').then(() => hotovaDovidka(env, 'bob@poshta.ua'));
  const kukaAny = await uviity(env, 'ana@poshta.ua');
  const nemaie = await zapyt(env, 'GET', '/dovidka/dzzzzzzzzzzzzzzzzzzzzzzzz/');
  for (const [shliakh, kuka] of [[id, null], [`${id}?k=nevirnyi`, null], [chuzha.pathname, kukaAny], [`${chuzha.pathname}${moia.search}`, null]]) {
    const v = await zapyt(env, 'GET', shliakh, { kuka });
    assert.equal(v.r.status, 404, shliakh);
    assert.equal(v.text, nemaie.text, 'чужа виглядає так само, як неіснуюча');
  }
});

test('довідка відкривається в «пісочниці»: її скрипт не бачить кабінету й кук нашого сайту', async () => {
  const env = seredovyshche();
  const u = await hotovaDovidka(env, 'ana@poshta.ua');
  const { r } = await zapyt(env, 'GET', u.pathname + u.search);
  const csp = r.headers.get('content-security-policy');
  assert.match(csp, /sandbox allow-scripts/);
  assert.doesNotMatch(csp, /allow-same-origin/);
  assert.match(csp, /form-action 'none'/);
  assert.equal(r.headers.get('referrer-policy'), 'no-referrer', 'ключ з адреси не йде на сайт реєстру');
});

test('кабінет: чужу підписку не скасувати, чужий «Стежу» не прибрати — користувач лише з сесії', async () => {
  const env = seredovyshche();
  const zam = sql(env, 'SELECT * FROM zamovlennia WHERE id = ?', await zamovyty(env, 'pidpyska', null, 'bob@poshta.ua'))[0];
  await spovistyty(env, podiiaTestu(env, zam, 'oplata', 'x'));
  const kb = await uviity(env, 'bob@poshta.ua');
  await zapyt(env, 'POST', '/kabinet/stezhu', { kuka: kb, forma: { budynok: '/budynok/zhylianska/5/' } });
  await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/', 'ana@poshta.ua');
  const ka = await uviity(env, 'ana@poshta.ua');
  const p = sql(env, 'SELECT id FROM pidpysky')[0].id;
  const { text } = await zapyt(env, 'POST', '/kabinet/skasuvaty', { kuka: ka, forma: { pidpyska: p, korystuvach_id: '1' } });
  assert.match(text, /Такої підписки немає/);
  assert.equal(sql(env, 'SELECT status FROM pidpysky')[0].status, 'aktyvna');
  await zapyt(env, 'POST', '/kabinet/stezhu/prybraty', { kuka: ka, forma: { budynok: '/budynok/zhylianska/5/' } });
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM stezhu')[0].n, 1);
  const { text: kabAny } = await zapyt(env, 'GET', '/kabinet/', { kuka: ka });
  assert.doesNotMatch(kabAny, /bob@poshta\.ua/, 'чужа пошта не видна');
});

test('CSRF: дія кабінету з чужого сайту або без Origin — 403, дані цілі', async () => {
  const env = seredovyshche();
  await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/');
  const kuka = await uviity(env);
  for (const origin of ['https://zlyi.example', null, 'null', 'https://mv.test.zlyi.example']) {
    const { r } = await zapyt(env, 'POST', '/kabinet/vydalyty', { kuka, origin, forma: { pidtverdzhuiu: 'tak' } });
    assert.equal(r.status, 403, String(origin));
    const z = await zapyt(env, 'POST', '/api/zamovlennia', { origin, forma: { tovar: 'dovidka', poshta: 'x@poshta.ua', zghoda: 'tak', odrazu: 'tak' } });
    assert.equal(z.r.status, 403);
    assert.equal((await zapyt(env, 'POST', '/kabinet/vkhid', { origin, forma: { poshta: 'ana@poshta.ua' } })).text.includes('на нашому сайті'), true);
  }
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM korystuvachi')[0].n, 1, 'нікого не видалено й не створено');
});

test('XSS: адреса й поля форм з тегами — на сторінці лише як текст', async () => {
  const env = seredovyshche();
  const zlo = '"><script>alert(1)</script><img src=x onerror=alert(2)> 5';
  const { text } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'dovidka', budynok: zlo, poshta: '<b>@x.ua', zghoda: 'tak', odrazu: 'tak' } });
  assert.doesNotMatch(text, /<script>alert|<img src=x/);
  assert.match(text, /&lt;script&gt;/);
  const kuka = await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/').then(() => uviity(env));
  const k = await zapyt(env, 'POST', '/kabinet/stezhu', { kuka, forma: { budynok: zlo } });
  assert.doesNotMatch(k.text, /<script>alert|<img src=x/);
  // CSP сторінок продажу: лише власні скрипти, жодних вбудованих
  assert.match(k.r.headers.get('content-security-policy'), /script-src 'self'; /);
  // пошта з тегами — не пошта
  assert.equal(L.chystaPoshta('<script>@x.ua'), null);
  assert.equal(L.chystaPoshta('a@b.ua\r\nBcc: c@d.ua'), null, 'без переносу рядка в заголовок листа');
});

test('пошти не витікають: вхід відповідає однаково для відомої й невідомої пошти; посилання входу — одноразове', async () => {
  const env = seredovyshche();
  await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/');
  const a = await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta: 'ana@poshta.ua' } });
  const b = await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta: 'nikhto@poshta.ua' } });
  assert.equal(a.text, b.text);
  assert.equal(a.r.status, b.r.status);
  const posylannia = new URL(env.__LYSTY.at(-1).tekst.match(/https:\S+/)[0]);
  const pershyi = await zapyt(env, 'GET', posylannia.pathname + posylannia.search);
  assert.equal(pershyi.r.status, 303);
  assert.match(pershyi.r.headers.get('set-cookie'), /HttpOnly; Secure; SameSite=Lax/);
  const druhyi = await zapyt(env, 'GET', posylannia.pathname + posylannia.search);
  assert.equal(druhyi.r.status, 200);
  assert.equal(druhyi.r.headers.get('set-cookie'), null, 'вдруге — без входу');
  // перебір листів входу на одну пошту — не більше 5 на годину
  env.__LYSTY.length = 0;
  for (let i = 0; i < 12; i++) await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta: 'ana@poshta.ua' } });
  assert.ok(env.__LYSTY.length <= 5, `листів: ${env.__LYSTY.length}`);
});

test('вбудовані назви замість таблиці чи обміну («constructor») — відмова, а не помилка сервера', async () => {
  const env = seredovyshche({ OBMIN_BALIV: 'tak' });
  const { r } = await zapyt(env, 'GET', '/api/admin/vyvantazhennia/constructor', { zaholovky: { authorization: 'Bearer admin-kliuch' } });
  assert.equal(r.status, 404);
  const { r: bez } = await zapyt(env, 'GET', '/api/admin/vyvantazhennia/skoro', { zaholovky: { authorization: 'Bearer ne-toi' } });
  assert.equal(bez.status, 401);
  const B = await import('../prodazh/bali.js');
  for (const tovar of ['constructor', '__proto__', 'toString']) {
    assert.equal((await B.obminiaty(env, 1, { tovar, zapyt: 'abcdefgh12' })).chomu, 'Такого обміну немає.', tovar);
  }
});

test('«Стежу»: не більше 100 адрес на людину', async () => {
  const env = seredovyshche();
  await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/');
  const kuka = await uviity(env);
  const k = sql(env, 'SELECT id FROM korystuvachi')[0].id;
  for (let i = 0; i < 100; i++) env.BAZA.db.prepare('INSERT INTO stezhu (korystuvach_id, budynok, adresa, stvoreno) VALUES (?, ?, ?, 0)').run(k, `/budynok/x/${i}/`, `x ${i}`);
  const { text } = await zapyt(env, 'POST', '/kabinet/stezhu', { kuka, forma: { budynok: '/budynok/zhylianska/5/' } });
  assert.match(text, /до 100 адрес/);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM stezhu')[0].n, 100);
});

test('карта підписника: без підписки — 403, без входу — на вхід, шлях за межі теки — немає', async () => {
  const KARTA = r2();
  await KARTA.put('karta/potochna.json', JSON.stringify({ versiia: 'v1' }));
  await KARTA.put('karta/v1/index.html', '<!doctype html>карта');
  await KARTA.put('karta/v1/spravy/1_1.json', '[[[0,"2024",0,0,[],"опис справи"]]]');
  await KARTA.put('karta/potochna.json.bak', 'секрет');
  const env = seredovyshche({ KARTA });
  assert.equal((await zapyt(env, 'GET', '/pidpysnyk/spravy/1_1.json')).r.status, 303);
  await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/');
  const kuka = await uviity(env);
  const bez = await zapyt(env, 'GET', '/pidpysnyk/spravy/1_1.json', { kuka });
  assert.equal(bez.r.status, 403);
  assert.doesNotMatch(bez.text, /опис справи/);
  const zam = sql(env, 'SELECT * FROM zamovlennia WHERE id = ?', await zamovyty(env, 'pidpyska', null))[0];
  await spovistyty(env, podiiaTestu(env, zam, 'oplata', 'p'));
  const z = await zapyt(env, 'GET', '/pidpysnyk/spravy/1_1.json', { kuka });
  assert.equal(z.r.status, 200);
  assert.match(z.r.headers.get('cache-control'), /private/);
  for (const s of ['/pidpysnyk/../potochna.json.bak', '/pidpysnyk/%2e%2e/potochna.json.bak', '/pidpysnyk/.%2e/.%2e/karta/potochna.json']) {
    assert.notEqual((await zapyt(env, 'GET', s, { kuka })).text, 'секрет', s);
  }
  // скасована й прострочена — доступу немає
  env.krok(40 * DEN);
  const kuka2 = await uviity(env);
  assert.equal((await zapyt(env, 'GET', '/pidpysnyk/spravy/1_1.json', { kuka: kuka2 })).r.status, 403);
});
