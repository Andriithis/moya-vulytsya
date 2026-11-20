// Тести позачергового прибрання події (ZAVDANNYA-161, п. 5). Запуск: node --test site/worker/testy/
// Справжній скрипт Workers, справжня схема D1 (SQLite у пам'яті), вигадані карта підписника (R2) і колоди ігор.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../index.js';
import { klitynka } from '../prodazh/karta.js';
import { sha256 } from '../prodazh/bezpeka.js';
import { kliuch, vidfiltruvaty } from '../prodazh/prybrannia.js';
import { d1, r2 } from './pidminy.mjs';

const SAIT = 'https://mv.test';
const T0 = 1_790_000_000;
const A = [50.45012, 30.52341];
const VERSIIA = '2026-11-08';
const H1 = 'ab0123456789abcdef0123456789abcd';   // 32 знаки — відбиток файла рішення
const H2 = 'cd9876543210fedcba9876543210fedc';
const URL1 = `https://od.reyestr.court.gov.ua/files/12/${H1}.rtf`;
const URL2 = `https://od.reyestr.court.gov.ua/files/34/${H2}.rtf`;

const KOLODA = {
  $schema: 'koloda.schema.json', versiya: 1, misto: 'Київ',
  podii: [
    { id: '111-1', vyd: 'Крадіжка', opys_korotkyi: 'вигаданий опис 1', adresa: 'вулиця Вигадана', rishennya_url: URL1, rishennya_nomer: '111' },
    { id: '222-1', vyd: 'Грабіж', opys_korotkyi: 'вигаданий опис 2', adresa: 'вулиця Інша', rishennya_url: URL2, rishennya_nomer: '222' },
  ],
};
const LITOPYS = {
  versiia: 2, podii: { '111-1': ['kradizhka', 2024, 'опис 1', 'вул. Вигадана', 50.4, 30.5, URL1, '111'], '222-1': ['hrabizh', 2023, 'опис 2', 'вул. Інша', 50.4, 30.5, URL2, '222'] },
  vulytsi: [['vyhadana', 'вулиця Вигадана', 'Шевченківський', 12, 'k', 50.4, 30.5, ['111-1', '222-1']]],
};

function seredovyshche() {
  const env = {
    PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 't', ADRESA_SAITU: SAIT,
    POSHTA_PARTNERA: 'partner@mv.test', ADMIN_KLIUCH: 'admin-kliuch',
    BAZA: d1(), DOVIDKY: r2(), KARTA: r2(), __LYSTY: [], __CHAS: () => T0,
    ASSETS: {
      async fetch(req) {
        const p = new URL(req.url).pathname;
        if (p === '/ihry/koloda.json') return Response.json(KOLODA);
        if (p === '/ihry/litopys.json') return Response.json(LITOPYS);
        return new Response('немає', { status: 404 });
      },
    },
  };
  const kl = klitynka(...A);
  const p = (k, v) => env.KARTA.m.set(`karta/${VERSIIA}/${k}`, JSON.stringify(v));
  env.KARTA.m.set('karta/potochna.json', JSON.stringify({ versiia: VERSIIA, kategorii: ['Крадіжка', 'Грабіж'] }));
  p(`indeks/${kl}.json`, [[A[0], A[1], 0, 'вулиця Вигадана, 1']]);
  p(`spravy/${kl}.json`, { 0: [
    [0, '2025-03-02', 21, '1/1/25', [`12${H1}`], 'вигаданий опис А'],
    [1, '2024-07-01', -1, '2/2/24', [`34${H2}`], 'вигаданий опис Б'],
  ] });
  // підписник
  const db = env.BAZA.db;
  db.prepare('INSERT INTO korystuvachi (id, poshta, stvoreno) VALUES (1, ?, ?)').run('ana@poshta.ua', T0);
  db.prepare(`INSERT INTO pidpysky (id, korystuvach_id, tovar, status, pochatok, diie_do, zamovlennia_id, stvoreno)
              VALUES ('p1', 1, 'pidpyska', 'aktyvna', ?, ?, 'z1', ?)`).run(T0 - 86400, T0 + 86400, T0);
  db.prepare('INSERT INTO sesii (hash, korystuvach_id, do_) VALUES (?, 1, ?)').run(sha256('sesiia-ani'), T0 + 3600);
  return env;
}
const ANA = 'mv_sesiia=sesiia-ani';

