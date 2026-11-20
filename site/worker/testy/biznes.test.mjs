// Тести «Для бізнесу» (ZAVDANNYA-157): запит зі сторінки, облік клієнтів, посилання на N днів, ліміт завантажень, вимкнення.
// Запуск: node --test site/worker/testy/. Справжній скрипт Workers, справжня схема D1 (SQLite), R2 — у пам'яті з вигаданою
// копією (жодних справжніх описів у репозиторії).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../index.js';
import { d1, r2 } from './pidminy.mjs';
import { MAKS_DNIV } from '../prodazh/biznes.js';

const SAIT = 'https://mv.test';
const T0 = 1_790_000_000;              // 2026-09-21
const ADMIN = 'admin-kliuch-testu';
const VERSIIA = '2026-11-08';

function seredovyshche({ prodazh = 'tak', biznes = true } = {}) {
  let chas = T0;
  const env = {
    PRODAZH: prodazh, PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 't', ADRESA_SAITU: SAIT, ADMIN_KLIUCH: ADMIN,
    POSHTA_PARTNERA: 'partner@pryklad.ua', BAZA: d1(), DOVIDKY: r2(), __LYSTY: [], __CHAS: () => chas,
    ASSETS: { async fetch() { return new Response('сайт', { status: 404 }); } },
  };
  env.krok = (s) => { chas += s; };
  if (biznes) env.BIZNES = r2();
  return env;
}

function pokastyKopiiu(env, kod) {
  const p = (k, v) => env.BIZNES.m.set(`biznes/${kod}/${VERSIIA}/${k}`, v);
  p('baza.db', 'SQLite format 3 (вигадана)'); p('csv.zip', 'PK вигаданий архів'); p('OPYS.md', '# Копія'); p('SHA256SUMS', 'x  baza.db\n');
  env.BIZNES.m.set(`biznes/${kod}/potochna.json`, JSON.stringify({ versiia: VERSIIA, fajly: [
    { imia: 'baza.db', bait: 151_000_000 }, { imia: 'csv.zip', bait: 26_000_000 }, { imia: 'OPYS.md', bait: 5000 }, { imia: 'SHA256SUMS', bait: 222 }] }));
}

async function zapyt(env, shliakh, { metod = 'GET', tilo, kliuch, origin } = {}) {
  const headers = {};
  if (kliuch) headers.authorization = `Bearer ${kliuch}`;
  if (origin) headers.origin = origin;
  if (tilo !== undefined) headers['content-type'] = 'application/json';
  const r = await worker.fetch(new Request(SAIT + shliakh, { method: metod, headers, body: tilo === undefined ? undefined : JSON.stringify(tilo), redirect: 'manual' }), env);
  return { r, text: await r.text() };
}
const admin = (env, shliakh, tilo) => zapyt(env, `/api/admin/biznes/${shliakh}`, { metod: tilo === undefined ? 'GET' : 'POST', tilo, kliuch: ADMIN });

async function klient(env, dani = {}) {
  const { r, text } = await admin(env, 'klient', { nazva: 'ТОВ «Вигадана агенція»', kontakt: 'ofis@vyhadana.ua', tarif: 'rik', diie_do: '2027-09-20', dohovir: 'Л-1/2026', ...dani });
  assert.equal(r.status, 201, text);
  return JSON.parse(text).klient;
}

async function posylannia(env, kod, dani = {}) {
  const { r, text } = await admin(env, 'posylannia', { klient: kod, dniv: 7, ...dani });
  return { status: r.status, ...JSON.parse(text) };
}
const shliakh = (url) => new URL(url).pathname;

const ZAPYT = { kompaniia: 'ТОВ «Вигадана агенція»', kontakt: 'ofis@vyhadana.ua', meta: 'nerukhomist', strok: 'rik',
  terytoriia: 'Київ, Печерський район', komentar: 'Для оцінки квартир', zghoda: true, kanal: 'biznes' };

