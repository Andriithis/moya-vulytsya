// ZAVDANNYA-143: ОСББ і рієлтор наскрізно — тестова оплата → кабінет → що людина отримує → лист.
// Справжній код Workers (site/worker/index.js) на справжній схемі (skhema.sql у SQLite), підставні сайт, сховище й пошта.
// Запуск: node --test site/worker/testy/  (Node 22+).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../index.js';
import TS from '../prodazh/tsiny.js';
import { shliakhBudynku } from '../prodazh/logika.js';
import { d1, r2 } from './pidminy.mjs';

const SAIT = 'https://mv.test';
const BUDYNKY = { '/budynok/zhylianska/5/': 'вулиця Жилянська, 5', '/budynok/obolonskyi/16/': 'проспект Оболонський, 16' };
const DEN = 86400;

function seredovyshche() {
  let chas = 1_790_000_000;
  const env = {
    PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 'test-kliuch', VYDACHA_KLIUCH: 'vydacha-kliuch',
    ADRESA_SAITU: SAIT, BAZA: d1(), DOVIDKY: r2(), __LYSTY: [], __CHAS: () => chas,
    ASSETS: {
      async fetch(req) {
        const p = new URL(req.url).pathname;
        if (BUDYNKY[p]) return new Response(`<!doctype html><main><h1>${BUDYNKY[p]}</h1></main>`, { status: 200 });
        return new Response('немає', { status: 404 });
      },
    },
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
const shchodnia = (env) => worker.scheduled({ cron: '17 3 * * *' }, env);

async function zamovyty(env, tovar, budynok, poshta) {
  const f = { tovar, poshta, zghoda: 'tak', odrazu: 'tak' };
  if (budynok) f.budynok = budynok;
  const { r, kudy } = await zapyt(env, 'POST', '/api/zamovlennia', { forma: f });
  assert.equal(r.status, 303, 'замовлення має вести на оплату');
  return new URL(kudy).pathname.match(/\/oplata\/test\/(z[a-z2-7]+)\//)[1];
}

async function oplatyty(env, id, napys = 'Оплата пройшла') {
  const { text } = await zapyt(env, 'GET', `/oplata/test/${id}/`);
  const m = [...text.matchAll(/<form method="post" action="\/api\/spovishchennia\/test">([\s\S]*?)<\/form>/g)]
    .map((x) => ({ forma: Object.fromEntries([...x[1].matchAll(/name="([^"]+)" value="([^"]*)"/g)].map((y) => [y[1], y[2]])),
      napys: x[1].match(/type="submit">([^<]+)</)[1] }))
    .find((x) => x.napys === napys);
  assert.ok(m, `немає кнопки «${napys}»`);
  return zapyt(env, 'POST', '/api/spovishchennia/test', { forma: m.forma, origin: null });
}

const AVT = { authorization: 'Bearer vydacha-kliuch' };
async function vydavach(env) {
  const ds = JSON.parse((await zapyt(env, 'GET', '/api/vnutr/cherha?n=10', { zaholovky: AVT })).text).dovidky;
  for (const d of ds) {
    assert.equal((await zapyt(env, 'PUT', `/api/vnutr/dovidka/${d.id}`, { zaholovky: AVT, tilo: '<!doctype html><p>довідка</p>' })).r.status, 204);
  }
  return ds;
}

async function uviity(env, poshta) {
  await zapyt(env, 'POST', '/kabinet/vkhid', { forma: { poshta } });
  const t = env.__LYSTY.filter((l) => l.komu === poshta && l.tema.startsWith('Вхід')).at(-1).tekst.match(/\?t=([a-z2-7]+)/)[1];
  assert.equal((await zapyt(env, 'GET', `/kabinet/vkhid/?t=${t}`)).r.status, 200);   // сторінка з кнопкою «Увійти» (ZAVDANNYA-161)
  const { r } = await zapyt(env, 'POST', '/kabinet/vkhid/uviity', { forma: { t } });
  return r.headers.get('set-cookie').split(';')[0];
}

test('адреса будинку: повне посилання на сторінку чи шлях без кінцевої «/» — той самий шлях', () => {
  assert.equal(shliakhBudynku('https://moya-vulytsya.ua/budynok/obolonskyi/16/'), '/budynok/obolonskyi/16/');
  assert.equal(shliakhBudynku(' /budynok/obolonskyi/16 '), '/budynok/obolonskyi/16/');
  assert.equal(shliakhBudynku('http://x.y/budynok/obolonskyi/16/?dzherelo=osbb#skargy'), '/budynok/obolonskyi/16/');
  assert.equal(shliakhBudynku('/kabinet/'), '/kabinet/', 'інше не перетворюємо — його відкине перевірка будинку');
});

test('ОСББ: форма без будинку — поле для посилання (раніше — глухий кут), що отримує — написано', async () => {
  const env = seredovyshche();
  const { text } = await zapyt(env, 'GET', '/oplata/?tovar=osbb&dzherelo=osbb');
  assert.match(text, /name="budynok"/, 'поле для будинку');
  assert.match(text, /приходить на пошту раз на\s+місяць/);
  assert.match(text, /За 3 дні до наступного списання/);
  assert.match(text, /1\s490\sгрн на рік/);
  const chuzhyi = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'osbb', budynok: '/budynok/nema/1/', poshta: 'o@poshta.ua', zghoda: 'tak', odrazu: 'tak' } });
  assert.equal(chuzhyi.r.status, 200);
  assert.match(chuzhyi.text, /Такого будинку в наших даних немає/);
  assert.match(chuzhyi.text, /name="budynok"/, 'можна виправити тут же');
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM zamovlennia')[0].n, 0);
});

