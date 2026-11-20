// «Судова практика» на сервері продажу (ZAVDANNYA-135). Запуск: node --test site/worker/testy/*.test.mjs (Node 22+).
// Справжній код Workers на справжній схемі (skhema.sql у SQLite), підставні сайт (ASSETS: довідник статей), R2 і пошта.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../index.js';
import TS from '../prodazh/tsiny.js';
import { d1, r2 } from './pidminy.mjs';

const SAIT = 'https://mv.test';
const DOVIDNYK = { statti: {
  'kupap-130': { stattia: 'ст.130 КУпАП', nazva: 'Керування в стані сп’яніння', sudy: ['Голосіївський', 'Дарницький'], chastyny: ['1', '2'] },
  'kk-185': { stattia: 'ст.185 КК', nazva: 'Крадіжка', sudy: ['Голосіївський'], chastyny: ['1', '2', '3', '4'] },
} };
const PS = 'штраф і позбавлення права керування';
const ST130 = { kodeks: 'КУпАП', nomer: '130', stattia: 'ст.130 КУпАП', nazva: 'Керування в стані сп’яніння', strok: true,
  kat: ['штраф', 'закрито: минули строки', 'закрито: немає складу'], pokarano: ['штраф'],
  ryadky: [['Голосіївський', '2025', '1', 'штраф', PS, 80, { 30: 40, 90: 40 }], ['Голосіївський', '2025', '1', 'закрито: минули строки', '', 20, {}],
    ['Дарницький', '2024', '1', 'штраф', PS, 300, { 60: 300 }], ['Дарницький', '2024', '2', 'штраф', PS, 5, {}]] };

/** Товари «Судової практики» в оферті: як після дописаної оферти (NE_V_OFERTI порожнє). */
function uvimknutySp(tak = true) {
  for (const t of TS.sudova) {
    const i = TS.prodaietsia.indexOf(t);
    if (tak && i < 0) TS.prodaietsia.push(t);
    if (!tak && i >= 0) TS.prodaietsia.splice(i, 1);
  }
}

function seredovyshche() {
  let chas = 1_790_000_000;
  const DOVIDKY = r2();
  DOVIDKY.m.set('praktyka/potochna.json', JSON.stringify({ versiia: '2026-11-19' }));
  DOVIDKY.m.set('praktyka/2026-11-19/kupap-130.json', JSON.stringify(ST130));
  const env = {
    PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 'test-kliuch', VYDACHA_KLIUCH: 'vydacha-kliuch',
    ADRESA_SAITU: SAIT, BAZA: d1(), DOVIDKY, __LYSTY: [], __CHAS: () => chas,
    ASSETS: { async fetch(req) {
      const p = new URL(req.url).pathname;
      if (p === '/sudova-praktyka/dovidnyk.json') return Response.json(DOVIDNYK);
      return new Response('немає', { status: 404 });
    } },
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

async function oplatyty(env, id) {
  const { text } = await zapyt(env, 'GET', `/oplata/test/${id}/`);
  const m = [...text.matchAll(/<form method="post" action="\/api\/spovishchennia\/test">([\s\S]*?)<\/form>/g)]
    .map((x) => Object.fromEntries([...x[1].matchAll(/name="([^"]+)" value="([^"]*)"/g)].map((y) => [y[1], y[2]])))
    .find((f) => f.podiia === 'oplata');
  assert.ok(m, 'немає кнопки оплати');
  return zapyt(env, 'POST', '/api/spovishchennia/test', { forma: m, origin: null });
}

async function zamovyty(env, tovar, dod = {}) {
  const { r, kudy, text } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar, poshta: 'yurist@poshta.ua', zghoda: 'tak', odrazu: 'tak', ne_dopomoga: 'tak', ...dod } });
  assert.equal(r.status, 303, `замовлення ${tovar}: ${text.slice(0, 300)}`);
  return new URL(kudy).pathname.match(/\/oplata\/test\/(z[a-z2-7]+)\//)[1];
}

async function uviity(env, poshta = 'yurist@poshta.ua') {
  await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta } });
  const t = env.__LYSTY.filter((l) => l.komu === poshta && l.tema.startsWith('Вхід')).at(-1).tekst.match(/vkhid\/\?t=([a-z2-7]+)/)[1];
  assert.equal((await zapyt(env, 'GET', `/kabinet/vkhid/?t=${t}`)).r.status, 200);   // сторінка з кнопкою «Увійти» (ZAVDANNYA-161)
  const { r } = await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t } });
  return r.headers.get('set-cookie').split(';')[0];
}