async function zapyt(env, metod, shliakh, { forma, kuka, origin = SAIT, zaholovky = {}, json } = {}) {
  const h = { ...zaholovky };
  if (origin) h.origin = origin;
  if (kuka) h.cookie = kuka;
  let body;
  if (forma) body = new URLSearchParams(forma);
  if (json) { body = JSON.stringify(json); h['content-type'] = 'application/json'; }
  const r = await worker.fetch(new Request(SAIT + shliakh, { method: metod, headers: h, body, redirect: 'manual' }), env);
  return { r, text: await r.text() };
}

async function uviityPartnerom(env, poshta = 'partner@mv.test') {
  await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta } });
  const lyst = env.__LYSTY.filter((l) => l.komu === poshta && l.tema.startsWith('Вхід')).at(-1);
  assert.ok(lyst, 'партнер без покупок отримує лист входу');
  const t = lyst.tekst.match(/\?t=([a-z2-7]+)/)[1];
  const { r } = await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t } });
  return r.headers.get('set-cookie').split(';')[0];
}

test('ключ рішення: посилання на файл, на сторінку Review, номер; інше — ні', () => {
  assert.equal(kliuch(URL1), `h:${H1}`);
  assert.equal(kliuch(`  ${URL1.toUpperCase()} `), `h:${H1}`);
  assert.equal(kliuch('https://reyestr.court.gov.ua/Review/123456789'), 'n:123456789');
  assert.equal(kliuch('123456789'), 'n:123456789');
  assert.equal(kliuch('https://moyavulytsya.ua/budynok/zhylianska/5/'), null);
  assert.equal(kliuch(''), null);
  assert.equal(kliuch('1/2/24'), null);
});

test('фільтр: колода, «Літопис» (словник + списки id), справи «Кваліфікуй», рядки карти — прибрано лише подію', () => {
  const k = [`h:${H1}`];
  const kol = vidfiltruvaty(KOLODA, k);
  assert.equal(kol.prybrano, 1);
  assert.deepEqual(kol.dani.podii.map((p) => p.id), ['222-1']);
  assert.equal(kol.dani.misto, 'Київ');
  const lt = vidfiltruvaty(LITOPYS, k);
  assert.deepEqual(Object.keys(lt.dani.podii), ['222-1']);
  assert.deepEqual(lt.dani.vulytsi[0][7], ['222-1'], 'id прибраної — і зі списку вулиці');
  assert.equal(lt.dani.vulytsi[0][1], 'вулиця Вигадана', 'рядок вулиці цілий');
  const kv = vidfiltruvaty({ versiia: 1, statti: { 'КК 185': { nazva: 'Крадіжка', chastyny: ['1'] } },
    spravy: [{ id: 'a', fabula: 'ф', rishennia: { nomer: '123456789', url: 'https://reyestr.court.gov.ua/Review/123456789' } },
      { id: 'b', fabula: 'ф', rishennia: { nomer: '987654321', url: 'https://reyestr.court.gov.ua/Review/987654321' } }] }, ['n:123456789']);
  assert.deepEqual(kv.dani.spravy.map((x) => x.id), ['b']);
  assert.ok(kv.dani.statti['КК 185'], 'довідник статей не чіпаємо');
  const vd = vidfiltruvaty({ zahadky: [{ slug: 'x', zvuzhennia: { a: 1 }, podiia: { url: URL1 } }, { slug: 'y', podiia: { url: URL2 } }] }, k);
  assert.deepEqual(vd.dani.zahadky.map((z) => z.slug), ['y']);
  // Review-номер не зачіпає довший номер
  assert.equal(vidfiltruvaty([{ url: 'https://reyestr.court.gov.ua/Review/1234567890' }], ['n:123456789']).prybrano, 0);
  // порожній список — ті самі дані
  assert.equal(vidfiltruvaty(KOLODA, []).dani, KOLODA);
});

