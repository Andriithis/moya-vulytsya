// Тести сервера продажу (ZAVDANNYA-99). Запуск: node --test site/worker/testy/  (Node 22+: потрібен node:sqlite).
// Справжній код Workers (site/worker/index.js) на справжній SQL-схемі (skhema.sql у SQLite — те саме, що D1),
// з підставними сайтом (ASSETS), сховищем файлів (R2) і поштою-заглушкою.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { generateKeyPairSync, createSign, createHash } from 'node:crypto';
import worker from '../index.js';
import { PEREKHIDNYKY, pidpysTestu } from '../prodazh/perekhidnyky.js';
import { sha3_256 } from '../prodazh/bezpeka.js';
import { prybraty } from '../prodazh/logika.js';
import t from '../prodazh/tsiny.js';

import { d1, r2 } from './pidminy.mjs';
const SAIT = 'https://mv.test';

const BUDYNKY = { '/budynok/zhylianska/5/': 'вулиця Жилянська, 5', '/budynok/obolonskyi/16/': 'проспект Оболонський, 16' };

function seredovyshche(dod = {}) {
  let chas = 1_790_000_000;
  const env = {
    PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 'test-kliuch', VYDACHA_KLIUCH: 'vydacha-kliuch',
    ADRESA_SAITU: SAIT, POSHTA_PARTNERA: 'partner@mv.test',
    BAZA: d1(), DOVIDKY: r2(), __LYSTY: [],
    __CHAS: () => chas,
    ASSETS: {
      async fetch(req) {
        const p = new URL(req.url).pathname;
        if (p === '/miy-budynok/') return new Response('вітрина', { status: 200 });
        if (BUDYNKY[p]) return new Response(`<!doctype html><main><h1>${BUDYNKY[p]}</h1><p>12 скарг</p></main>`, { status: 200 });
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
  let body = tilo;
  if (forma) body = new URLSearchParams(forma);
  const r = await worker.fetch(new Request(SAIT + shliakh, { method: metod, headers: h, body, redirect: 'manual' }), env);
  return { r, text: await r.text(), kudy: r.headers.get('location') };
}

const sql = (env, s, ...p) => env.BAZA.db.prepare(s).all(...p);
const polia = (html) => [...html.matchAll(/<form method="post" action="\/api\/spovishchennia\/test">([\s\S]*?)<\/form>/g)].map((m) => ({
  forma: Object.fromEntries([...m[1].matchAll(/name="([^"]+)" value="([^"]*)"/g)].map((x) => [x[1], x[2]])),
  napys: m[1].match(/type="submit">([^<]+)</)[1],
}));

async function zamovyty(env, tovar, budynok, poshta = 'ana@poshta.ua', dod = {}) {
  const f = { tovar, poshta, zghoda: 'tak', odrazu: 'tak', ...dod };
  if (budynok) f.budynok = budynok;
  const { r, kudy } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: f });
  assert.equal(r.status, 303, 'замовлення має вести на оплату');
  return new URL(kudy).pathname.match(/\/oplata\/test\/(z[a-z2-7]+)\//)[1];
}

async function oplatyty(env, id, napys = 'Оплата пройшла') {
  const { text } = await zapyt(env, 'GET', `/oplata/test/${id}/`);
  const k = polia(text).find((x) => x.napys === napys);
  assert.ok(k, `немає кнопки «${napys}»`);
  return zapyt(env, 'POST', '/api/spovishchennia/test', { forma: k.forma, origin: null });
}

const AVT = { authorization: 'Bearer vydacha-kliuch' };
async function vydavach(env, html = '<!doctype html><title>довідка</title><p>Опис події лише після оплати</p>') {
  const { text } = await zapyt(env, 'GET', '/api/vnutr/cherha?n=10', { zaholovky: AVT });
  const ds = JSON.parse(text).dovidky;
  for (const d of ds) {
    const { r } = await zapyt(env, 'PUT', `/api/vnutr/dovidka/${d.id}`, { zaholovky: AVT, tilo: html });
    assert.equal(r.status, 204);
  }
  return ds;
}

const posylannia = (lyst) => lyst.tekst.match(/https:\/\/mv\.test(\/dovidka\/d[a-z2-7]+\/\?k=[a-z2-7]+)/)[1];

async function uviity(env, poshta = 'ana@poshta.ua') {
  await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta } });
  const lyst = env.__LYSTY.filter((l) => l.komu === poshta && l.tema.startsWith('Вхід')).at(-1);
  const t = lyst.tekst.match(/\/kabinet\/vkhid\/\?t=([a-z2-7]+)/)[1];
  const storinka = await zapyt(env, 'GET', `/kabinet/vkhid/?t=${t}`);
  assert.equal(storinka.r.status, 200);
  assert.match(storinka.text, /Увійти<\/button>/);
  const { r, kudy } = await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t } });
  assert.equal(r.status, 303);
  assert.equal(new URL(kudy).pathname, '/kabinet/');
  return r.headers.get('set-cookie').split(';')[0];
}

