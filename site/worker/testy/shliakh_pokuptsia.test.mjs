// ZAVDANNYA-150: шлях покупця на сервері продажу — будинок словами (п. 6), залишок довідок замість другої оплати (п. 3),
// опис підписки на формі (п. 5), без службових слів (п. 12). Справжній код Workers на справжній схемі (як osbb_rieltor).
// Запуск: node --test site/worker/testy/  (Node 22+).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../index.js';
import TS from '../prodazh/tsiny.js';
import { d1, r2 } from './pidminy.mjs';

const SAIT = 'https://mv.test';
const BUDYNKY = {
  '/budynok/zhylianska/5/': 'вулиця Жилянська, 5', '/budynok/obolonskyi/16/': 'проспект Оболонський, 16',
  '/budynok/demiivska/45/': 'вулиця Деміївська, 45', '/budynok/demiivskyi-provulok/45/': 'провулок Деміївський, 45',
};
// файл пошуку будинків сайту (vulytsi/budynky.json): [назва, slug вулиці, старі назви, [[номер, сторінка], …]]
const POSHUK = [
  ['вулиця Жилянська', 'zhylianska', 'Жаданівського', [['5', '/budynok/zhylianska/5/']]],
  ['проспект Оболонський', 'obolonskyi', '', [['16', '/budynok/obolonskyi/16/']]],
  ['вулиця Деміївська', 'demiivska', '', [['45', '/budynok/demiivska/45/']]],
  ['провулок Деміївський', 'demiivskyi-provulok', '', [['45', '/budynok/demiivskyi-provulok/45/']]],
];

function seredovyshche() {
  let chas = 1_790_000_000;
  const env = {
    PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 'test-kliuch', VYDACHA_KLIUCH: 'vydacha-kliuch',
    ADRESA_SAITU: SAIT, BAZA: d1(), DOVIDKY: r2(), __LYSTY: [], __CHAS: () => chas,
    ASSETS: {
      async fetch(req) {
        const p = new URL(req.url).pathname;
        if (p === '/vulytsi/budynky.json') return Response.json(POSHUK);
        if (BUDYNKY[p]) return new Response(`<!doctype html><main><h1>${BUDYNKY[p]}</h1></main>`, { status: 200 });
        return new Response('немає', { status: 404 });
      },
    },
  };
  env.krok = (s) => { chas += s; };
  return env;
}

async function zapyt(env, metod, shliakh, { forma, kuka, origin = SAIT } = {}) {
  const h = {};
  if (origin) h.origin = origin;
  if (kuka) h.cookie = kuka;
  const r = await worker.fetch(new Request(SAIT + shliakh, { method: metod, headers: h, body: forma ? new URLSearchParams(forma) : undefined, redirect: 'manual' }), env);
  return { r, text: await r.text(), kudy: r.headers.get('location') };
}
const sql = (env, s, ...p) => env.BAZA.db.prepare(s).all(...p);

async function zamovyty(env, tovar, budynok, poshta) {
  const f = { tovar, poshta, zghoda: 'tak', odrazu: 'tak' };
  if (budynok) f.budynok = budynok;
  const { r, kudy, text } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: f });
  assert.equal(r.status, 303, `замовлення має вести на оплату: ${text.slice(0, 300)}`);
  return new URL(kudy).pathname.match(/\/oplata\/test\/(z[a-z2-7]+)\//)[1];
}

async function oplatyty(env, id) {
  const { text } = await zapyt(env, 'GET', `/oplata/test/${id}/`);
  const m = [...text.matchAll(/<form method="post" action="\/api\/spovishchennia\/test">([\s\S]*?)<\/form>/g)]
    .map((x) => Object.fromEntries([...x[1].matchAll(/name="([^"]+)" value="([^"]*)"/g)].map((y) => [y[1], y[2]])))[0];
  return zapyt(env, 'POST', '/api/spovishchennia/test', { forma: m, origin: null });
}

async function uviity(env, poshta) {
  await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta } });
  const t = env.__LYSTY.filter((l) => l.komu === poshta && l.tema.startsWith('Вхід')).at(-1).tekst.match(/\?t=([a-z2-7]+)/)[1];
  assert.equal((await zapyt(env, 'GET', `/kabinet/vkhid/?t=${t}`)).r.status, 200);   // сторінка з кнопкою «Увійти» (ZAVDANNYA-161)
  const { r } = await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t } });
  return r.headers.get('set-cookie').split(';')[0];
}

test('п. 6: ОСББ — будинок словами («Оболонський 16», «вул. Жилянська, буд. 5», стара назва), без посилання', async () => {
  const env = seredovyshche();
  const { text } = await zapyt(env, 'GET', '/oplata/?tovar=osbb&dzherelo=osbb');
  assert.match(text, /Будинок — вулиця й номер/);
  assert.match(text, /list="budynok-pidkazky"/, 'підказки адрес');
  assert.match(text, /\/sait\/budynok-pole\.js/);
  assert.doesNotMatch(text, /вставте посилання|https:\/\/…\/budynok/i, 'посилання більше не просимо');
  for (const [vvedeno, budynok] of [['Оболонський 16', '/budynok/obolonskyi/16/'], ['вул. Жилянська, буд. 5', '/budynok/zhylianska/5/'],
    ['Жаданівського 5', '/budynok/zhylianska/5/'], ['https://mv.test/budynok/obolonskyi/16/', '/budynok/obolonskyi/16/']]) {
    await zamovyty(env, 'osbb', vvedeno, `o${vvedeno.length}@poshta.ua`);
    assert.equal(sql(env, 'SELECT budynok FROM zamovlennia ORDER BY rowid DESC LIMIT 1')[0].budynok, budynok, vvedeno);
  }
});

