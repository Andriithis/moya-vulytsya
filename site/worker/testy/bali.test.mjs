// Бали ігор ↔ кабінет (ZAVDANNYA-123; MV-130, MV-138). Запуск: node --test site/worker/testy/
// Стик вимкнений (OBMIN_BALIV не 'tak') — обміну немає; увімкнений — «чужі бали не обміняти», «двічі не обміняти».
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../index.js';
import * as B from '../prodazh/bali.js';
import { d1, r2 } from './pidminy.mjs';

const SAIT = 'https://mv.test';
const BUDYNKY = { '/budynok/zhylianska/5/': 'вулиця Жилянська, 5', '/budynok/obolonskyi/16/': 'проспект Оболонський, 16' };

function seredovyshche(dod = {}) {
  let chas = 1_790_000_000;
  const env = {
    PRODAZH: 'tak', OBMIN_BALIV: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 't', VYDACHA_KLIUCH: 'v',
    ADRESA_SAITU: SAIT, BAZA: d1(), DOVIDKY: r2(), __LYSTY: [], __CHAS: () => chas,
    ASSETS: { async fetch(req) { const p = new URL(req.url).pathname; return BUDYNKY[p] ? new Response(`<h1>${BUDYNKY[p]}</h1>`) : new Response('немає', { status: 404 }); } },
    ...dod,
  };
  env.krok = (s) => { chas += s; };
  return env;
}
const sql = (env, s, ...p) => env.BAZA.db.prepare(s).all(...p);

async function zapyt(env, metod, shliakh, { forma, kuka, origin = SAIT } = {}) {
  const h = {};
  if (origin) h.origin = origin;
  if (kuka) h.cookie = kuka;
  const r = await worker.fetch(new Request(SAIT + shliakh, { method: metod, headers: h, body: forma ? new URLSearchParams(forma) : undefined, redirect: 'manual' }), env);
  return { r, text: await r.text() };
}

async function uviity(env, poshta) {
  await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta } });
  const t = env.__LYSTY.filter((l) => l.komu === poshta).at(-1).tekst.match(/\?t=([a-z2-7]+)/)[1];
  assert.equal((await zapyt(env, 'GET', `/kabinet/vkhid/?t=${t}`)).r.status, 200);   // сторінка з кнопкою «Увійти» (ZAVDANNYA-161)
  const { r } = await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t } });
  return r.headers.get('set-cookie').split(';')[0];
}
/** Людина з акаунтом: запис у korystuvachi, вхід за посиланням із листа, «Стежу» на будинок. */
async function liudyna(env, poshta) {
  env.BAZA.db.prepare('INSERT INTO korystuvachi (poshta, stvoreno) VALUES (?, ?)').run(poshta, 1);
  const id = sql(env, 'SELECT id FROM korystuvachi WHERE poshta = ?', poshta)[0].id;
  const kuka = await uviity(env, poshta);
  await zapyt(env, 'POST', '/kabinet/stezhu', { kuka, forma: { budynok: '/budynok/zhylianska/5/' } });
  return { id, kuka };
}
const zapytZKabinetu = (html, tovar) => html.match(new RegExp(`name="tovar" value="${tovar}"><input type="hidden" name="zapyt" value="([a-z0-9]+)"`))[1];

test('курс сервера — той самий, що в грі (site/ihry/nalashtuvannia.json)', async () => {
  const fs = await import('node:fs');
  const k = JSON.parse(fs.readFileSync(new URL('../../ihry/nalashtuvannia.json', import.meta.url), 'utf8'));
  assert.equal(B.KURS.ochok_za_bal, k.ochok_za_bal);
  assert.equal(B.KURS.stelia_baliv_na_den, k.stelia_baliv_na_den);
  assert.equal(B.KURS.obminiv_na_30_dniv, k.obminiv_na_30_dniv);
  for (const t of k.obmin) assert.equal(B.KURS.obmin[t.id].baliv, t.baliv, t.id);
  assert.equal(k.obmin_uvimkneno, false, 'у грі обмін вимкнений, доки немає висновку юриста й кабінету');
});

test('вимкнено (без OBMIN_BALIV): у кабінеті немає балів, адреса обміну — «немає», нічого не пишеться', async () => {
  const env = seredovyshche({ OBMIN_BALIV: undefined });
  const a = await liudyna(env, 'ana@poshta.ua');
  await B.narakhuvaty(env, a.id, 300000, 'x', 'hra:test');
  const k = await zapyt(env, 'GET', '/kabinet/', { kuka: a.kuka });
  assert.ok(!k.text.includes('Бали ігор'));
  const o = await zapyt(env, 'POST', '/kabinet/obmin', { kuka: a.kuka, forma: { tovar: 'pidpyska-misiats', zapyt: 'abcdefgh12' } });
  assert.equal(o.r.status, 404);
  assert.deepEqual((await B.obminiaty(env, a.id, { tovar: 'pidpyska-misiats', zapyt: 'abcdefgh12' })).ok, false);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM bali_rukh WHERE zmina < 0')[0].n, 0);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM zamovlennia')[0].n, 0);
});