// ---------------------------------------------------------------- ціна

test('ціну з адреси сторінки чи форми не підробити: сума — лише з таблиці цін', async () => {
  const env = seredovyshche();
  const { text } = await zapyt(env, 'GET', '/oplata/?tovar=dovidka&budynok=/budynok/zhylianska/5/&tsina=1&suma=1');
  assert.match(text, /199 грн/);
  assert.doesNotMatch(text, /value="1"/);
  const id = await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/', 'ana@poshta.ua', { suma: '1', tsina: '1', amount: '1' });
  assert.equal(sql(env, 'SELECT suma FROM zamovlennia WHERE id = ?', id)[0].suma, 199);
  for (const [tovar, suma] of [['zvit', t.tsiny.zvit], ['try', t.tsiny.try], ['pidpyska', t.tsiny.pidpyska], ['osbb', t.tsiny.osbb]]) {
    const z = await zamovyty(env, tovar, tovar === 'pidpyska' ? null : '/budynok/zhylianska/5/');
    assert.equal(sql(env, 'SELECT suma FROM zamovlennia WHERE id = ?', z)[0].suma, suma);
  }
});

test('сповіщення з іншою сумою (навіть із правильним підписом) нічого не видає', async () => {
  const env = seredovyshche();
  const id = await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/');
  const f = { zamovlennia: id, suma: '1', podiia: 'oplata', chas: '1' };
  await zapyt(env, 'POST', '/api/spovishchennia/test', { forma: { ...f, pidpys: pidpysTestu(env, f) }, origin: null });
  assert.equal(sql(env, 'SELECT status FROM zamovlennia WHERE id = ?', id)[0].status, 'stvoreno');
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 0);
  assert.ok(env.__LYSTY.some((l) => l.komu === 'partner@mv.test' && /іншою сумою/.test(l.tema)));
});

test('бізнес, «додаткова» без підписки, неіснуючий будинок і невідомий товар — замовлення не створюються', async () => {
  const env = seredovyshche();
  for (const f of [{ tovar: 'biznes' }, { tovar: 'dodatkova', budynok: '/budynok/zhylianska/5/' }, { tovar: 'shcho', budynok: '/budynok/zhylianska/5/' },
    { tovar: 'dovidka', budynok: '/budynok/nemaie/1/' }, { tovar: 'dovidka', budynok: '/zahlushka/../budynok/zhylianska/5/' }]) {
    const { r } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { ...f, poshta: 'a@b.ua', zghoda: 'tak', odrazu: 'tak' } });
    assert.notEqual(r.status, 303);
  }
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM zamovlennia')[0].n, 0);
  const { r } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'dovidka', budynok: '/budynok/zhylianska/5/', poshta: 'a@b.ua', zghoda: 'tak', odrazu: 'tak' }, origin: 'https://zlyi.test' });
  assert.equal(r.status, 403, 'форма з чужого сайту');
});

// ---------------------------------------------------------------- оплата → видача

