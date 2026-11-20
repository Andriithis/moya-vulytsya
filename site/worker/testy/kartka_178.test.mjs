// ZAVDANNYA-178 (MV-183): «картка для мешканців / клієнта» на сервері продажу і тема листа ОСББ з речення генератора.
// Справжній код Workers на справжній схемі (skhema.sql у SQLite), підставні сайт, сховище й пошта.
// Запуск: node --test site/worker/testy/  (Node 22+).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../index.js';
import { pidsumokZDovidky } from '../prodazh/logika.js';
import { d1, r2 } from './pidminy.mjs';

const SAIT = 'https://mv.test';
const BUDYNKY = { '/budynok/zhylianska/5/': 'вулиця Жилянська, 5', '/budynok/obolonskyi/16/': 'проспект Оболонський, 16' };
const AVT = { authorization: 'Bearer vydacha-kliuch' };
const NAPYS = 'Коротка картка для мешканців (лише числа)';
const KARTKA = '<!doctype html><title>картка</title><p>Скарг до 1551 за рік: 84</p>';
const MISIATS = 'Жовтень: 19 звернень до 1551 (у вересні — 29); світло — 7, у сусідніх типово 1.';
const DOVIDKA_OSBB = `<!DOCTYPE html>\n<html lang="uk"><head><meta charset="utf-8"><title>т</title><meta name="pidsumok" content="${
  MISIATS.replace(/&/g, '&amp;')}"></head><body><p>довідка з описами подій</p></body></html>`;

function seredovyshche(baza = d1()) {
  const env = {
    PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 'test-kliuch', VYDACHA_KLIUCH: 'vydacha-kliuch',
    ADRESA_SAITU: SAIT, BAZA: baza, DOVIDKY: r2(), __LYSTY: [], __CHAS: () => 1_790_000_000,
    ASSETS: {
      async fetch(req) {
        const p = new URL(req.url).pathname;
        if (BUDYNKY[p]) return new Response(`<!doctype html><main><h1>${BUDYNKY[p]}</h1></main>`, { status: 200 });
        return new Response('немає', { status: 404 });
      },
    },
  };
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

async function kupyty(env, tovar, budynok, poshta) {
  const { kudy } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar, budynok, poshta, zghoda: 'tak', odrazu: 'tak' } });
  const id = new URL(kudy).pathname.match(/\/oplata\/test\/(z[a-z2-7]+)\//)[1];
  const { text } = await zapyt(env, 'GET', `/oplata/test/${id}/`);
  const f = [...text.matchAll(/<form method="post" action="\/api\/spovishchennia\/test">([\s\S]*?)<\/form>/g)]
    .find((x) => x[1].includes('Оплата пройшла'))[1];
  await zapyt(env, 'POST', '/api/spovishchennia/test', { forma: Object.fromEntries([...f.matchAll(/name="([^"]+)" value="([^"]*)"/g)].map((y) => [y[1], y[2]])), origin: null });
}

/** Видавач: картка (якщо є) — до довідки, як site/prodazh/vydavach.py. */
async function vydavach(env, { kartka = KARTKA, dovidka = '<!doctype html><p>довідка з описами подій</p>' } = {}) {
  const ds = JSON.parse((await zapyt(env, 'GET', '/api/vnutr/cherha?n=10', { zaholovky: AVT })).text).dovidky;
  const statusy = [];
  for (const d of ds) {
    if (kartka) statusy.push((await zapyt(env, 'PUT', `/api/vnutr/kartka/${d.id}`, { zaholovky: AVT, tilo: kartka })).r.status);
    assert.equal((await zapyt(env, 'PUT', `/api/vnutr/dovidka/${d.id}`, { zaholovky: AVT, tilo: dovidka })).r.status, 204);
  }
  return { ds, statusy };
}

async function uviity(env, poshta) {
  await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta } });
  const t = env.__LYSTY.filter((l) => l.komu === poshta && l.tema.startsWith('Вхід')).at(-1).tekst.match(/\?t=([a-z2-7]+)/)[1];
  const { r } = await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t } });
  return r.headers.get('set-cookie').split(';')[0];
}
const lyst = (env, poshta) => env.__LYSTY.filter((l) => l.komu === poshta && !l.tema.startsWith('Вхід') && !l.tema.startsWith('Оплату')).at(-1);
const shliakh = (tekst, re) => tekst.match(re)?.[1];

