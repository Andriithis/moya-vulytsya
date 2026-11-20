// Тести карти підписника зі сховища R2 (ZAVDANNYA-133, п. 1). Запуск: node --test site/worker/testy/
// Справжній скрипт Workers (site/worker/index.js), справжня схема D1 (skhema.sql у SQLite), R2 — у пам'яті з вигаданою
// картою (жодних справжніх описів у репозиторії: вони лише в приватному сховищі).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../index.js';
import { klitynka, KLITYNKA } from '../prodazh/karta.js';
import { sha256 } from '../prodazh/bezpeka.js';
import { d1, r2 } from './pidminy.mjs';

const SAIT = 'https://mv.test';
const T0 = 1_790_000_000;
const A = [50.45012, 30.52341], B = [50.45031, 30.52388];      // дві адреси в одній клітинці
const VERSIIA = '2026-11-08';

function seredovyshche({ karta = true } = {}) {
  const env = {
    PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 't', ADRESA_SAITU: SAIT,
    BAZA: d1(), DOVIDKY: r2(), __LYSTY: [], __CHAS: () => T0,
    ASSETS: { async fetch() { return new Response('сайт', { status: 404 }); } },
  };
  if (karta) {
    env.KARTA = r2();
    const kl = klitynka(...A);
    const p = (k, v) => env.KARTA.m.set(`karta/${VERSIIA}/${k}`, typeof v === 'string' ? v : JSON.stringify(v));
    env.KARTA.m.set('karta/potochna.json', JSON.stringify({ versiia: VERSIIA, kategorii: ['Крадіжка', 'Грабіж'] }));
    p('index.html', '<!doctype html><title>Карта підписника</title>');
    p(`indeks/${kl}.json`, [[A[0], A[1], 0, 'вулиця Вигадана, 1'], [B[0], B[1], 1, 'вулиця Вигадана, 3']]);
    p(`spravy/${kl}.json`, {
      0: [[1, '2025-03-02', 21, '1/1/25', ['ab0123456789abcdef0123456789abcdef'], 'Особа 1 вигаданий опис А']],
      1: [[0, '2024-07-01', -1, '2/2/24', [], 'вигаданий опис Б']],
    });
  }
  return env;
}

function pidpysnyk(env, { diie_do = T0 + 86400, status = 'aktyvna' } = {}) {
  const db = env.BAZA.db;
  db.prepare('INSERT INTO korystuvachi (id, poshta, stvoreno) VALUES (1, ?, ?)').run('ana@poshta.ua', T0);
  db.prepare(`INSERT INTO pidpysky (id, korystuvach_id, tovar, status, pochatok, diie_do, zamovlennia_id, stvoreno)
              VALUES ('p1', 1, 'pidpyska', ?, ?, ?, 'z1', ?)`).run(status, T0 - 86400, diie_do, T0);
  db.prepare('INSERT INTO sesii (hash, korystuvach_id, do_) VALUES (?, 1, ?)').run(sha256('sesiia-ani'), T0 + 3600);
  return 'mv_sesiia=sesiia-ani';
}

async function zapyt(env, shliakh, kuka) {
  const r = await worker.fetch(new Request(SAIT + shliakh, { headers: kuka ? { cookie: kuka } : {}, redirect: 'manual' }), env);
  return { r, text: await r.text() };
}

test('клітинка — та сама формула, що в збирачі карти (map_adresy: KLITYNKA / 4, floor)', () => {
  assert.deepEqual(KLITYNKA, [0.018 / 4, 0.028 / 4]);
  assert.equal(klitynka(50.45012, 30.52341), `${Math.floor(50.45012 / 0.0045)}_${Math.floor(30.52341 / 0.007)}`);
});

test('без входу карти немає: на вхід у кабінет, описів у відповіді немає', async () => {
  const env = seredovyshche();
  for (const s of ['/pidpysnyk/', `/pidpysnyk/spravy/${klitynka(...A)}.json`, `/pidpysnyk/api/podii?la=${A[0]}&lo=${A[1]}`]) {
    const { r, text } = await zapyt(env, s);
    assert.equal(r.status, 303, s);
    assert.match(r.headers.get('location'), /\/kabinet\/$/);
    assert.doesNotMatch(text, /вигаданий опис/);
  }
});