test('п. 6: кілька вулиць підходять — просимо обрати; немає будинку — кажемо чесно й лишаємо введене', async () => {
  const env = seredovyshche();
  let { text } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'osbb', budynok: 'Деміївськ 45', poshta: 'o@poshta.ua', zghoda: 'tak', odrazu: 'tak' } });
  assert.match(text, /Підходить кілька адрес: вулиця Деміївська, 45; провулок Деміївський, 45/);
  assert.match(text, /value="o@poshta\.ua"/, 'пошту не треба вписувати знову');
  // з підказки — повна назва: одна адреса
  await zamovyty(env, 'osbb', 'вулиця Деміївська, 45', 'o2@poshta.ua');
  ({ text } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'osbb', budynok: 'Хрещатик 999', poshta: 'o@poshta.ua', zghoda: 'tak', odrazu: 'tak' } }));
  assert.match(text, /Такого будинку в наших даних немає/);
  assert.match(text, /value="Хрещатик 999"/);
});

test('п. 6: рієлтор «Мої об\'єкти» і «Стежу» — адреса словами', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'rieltor', null, 'r@poshta.ua'));
  const k = await uviity(env, 'r@poshta.ua');
  const kab = (await zapyt(env, 'GET', '/kabinet/', { kuka: k })).text;
  assert.match(kab, /Новий об'єкт — вулиця й номер/);
  assert.match(kab, /Додати будинок — вулиця й номер/);
  assert.doesNotMatch(kab, /docs\/|\.md\)|Скопіюйте адресу/);
  assert.match((await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: k, forma: { budynok: 'Деміївська 45' } })).text, /Довідку на вулиця Деміївська, 45 готуємо/);
  assert.match((await zapyt(env, 'POST', '/kabinet/stezhu', { kuka: k, forma: { budynok: 'Оболонський 16' } })).text, /Стежите: проспект Оболонський, 16/);
  assert.match((await zapyt(env, 'POST', '/kabinet/stezhu', { kuka: k, forma: { budynok: 'Оболонський' } })).text, /Додайте номер будинку/);
});

test('п. 3: з пакетом «3 довідки» кнопка «Довідка» пропонує залишок, а не нову оплату; без залишку — звичайна оплата', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'try', '/budynok/zhylianska/5/', 't@poshta.ua'));
  const k = await uviity(env, 't@poshta.ua');
  let { text } = await zapyt(env, 'GET', '/oplata/?tovar=dovidka&budynok=/budynok/obolonskyi/16/', { kuka: k });
  assert.match(text, /Використати залишок \(2\)/);
  assert.match(text, /action="\/kabinet\/dovidka"/);
  assert.match(text, /<button class="knopka" type="submit">Перейти до оплати/, 'оплата — другою, не головною');
  ({ text } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: k, forma: { budynok: '/budynok/obolonskyi/16/' } }));
  assert.match(text, /готуємо/);
  assert.equal(sql(env, `SELECT COUNT(*) n FROM zamovlennia WHERE tovar = 'dovidka'`)[0].n, 0, 'другої оплати немає');
  await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: k, forma: { budynok: '/budynok/obolonskyi/16/', shche: 'tak' } });
  ({ text } = await zapyt(env, 'GET', '/oplata/?tovar=dovidka&budynok=/budynok/obolonskyi/16/', { kuka: k }));
  assert.doesNotMatch(text, /Використати залишок/, 'залишку немає — лише оплата');
  // без входу — як раніше
  ({ text } = await zapyt(env, 'GET', '/oplata/?tovar=dovidka&budynok=/budynok/obolonskyi/16/'));
  assert.doesNotMatch(text, /Використати залишок/);
});

test('п. 3: ОСББ — залишок лише на свій будинок', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'osbb', '/budynok/obolonskyi/16/', 'osbb@poshta.ua'));
  const k = await uviity(env, 'osbb@poshta.ua');
  env.krok(32 * 86400);
  const k2 = await uviity(env, 'osbb@poshta.ua');
  assert.match((await zapyt(env, 'GET', '/oplata/?tovar=dovidka&budynok=/budynok/obolonskyi/16/', { kuka: k2 })).text, /Використати залишок \(1\)/);
  assert.doesNotMatch((await zapyt(env, 'GET', '/oplata/?tovar=dovidka&budynok=/budynok/zhylianska/5/', { kuka: k2 })).text, /Використати залишок/);
  void k;
});