test('картка: видавач кладе до довідки, лист «готово» дає своє посилання; ключ довідки її не відкриває і навпаки', async () => {
  const env = seredovyshche();
  await kupyty(env, 'dovidka', '/budynok/obolonskyi/16/', 'ana@poshta.ua');
  const { ds, statusy } = await vydavach(env);
  assert.deepEqual(statusy, [204]);
  const l = lyst(env, 'ana@poshta.ua');
  assert.match(l.tekst, new RegExp(`${NAPYS.replace(/[()]/g, '\\$&')} — її можна переслати`));
  const kartka = shliakh(l.tekst, /https:\/\/mv\.test(\/dovidka\/d[a-z2-7]+\/kartka\/\?k=[a-z2-7]+)/);
  const dovidka = shliakh(l.tekst, /https:\/\/mv\.test(\/dovidka\/d[a-z2-7]+\/\?k=[a-z2-7]+)/);
  assert.ok(kartka && dovidka);
  let v = await zapyt(env, 'GET', kartka);
  assert.equal(v.r.status, 200);
  assert.equal(v.text, KARTKA);
  assert.match(v.r.headers.get('content-security-policy'), /sandbox/, 'той самий захист, що в довідки');
  assert.equal(v.r.headers.get('cache-control'), 'private, no-store');
  const kKartky = kartka.split('?k=')[1], kDovidky = dovidka.split('?k=')[1];
  assert.equal((await zapyt(env, 'GET', `/dovidka/${ds[0].id}/kartka/?k=${kDovidky}`)).r.status, 404, 'ключ довідки картку не відкриває');
  assert.equal((await zapyt(env, 'GET', `/dovidka/${ds[0].id}/?k=${kKartky}`)).r.status, 404, 'ключ картки довідку не відкриває');
  assert.equal((await zapyt(env, 'GET', `/dovidka/${ds[0].id}/kartka/`)).r.status, 404, 'без ключа й без входу — ні');
  assert.equal((await zapyt(env, 'GET', `/dovidka/${ds[0].id}/kartka/?k=${'a'.repeat(39)}`)).r.status, 404);
  const [rd] = sql(env, 'SELECT kartka_fail, kartka_hash FROM dovidky');
  assert.ok(rd.kartka_fail && rd.kartka_hash && !rd.kartka_hash.includes(kKartky), 'ключ не зберігаємо — лише його відбиток');
});

