// Поштовх видавачу в GitHub Actions (ZAVDANNYA-133, п. 2). Запуск: node --test site/worker/testy/
// GitHub підмінено: перехоплюємо fetch і дивимось, що й куди сервер надіслав.
import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import worker, { CHASTO } from '../index.js';
import * as L from '../prodazh/logika.js';
import { shturhnuty, pidhaniaty } from '../prodazh/vydavach.js';
import { d1, r2 } from './pidminy.mjs';

const T0 = 1_790_000_000;
const spravzhnii = globalThis.fetch;
afterEach(() => { globalThis.fetch = spravzhnii; });

function perekhopyty(status = 204) {
  const zapyty = [];
  globalThis.fetch = async (url, o = {}) => {
    zapyty.push({ url: String(url), metod: o.method, h: o.headers, tilo: o.body && JSON.parse(o.body) });
    if (status === 'zbii') throw new Error('мережа');
    return new Response(null, { status });
  };
  return zapyty;
}

function seredovyshche(dod = {}) {
  let chas = T0;
  const env = { PRODAZH: 'tak', BAZA: d1(), DOVIDKY: r2(), __LYSTY: [], __CHAS: () => chas, ...dod };
  env.krok = (s) => { chas += s; };
  return env;
}
const GH = { VYDAVACH_GITHUB: 'Andriithis/dani-edrsr/vydavach.yml@main', VYDAVACH_GITHUB_TOKEN: 'gh-test' };

function zamovlennia(env, status = 'oplacheno') {
  env.BAZA.db.prepare(`INSERT INTO zamovlennia (id, korystuvach_id, tovar, suma, status, servis, stvoreno) VALUES ('z1', 1, 'dovidka', 199, ?, 'test', ?)`)
    .run(status, T0);
}

test('без налаштування GitHub довідка ставиться в чергу, а нікуди нічого не йде', async () => {
  const z = perekhopyty();
  const env = seredovyshche();
  zamovlennia(env);
  const id = await L.postavytyDovidku(env, { korystuvach_id: 1, zamovlennia_id: 'z1', budynok: '/budynok/a/1/', adresa: 'вулиця А, 1', rezhym: 'dovidka' });
  assert.match(id, /^d/);
  assert.equal(z.length, 0);
});

test('оплачена довідка в черзі → один запит workflow_dispatch у GitHub із токеном і гілкою', async () => {
  const z = perekhopyty();
  const env = seredovyshche(GH);
  zamovlennia(env);
  await L.postavytyDovidku(env, { korystuvach_id: 1, zamovlennia_id: 'z1', budynok: '/budynok/a/1/', adresa: 'вулиця А, 1', rezhym: 'dovidka' });
  assert.equal(z.length, 1);
  assert.equal(z[0].url, 'https://api.github.com/repos/Andriithis/dani-edrsr/actions/workflows/vydavach.yml/dispatches');
  assert.equal(z[0].metod, 'POST');
  assert.equal(z[0].h.authorization, 'Bearer gh-test');
  assert.equal(z[0].tilo.ref, 'main');
  // у запиті до GitHub немає ні пошти, ні адреси будинку — лише «є робота»
  assert.doesNotMatch(JSON.stringify(z[0].tilo), /вулиця|@/);
});

test('GitHub недоступний чи відмовив — довідка однаково в черзі, помилки немає', async () => {
  for (const st of ['zbii', 401]) {
    perekhopyty(st);
    const env = seredovyshche(GH);
    zamovlennia(env);
    const id = await L.postavytyDovidku(env, { korystuvach_id: 1, zamovlennia_id: 'z1', budynok: '/b/', adresa: 'А', rezhym: 'dovidka' });
    assert.equal(env.BAZA.db.prepare('SELECT status FROM dovidky WHERE id = ?').get(id).status, 'v_cherzi');
    assert.equal(await shturhnuty(env), false);
  }
});

test('розклад: штовхає лише коли оплачена довідка чекає довше за 5 хв', async () => {
  const z = perekhopyty();
  const env = seredovyshche(GH);
  zamovlennia(env);
  await L.postavytyDovidku(env, { korystuvach_id: 1, zamovlennia_id: 'z1', budynok: '/b/', adresa: 'А', rezhym: 'dovidka' });
  z.length = 0;
  assert.equal(await pidhaniaty(env), false, 'щойно поставлена — ще чекаємо перший поштовх');
  env.krok(301);
  assert.equal(await pidhaniaty(env), true);
  assert.equal(z.length, 1);
  // розклад Workers кожні 10 хв іде сюди, а не в щоденне прибирання
  z.length = 0;
  await worker.scheduled({ cron: CHASTO }, env);
  assert.equal(z.length, 1);
});

test('розклад: неоплачене замовлення не штовхає', async () => {
  const z = perekhopyty();
  const env = seredovyshche(GH);
  zamovlennia(env, 'stvoreno');
  env.BAZA.db.prepare(`INSERT INTO dovidky (id, korystuvach_id, zamovlennia_id, budynok, adresa, rezhym, stvoreno) VALUES ('dx', 1, 'z1', '/b/', 'А', 'dovidka', ?)`).run(T0);
  env.krok(3600);
  assert.equal(await pidhaniaty(env), false);
  assert.equal(z.length, 0);
});

test('погано записана змінна — вимкнено, а не запит кудись', async () => {
  const z = perekhopyty();
  const env = seredovyshche({ VYDAVACH_GITHUB: 'https://evil.example/x', VYDAVACH_GITHUB_TOKEN: 't' });
  assert.equal(await shturhnuty(env), false);
  assert.equal(z.length, 0);
});