test('запит зі сторінки /biznes/: записано, партнеру — лист без контакту; без згоди чи з чужого сайту — ні', async () => {
  for (const rezhym of ['skoro', 'tak']) {
    const env = seredovyshche({ prodazh: rezhym });
    assert.equal((await zapyt(env, '/api/forma/biznes', { metod: 'POST', tilo: ZAPYT, origin: SAIT })).r.status, 201);
    const z = env.BAZA.db.prepare('SELECT * FROM biznes_zapyty').all();
    assert.equal(z.length, 1);
    assert.equal(z[0].meta, 'nerukhomist');
    assert.equal(env.__LYSTY.length, 1);
    assert.equal(env.__LYSTY[0].komu, 'partner@pryklad.ua');
    assert.doesNotMatch(env.__LYSTY[0].tekst, /vyhadana|Вигадана/, 'контакт і назва компанії в листі не пишемо');
    assert.equal((await zapyt(env, '/api/forma/biznes', { metod: 'POST', tilo: { ...ZAPYT, zghoda: false }, origin: SAIT })).r.status, 400);
    assert.equal((await zapyt(env, '/api/forma/biznes', { metod: 'POST', tilo: { ...ZAPYT, meta: 'zlamaty' }, origin: SAIT })).r.status, 400);
    assert.equal((await zapyt(env, '/api/forma/biznes', { metod: 'POST', tilo: { ...ZAPYT, kontakt: '  ' }, origin: SAIT })).r.status, 400);
    assert.equal((await zapyt(env, '/api/forma/biznes', { metod: 'POST', tilo: ZAPYT, origin: 'https://chuzhyi.test' })).r.status, 403);
  }
});

test('засмічення: понад 3 запити з одного контакту за добу — не пишемо (відповідь та сама)', async () => {
  const env = seredovyshche();
  for (let i = 0; i < 5; i++) assert.equal((await zapyt(env, '/api/forma/biznes', { metod: 'POST', tilo: ZAPYT, origin: SAIT })).r.status, 201);
  assert.equal(env.BAZA.db.prepare('SELECT COUNT(*) AS n FROM biznes_zapyty').get().n, 3);
  env.krok(86400 + 1);
  await zapyt(env, '/api/forma/biznes', { metod: 'POST', tilo: ZAPYT, origin: SAIT });
  assert.equal(env.BAZA.db.prepare('SELECT COUNT(*) AS n FROM biznes_zapyty').get().n, 4);
});

test('облік лише з ключем партнера', async () => {
  const env = seredovyshche();
  for (const k of [undefined, 'ne-toi']) {
    const { r } = await zapyt(env, '/api/admin/biznes/klienty', { kliuch: k });
    assert.equal(r.status, 401);
    assert.equal((await zapyt(env, '/api/admin/biznes/klient', { metod: 'POST', tilo: { nazva: 'x' }, kliuch: k })).r.status, 401);
  }
});