test('ОСББ наскрізно: оплата → перша довідка → щомісяця сама → лист за 3 дні → скасування', async () => {
  const env = seredovyshche();
  const poshta = 'pravlinnia@poshta.ua';
  const id = await zamovyty(env, 'osbb', 'https://mv.test/budynok/obolonskyi/16', poshta);
  assert.equal(sql(env, 'SELECT budynok FROM zamovlennia')[0].budynok, '/budynok/obolonskyi/16/', 'посилання → шлях');
  await oplatyty(env, id);
  const p = sql(env, `SELECT * FROM pidpysky WHERE tovar = 'osbb'`)[0];
  assert.equal(p.status, 'aktyvna');

  // перша довідка — одразу після оплати, режим osbb (генератор --osbb), лист — «Щомісячна довідка для ОСББ»
  let ds = await vydavach(env);
  assert.deepEqual(ds.map((d) => [d.rezhym, d.adresa]), [['osbb', 'проспект Оболонський, 16']]);
  const lyst = env.__LYSTY.filter((l) => l.komu === poshta).at(-1);
  assert.match(lyst.tema, /^Щомісячна довідка для ОСББ: проспект Оболонський, 16$/);
  assert.match(lyst.tekst, /Наступна прийде сама через місяць/);
  assert.doesNotMatch(lyst.tekst, /прогноз|рейтинг|небезпечн/);

  // того самого дня розклад нічого не додає
  await shchodnia(env);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 1);

  // кабінет: свій будинок, «приходить сама», наступна — дата
  let kuka = await uviity(env, poshta);
  let { text } = await zapyt(env, 'GET', '/kabinet/', { kuka });
  assert.match(text, /Мій будинок \(ОСББ\)/);
  assert.match(text, /приходить сама/);
  assert.match(text, /наступна — \d\d\.\d\d\.\d{4}/);
  assert.match(text, /щомісячна довідка ОСББ/);

  // 11 місяців поспіль — щомісяця одна довідка, сама, без жодної дії правління
  for (let m = 2; m <= 12; m++) {
    env.krok(31 * DEN);
    await shchodnia(env);
    await shchodnia(env);           // двічі за день — не дублює
    ds = await vydavach(env);
    assert.equal(ds.length, 1, `місяць ${m}: одна довідка`);
    assert.equal(ds[0].rezhym, 'osbb');
    if (sql(env, `SELECT diie_do FROM pidpysky`)[0].diie_do - env.__CHAS() < 3 * DEN) break;
  }
  const n = sql(env, `SELECT COUNT(*) n FROM dovidky WHERE pidpyska_id = ?`, p.id)[0].n;
  assert.ok(n >= 11 && n <= 12, `за рік — 11–12 довідок, є ${n}`);

  // лист за 3 дні до річного списання (MV-155, П7) — той самий щоденний розклад, один раз
  const doKintsia = sql(env, `SELECT diie_do FROM pidpysky`)[0].diie_do - env.__CHAS();
  env.krok(doKintsia - 2 * DEN);
  await shchodnia(env); await shchodnia(env);
  const nahad = env.__LYSTY.filter((l) => l.komu === poshta && l.tema.includes('річна оплата'));
  assert.equal(nahad.length, 1);
  assert.match(nahad[0].tekst, /1\s490\sгрн/);

  // скасування: доступ і щомісячні довідки — до кінця оплаченого року; після — нічого
  kuka = await uviity(env, poshta);
  ({ text } = await zapyt(env, 'POST', '/kabinet/skasuvaty', { kuka, forma: { pidpyska: p.id } }));
  assert.match(text, /Підписку скасовано/);
  ({ text } = await zapyt(env, 'GET', '/kabinet/', { kuka }));
  assert.match(text, /нових списань не буде/);
  env.krok(5 * DEN);
  const bulo = sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n;
  await shchodnia(env);
  env.krok(40 * DEN);
  await shchodnia(env);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, bulo, 'рік скінчився — довідок немає');
});