test('повний шлях: замовлення → тестова оплата → черга → генератор → лист → довідка за посиланням', async () => {
  const env = seredovyshche();
  const id = await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/');
  assert.deepEqual(await vydavach(env), [], 'до оплати черга порожня');
  const { r, kudy } = await oplatyty(env, id);
  assert.equal(r.status, 303);
  assert.match(kudy, /\/oplata\/dyakuiemo\//);
  const { r: bez } = await zapyt(env, 'GET', '/api/vnutr/cherha', { zaholovky: { authorization: 'Bearer ne-toi' } });
  assert.equal(bez.status, 401, 'черга — лише з ключем видавача');
  const ds = await vydavach(env);
  assert.equal(ds.length, 1);
  assert.deepEqual(Object.keys(ds[0]).sort(), ['adresa', 'budynok', 'id', 'rezhym']);
  assert.equal(ds[0].adresa, 'вулиця Жилянська, 5', 'адреса — із заголовка сторінки будинку');
  assert.equal(ds[0].rezhym, 'dovidka');
  const lyst = env.__LYSTY.find((l) => l.komu === 'ana@poshta.ua' && /^Довідка/.test(l.tema));
  assert.ok(lyst, 'лист із посиланням');
  const { r: d, text } = await zapyt(env, 'GET', posylannia(lyst));
  assert.equal(d.status, 200);
  assert.match(text, /Опис події лише після оплати/);
  assert.match(d.headers.get('cache-control'), /no-store/);
  assert.match(d.headers.get('x-robots-tag'), /noindex/);
  // повний звіт — режим povnyi
  const z2 = await zamovyty(env, 'zvit', '/budynok/obolonskyi/16/');
  await oplatyty(env, z2);
  const { text: t2 } = await zapyt(env, 'GET', '/api/vnutr/cherha', { zaholovky: AVT });
  assert.equal(JSON.parse(t2).dovidky[0].rezhym, 'povnyi');
});

test('чужий не відкриє чужу довідку', async () => {
  const env = seredovyshche();
  const id = await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/', 'ana@poshta.ua');
  await oplatyty(env, id);
  await vydavach(env);
  const prava = posylannia(env.__LYSTY.find((l) => /^Довідка/.test(l.tema)));
  const nomer = prava.match(/\/dovidka\/(d[a-z2-7]+)\//)[1];
  // інший покупець зі своєю сесією
  const z = await zamovyty(env, 'dovidka', '/budynok/obolonskyi/16/', 'bohdan@poshta.ua');
  await oplatyty(env, z);
  const kuka = await uviity(env, 'bohdan@poshta.ua');
  for (const [shliakh, k] of [[`/dovidka/${nomer}/`, null], [`/dovidka/${nomer}/?k=`, null], [`/dovidka/${nomer}/?k=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`, null],
    [`/dovidka/${nomer}/`, kuka], [`/dovidka/${nomer}/?k=${prava.split('k=')[1].slice(0, -1)}x`, kuka], ['/dovidka/dneisnuie/', kuka]]) {
    const { r, text } = await zapyt(env, 'GET', shliakh, { kuka: k });
    assert.equal(r.status, 404, shliakh);
    assert.doesNotMatch(text, /Опис події/);
  }
  // власник — за посиланням або з кабінету
  assert.equal((await zapyt(env, 'GET', prava)).r.status, 200);
  const moia = await uviity(env, 'ana@poshta.ua');
  assert.equal((await zapyt(env, 'GET', `/dovidka/${nomer}/`, { kuka: moia })).r.status, 200);
  // і в кабінеті іншого її немає
  const { text } = await zapyt(env, 'GET', '/kabinet/', { kuka });
  assert.doesNotMatch(text, new RegExp(nomer));
});

test('підпис сповіщення перевіряється; повтор сповіщення не дає другої довідки', async () => {
  const env = seredovyshche();
  const id = await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/');
  const f = { zamovlennia: id, suma: '199', podiia: 'oplata', chas: '5' };
  const { r } = await zapyt(env, 'POST', '/api/spovishchennia/test', { forma: { ...f, pidpys: 'pidroblenyi' }, origin: null });
  assert.equal(r.status, 403);
  const { r: r2_ } = await zapyt(env, 'POST', '/api/spovishchennia/test', { forma: { ...f, pidpys: pidpysTestu({ TEST_KLIUCH: 'inshyi' }, f) }, origin: null });
  assert.equal(r2_.status, 403);
  assert.equal(sql(env, 'SELECT status FROM zamovlennia WHERE id = ?', id)[0].status, 'stvoreno');
  const dobra = { ...f, pidpys: pidpysTestu(env, f) };
  await zapyt(env, 'POST', '/api/spovishchennia/test', { forma: dobra, origin: null });
  await zapyt(env, 'POST', '/api/spovishchennia/test', { forma: dobra, origin: null });
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 1);
});

test('тестова оплата вимкнена, якщо не ввімкнено обидві змінні; PRODAZH вимкнено — звичайний сайт', async () => {
  const env = seredovyshche({ TESTOVA_OPLATA: undefined });
  assert.equal((await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'dovidka', budynok: '/budynok/zhylianska/5/', poshta: 'a@b.ua', zghoda: 'tak', odrazu: 'tak' } })).r.status, 503);
  const f = { zamovlennia: 'zaaaa', suma: '199', podiia: 'oplata', chas: '1' };
  assert.equal((await zapyt(env, 'POST', '/api/spovishchennia/test', { forma: { ...f, pidpys: pidpysTestu(env, f) } })).r.status, 404);
  const vymk = seredovyshche({ PRODAZH: undefined });
  const { r, text } = await zapyt(vymk, 'GET', '/oplata/?tovar=dovidka');
  assert.equal(r.status, 404);
  assert.equal(text, 'немає', 'запит пішов до статичного сайту');
  assert.equal((await zapyt(vymk, 'GET', '/miy-budynok/')).text, 'вітрина', 'решта сайту — як раніше');
});