test('п. 5, 12: форма підписки 399 каже, що входить (той самий перелік, що на сайті); без службового', async () => {
  const env = seredovyshche();
  const { text } = await zapyt(env, 'GET', '/oplata/?tovar=pidpyska&dzherelo=miy-budynok');
  assert.match(text, /Що дає підписка/);
  for (const x of TS.pidpyska_daie) assert.ok(text.includes(x.replace(/«/g, '«')), x);
  assert.doesNotMatch(text, /Ціну бере сервер|таблиці цін|медіан|MV-\d|docs\//);
  assert.match(text, /Доступ відкривається одразу після оплати/);
});

// ---------------------------------------------------------------- п. 4: щомісячний лист «Стежу»
const AVT = { authorization: 'Bearer vydacha-kliuch' };
async function vnutr(env, metod, shliakh, tilo) {
  const r = await worker.fetch(new Request(SAIT + shliakh, { method: metod, headers: { ...AVT, 'content-type': 'application/json' },
    body: tilo ? JSON.stringify(tilo) : undefined }), env);
  return { r, text: await r.text() };
}

test('п. 4: черга листа «Стежу» — лише дійсна підписка з адресами, без пошти; один лист на місяць; вимкнути в кабінеті', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'pidpyska', null, 'p@poshta.ua'));
  await oplatyty(env, await zamovyty(env, 'try', '/budynok/zhylianska/5/', 'try@poshta.ua'));     // не підписка — листа немає
  const kp = await uviity(env, 'p@poshta.ua');
  const kt = await uviity(env, 'try@poshta.ua');
  assert.match((await zapyt(env, 'GET', '/kabinet/', { kuka: kp })).text, /Раз на місяць, після оновлення даних, надсилаємо лист/);
  await zapyt(env, 'POST', '/kabinet/stezhu', { kuka: kp, forma: { budynok: 'Оболонський 16' } });
  await zapyt(env, 'POST', '/kabinet/stezhu', { kuka: kt, forma: { budynok: 'Жилянська 5' } });
  assert.equal((await vnutr(env, 'GET', '/api/vnutr/stezhu?period=2026-11')).r.status, 200);
  const bezKliucha = await worker.fetch(new Request(`${SAIT}/api/vnutr/stezhu?period=2026-11`), env);
  assert.equal(bezKliucha.status, 401);
  let { text } = await vnutr(env, 'GET', '/api/vnutr/stezhu?period=2026-11');
  const ch = JSON.parse(text).pidpysnyky;
  assert.equal(ch.length, 1, 'лише підписник');
  assert.deepEqual(ch[0].adresy, [{ budynok: '/budynok/obolonskyi/16/', adresa: 'проспект Оболонський, 16' }]);
  assert.doesNotMatch(text, /@/, 'пошти в черзі немає');
  const lyst = { period: '2026-11', tema: 'Нове біля дому · 1–30 листопада', tekst: 'Моя вулиця\n\nтекст листа' };
  assert.equal((await vnutr(env, 'POST', `/api/vnutr/lyst-stezhu/${ch[0].id}`, lyst)).r.status, 204);
  assert.equal(env.__LYSTY.at(-1).komu, 'p@poshta.ua');
  assert.equal(env.__LYSTY.at(-1).tema, lyst.tema);
  assert.equal((await vnutr(env, 'POST', `/api/vnutr/lyst-stezhu/${ch[0].id}`, lyst)).r.status, 409, 'вдруге за місяць — ні');
  assert.equal(JSON.parse((await vnutr(env, 'GET', '/api/vnutr/stezhu?period=2026-11')).text).pidpysnyky.length, 0);
  assert.equal(JSON.parse((await vnutr(env, 'GET', '/api/vnutr/stezhu?period=2026-12')).text).pidpysnyky.length, 1, 'наступний місяць — знову');
  // вимкнув у кабінеті — у черзі немає й надіслати не можна
  ({ text } = await zapyt(env, 'POST', '/kabinet/stezhu/lyst', { kuka: kp, forma: { lyst: 'ni' } }));
  assert.match(text, /більше не надсилатимемо/);
  assert.match(text, /Надсилати лист/);
  assert.equal(JSON.parse((await vnutr(env, 'GET', '/api/vnutr/stezhu?period=2026-12')).text).pidpysnyky.length, 0);
  assert.equal((await vnutr(env, 'POST', `/api/vnutr/lyst-stezhu/${ch[0].id}`, { ...lyst, period: '2026-12' })).r.status, 404);
  await zapyt(env, 'POST', '/kabinet/stezhu/lyst', { kuka: kp, forma: { lyst: 'tak' } });
  assert.equal(JSON.parse((await vnutr(env, 'GET', '/api/vnutr/stezhu?period=2026-12')).text).pidpysnyky.length, 1);
  // підписка скінчилась — листа немає
  env.krok(40 * 86400);
  assert.equal(JSON.parse((await vnutr(env, 'GET', '/api/vnutr/stezhu?period=2027-01')).text).pidpysnyky.length, 0);
  assert.equal((await vnutr(env, 'GET', '/api/vnutr/stezhu?period=листопад')).r.status, 400);
});