test('партнер: звернення → «Прибрати подію зараз» → зникла з карти підписника й колод одразу; журнал; повернути', async () => {
  const env = seredovyshche();
  const kl = klitynka(...A);
  // людина надіслала звернення через форму сайту (з тегами — на сторінці лише текстом)
  assert.equal((await zapyt(env, 'POST', '/api/forma/zvernennya', { json: { posylannya: URL1, shcho_ne_tak: 'vydalyty',
    poyasnennya: '<script>alert(1)</script> це я', kontakt: 'lyudyna@poshta.ua', zghoda: true } })).r.status, 201);
  const kuka = await uviityPartnerom(env);
  assert.match((await zapyt(env, 'GET', '/kabinet/', { kuka })).text, /href="\/kabinet\/zvernennia\/"/);
  const st = await zapyt(env, 'GET', '/kabinet/zvernennia/', { kuka });
  assert.equal(st.r.status, 200);
  assert.match(st.text, /чекає відповіді/);
  assert.match(st.text, /lyudyna@poshta\.ua/);
  assert.doesNotMatch(st.text, /<script>alert/);
  assert.match(st.text, new RegExp(`value="${URL1.replace(/[.]/g, '\\.')}"`), 'посилання зі звернення — уже в полі');
  // до прибрання підписник бачить обидві події
  assert.match((await zapyt(env, 'GET', `/pidpysnyk/spravy/${kl}.json`, { kuka: ANA })).text, /опис А/);
  const zvId = env.BAZA.db.prepare('SELECT id FROM zvernennya').get().id;
  const v = await zapyt(env, 'POST', '/kabinet/zvernennia/prybraty', { kuka, forma: { posylannia: URL1, zvernennya: String(zvId), prychyna: 'zvernennya' } });
  assert.match(v.text, /Подію прибрано/);
  // карта підписника: файл клітинки і «події адреси» — без події А, з подією Б
  const sp = await zapyt(env, 'GET', `/pidpysnyk/spravy/${kl}.json`, { kuka: ANA });
  assert.equal(sp.r.status, 200);
  assert.doesNotMatch(sp.text, /опис А/);
  assert.match(sp.text, /опис Б/);
  assert.match(sp.r.headers.get('cache-control'), /private/);
  const pa = JSON.parse((await zapyt(env, 'GET', `/pidpysnyk/api/podii?la=${A[0]}&lo=${A[1]}`, { kuka: ANA })).text);
  assert.deepEqual(pa.podii.map((p) => p.opys), ['вигаданий опис Б']);
  // колоди ігор
  const kol = JSON.parse((await zapyt(env, 'GET', '/ihry/koloda.json')).text);
  assert.deepEqual(kol.podii.map((p) => p.id), ['222-1']);
  const lt = JSON.parse((await zapyt(env, 'GET', '/ihry/litopys.json')).text);
  assert.deepEqual(Object.keys(lt.podii), ['222-1']);
  // журнал: хто, коли, за яким зверненням; без даних людини
  const zh = env.BAZA.db.prepare('SELECT * FROM prybrani_podii').all();
  assert.equal(zh.length, 1);
  assert.equal(zh[0].kliuch, `h:${H1}`);
  assert.equal(zh[0].zvernennya_id, zvId);
  assert.equal(zh[0].khto, 'partner@mv.test');
  assert.equal(zh[0].prybrano, T0);
  assert.doesNotMatch(JSON.stringify(zh), /lyudyna/);
  // повтор — без дубля
  assert.match((await zapyt(env, 'POST', '/kabinet/zvernennia/prybraty', { kuka, forma: { posylannia: URL1 } })).text, /вже прибрано/);
  assert.equal(env.BAZA.db.prepare('SELECT COUNT(*) AS n FROM prybrani_podii').get().n, 1);
  // закрити звернення
  await zapyt(env, 'POST', '/kabinet/zvernennia/zakryty', { kuka, forma: { zvernennya: String(zvId) } });
  assert.equal(env.BAZA.db.prepare('SELECT zakryto FROM zvernennya').get().zakryto, T0);
  // помилково — повернути: подія знову на карті, у журналі — час повернення
  await zapyt(env, 'POST', '/kabinet/zvernennia/povernuty', { kuka, forma: { id: String(zh[0].id) } });
  assert.match((await zapyt(env, 'GET', `/pidpysnyk/spravy/${kl}.json`, { kuka: ANA })).text, /опис А/);
  assert.equal(JSON.parse((await zapyt(env, 'GET', '/ihry/koloda.json')).text).podii.length, 2);
  assert.equal(env.BAZA.db.prepare('SELECT povernuto FROM prybrani_podii').get().povernuto, T0);
  // невпізнане посилання — пояснення, нічого не прибрано
  assert.match((await zapyt(env, 'POST', '/kabinet/zvernennia/prybraty', { kuka, forma: { posylannia: '/budynok/x/1/' } })).text, /Не впізнали рішення/);
});