test('кабінет: кнопка картки поруч із довідкою; нове посилання закриває старе; «Закрити» — лише власнику лишається', async () => {
  const env = seredovyshche();
  await kupyty(env, 'dovidka', '/budynok/obolonskyi/16/', 'ana@poshta.ua');
  const { ds } = await vydavach(env);
  const id = ds[0].id;
  const stara = shliakh(lyst(env, 'ana@poshta.ua').tekst, /https:\/\/mv\.test(\/dovidka\/d[a-z2-7]+\/kartka\/\?k=[a-z2-7]+)/);
  const kuka = await uviity(env, 'ana@poshta.ua');
  let { text } = await zapyt(env, 'GET', '/kabinet/', { kuka });
  assert.ok(text.includes(`<a href="/dovidka/${id}/kartka/">${NAPYS}</a>`), 'кнопка з текстом із завдання');
  assert.match(text, /Посилання, щоб поділитися/);
  assert.match(text, /Закрити посилання на картку/);
  assert.equal((await zapyt(env, 'GET', `/dovidka/${id}/kartka/`, { kuka })).r.status, 200, 'власнику — з кабінету, без ключа');

  // нове посилання: старе більше не відкривається, нове — так
  ({ text } = await zapyt(env, 'POST', '/kabinet/kartka/nove', { forma: { dovidka: id }, kuka }));
  const nove = shliakh(text, /https:\/\/mv\.test(\/dovidka\/d[a-z2-7]+\/kartka\/\?k=[a-z2-7]+)/);
  assert.ok(nove && nove !== stara);
  assert.match(text, /старе більше не відкривається/);
  assert.equal((await zapyt(env, 'GET', stara)).r.status, 404, 'старе посилання відкликано');
  assert.equal((await zapyt(env, 'GET', nove)).r.status, 200);

  // чужий не може ні дати нове посилання, ні закрити
  await kupyty(env, 'dovidka', '/budynok/zhylianska/5/', 'bo@poshta.ua');
  await vydavach(env);
  const kuka2 = await uviity(env, 'bo@poshta.ua');
  ({ text } = await zapyt(env, 'POST', '/kabinet/kartka/nove', { forma: { dovidka: id }, kuka: kuka2 }));
  assert.match(text, /Такої картки немає/);
  ({ text } = await zapyt(env, 'POST', '/kabinet/kartka/zakryty', { forma: { dovidka: id }, kuka: kuka2 }));
  assert.match(text, /Такої картки немає/);
  assert.equal((await zapyt(env, 'GET', nove)).r.status, 200);
  assert.equal((await zapyt(env, 'GET', `/dovidka/${id}/kartka/`, { kuka: kuka2 })).r.status, 404, 'чужа картка — ні');
  // дію кабінету — лише з нашого сайту
  assert.equal((await zapyt(env, 'POST', '/kabinet/kartka/nove', { forma: { dovidka: id }, kuka, origin: 'https://zlyi.test' })).r.status, 403);

  // закрити: посилання не відкривається, власнику — так, кнопки «Закрити» вже немає
  ({ text } = await zapyt(env, 'POST', '/kabinet/kartka/zakryty', { forma: { dovidka: id }, kuka }));
  assert.match(text, /Посилання на картку закрито/);
  assert.doesNotMatch(text, /Закрити посилання на картку/);
  assert.equal((await zapyt(env, 'GET', nove)).r.status, 404);
  assert.equal((await zapyt(env, 'GET', `/dovidka/${id}/kartka/`, { kuka })).r.status, 200);
});

test('картка: без неї — довідка як раніше; «Судова практика» картки не бере; видалення даних прибирає й картку', async () => {
  const env = seredovyshche();
  await kupyty(env, 'dovidka', '/budynok/obolonskyi/16/', 'ana@poshta.ua');
  await vydavach(env, { kartka: null });
  const l = lyst(env, 'ana@poshta.ua');
  assert.doesNotMatch(l.tekst, /картк/i, 'без картки — без рядка про неї');
  const kuka = await uviity(env, 'ana@poshta.ua');
  assert.doesNotMatch((await zapyt(env, 'GET', '/kabinet/', { kuka })).text, /Коротка картка/);

  // картку після готової довідки сервер не бере (лист уже пішов)
  const [d] = sql(env, 'SELECT id FROM dovidky');
  assert.equal((await zapyt(env, 'PUT', `/api/vnutr/kartka/${d.id}`, { zaholovky: AVT, tilo: KARTKA })).r.status, 409);
  assert.equal((await zapyt(env, 'PUT', `/api/vnutr/kartka/${d.id}`, { tilo: KARTKA })).r.status, 401, 'без ключа видавача — ні');

  // видалення даних: файли довідки й картки — геть
  const env2 = seredovyshche();
  await kupyty(env2, 'dovidka', '/budynok/obolonskyi/16/', 'vo@poshta.ua');
  await vydavach(env2);
  assert.equal(env2.DOVIDKY.m.size, 2);
  const k2 = await uviity(env2, 'vo@poshta.ua');
  await zapyt(env2, 'POST', '/kabinet/vydalyty', { forma: { pidtverdzhuiu: 'tak', rozumiiu: 'tak' }, kuka: k2 });
  assert.equal(env2.DOVIDKY.m.size, 0, 'картка зникає разом із довідкою');
  assert.deepEqual({ ...sql(env2, 'SELECT kartka_fail, kartka_hash FROM dovidky')[0] }, { kartka_fail: null, kartka_hash: null });

  // «Судова практика» (rezhym sp) — без картки: у неї немає будинку
  env2.BAZA.db.prepare(`INSERT INTO dovidky (id, zamovlennia_id, budynok, adresa, rezhym, status, stvoreno) VALUES ('dsp', 'z', '', 'ст. 130', 'sp', 'hotuietsia', 1)`).run();
  assert.equal((await zapyt(env2, 'PUT', '/api/vnutr/kartka/dsp', { zaholovky: AVT, tilo: KARTKA })).r.status, 409);
  assert.equal(env2.DOVIDKY.m.size, 0);
});