test('ОСББ: чергове річне списання — новий рік, щомісячні довідки тривають', async () => {
  const env = seredovyshche();
  const id = await zamovyty(env, 'osbb', '/budynok/obolonskyi/16/', 'r@poshta.ua');
  await oplatyty(env, id);
  await vydavach(env);
  env.krok(366 * DEN);
  await oplatyty(env, id, 'Списання наступного періоду');
  const p = sql(env, `SELECT * FROM pidpysky`)[0];
  assert.equal(p.status, 'aktyvna');
  assert.ok(p.diie_do - env.__CHAS() > 360 * DEN, 'ще рік');
  await shchodnia(env);
  assert.deepEqual((await vydavach(env)).map((d) => d.rezhym), ['osbb'], 'новий рік — довідка першого місяця');
});

test('рієлтор наскрізно: «Мої об\'єкти», 5 на місяць з лічильником, 6-та — за 99, новий місяць — знову 5', async () => {
  const env = seredovyshche();
  const poshta = 'rieltor@poshta.ua';
  const { text: forma } = await zapyt(env, 'GET', '/oplata/?tovar=rieltor');
  assert.match(forma, /5 довідок про будинки на місяць/);
  assert.match(forma, /Мої об'єкти/);
  assert.doesNotMatch(forma, /name="budynok"/, 'рієлтору будинок при оплаті не потрібен');
  await oplatyty(env, await zamovyty(env, 'rieltor', null, poshta));
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 0, 'без будинку — довідки одразу немає');

  const kuka = await uviity(env, poshta);
  let { text } = await zapyt(env, 'GET', '/kabinet/', { kuka });
  assert.match(text, /Мої об'єкти/);
  assert.match(text, /<b>0 з 5<\/b> довідок цього місяця використано · лишилось <b>5<\/b>/);

  // новий об'єкт — повним посиланням на сторінку будинку
  ({ text } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka, forma: { budynok: 'https://mv.test/budynok/zhylianska/5/' } }));
  assert.match(text, /готуємо/);
  await vydavach(env);
  const lyst = env.__LYSTY.filter((l) => l.komu === poshta && l.tema.startsWith('Довідка')).at(-1);
  assert.match(lyst.tekst, /лишилось довідок: 4 з 5/);
  for (const b of ['/budynok/obolonskyi/16/', '/budynok/zhylianska/5/', '/budynok/zhylianska/5/', '/budynok/obolonskyi/16/']) {
    assert.match((await zapyt(env, 'POST', '/kabinet/dovidka', { kuka, forma: { budynok: b } })).text, /готуємо/);
  }
  await vydavach(env);
  ({ text } = await zapyt(env, 'GET', '/kabinet/', { kuka }));
  assert.match(text, /<b>5 з 5<\/b>[^<]*лишилось <b>0<\/b>/);
  const obiekty = text.slice(text.indexOf('id="obiekty"'), text.indexOf('</section>', text.indexOf('id="obiekty"')));
  assert.match(obiekty, /вулиця Жилянська, 5<\/a> — 3\sдовідки/);
  assert.match(obiekty, /проспект Оболонський, 16<\/a> — 2\sдовідки/);
  assert.equal((obiekty.match(/Нова довідка/g) || []).length, 2, 'по кнопці на об\'єкт');

  // 6-та — спершу питаємо (П6), потім оплата 99 і довідка поза лічильником
  ({ text } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka, forma: { budynok: '/budynok/zhylianska/5/' } }));
  assert.match(text, /Додаткова довідка/);
  assert.match(text, /99\sгрн/);
  const { kudy } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka, forma: { budynok: '/budynok/zhylianska/5/', odrazu: 'tak' } });
  await oplatyty(env, new URL(kudy).pathname.match(/(z[a-z2-7]+)/)[1]);
  assert.equal((await vydavach(env)).length, 1);
  assert.equal(sql(env, `SELECT suma FROM zamovlennia WHERE tovar = 'dodatkova'`)[0].suma, TS.tsiny.dodatkova);

  // наступного місяця (після списання) — знову 5
  env.krok(31 * DEN);
  await oplatyty(env, sql(env, `SELECT zamovlennia_id FROM pidpysky`)[0].zamovlennia_id, 'Списання наступного періоду');
  const kuka2 = await uviity(env, poshta);
  ({ text } = await zapyt(env, 'GET', '/kabinet/', { kuka: kuka2 }));
  assert.match(text, /<b>0 з 5<\/b>/);
  assert.match(text, /вулиця Жилянська, 5<\/a> — 4\sдовідки/, 'об\'єкти лишаються');
});