test('вхід без дійсної підписки — «для підписників» (403), і скінчена підписка теж', async () => {
  for (const stan of [{ diie_do: T0 - 1 }, { status: 'ochikuie' }]) {
    const env = seredovyshche();
    const kuka = pidpysnyk(env, stan);
    const { r, text } = await zapyt(env, `/pidpysnyk/spravy/${klitynka(...A)}.json`, kuka);
    assert.equal(r.status, 403);
    assert.match(text, /для підписників/);
    assert.doesNotMatch(text, /вигаданий опис/);
  }
});

test('підписник: карта, файли й «події адреси» з посиланням на рішення', async () => {
  const env = seredovyshche();
  const kuka = pidpysnyk(env);
  let { r, text } = await zapyt(env, '/pidpysnyk/', kuka);
  assert.equal(r.status, 200);
  assert.match(text, /Карта підписника/);
  assert.match(r.headers.get('cache-control'), /^private/);
  assert.equal(r.headers.get('x-robots-tag'), 'noindex, nofollow');
  ({ r, text } = await zapyt(env, `/pidpysnyk/api/podii?la=${A[0] + 0.00005}&lo=${A[1]}`, kuka));   // ≈ 6 м від точки
  assert.equal(r.status, 200);
  const v = JSON.parse(text);
  assert.equal(v.adresa, 'вулиця Вигадана, 1');
  assert.equal(v.podii.length, 1);
  assert.equal(v.podii[0].stattia, 'Грабіж');
  assert.equal(v.podii[0].rishennia[0], 'https://od.reyestr.court.gov.ua/files/ab/0123456789abcdef0123456789abcdef.rtf');
  ({ text } = await zapyt(env, `/pidpysnyk/api/podii?la=${B[0]}&lo=${B[1]}`, kuka));
  assert.equal(JSON.parse(text).adresa, 'вулиця Вигадана, 3');
  // повз точки (≈ 300 м) — порожньо, а не сусідня адреса
  ({ r } = await zapyt(env, `/pidpysnyk/api/podii?la=${A[0] + 0.003}&lo=${A[1]}`, kuka));
  assert.equal(r.status, 404);
  ({ r } = await zapyt(env, '/pidpysnyk/api/podii?la=abc&lo=1', kuka));
  assert.equal(r.status, 400);
});

test('шляхи поза картою не відкриваються (../, маніфест, інші ключі сховища)', async () => {
  const env = seredovyshche();
  env.KARTA.m.set('inshe/taiemne.json', '{"taiemne":1}');
  const kuka = pidpysnyk(env);
  for (const s of ['/pidpysnyk/../inshe/taiemne.json', '/pidpysnyk/..%2Finshe%2Ftaiemne.json', '/pidpysnyk/%2e%2e/potochna.json']) {
    const { r, text } = await zapyt(env, s, kuka);
    assert.notEqual(r.status, 200, s);
    assert.doesNotMatch(text, /taiemne/);
  }
});

test('без сховища KARTA адреса — звичайний сайт (карту ще не викладено)', async () => {
  const env = seredovyshche({ karta: false });
  const { r, text } = await zapyt(env, '/pidpysnyk/', pidpysnyk(env));
  assert.equal(r.status, 404);
  assert.equal(text, 'сайт');
});

test('ліміт описів на добу (ZAVDANNYA-161, п. 2): клітинки й «події адреси» рахуються разом; понад межу — 429; завтра — знову', async () => {
  const env = seredovyshche();
  env.KARTA_NA_DEN = '5';
  env.POSHTA_PARTNERA = 'partner@mv.test';
  const kuka = pidpysnyk(env);
  const kl = klitynka(...A);
  for (let i = 0; i < 3; i++) assert.equal((await zapyt(env, `/pidpysnyk/spravy/${kl}.json`, kuka)).r.status, 200);
  for (let i = 0; i < 2; i++) assert.equal((await zapyt(env, `/pidpysnyk/api/podii?la=${A[0]}&lo=${A[1]}`, kuka)).r.status, 200);
  assert.equal(env.__LYSTY.filter((l) => /ліміт описів/.test(l.tema)).length, 1, 'партнер дізнався один раз');
  assert.doesNotMatch(env.__LYSTY.at(-1).tekst, /ana@poshta/, 'без пошти людини');
  const zabahato = await zapyt(env, `/pidpysnyk/spravy/${kl}.json`, kuka);
  assert.equal(zabahato.r.status, 429);
  assert.doesNotMatch(zabahato.text, /вигаданий опис/);
  assert.equal((await zapyt(env, `/pidpysnyk/api/podii?la=${A[0]}&lo=${A[1]}`, kuka)).r.status, 429);
  // сама карта й інші файли — без ліміту
  assert.equal((await zapyt(env, '/pidpysnyk/', kuka)).r.status, 200);
  assert.equal(env.__LYSTY.filter((l) => /ліміт описів/.test(l.tema)).length, 1, 'лист — не на кожен зайвий запит');
  // наступна доба (UTC) — знову можна
  env.__CHAS = () => T0 + 86400;
  env.BAZA.db.prepare('UPDATE sesii SET do_ = ?').run(T0 + 2 * 86400);
  env.BAZA.db.prepare('UPDATE pidpysky SET diie_do = ?').run(T0 + 30 * 86400);
  assert.equal((await zapyt(env, `/pidpysnyk/spravy/${kl}.json`, kuka)).r.status, 200);
});

