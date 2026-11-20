// Тести ZAVDANNYA-172: виправлення за критиками 166, 167, 169, 171 — «Дякуємо» за товаром, «скоро» з увімкненою оплатою,
// кабінет (карта, підтвердження видалення, за роллю), листи, логотип, звернення. Запуск: node --test site/worker/testy/
// Справжній код Workers на справжній SQL-схемі (як prodazh.test.mjs).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../index.js';
import { d1, r2 } from './pidminy.mjs';

const SAIT = 'https://mv.test';
const BUDYNKY = { '/budynok/zhylianska/5/': 'вулиця Жилянська, 5', '/budynok/obolonskyi/16/': 'проспект Оболонський, 16' };

function seredovyshche(dod = {}) {
  let chas = 1_790_000_000;
  const env = {
    PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 'test-kliuch', VYDACHA_KLIUCH: 'vydacha-kliuch',
    ADRESA_SAITU: SAIT, POSHTA_PARTNERA: 'partner@mv.test',
    BAZA: d1(), DOVIDKY: r2(), __LYSTY: [], __CHAS: () => chas,
    ASSETS: {
      async fetch(req) {
        const p = new URL(req.url).pathname;
        if (BUDYNKY[p]) return new Response(`<!doctype html><main><h1>${BUDYNKY[p]}</h1></main>`, { status: 200 });
        return new Response('немає', { status: 404 });
      },
    },
    ...dod,
  };
  env.krok = (s) => { chas += s; };
  return env;
}

export async function zapyt(env, metod, shliakh, { forma, kuka, origin = SAIT, zaholovky = {}, tilo } = {}) {
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

async function zamovyty(env, tovar, budynok, poshta = 'ana@poshta.ua') {
  const f = { tovar, poshta, zghoda: 'tak', odrazu: 'tak' };
  if (budynok) f.budynok = budynok;
  const { r, kudy } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: f });
  assert.equal(r.status, 303, 'замовлення має вести на оплату');
  return new URL(kudy).pathname.match(/\/oplata\/test\/(z[a-z2-7]+)\//)[1];
}
async function oplatyty(env, id) {
  const { text } = await zapyt(env, 'GET', `/oplata/test/${id}/`);
  const k = polia(text).find((x) => x.napys === 'Оплата пройшла');
  return zapyt(env, 'POST', '/api/spovishchennia/test', { forma: k.forma, origin: null });
}
async function uviity(env, poshta = 'ana@poshta.ua') {
  await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta } });
  const lyst = env.__LYSTY.filter((l) => l.komu === poshta && l.tema.startsWith('Вхід')).at(-1);
  const t = lyst.tekst.match(/\/kabinet\/vkhid\/\?t=([a-z2-7]+)/)[1];
  const { r } = await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t } });
  return r.headers.get('set-cookie').split(';')[0];
}
const AVT = { authorization: 'Bearer vydacha-kliuch' };
async function vydavach(env) {
  const { text } = await zapyt(env, 'GET', '/api/vnutr/cherha?n=10', { zaholovky: AVT });
  const ds = JSON.parse(text).dovidky;
  for (const d of ds) await zapyt(env, 'PUT', `/api/vnutr/dovidka/${d.id}`, { zaholovky: AVT, tilo: '<!doctype html><p>довідка</p>' });
  return ds;
}

// ---------------------------------------------------------------- «Дякуємо» (ZVIT-166 З-8, ZVIT-167 п. 9, ZVIT-169 п. 1)

test('«Дякуємо» за товаром: підписка — «Відкрити карту», не «довідку почнемо готувати»; звіт — «звіт»; довідка — як була', async () => {
  const env = seredovyshche();
  const pidp = await zamovyty(env, 'pidpyska');
  const { kudy } = await oplatyty(env, pidp);
  let { text } = await zapyt(env, 'GET', new URL(kudy).pathname + new URL(kudy).search);
  assert.match(text, /карта підписника/);
  assert.match(text, /href="\/pidpysnyk\/">Відкрити карту</);
  assert.ok(!/довідку почнемо готувати/.test(text));

  const zv = await zamovyty(env, 'zvit', '/budynok/zhylianska/5/');
  ({ text } = await zapyt(env, 'GET', `/oplata/dyakuiemo/?z=${zv}`));
  assert.match(text, /звіт почнемо готувати/);
  assert.ok(!/Відкрити карту/.test(text));

  const dv = await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/');
  ({ text } = await zapyt(env, 'GET', `/oplata/dyakuiemo/?z=${dv}`));
  assert.match(text, /довідку почнемо готувати/);
  ({ text } = await zapyt(env, 'GET', '/oplata/dyakuiemo/?z=../../x'));
  assert.match(text, /довідку почнемо готувати/, 'невідомий номер — загальний текст, без помилки');
});

test('форма повного звіту каже «звіт», підписки — «вхід у кабінет», не «посилання на довідку»', async () => {
  const env = seredovyshche();
  let { text } = await zapyt(env, 'GET', '/oplata/?tovar=zvit&budynok=/budynok/zhylianska/5/');
  assert.match(text, /посилання на звіт/);
  assert.ok(!/посилання на довідку/.test(text));
  ({ text } = await zapyt(env, 'GET', '/oplata/?tovar=pidpyska'));
  assert.ok(!/посилання на довідку/.test(text));
});

test('«скоро» з увімкненою оплатою («Судова практика»): після «Залишити пошту» — «Записали», не «підтвердить оплату»', async () => {
  const env = seredovyshche();
  const v = await zapyt(env, 'POST', '/api/skoro', { forma: { tovar: 'spdovidka', poshta: 'yu@b.ua', zghoda: 'tak' } });
  assert.equal(v.r.status, 303);
  const { text } = await zapyt(env, 'GET', new URL(v.kudy).pathname);
  assert.match(text, /Записали/);
  assert.ok(!/підтвердить оплату/.test(text));
  assert.ok(!/довідку почнемо готувати/.test(text));
});