test('видавач: помилка тричі — «не вдалося» і лист партнеру; узяте й забуте повертається в чергу через 30 хв', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/'));
  for (let i = 0; i < 3; i++) {
    const { text } = await zapyt(env, 'GET', '/api/vnutr/cherha', { zaholovky: AVT });
    const [d] = JSON.parse(text).dovidky;
    assert.ok(d, `спроба ${i + 1}`);
    assert.equal((await zapyt(env, 'POST', `/api/vnutr/pomylka/${d.id}`, { zaholovky: AVT })).r.status, 204);
  }
  assert.equal(sql(env, 'SELECT status FROM dovidky')[0].status, 'pomylka');
  assert.ok(env.__LYSTY.some((l) => l.komu === 'partner@mv.test' && /не вдалося/i.test(l.tema)));
  await oplatyty(env, await zamovyty(env, 'dovidka', '/budynok/obolonskyi/16/'));
  assert.equal((await vydavach(env, null).catch(() => null)), null);  // узяли й «упали» без відповіді (PUT не пройшов)
  assert.equal(JSON.parse((await zapyt(env, 'GET', '/api/vnutr/cherha', { zaholovky: AVT })).text).dovidky.length, 0);
  env.krok(31 * 60);
  assert.equal(JSON.parse((await zapyt(env, 'GET', '/api/vnutr/cherha', { zaholovky: AVT })).text).dovidky.length, 1);
});

// ---------------------------------------------------------------- підписка, пакет, кабінет

test('підписка: 1 довідка на місяць, далі «додаткова» за 99; нове списання — новий місяць; скасування', async () => {
  const env = seredovyshche();
  const id = await zamovyty(env, 'pidpyska', null);
  await oplatyty(env, id);
  const p = sql(env, 'SELECT * FROM pidpysky')[0];
  assert.equal(p.status, 'aktyvna');
  let kuka = await uviity(env);
  let { text } = await zapyt(env, 'GET', '/kabinet/', { kuka });
  assert.match(text, /лишилось: 1/);
  ({ text } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka, forma: { budynok: '/budynok/zhylianska/5/' } }));
  assert.match(text, /готуємо/);
  // MV-155, П6: додаткова (оплата 99) — спершу сторінка з галочкою «надіслати одразу», без неї до оплати не пускає.
  ({ text } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka, forma: { budynok: '/budynok/obolonskyi/16/' } }));
  assert.match(text, /name="odrazu" value="tak" required/);
  assert.equal(sql(env, `SELECT COUNT(*) n FROM zamovlennia WHERE tovar = 'dodatkova'`)[0].n, 0);
  const { r, kudy } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka, forma: { budynok: '/budynok/obolonskyi/16/', odrazu: 'tak' } });
  assert.equal(r.status, 303);
  const dod = new URL(kudy).pathname.match(/(z[a-z2-7]+)/)[1];
  const z = sql(env, 'SELECT * FROM zamovlennia WHERE id = ?', dod)[0];
  assert.equal(z.tovar, 'dodatkova');
  assert.equal(z.suma, 99);
  await oplatyty(env, dod);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 2);
  // через місяць — чергове списання сервісом
  env.krok(31 * 86400);
  kuka = await uviity(env);   // сесія — 30 днів
  ({ text } = await zapyt(env, 'GET', '/kabinet/', { kuka }));
  assert.doesNotMatch(text, /лишилось/, 'не оплачено — підписка не діє');
  await oplatyty(env, id, 'Списання наступного періоду');
  ({ text } = await zapyt(env, 'GET', '/kabinet/', { kuka }));
  assert.match(text, /лишилось: 1/);
  // скасування: списань більше немає, доступ — до кінця оплаченого місяця
  ({ text } = await zapyt(env, 'POST', '/kabinet/skasuvaty', { kuka, forma: { pidpyska: p.id } }));
  assert.match(text, /скасовано/i);
  assert.equal(sql(env, 'SELECT status FROM pidpysky')[0].status, 'skasovana');
  ({ text } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka, forma: { budynok: '/budynok/zhylianska/5/' } }));
  assert.match(text, /готуємо/, 'скасована, але оплачений місяць діє');
});