test('ліміт описів: без змінної — 300 на добу, з запасом для людини', async () => {
  const { limitOpysiv, OPYSIV_NA_DEN } = await import('../prodazh/karta.js');
  assert.equal(OPYSIV_NA_DEN, 300);
  assert.equal(limitOpysiv({}), 300);
  assert.equal(limitOpysiv({ KARTA_NA_DEN: '1000' }), 1000);
});

test('«Стежу» з картки адреси (ZAVDANNYA-151): та сама таблиця, що кабінет; лише підписник і лише з нашого сайту', async () => {
  const env = seredovyshche();
  const POSHUK = [['вулиця Вигадана', 'vyhadana', '', [['1', '/budynok/vyhadana/1/'], ['3', '/budynok/vyhadana/3/']]]];
  env.ASSETS = { async fetch(req) {
    const p = new URL(req.url).pathname;
    if (p === '/vulytsi/budynky.json') return Response.json(POSHUK);
    if (p === '/budynok/vyhadana/1/') return new Response('<main><h1>вулиця Вигадана, 1</h1></main>');
    return new Response('немає', { status: 404 });
  } };
  const post = (kuka, tilo, origin = SAIT) => worker.fetch(new Request(SAIT + '/pidpysnyk/api/stezhu', {
    method: 'POST', redirect: 'manual', body: JSON.stringify(tilo),
    headers: { 'content-type': 'application/json', ...(origin ? { origin } : {}), ...(kuka ? { cookie: kuka } : {}) } }), env);
  const n = () => env.BAZA.db.prepare('SELECT COUNT(*) n FROM stezhu').get().n;
  // без входу — на вхід, нічого не записано
  assert.equal((await post(null, { dia: 'dodaty', adresa: 'вул. Вигадана, 1' })).status, 303);
  const kuka = pidpysnyk(env);
  // чужа сторінка — 403
  assert.equal((await post(kuka, { dia: 'dodaty', adresa: 'вул. Вигадана, 1' }, 'https://zlyi.test')).status, 403);
  assert.equal(n(), 0);
  // підпис з карти («вул. Вигадана, 1») знаходить будинок сайту
  let r = await post(kuka, { dia: 'dodaty', adresa: 'вул. Вигадана, 1' });
  let v = await r.json();
  assert.equal(r.status, 200);
  assert.equal(v.budynok, '/budynok/vyhadana/1/');
  assert.deepEqual(v.adresy, [{ budynok: '/budynok/vyhadana/1/', adresa: 'вулиця Вигадана, 1' }]);
  // повтор не дублює; список — і через GET
  await post(kuka, { dia: 'dodaty', adresa: 'вул. Вигадана, 1' });
  assert.equal(n(), 1);
  const g = await worker.fetch(new Request(SAIT + '/pidpysnyk/api/stezhu', { headers: { cookie: kuka } }), env);
  assert.equal((await g.json()).adresy.length, 1);
  // будинку без сторінки на сайті — чесне «немає», не запис
  r = await post(kuka, { dia: 'dodaty', adresa: 'вул. Вигадана, 3' });
  assert.equal(r.status, 404);
  assert.match((await r.json()).chomu, /Такого будинку/);
  // прибрати
  v = await (await post(kuka, { dia: 'prybraty', budynok: '/budynok/vyhadana/1/' })).json();
  assert.deepEqual(v.adresy, []);
  assert.equal(n(), 0);
});