const AVT = { authorization: 'Bearer vydacha-kliuch' };

test('поки товарів немає в оферті — «скоро» навіть з увімкненою оплатою, замовлення не створюється', async () => {
  uvimknutySp(false);
  const env = seredovyshche();
  for (const tovar of TS.sudova) {
    const { text } = await zapyt(env, 'GET', `/oplata/?tovar=${tovar}&stattia=kupap-130`);
    assert.match(text, /Скоро — залиште пошту/);
    const { r } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar, stattia: 'kupap-130', poshta: 'a@b.ua', zghoda: 'tak', odrazu: 'tak', ne_dopomoga: 'tak' } });
    assert.equal(r.status, 400);
  }
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM zamovlennia')[0].n, 0);
});

test('довідка людині: стаття → суд і частина з довідника → оплата → черга з параметрами → лист', async () => {
  uvimknutySp();
  const env = seredovyshche();
  let { text } = await zapyt(env, 'GET', '/oplata/?tovar=spdovidka');
  assert.match(text, /оберіть статтю/);
  ({ text } = await zapyt(env, 'GET', '/oplata/?tovar=spdovidka&stattia=kupap-130'));
  assert.match(text, /Голосіївський районний суд/);
  assert.match(text, /не знаю — усі суди міста/);
  assert.match(text, /199\u00a0грн/);
  assert.match(text, /не юридична допомога/);
  assert.doesNotMatch(text, /Будинок/);
  // чужі суд, частина, стаття — ні
  for (const f of [{ stattia: 'kupap-130', sud: 'Неіснуючий' }, { stattia: 'kupap-130', chastyna: '9' }, { stattia: 'kk-999' }, { stattia: '../x' }]) {
    const { r } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'spdovidka', ...f, poshta: 'a@b.ua', zghoda: 'tak', odrazu: 'tak', ne_dopomoga: 'tak' } });
    assert.equal(r.status, 400, JSON.stringify(f));
  }
  // без галочки «не юридична допомога» — ні
  const { r: bez, text: tb } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'spdovidka', stattia: 'kupap-130', poshta: 'a@b.ua', zghoda: 'tak', odrazu: 'tak' } });
  assert.notEqual(bez.status, 303);
  assert.match(tb, /юридична допомога/);
  const id = await zamovyty(env, 'spdovidka', { stattia: 'kupap-130', sud: 'Голосіївський', chastyna: '1', suma: '1', adresa: 'підробка' });
  const z = sql(env, 'SELECT * FROM zamovlennia WHERE id = ?', id)[0];
  assert.equal(z.suma, 199);
  assert.equal(z.adresa, 'ст.\u00a0130 ч.\u00a01 КУпАП — Голосіївський районний суд');
  assert.deepEqual(JSON.parse(z.parametry), { stattia: 'ст.130 КУпАП', sud: 'Голосіївський', chastyna: '1' });
  let { text: ch } = await zapyt(env, 'GET', '/api/vnutr/cherha?n=5', { zaholovky: AVT });
  assert.deepEqual(JSON.parse(ch).dovidky, [], 'до оплати — порожньо');
  await oplatyty(env, id);
  ({ text: ch } = await zapyt(env, 'GET', '/api/vnutr/cherha?n=5', { zaholovky: AVT }));
  const [d] = JSON.parse(ch).dovidky;
  assert.equal(d.rezhym, 'sp');
  assert.equal(d.budynok, '');
  assert.deepEqual(d.parametry, { stattia: 'ст.130 КУпАП', sud: 'Голосіївський', chastyna: '1' });
  const { r } = await zapyt(env, 'PUT', `/api/vnutr/dovidka/${d.id}`, { zaholovky: AVT, tilo: '<!doctype html><p>довідка</p>' });
  assert.equal(r.status, 204);
  const lyst = env.__LYSTY.find((l) => l.tema.startsWith('Судова практика'));
  assert.ok(lyst, 'лист про готову довідку');
  assert.match(lyst.tekst, /не юридична допомога/);
  const kuka = await uviity(env);
  const { text: kab } = await zapyt(env, 'GET', '/kabinet/', { kuka });
  assert.match(kab, /судова практика/);
  assert.match(kab, /Можна взяти ще: немає/, 'довідка «Судової практики» не дає довідок про будинки');
});