test('рієлтор — 5 довідок на місяць; ОСББ — рік і лише свій будинок; пакет «3 довідки»', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'rieltor', null, 'rieltor@poshta.ua'));
  const kr = await uviity(env, 'rieltor@poshta.ua');
  for (let i = 0; i < 5; i++) {
    const { text } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: kr, forma: { budynok: '/budynok/zhylianska/5/' } });
    assert.match(text, /готуємо/, `довідка ${i + 1}`);
  }
  assert.match((await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: kr, forma: { budynok: '/budynok/zhylianska/5/' } })).text, /Додаткова довідка/);
  assert.equal((await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: kr, forma: { budynok: '/budynok/zhylianska/5/', odrazu: 'tak' } })).r.status, 303);

  await oplatyty(env, await zamovyty(env, 'osbb', '/budynok/obolonskyi/16/', 'osbb@poshta.ua'));
  const o = sql(env, `SELECT * FROM pidpysky WHERE tovar = 'osbb'`)[0];
  assert.ok(o.diie_do - o.pochatok > 360 * 86400, 'ОСББ — рік');
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky WHERE pidpyska_id = ?', o.id)[0].n, 1, 'перша довідка — одразу');
  const ko = await uviity(env, 'osbb@poshta.ua');
  const { r, kudy } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: ko, forma: { budynok: '/budynok/zhylianska/5/' } });
  assert.equal(r.status, 303);
  assert.match(kudy, /\/oplata\/\?tovar=dovidka/, 'чужий будинок — лише купити');
  env.krok(32 * 86400);
  const ko2 = await uviity(env, 'osbb@poshta.ua');
  assert.match((await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: ko2, forma: { budynok: '/budynok/obolonskyi/16/' } })).text, /готуємо/,
    'наступного місяця — знову свій будинок');

  await oplatyty(env, await zamovyty(env, 'try', '/budynok/zhylianska/5/', 'try@poshta.ua'));
  const kt = await uviity(env, 'try@poshta.ua');
  assert.match((await zapyt(env, 'GET', '/kabinet/', { kuka: kt })).text, /2 з пакета/);
  for (let i = 0; i < 2; i++) assert.match((await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: kt, forma: { budynok: '/budynok/obolonskyi/16/' } })).text, /готуємо/);
  assert.equal((await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: kt, forma: { budynok: '/budynok/obolonskyi/16/' } })).r.status, 303);
});