test('кабінет звернень: людині й без входу — немає; дія з чужого сайту — 403; вивантаження журналу — з ключем', async () => {
  const env = seredovyshche();
  assert.equal((await zapyt(env, 'GET', '/kabinet/zvernennia/')).r.status, 303, 'без входу — на вхід');
  assert.equal((await zapyt(env, 'GET', '/kabinet/zvernennia/', { kuka: ANA })).r.status, 404, 'підписник — не партнер');
  assert.equal((await zapyt(env, 'POST', '/kabinet/zvernennia/prybraty', { kuka: ANA, forma: { posylannia: URL1 } })).r.status, 404);
  assert.doesNotMatch((await zapyt(env, 'GET', '/kabinet/', { kuka: ANA })).text, /kabinet\/zvernennia/);
  const kuka = await uviityPartnerom(env);
  assert.equal((await zapyt(env, 'POST', '/kabinet/zvernennia/prybraty', { kuka, origin: 'https://zlyi.test', forma: { posylannia: URL1 } })).r.status, 403);
  assert.equal(env.BAZA.db.prepare('SELECT COUNT(*) AS n FROM prybrani_podii').get().n, 0);
  // те саме для скриптів — ключ ADMIN_KLIUCH
  const AVT = { authorization: 'Bearer admin-kliuch' };
  assert.equal((await zapyt(env, 'POST', '/api/admin/prybraty-podiyu', { forma: { posylannia: URL2 } })).r.status, 401);
  const a = await zapyt(env, 'POST', '/api/admin/prybraty-podiyu', { zaholovky: AVT, forma: { posylannia: URL2, prychyna: 'skasovano' } });
  assert.equal(JSON.parse(a.text).kliuch, `h:${H2}`);
  assert.equal(JSON.parse((await zapyt(env, 'GET', '/ihry/koloda.json')).text).podii.length, 1);
  assert.equal(JSON.parse((await zapyt(env, 'GET', '/api/admin/prybrani', { zaholovky: AVT })).text).zhurnal.length, 1);
  const csv = await zapyt(env, 'GET', '/api/admin/vyvantazhennia/prybrani_podii', { zaholovky: AVT });
  assert.match(csv.text, new RegExp(H2));
  // видавач і збирання даних беруть список ключів своїм ключем
  env.VYDACHA_KLIUCH = 'vydacha';
  const vn = await zapyt(env, 'GET', '/api/vnutr/prybrani', { zaholovky: { authorization: 'Bearer vydacha' } });
  assert.deepEqual(JSON.parse(vn.text).prybrani, [`h:${H2}`]);
  // інший партнер зі списку PARTNERY теж може; POSHTA_PARTNERA тоді — ні
  env.PARTNERY = 'mykyta@mv.test, inshyi@mv.test';
  assert.equal((await zapyt(env, 'GET', '/kabinet/zvernennia/', { kuka })).r.status, 404);
  const k2 = await uviityPartnerom(env, 'inshyi@mv.test');
  assert.equal((await zapyt(env, 'GET', '/kabinet/zvernennia/', { kuka: k2 })).r.status, 200);
});

test('без прибраних подій колода віддається як є; без бази продажу скрипт колод не чіпає', async () => {
  const env = seredovyshche();
  const r = await zapyt(env, 'GET', '/ihry/koloda.json');
  assert.equal(JSON.parse(r.text).podii.length, 2);
  const bez = { ASSETS: env.ASSETS };
  const r2_ = await worker.fetch(new Request(`${SAIT}/ihry/koloda.json`), bez);
  assert.equal((await r2_.json()).podii.length, 2);
});

test('стара база без нових таблиць (не виконано skhema-161.sql): карта, колоди й «Видалити мої дані» працюють', async () => {
  const env = seredovyshche();
  env.BAZA.db.exec('DROP TABLE karta_zavantazhennia; DROP TABLE prybrani_podii;');
  assert.equal((await zapyt(env, 'GET', `/pidpysnyk/spravy/${klitynka(...A)}.json`, { kuka: ANA })).r.status, 200);
  assert.equal(JSON.parse((await zapyt(env, 'GET', '/ihry/koloda.json')).text).podii.length, 2);
  // людина без підписки (у підписника спершу скасовується підписка в платіжному сервісі — тут його немає)
  env.BAZA.db.prepare('INSERT INTO korystuvachi (id, poshta, stvoreno) VALUES (2, ?, ?)').run('bo@poshta.ua', T0);
  env.BAZA.db.prepare('INSERT INTO sesii (hash, korystuvach_id, do_) VALUES (?, 2, ?)').run(sha256('sesiia-bo'), T0 + 3600);
  const { r, text } = await zapyt(env, 'POST', '/kabinet/vydalyty', { kuka: 'mv_sesiia=sesiia-bo', forma: { pidtverdzhuiu: 'tak', rozumiiu: 'tak' } });
  assert.equal(r.status, 200);
  assert.match(text, /Дані видалено/);
  assert.equal(env.BAZA.db.prepare(`SELECT COUNT(*) AS n FROM korystuvachi WHERE poshta = 'bo@poshta.ua'`).get().n, 0);
});