test('посилання: без копії — ні; з копією — сторінка компанії й файли, лічильник, строк не довший за договір', async () => {
  const env = seredovyshche();
  const kod = await klient(env, { diie_do: '2026-09-24' });                        // договір — ще 3 дні
  assert.equal(kod, 'k1');
  assert.equal((await posylannia(env, kod)).status, 409, 'копії ще немає');
  pokastyKopiiu(env, kod);
  assert.equal((await posylannia(env, kod, { dniv: MAKS_DNIV + 1 })).status, 400);
  assert.equal((await posylannia(env, kod, { dniv: 0 })).status, 400);
  const p = await posylannia(env, kod, { dniv: 30 });
  assert.equal(p.status, 201);
  assert.ok(p.do_ <= Date.UTC(2026, 8, 24, 23, 59, 59) / 1000, 'посилання не довше за договір');
  assert.match(p.posylannia, /^https:\/\/mv\.test\/kopiia\/[a-z2-7]{50,}\/$/);
  // ключ у базі — лише хешем
  const ryadok = env.BAZA.db.prepare('SELECT * FROM biznes_posylannia').get();
  assert.ok(!p.posylannia.includes(ryadok.hash));
  const s = await zapyt(env, shliakh(p.posylannia));
  assert.equal(s.r.status, 200);
  assert.match(s.text, /Вигадана агенція/);
  assert.match(s.text, /csv\.zip/);
  assert.match(s.text, /не перепродавати/);
  assert.equal(s.r.headers.get('x-robots-tag'), 'noindex, nofollow');
  assert.equal(s.r.headers.get('referrer-policy'), 'no-referrer');
  assert.match(s.r.headers.get('cache-control'), /no-store/);
  const f = await zapyt(env, shliakh(p.posylannia) + 'baza.db');
  assert.equal(f.r.status, 200);
  assert.equal(f.text, 'SQLite format 3 (вигадана)');
  assert.match(f.r.headers.get('content-disposition'), /attachment; filename="moya-vulytsya-2026-11-08-baza\.db"/);
  assert.equal(env.BAZA.db.prepare('SELECT COUNT(*) AS n FROM biznes_zavantazhennia').get().n, 1);
  // строк договору минув — посилання не діє, хоч його власний строк ще ні
  env.krok(4 * 86400);
  assert.equal((await zapyt(env, shliakh(p.posylannia))).r.status, 404);
  assert.equal((await posylannia(env, kod)).status, 409, 'договір минув — нове посилання не видати');
  // продовження договору повертає доступ
  assert.equal((await admin(env, `klient/${kod}`, { diie_do: '2027-09-30' })).r.status, 200);
  // старе посилання було обрізане строком договору — лишається недійсним; нове — діє
  assert.equal((await zapyt(env, shliakh(p.posylannia))).r.status, 404);
  const nove = await posylannia(env, kod);
  assert.equal((await zapyt(env, shliakh(nove.posylannia))).r.status, 200);
});

test('строк посилання: N днів, потім «не діє» — так само, як і невідомий ключ', async () => {
  const env = seredovyshche();
  const kod = await klient(env);
  pokastyKopiiu(env, kod);
  const p = await posylannia(env, kod, { dniv: 2 });
  env.krok(2 * 86400 - 10);
  assert.equal((await zapyt(env, shliakh(p.posylannia))).r.status, 200);
  env.krok(20);
  const prostr = await zapyt(env, shliakh(p.posylannia));
  const nevidomyi = await zapyt(env, '/kopiia/' + 'a'.repeat(52) + '/');
  assert.equal(prostr.r.status, 404);
  assert.equal(nevidomyi.r.status, 404);
  assert.equal(prostr.text, nevidomyi.text, 'прострочений і невідомий ключ — однакова відповідь');
});

test('файли — лише з переліку; шлях з «..» і чужі імена — ні', async () => {
  const env = seredovyshche();
  const kod = await klient(env);
  pokastyKopiiu(env, kod);
  env.BIZNES.m.set('biznes/k2/2026-11-08/baza.db', 'чужа копія');
  const p = shliakh((await posylannia(env, kod)).posylannia);
  for (const z of ['..%2F..%2Fk2%2F2026-11-08%2Fbaza.db', 'potochna.json', 'index.html', 'baza.db/x']) {
    const { r, text } = await zapyt(env, p + z);
    assert.equal(r.status, 404, z);
    assert.doesNotMatch(text, /чужа копія/);
  }
  assert.equal((await zapyt(env, p + 'baza.db', { metod: 'POST', tilo: {} })).r.status, 405);
});

test('ліміт завантажень: понад maks — 429, і одночасні запити його не перевищують', async () => {
  const env = seredovyshche();
  const kod = await klient(env);
  pokastyKopiiu(env, kod);
  const p = shliakh((await posylannia(env, kod, { maks: 3 })).posylannia);
  const v = await Promise.all(Array.from({ length: 6 }, () => zapyt(env, p + 'csv.zip')));
  assert.equal(v.filter((x) => x.r.status === 200).length, 3);
  assert.equal(v.filter((x) => x.r.status === 429).length, 3);
  assert.match((await zapyt(env, p)).text, /лишилось: 0/);
});