test('кабінет: посилання входу одноразове й на 30 хвилин; не більше 5 листів на годину; чужа пошта не розкривається', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/'));
  const { text } = await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta: 'nikhto@poshta.ua' } });
  const { text: t2 } = await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta: 'ana@poshta.ua' } });
  assert.equal(text.replace(/\s+/g, ''), t2.replace(/\s+/g, ''), 'однакова відповідь для відомої й невідомої пошти');
  const lyst = env.__LYSTY.filter((l) => l.tema.startsWith('Вхід')).at(-1);
  const t = lyst.tekst.match(/\?t=([a-z2-7]+)/)[1];
  assert.equal((await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t } })).r.status, 303);
  assert.notEqual((await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t } })).r.status, 303, 'вдруге — ні');
  await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta: 'ana@poshta.ua' } });
  env.krok(31 * 60);
  const t3 = env.__LYSTY.filter((l) => l.tema.startsWith('Вхід')).at(-1).tekst.match(/\?t=([a-z2-7]+)/)[1];
  assert.notEqual((await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t: t3 } })).r.status, 303, 'за 30 хв — застаріле');
  assert.match((await zapyt(env, 'GET', `/kabinet/vkhid/?t=${t3}`)).text, /застаріло/);
  const bulo = env.__LYSTY.length;
  for (let i = 0; i < 8; i++) await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta: 'ana@poshta.ua' } });
  assert.ok(env.__LYSTY.length - bulo <= 5);
  // дії кабінету — лише з нашого сайту і лише з сесією
  assert.equal((await zapyt(env, 'POST', '/kabinet/stezhu', { forma: { budynok: '/budynok/zhylianska/5/' } })).r.status, 303);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM stezhu')[0].n, 0);
});

test('«Стежу» й видалення даних на запит: пошта, файли, вхід зникають; замовлення лишаються без людини', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/'));
  await vydavach(env);
  const prava = posylannia(env.__LYSTY.find((l) => /^Довідка/.test(l.tema)));
  const kuka = await uviity(env);
  assert.match((await zapyt(env, 'POST', '/kabinet/stezhu', { kuka, forma: { budynok: '/budynok/obolonskyi/16/' } })).text, /Стежите: проспект Оболонський, 16/);
  assert.equal((await zapyt(env, 'POST', '/kabinet/stezhu', { kuka, forma: { budynok: '/budynok/vyhadana/1/' } })).text.includes('Такого будинку'), true);
  assert.equal((await zapyt(env, 'POST', '/kabinet/stezhu', { kuka, forma: { budynok: '/budynok/obolonskyi/16/' }, origin: 'https://zlyi.test' })).r.status, 403);
  assert.equal(env.DOVIDKY.m.size, 1);
  const { r } = await zapyt(env, 'POST', '/kabinet/vydalyty', { kuka, forma: { pidtverdzhuiu: 'tak' } });
  assert.match(r.headers.get('set-cookie'), /Max-Age=0/);
  assert.equal(env.DOVIDKY.m.size, 0, 'файл довідки видалено');
  for (const t of ['korystuvachi', 'stezhu', 'sesii', 'vkhody']) assert.equal(sql(env, `SELECT COUNT(*) n FROM ${t}`)[0].n, 0, t);
  const z = sql(env, 'SELECT * FROM zamovlennia')[0];
  assert.equal(z.korystuvach_id, null);
  assert.equal(z.suma, 199);
  assert.equal((await zapyt(env, 'GET', prava)).r.status, 404);
  assert.equal((await zapyt(env, 'GET', '/kabinet/', { kuka })).text.includes('Надіслати посилання'), true, 'сесії більше немає');
});