test('підписка юриста: таблиці по судах і роках, CSV з лімітом, 3 довідки на місяць; карти подій не дає', async () => {
  uvimknutySp();
  const env = seredovyshche();
  const id = await zamovyty(env, 'spyurist');
  const kuka = await uviity(env);
  let { r } = await zapyt(env, 'GET', '/pidpysnyk/praktyka/', { kuka });
  assert.equal(r.status, 403, 'до оплати — ні');
  ({ r } = await zapyt(env, 'GET', '/pidpysnyk/praktyka/'));
  assert.equal(r.status, 303, 'без входу — на вхід');
  await oplatyty(env, id);
  assert.equal(sql(env, 'SELECT tovar, status FROM pidpysky')[0].status, 'aktyvna');
  let text;
  ({ r, text } = await zapyt(env, 'GET', '/pidpysnyk/praktyka/?stattia=kupap-130', { kuka }));
  assert.equal(r.status, 200);
  assert.match(text, /Разом: 405 справ/);
  assert.match(text, /Голосіївський/);
  assert.match(text, /Дарницький/);
  assert.doesNotMatch(text, /суддя/i);
  ({ text } = await zapyt(env, 'GET', '/pidpysnyk/praktyka/?stattia=kupap-130&sud=Голосіївський&chastyna=1', { kuka }));
  assert.match(text, /Разом: 100 справ/);
  assert.match(text, /80\u00a0%/, "штраф 80 з 100");
  // частина 2 — 5 справ: «замало», а не частка
  ({ text } = await zapyt(env, 'GET', '/pidpysnyk/praktyka/?stattia=kupap-130&chastyna=2', { kuka }));
  assert.match(text, /замало/);
  // CSV
  let c;
  ({ r, text: c } = await zapyt(env, 'GET', '/pidpysnyk/praktyka/csv?stattia=kupap-130&sud=Голосіївський', { kuka }));
  assert.equal(r.status, 200);
  assert.match(r.headers.get('content-type'), /text\/csv/);
  assert.match(c, /разом;Разом за фільтром;100;/);
  assert.match(c, /не юридична допомога/);
  for (let i = 1; i < 50; i++) await zapyt(env, 'GET', '/pidpysnyk/praktyka/csv?stattia=kupap-130', { kuka });
  ({ r } = await zapyt(env, 'GET', '/pidpysnyk/praktyka/csv?stattia=kupap-130', { kuka }));
  assert.equal(r.status, 429, 'понад 50 на добу');
  env.krok(86400);
  ({ r } = await zapyt(env, 'GET', '/pidpysnyk/praktyka/csv?stattia=kupap-130', { kuka }));
  assert.equal(r.status, 200, 'наступної доби — знову');
  // карта подій — ні (вона для підписки на будинки)
  ({ r } = await zapyt(env, 'GET', '/pidpysnyk/', { kuka }));
  assert.notEqual(r.status, 200);
  // довідки з підписки: 3, далі — купити
  for (let i = 0; i < 3; i++) {
    ({ r, text } = await zapyt(env, 'POST', '/pidpysnyk/praktyka/dovidka', { kuka, forma: { stattia: 'kupap-130', sud: 'Дарницький', chastyna: '' } }));
    assert.match(text, /готуємо/);
  }
  ({ text } = await zapyt(env, 'POST', '/pidpysnyk/praktyka/dovidka', { kuka, forma: { stattia: 'kupap-130' } }));
  assert.match(text, /використано/);
  ({ r } = await zapyt(env, 'POST', '/pidpysnyk/praktyka/dovidka', { kuka, forma: { stattia: 'kupap-130' }, origin: 'https://zlyi.test' }));
  assert.equal(r.status, 403);
  const ds = sql(env, `SELECT rezhym, budynok, adresa, parametry FROM dovidky`);
  assert.equal(ds.length, 3);
  assert.ok(ds.every((d) => d.rezhym === 'sp' && d.budynok === '' && JSON.parse(d.parametry).sud === 'Дарницький'));
});

test('підписка на будинки не відкриває практику юриста', async () => {
  uvimknutySp();
  const env = seredovyshche();
  const { kudy } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'pidpyska', poshta: 'yurist@poshta.ua', zghoda: 'tak', odrazu: 'tak' } });
  await oplatyty(env, new URL(kudy).pathname.match(/(z[a-z2-7]+)/)[1]);
  const kuka = await uviity(env);
  const { r } = await zapyt(env, 'GET', '/pidpysnyk/praktyka/', { kuka });
  assert.equal(r.status, 403);
});