test('вимкнення: клієнт і всі посилання — одразу; «лише посилання» лишає клієнта', async () => {
  const env = seredovyshche();
  const kod = await klient(env);
  pokastyKopiiu(env, kod);
  const a = shliakh((await posylannia(env, kod)).posylannia);
  const b = shliakh((await posylannia(env, kod)).posylannia);
  const v = await admin(env, 'vymknuty', { klient: kod, lyshe_posylannia: true });
  assert.equal(JSON.parse(v.text).posylan_vymkneno, 2);
  assert.equal((await zapyt(env, a)).r.status, 404);
  assert.equal((await zapyt(env, b + 'baza.db')).r.status, 404);
  const c = shliakh((await posylannia(env, kod)).posylannia);           // клієнт діє — нове посилання можна
  assert.equal((await zapyt(env, c)).r.status, 200);
  await admin(env, 'vymknuty', { klient: kod, prychyna: 'договір розірвано' });
  assert.equal((await zapyt(env, c)).r.status, 404);
  assert.equal((await posylannia(env, kod)).status, 409);
  const spysok = JSON.parse((await admin(env, 'klienty')).text).klienty;
  assert.equal(spysok[0].diie, false);
  assert.equal(spysok[0].prychyna, 'договір розірвано');
  assert.equal(spysok[0].kopiia, VERSIIA);
  // продовжити без «uvimknuty» — не вмикає; з ним — так
  await admin(env, `klient/${kod}`, { diie_do: '2028-01-01' });
  assert.equal((await posylannia(env, kod)).status, 409);
  await admin(env, `klient/${kod}`, { uvimknuty: true });
  assert.equal((await posylannia(env, kod)).status, 201);
});

test('копії різних клієнтів не змішуються', async () => {
  const env = seredovyshche();
  const k1 = await klient(env), k2 = await klient(env, { nazva: 'ТОВ «Друга»' });
  pokastyKopiiu(env, k1);
  env.BIZNES.m.set(`biznes/${k2}/${VERSIIA}/baza.db`, 'копія другого');
  env.BIZNES.m.set(`biznes/${k2}/potochna.json`, JSON.stringify({ versiia: VERSIIA, fajly: [{ imia: 'baza.db', bait: 10 }] }));
  const p1 = shliakh((await posylannia(env, k1)).posylannia), p2 = shliakh((await posylannia(env, k2)).posylannia);
  assert.equal((await zapyt(env, p1 + 'baza.db')).text, 'SQLite format 3 (вигадана)');
  assert.equal((await zapyt(env, p2 + 'baza.db')).text, 'копія другого');
  assert.equal((await zapyt(env, p2 + 'csv.zip')).r.status, 404, 'файла немає в маніфесті другого');
});

test('без сховища BIZNES і в режимі «скоро»', async () => {
  const bez = seredovyshche({ biznes: false });
  const kod = await klient(bez);
  assert.equal((await posylannia(bez, kod)).status, 409);
  assert.equal((await zapyt(bez, '/kopiia/' + 'a'.repeat(52) + '/')).r.status, 404);
  const skoro = seredovyshche({ prodazh: 'skoro' });
  const k = await klient(skoro);
  pokastyKopiiu(skoro, k);
  const p = await posylannia(skoro, k);
  assert.equal((await zapyt(skoro, shliakh(p.posylannia))).r.status, 200, '«Для бізнесу» працює й до оплати на сайті');
});

test('нагадування партнеру за 14 днів до кінця договору — один раз; CSV запитів без формул', async () => {
  const env = seredovyshche();
  await klient(env, { diie_do: '2026-10-01' });          // ≈ 10 днів
  await klient(env, { diie_do: '2027-01-01' });          // далеко
  await worker.scheduled({ cron: '17 2 * * *' }, env);
  await worker.scheduled({ cron: '17 2 * * *' }, env);
  const lysty = env.__LYSTY.filter((l) => /спливає/.test(l.tema));
  assert.equal(lysty.length, 1);
  assert.match(lysty[0].tema, /k1/);
  await zapyt(env, '/api/forma/biznes', { metod: 'POST', tilo: { ...ZAPYT, kompaniia: '=HYPERLINK("x")' }, origin: SAIT });
  const csv = await admin(env, 'zapyty.csv');
  assert.equal(csv.r.status, 200);
  assert.match(csv.text, /'=HYPERLINK/);
  assert.match(csv.r.headers.get('content-type'), /text\/csv/);
});