test('щоденне прибирання: файли довідок старші за строк зберігання видаляються', async () => {
  const env = seredovyshche({ DOVIDKY_DNIV: '30' });
  await oplatyty(env, await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/'));
  await vydavach(env);
  env.krok(31 * 86400);
  assert.equal(await prybraty(env), 1);
  assert.equal(env.DOVIDKY.m.size, 0);
  assert.equal(sql(env, 'SELECT status FROM dovidky')[0].status, 'vydaleno');
});

// ---------------------------------------------------------------- перехідники справжніх сервісів (без мережі)

test('LiqPay: форма з підписом; сповіщення з правильним підписом приймається, з іншим — ні; sha3-256 як у документації', async () => {
  for (const hesh of [undefined, 'sha3-256']) {
    const env = { LIQPAY_PUBLIC_KEY: 'pub', LIQPAY_PRIVATE_KEY: 'priv', LIQPAY_HESH: hesh };
    const zam = { id: 'zabc', suma: 399, stvoreno: 1_790_000_000 };
    const v = await PEREKHIDNYKY.liqpay.stvoryty({ zam, pidpyska: { period_misiatsiv: 1 }, opys: 'Підписка', adresa: SAIT, env });
    const dani = JSON.parse(Buffer.from(v.forma.polia.data, 'base64').toString());
    assert.equal(dani.action, 'subscribe');
    assert.equal(dani.subscribe_periodicity, 'month');
    assert.equal(dani.amount, 399);
    const alg = hesh || 'sha1';
    const ochik = alg === 'sha1' ? createHash('sha1').update('priv' + v.forma.polia.data + 'priv').digest('base64')
      : createHash('sha3-256').update('priv' + v.forma.polia.data + 'priv').digest('base64');
    assert.equal(v.forma.polia.signature, ochik);
    const data = Buffer.from(JSON.stringify({ order_id: 'zabc', amount: 399, currency: 'UAH', status: 'success', payment_id: 7 })).toString('base64');
    const pidpys = alg === 'sha1' ? createHash('sha1').update('priv' + data + 'priv').digest('base64') : createHash('sha3-256').update('priv' + data + 'priv').digest('base64');
    const z = (s) => new Request(SAIT, { method: 'POST', body: new URLSearchParams({ data, signature: s }) });
    const { podii } = await PEREKHIDNYKY.liqpay.perevirka(z(pidpys), env);
    assert.deepEqual(podii.map((p) => [p.zamovlennia_id, p.suma, p.valiuta, p.podiia]), [['zabc', 399, 'UAH', 'oplata']]);
    await assert.rejects(PEREKHIDNYKY.liqpay.perevirka(z('AAAA' + pidpys.slice(4)), env));
  }
});

test('plata by mono: підпис ECDSA сповіщення перевіряється; підписку чесно не підтримує', async () => {
  const { publicKey, privateKey } = generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
  const env = { MONO_PUBKEY: Buffer.from(publicKey.export({ type: 'spki', format: 'pem' })).toString('base64') };
  const tilo = JSON.stringify({ invoiceId: 'inv1', status: 'success', amount: 19900, ccy: 980, reference: 'zabc', modifiedDate: '2026-11-17T10:00:00Z' });
  const s = createSign('SHA256'); s.update(tilo);
  const xsign = s.sign(privateKey).toString('base64');
  const z = (t, x) => new Request(SAIT, { method: 'POST', body: t, headers: { 'x-sign': x } });
  const { podii } = await PEREKHIDNYKY.mono.perevirka(z(tilo, xsign), env);
  assert.deepEqual(podii.map((p) => [p.zamovlennia_id, p.suma, p.valiuta, p.podiia]), [['zabc', 199, 'UAH', 'oplata']]);
  await assert.rejects(PEREKHIDNYKY.mono.perevirka(z(tilo.replace('19900', '100'), xsign), env));
  await assert.rejects(PEREKHIDNYKY.mono.stvoryty({ zam: { id: 'z', suma: 399 }, pidpyska: { period_misiatsiv: 1 }, env }), /mono/);
});

test('SHA3-256 на чистому JS дорівнює node:crypto', () => {
  for (const t of ['', 'abc', 'ї'.repeat(200), 'x'.repeat(136)]) {
    assert.equal(Buffer.from(sha3_256(new TextEncoder().encode(t))).toString('hex'), createHash('sha3-256').update(t).digest('hex'));
  }
});

test('видалення на запит через партнера: лише з ключем партнера; підписку спершу скасовано', async () => {
  const env = seredovyshche({ ADMIN_KLIUCH: 'admin-kliuch' });
  await oplatyty(env, await zamovyty(env, 'pidpyska', null, 'olia@poshta.ua'));
  const z = (k) => zapyt(env, 'POST', '/api/admin/vydalyty', { forma: { poshta: 'olia@poshta.ua' }, origin: null, zaholovky: { authorization: `Bearer ${k}` } });
  assert.equal((await z('ne-toi')).r.status, 401);
  assert.equal((await z('vydacha-kliuch')).r.status, 401, 'ключ видавача не дає видаляти');
  const { text } = await z('admin-kliuch');
  assert.deepEqual(JSON.parse(text), { vydaleno: true });
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM korystuvachi')[0].n, 0);
  assert.equal(sql(env, 'SELECT status FROM pidpysky')[0].status, 'skasovana');
});

test('вхід (ZAVDANNYA-161, п. 1): поштовий сканер відкриває посилання — вхід не згоряє; увійти — лише кнопкою з нашого сайту', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/'));
  await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta: 'ana@poshta.ua' } });
  const lyst = env.__LYSTY.filter((l) => l.tema.startsWith('Вхід')).at(-1);
  assert.match(lyst.tekst, /натисніть «Увійти»/);
  const t = lyst.tekst.match(/\?t=([a-z2-7]+)/)[1];
  // сканер пошти тричі відкрив посилання (GET) — сесії немає, вхід не витрачено
  for (let i = 0; i < 3; i++) {
    const { r, text } = await zapyt(env, 'GET', `/kabinet/vkhid/?t=${t}`, { origin: null });
    assert.equal(r.status, 200);
    assert.equal(r.headers.get('set-cookie'), null);
    assert.match(text, /name="t" value="[a-z2-7]+"/);
    assert.equal(r.headers.get('cache-control'), 'no-store');
  }
  assert.equal(sql(env, 'SELECT COUNT(*) AS n FROM sesii')[0].n, 0);
  // кнопка з чужого сайту — ні
  assert.equal((await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t }, origin: 'https://zlyi.test' })).r.status, 403);
  // людина натиснула «Увійти»
  const { r, kudy } = await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t } });
  assert.equal(r.status, 303);
  assert.equal(new URL(kudy).pathname, '/kabinet/');
  assert.match(r.headers.get('set-cookie'), /^mv_sesiia=/);
  // після входу сторінка з посиланням каже «застаріло», а не показує кнопку
  assert.doesNotMatch((await zapyt(env, 'GET', `/kabinet/vkhid/?t=${t}`)).text, /Увійти<\/button>/);
  // вигаданий ключ — «застаріло», без кнопки
  assert.match((await zapyt(env, 'GET', '/kabinet/vkhid/?t=<script>')).text, /застаріло/);
});