test('стара база без стовпців картки (skhema-178.sql не виконано): довідка, лист і кабінет — як раніше', async () => {
  const baza = d1();
  baza.db.exec('ALTER TABLE dovidky DROP COLUMN kartka_fail; ALTER TABLE dovidky DROP COLUMN kartka_hash;');
  const env = seredovyshche(baza);
  await kupyty(env, 'dovidka', '/budynok/obolonskyi/16/', 'ana@poshta.ua');
  const { statusy } = await vydavach(env);
  assert.deepEqual(statusy, [409], 'картку стара база не бере — видавач іде далі');
  assert.equal(env.DOVIDKY.m.size, 1, 'і файла картки в сховищі не лишає');
  assert.match(lyst(env, 'ana@poshta.ua').tekst, /Відкрити: https:\/\/mv\.test\/dovidka\//);
  const kuka = await uviity(env, 'ana@poshta.ua');
  const { r, text } = await zapyt(env, 'GET', '/kabinet/', { kuka });
  assert.equal(r.status, 200);
  assert.doesNotMatch(text, /Коротка картка/);
  await zapyt(env, 'POST', '/kabinet/vydalyty', { forma: { pidtverdzhuiu: 'tak', rozumiiu: 'tak' }, kuka });
  assert.equal(env.DOVIDKY.m.size, 0);
});

test('ОСББ: тема листа — речення місяця з довідки (meta pidsumok), картка — і в листі ОСББ, і в кабінеті', async () => {
  assert.equal(pidsumokZDovidky(DOVIDKA_OSBB), MISIATS);
  assert.equal(pidsumokZDovidky('<!doctype html><p>без meta</p>'), '');
  assert.equal(pidsumokZDovidky('<meta name="pidsumok" content="a &quot;b&quot; &amp; c\nd">'), 'a "b" & c d', 'один рядок, без кодів HTML');
  const dovge = pidsumokZDovidky(`<meta name="pidsumok" content="${'слово '.repeat(60)}">`);
  assert.ok(dovge.length <= 160 && dovge.endsWith('…'));

  const env = seredovyshche();
  await kupyty(env, 'osbb', '/budynok/obolonskyi/16/', 'pravlinnia@poshta.ua');
  await vydavach(env, { dovidka: DOVIDKA_OSBB });
  const l = lyst(env, 'pravlinnia@poshta.ua');
  assert.equal(l.tema, `проспект Оболонський, 16. ${MISIATS}`);
  assert.doesNotMatch(l.tema, /[\r\n]/);
  assert.match(l.tekst, new RegExp(`Цього місяця: ${MISIATS.replace(/[()]/g, '\\$&')}`));
  assert.match(l.tekst, /Коротка картка для мешканців \(лише числа\) — її можна переслати/);
  const kuka = await uviity(env, 'pravlinnia@poshta.ua');
  const { text } = await zapyt(env, 'GET', '/kabinet/', { kuka });
  const osbb = text.slice(text.indexOf('id="osbb"'));
  assert.ok(osbb.includes(NAPYS), 'у розділі «Мій будинок (ОСББ)» — поруч із довідкою');

  // довідка без речення місяця — тема як раніше
  const env2 = seredovyshche();
  await kupyty(env2, 'osbb', '/budynok/obolonskyi/16/', 'p2@poshta.ua');
  await vydavach(env2);
  assert.equal(lyst(env2, 'p2@poshta.ua').tema, 'Щомісячна довідка для ОСББ: проспект Оболонський, 16');
});