test('нарахування: 100 очок = 1 бал, стеля 300 на добу, той самий ключ удруге — нічого', async () => {
  const env = seredovyshche();
  const a = await liudyna(env, 'ana@poshta.ua');
  assert.equal(await B.narakhuvaty(env, a.id, 12345, 'h1', 'hra:vgadai'), 123);
  assert.equal(await B.narakhuvaty(env, a.id, 12345, 'h1', 'hra:vgadai'), 0, 'повтор');
  assert.equal(await B.narakhuvaty(env, a.id, 50000, 'h2', 'hra:vgadai'), 177, 'до стелі');
  assert.equal(await B.narakhuvaty(env, a.id, 50000, 'h3', 'hra:vgadai'), 0);
  env.krok(86400);
  assert.equal(await B.narakhuvaty(env, a.id, 50000, 'h4', 'hra:vgadai'), 300, 'нова доба');
  assert.equal(await B.balans(env, a.id), 600);
});

function dodatyBali(env, id, n) {   // як після багатьох днів гри (обходимо денну стелю — лише для тесту)
  env.BAZA.db.prepare('INSERT INTO bali_rukh (korystuvach_id, zmina, prychyna, kliuch, stvoreno) VALUES (?, ?, ?, ?, ?)').run(id, n, 'test', 'test:' + id + ':' + n, 1);
}

test('чужі бали не обміняти: користувач — лише з сесії; id і пошта з форми ігноруються', async () => {
  const env = seredovyshche();
  const a = await liudyna(env, 'ana@poshta.ua');
  const b = await liudyna(env, 'bohdan@poshta.ua');
  dodatyBali(env, a.id, 5000);                         // бали є лише в Ані
  const kB = await zapyt(env, 'GET', '/kabinet/', { kuka: b.kuka });
  assert.match(kB.text, /<b>0<\/b> балів/);
  const o = await zapyt(env, 'POST', '/kabinet/obmin', { kuka: b.kuka, forma: {
    tovar: 'pidpyska-misiats', zapyt: zapytZKabinetu(kB.text, 'pidpyska-misiats'), korystuvach_id: String(a.id), poshta: 'ana@poshta.ua' } });
  assert.match(o.text, /Потрібно 3000 балів/);
  assert.equal(await B.balans(env, a.id), 5000, 'бали Ані не зачеплено');
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM pidpysky')[0].n, 0);
  // без сесії — на вхід; з чужого сайту — ні
  assert.equal((await zapyt(env, 'POST', '/kabinet/obmin', { forma: { tovar: 'pidpyska-misiats', zapyt: 'abcdefgh12' } })).r.status, 303);
  assert.equal((await zapyt(env, 'POST', '/kabinet/obmin', { kuka: a.kuka, origin: 'https://zlyi.test', forma: { tovar: 'pidpyska-misiats', zapyt: 'abcdefgh12' } })).r.status, 403);
  assert.equal(await B.balans(env, a.id), 5000);
});

test('двічі не обміняти: повтор форми — один обмін; другий обмін — лише через 30 днів', async () => {
  const env = seredovyshche();
  const a = await liudyna(env, 'ana@poshta.ua');
  dodatyBali(env, a.id, 5000);
  const k = await zapyt(env, 'GET', '/kabinet/', { kuka: a.kuka });
  const forma = { tovar: 'dovidka', budynok: '/budynok/zhylianska/5/', zapyt: zapytZKabinetu(k.text, 'dovidka') };
  assert.match((await zapyt(env, 'POST', '/kabinet/obmin', { kuka: a.kuka, forma })).text, /довідку на вулиця Жилянська, 5 готуємо/);
  assert.match((await zapyt(env, 'POST', '/kabinet/obmin', { kuka: a.kuka, forma })).text, /Цей обмін уже зроблено/);
  assert.equal(await B.balans(env, a.id), 3500);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 1, 'одна довідка');
  const z = sql(env, `SELECT * FROM zamovlennia`);
  assert.equal(z.length, 1);
  assert.equal(z[0].suma, 0);
  assert.equal(z[0].servis, 'bali');
  // інша форма (новий номер) у ті самі 30 днів — ні, хоч балів і досить
  const k2 = await zapyt(env, 'GET', '/kabinet/', { kuka: a.kuka });
  const f2 = { tovar: 'pidpyska-misiats', zapyt: zapytZKabinetu(k2.text, 'pidpyska-misiats') };
  assert.match((await zapyt(env, 'POST', '/kabinet/obmin', { kuka: a.kuka, forma: f2 })).text, /раз на 30 днів/);
  assert.equal(await B.balans(env, a.id), 3500);
  // одночасні запити з різними номерами (два вкладки) — списання лише одне
  env.krok(31 * 86400);
  const r = await Promise.all(['vkladka1xx', 'vkladka2xx'].map((zapyt) => B.obminiaty(env, a.id, { tovar: 'pidpyska-misiats', zapyt })));
  assert.equal(r.filter((x) => x.ok).length, 1);
  assert.equal(await B.balans(env, a.id), 500);
  const kin = await zapyt(env, 'GET', '/kabinet/', { kuka: await uviity(env, 'ana@poshta.ua') });   // сесія — 30 днів
  assert.match(kin.text, /за бали, діє до/);
});

test('видалення даних прибирає й бали', async () => {
  const env = seredovyshche();
  const a = await liudyna(env, 'ana@poshta.ua');
  dodatyBali(env, a.id, 2000);
  await zapyt(env, 'POST', '/kabinet/vydalyty', { kuka: a.kuka, forma: { pidtverdzhuiu: 'tak' } });
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM bali_rukh')[0].n, 0);
});