test('звичайна підписка й довідка — без розділів ОСББ і рієлтора', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'pidpyska', null, 'p@poshta.ua'));
  const { text } = await zapyt(env, 'GET', '/kabinet/', { kuka: await uviity(env, 'p@poshta.ua') });
  assert.doesNotMatch(text, /Мої об'єкти|Мій будинок \(ОСББ\)/);
  await shchodnia(env);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 0, 'розклад ставить довідки лише ОСББ');
});

test('довідка, яку не вдалося зібрати, ліміту рієлтора не з\'їдає; ОСББ — без щоденних повторів; сторінки — same-origin', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'rieltor', null, 'a@poshta.ua'));
  const kuka = await uviity(env, 'a@poshta.ua');
  await zapyt(env, 'POST', '/kabinet/dovidka', { kuka, forma: { budynok: '/budynok/zhylianska/5/' } });
  for (let i = 0; i < 3; i++) {
    const [d] = JSON.parse((await zapyt(env, 'GET', '/api/vnutr/cherha?n=10', { zaholovky: AVT })).text).dovidky;
    await zapyt(env, 'POST', `/api/vnutr/pomylka/${d.id}`, { zaholovky: AVT });
  }
  assert.equal(sql(env, 'SELECT status FROM dovidky')[0].status, 'pomylka');
  assert.match((await zapyt(env, 'GET', '/kabinet/', { kuka })).text, /<b>0 з 5<\/b>/);

  await oplatyty(env, await zamovyty(env, 'osbb', '/budynok/obolonskyi/16/', 'o@poshta.ua'));
  for (let i = 0; i < 3; i++) {
    const ds = JSON.parse((await zapyt(env, 'GET', '/api/vnutr/cherha?n=10', { zaholovky: AVT })).text).dovidky;
    for (const d of ds) await zapyt(env, 'POST', `/api/vnutr/pomylka/${d.id}`, { zaholovky: AVT });
  }
  await shchodnia(env); env.krok(DEN); await shchodnia(env);
  assert.equal(sql(env, `SELECT COUNT(*) n FROM dovidky WHERE rezhym = 'osbb'`)[0].n, 1, 'не щодня знову');

  // з no-referrer браузер шле формам «Origin: null» — і сервер відхиляв кожне замовлення та вхід
  const { r, text } = await zapyt(env, 'GET', '/oplata/?tovar=osbb');
  assert.equal(r.headers.get('referrer-policy'), 'same-origin');
  assert.match(text, /<meta name="referrer" content="same-origin">/);
});