test('лист «Оплату отримано» (ZAVDANNYA-161, п. 3): одразу після оплати — що, сума, номер, коли й де, як повернути; один раз', async () => {
  const env = seredovyshche();
  const id = await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/');
  assert.equal(env.__LYSTY.filter((l) => /^Оплату отримано/.test(l.tema)).length, 0, 'до оплати — нічого');
  await oplatyty(env, id);
  const lysty = env.__LYSTY.filter((l) => /^Оплату отримано/.test(l.tema));
  assert.equal(lysty.length, 1);
  const l = lysty[0];
  assert.equal(l.komu, 'ana@poshta.ua');
  assert.match(l.tema, /Довідка про будинок/);
  assert.match(l.tekst, /вулиця Жилянська, 5/);
  assert.match(l.tekst, new RegExp(`Сума: ${t.tsiny.dovidka} грн`));
  assert.match(l.tekst, new RegExp(`Замовлення: ${id}`));
  assert.match(l.tekst, /не пізніше ніж за 1 робочий день/);
  assert.match(l.tekst, /Повернення — за офертою/);
  assert.match(l.tekst, /https:\/\/mv\.test\/zahlushka\/oferta\.html/);
  // повтор того самого сповіщення й друга подія «оплачено» — другого листа немає
  await oplatyty(env, id);
  assert.equal(env.__LYSTY.filter((l) => /^Оплату отримано/.test(l.tema)).length, 1);
});

test('лист «Оплату отримано»: підписка — до якої дати, як скасувати; чергове списання — «продовжено»; відмова — без листа', async () => {
  const env = seredovyshche();
  const id = await zamovyty(env, 'pidpyska', null, 'bo@poshta.ua');
  await oplatyty(env, id);
  const l = env.__LYSTY.find((x) => /^Оплату отримано/.test(x.tema));
  assert.match(l.tekst, /Доступ відкрито до \d\d\.\d\d\.\d{4}/);
  assert.match(l.tekst, /\/pidpysnyk\//);
  assert.match(l.tekst, /Скасувати — у кабінеті/);
  env.krok(29 * 86400);
  await oplatyty(env, id, 'Списання наступного періоду');
  const p = env.__LYSTY.filter((x) => /^Оплату отримано/.test(x.tema));
  assert.equal(p.length, 2);
  assert.match(p[1].tema, /продовжено/);
  assert.match(p[1].tekst, /Доступ продовжено до/);
  const id2 = await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/', 'vira@poshta.ua');
  await oplatyty(env, id2, 'Відмова');
  assert.equal(env.__LYSTY.filter((x) => x.komu === 'vira@poshta.ua' && /^Оплату отримано/.test(x.tema)).length, 0);
});
