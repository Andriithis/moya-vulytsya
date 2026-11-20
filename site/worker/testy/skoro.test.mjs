// Тести ZAVDANNYA-132: режим «скоро», форми сайту в D1, вивантаження для партнера, галочка П6, лист ОСББ П7, пісочниця LiqPay.
// Запуск: node --test site/worker/testy/  (Node 22+). Справжній код Workers на справжній SQL-схемі (як prodazh.test.mjs).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../index.js';
import { PEREKHIDNYKY, pidpysTestu } from '../prodazh/perekhidnyky.js';
import TS from '../prodazh/tsiny.js';
import { d1, r2 } from './pidminy.mjs';

const SAIT = 'https://mv.test';
const BUDYNKY = { '/budynok/zhylianska/5/': 'вулиця Жилянська, 5', '/budynok/obolonskyi/16/': 'проспект Оболонський, 16' };

function seredovyshche(dod = {}) {
  let chas = 1_790_000_000;
  const env = {
    PRODAZH: 'skoro', ADRESA_SAITU: SAIT, ADMIN_KLIUCH: 'admin-kliuch', POSHTA_PARTNERA: 'partner@mv.test',
    BAZA: d1(), DOVIDKY: r2(), __LYSTY: [], __CHAS: () => chas,
    ASSETS: {
      async fetch(req) {
        const p = new URL(req.url).pathname;
        if (BUDYNKY[p]) return new Response(`<!doctype html><main><h1>${BUDYNKY[p]}</h1></main>`, { status: 200 });
        return new Response(`статичний ${p}`, { status: p === '/oplata/' ? 200 : 404 });
      },
    },
    ...dod,
  };
  env.krok = (s) => { chas += s; };
  return env;
}

async function zapyt(env, metod, shliakh, { forma, json, origin = SAIT, zaholovky = {} } = {}) {
  const h = { ...zaholovky };
  if (origin) h.origin = origin;
  let body;
  if (forma) body = new URLSearchParams(forma);
  if (json) { body = JSON.stringify(json); h['content-type'] = 'application/json'; }
  const r = await worker.fetch(new Request(SAIT + shliakh, { method: metod, headers: h, body, redirect: 'manual' }), env);
  return { r, text: await r.text(), kudy: r.headers.get('location') };
}
const sql = (env, s, ...p) => env.BAZA.db.prepare(s).all(...p);

test('«скоро»: сторінка показує товар, ціну й будинок; пошта, товар і будинок записуються; без згоди й з чужого сайту — ні', async () => {
  const env = seredovyshche();
  const { text } = await zapyt(env, 'GET', '/oplata/?tovar=dovidka&budynok=/budynok/zhylianska/5/&dzherelo=budynok&adresa=ПІДРОБКА');
  assert.match(text, /Скоро — залиште пошту/);
  assert.match(text, /Довідка про будинок/);
  assert.match(text, /вулиця Жилянська, 5/);
  assert.ok(!text.includes('ПІДРОБКА'), 'адреса — лише зі сторінки будинку');
  assert.match(text, new RegExp(`${TS.tsiny.dovidka}\\s?грн`));
  assert.ok(!/odrazu/.test(text), 'у «скоро» нічого не оплачують — галочки П6 немає');
  assert.ok(!text.includes('href="/kabinet/"'), 'у «скоро» кабінету ще немає — і посилання на нього');

  const f = { tovar: 'dovidka', budynok: '/budynok/zhylianska/5/', poshta: ' Ana@Poshta.UA ', zghoda: 'tak', dzherelo: 'budynok' };
  let v = await zapyt(env, 'POST', '/api/skoro', { forma: f });
  assert.equal(v.r.status, 303);
  assert.match(v.kudy, /\/oplata\/zapysaly\/$/);
  await zapyt(env, 'POST', '/api/skoro', { forma: f });                                   // повтор — не дублюється
  const rr = sql(env, 'SELECT poshta, tovar, budynok, adresa, kanal FROM skoro');
  assert.deepEqual(rr.map((x) => ({ ...x })), [{ poshta: 'ana@poshta.ua', tovar: 'dovidka', budynok: '/budynok/zhylianska/5/', adresa: 'вулиця Жилянська, 5', kanal: 'budynok' }]);

  v = await zapyt(env, 'POST', '/api/skoro', { forma: { ...f, zghoda: '' } });
  assert.match(v.text, /Потрібна згода/);
  v = await zapyt(env, 'POST', '/api/skoro', { forma: { ...f, budynok: '/budynok/nemaie/1/' } });
  assert.match(v.text, /Такого будинку/);
  v = await zapyt(env, 'POST', '/api/skoro', { forma: { ...f, poshta: 'ne-poshta' } });
  assert.match(v.text, /Перевірте пошту/);
  v = await zapyt(env, 'POST', '/api/skoro', { forma: { ...f, tovar: 'shcho' } });
  assert.equal(v.r.status, 400);
  v = await zapyt(env, 'POST', '/api/skoro', { forma: { ...f, poshta: 'b@b.ua' }, origin: 'https://zlyi.test' });
  assert.equal(v.r.status, 403);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM skoro')[0].n, 1);

  await zapyt(env, 'POST', '/api/skoro', { forma: { tovar: 'pidpyska', poshta: 'b@b.ua', zghoda: 'tak' } });
  await zapyt(env, 'POST', '/api/skoro', { forma: { tovar: 'sudova', poshta: 'b@b.ua', zghoda: 'tak', dzherelo: 'Погано!' } });
  assert.deepEqual(sql(env, `SELECT tovar, budynok, kanal FROM skoro WHERE poshta = 'b@b.ua' ORDER BY id`).map((x) => [x.tovar, x.budynok, x.kanal]),
    [['pidpyska', '', 'priamo'], ['sudova', '', 'inshe']]);
});

test('«скоро»: оплати, кабінету, довідок і тестової оплати немає; бізнес — на свою вітрину; вимкнено — статичний сайт', async () => {
  const env = seredovyshche({ PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 'k' });
  const z = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'dovidka', budynok: '/budynok/zhylianska/5/', poshta: 'a@b.ua', zghoda: 'tak', odrazu: 'tak' } });
  assert.equal(z.r.status, 404);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM zamovlennia')[0].n, 0);
  assert.equal((await zapyt(env, 'GET', '/kabinet/')).r.status, 404);
  assert.match((await zapyt(env, 'GET', '/kabinet/')).text, /статичний/);
  assert.match((await zapyt(env, 'GET', '/oplata/?tovar=biznes')).kudy, /\/biznes\/$/);
  const vymk = seredovyshche({ PRODAZH: '' });
  assert.match((await zapyt(vymk, 'GET', '/oplata/?tovar=dovidka')).text, /статичний \/oplata\//);
  assert.match((await zapyt(vymk, 'POST', '/api/skoro', { forma: { tovar: 'dovidka' } })).text, /статичний/);
});

test('форми сайту: передзамовлення, звернення (лист партнеру), чотири числа; перевірки як у nadsylannya.js', async () => {
  for (const PRODAZH of ['skoro', 'tak']) {
    const env = seredovyshche({ PRODAZH });
    assert.equal((await zapyt(env, 'POST', '/api/forma/zayavka', { json: { shcho: 'analiz', misto: 'Київ', adresa: 'Жилянська 5', kontakt: 'a@b.ua', zghoda: true, kanal: 'oplata-dovidka' } })).r.status, 201);
    assert.equal((await zapyt(env, 'POST', '/api/forma/zayavka', { json: { shcho: 'analiz', misto: 'Київ', kontakt: 'a@b.ua', zghoda: false } })).r.status, 400);
    assert.equal((await zapyt(env, 'POST', '/api/forma/zayavka', { json: { misto: 'Київ', kontakt: 'a@b.ua', zghoda: true }, origin: 'https://zlyi.test' })).r.status, 403);
    assert.equal((await zapyt(env, 'POST', '/api/forma/zayavka', { json: { shcho: 'zlom', misto: 'К'.repeat(500), kontakt: 'x', zghoda: true } })).r.status, 201);
    const z = sql(env, 'SELECT shcho, length(misto) m, kanal FROM zayavka ORDER BY id');
    assert.deepEqual(z.map((x) => [x.shcho, x.m, x.kanal]), [['analiz', 4, 'oplata-dovidka'], ['povidomyty', 80, 'priamo']]);

    assert.equal((await zapyt(env, 'POST', '/api/forma/zvernennya', { json: { posylannya: 'https://reyestr.court.gov.ua/Review/1', shcho_ne_tak: 'vydalyty', kontakt: 'tel 1', zghoda: true } })).r.status, 201);
    assert.equal((await zapyt(env, 'POST', '/api/forma/zvernennya', { json: { posylannya: 'x', shcho_ne_tak: 'shcho', kontakt: 'tel', zghoda: true } })).r.status, 400);
    assert.equal(sql(env, 'SELECT COUNT(*) n FROM zvernennya')[0].n, 1);
    const lyst = env.__LYSTY.find((l) => l.komu === 'partner@mv.test');
    assert.match(lyst.tema, /Нове звернення/);
    assert.match(lyst.tekst, /10 робочих днів/);
    assert.ok(!lyst.tekst.includes('tel 1'), 'контакт людини в лист не пишемо');

    for (let i = 0; i < 3; i++) await zapyt(env, 'POST', '/api/forma/podiya', { json: { nazva: 'pryishly', kanal: 'tg' } });
    assert.equal((await zapyt(env, 'POST', '/api/forma/podiya', { json: { nazva: 'vzlom' } })).r.status, 400);
    assert.deepEqual(sql(env, 'SELECT nazva, kanal, n FROM podiya').map((x) => [x.nazva, x.kanal, x.n]), [['pryishly', 'tg', 3]]);
    assert.equal((await zapyt(env, 'POST', '/api/forma/inshe', { json: {} })).r.status, 404);
  }
});

test('вивантаження для партнера: лише з ключем; CSV не виконує формули; невідома таблиця — ні', async () => {
  const env = seredovyshche();
  await zapyt(env, 'POST', '/api/forma/zayavka', { json: { shcho: 'analiz', misto: '=HYPERLINK("x")', kontakt: 'a@b.ua, "лапки"', zghoda: true } });
  assert.equal((await zapyt(env, 'GET', '/api/admin/vyvantazhennia/zayavka')).r.status, 401);
  assert.equal((await zapyt(env, 'GET', '/api/admin/vyvantazhennia/zayavka', { zaholovky: { authorization: 'Bearer ne-toi' } })).r.status, 401);
  const { r, text } = await zapyt(env, 'GET', '/api/admin/vyvantazhennia/zayavka', { zaholovky: { authorization: 'Bearer admin-kliuch' } });
  assert.equal(r.status, 200);
  assert.match(r.headers.get('content-type'), /text\/csv/);
  assert.match(text, /^id,shcho,misto/);           // BOM (для Excel) Response.text() прибирає — звіряємо байти нижче
  const bajty = new Uint8Array(await (await worker.fetch(new Request(SAIT + '/api/admin/vyvantazhennia/zayavka', { headers: { authorization: 'Bearer admin-kliuch' } }), env)).arrayBuffer());
  assert.deepEqual([...bajty.slice(0, 3)], [0xef, 0xbb, 0xbf]);
  assert.match(text, /'=HYPERLINK/);
  assert.match(text, /"a@b\.ua, ""лапки"""/);
  assert.equal((await zapyt(env, 'GET', '/api/admin/vyvantazhennia/korystuvachi', { zaholovky: { authorization: 'Bearer admin-kliuch' } })).r.status, 404);
  assert.equal((await zapyt(seredovyshche({ ADMIN_KLIUCH: '' }), 'GET', '/api/admin/vyvantazhennia/skoro', { zaholovky: { authorization: 'Bearer ' } })).r.status, 401);
});

// ---------------------------------------------------------------- П6, П7 (режим 'tak')

const PRODAZH = { PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 'test-kliuch' };

test('MV-155, П6: без галочки «надіслати одразу» замовлення не створюється; на формі — обов\'язкова галочка', async () => {
  const env = seredovyshche(PRODAZH);
  const { text } = await zapyt(env, 'GET', '/oplata/?tovar=dovidka&budynok=/budynok/zhylianska/5/');
  assert.match(text, /<input type="checkbox" name="odrazu" value="tak" required> Прошу надіслати одразу; після надсилання відмовитися не можна/);
  for (const odrazu of [undefined, '', 'ni']) {
    const f = { tovar: 'dovidka', budynok: '/budynok/zhylianska/5/', poshta: 'a@b.ua', zghoda: 'tak' };
    if (odrazu !== undefined) f.odrazu = odrazu;
    const v = await zapyt(env, 'POST', '/api/zamovlennia', { forma: f });
    assert.equal(v.r.status, 200);
    assert.match(v.text, /без цього оплатити не можна/);
  }
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM zamovlennia')[0].n, 0);
  const v = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'dovidka', budynok: '/budynok/zhylianska/5/', poshta: 'a@b.ua', zghoda: 'tak', odrazu: 'tak' } });
  assert.equal(v.r.status, 303);
});

async function oplatytyOsbb(env, poshta) {
  const v = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'osbb', budynok: '/budynok/obolonskyi/16/', poshta, zghoda: 'tak', odrazu: 'tak' } });
  const id = new URL(v.kudy).pathname.match(/(z[a-z2-7]+)/)[1];
  const p = { zamovlennia: id, suma: String(TS.tsiny.osbb), podiia: 'oplata', chas: 'c1' };
  await zapyt(env, 'POST', '/api/spovishchennia/test', { forma: { ...p, pidpys: pidpysTestu(env, p) }, origin: null });
  return id;
}

test('MV-155, П7: лист ОСББ за 3 дні до річного списання — один раз; скасованим — ні; наступного року — знову', async () => {
  const env = seredovyshche(PRODAZH);
  await oplatytyOsbb(env, 'osbb@poshta.ua');
  await oplatytyOsbb(env, 'skasuvav@poshta.ua');
  env.BAZA.db.prepare(`UPDATE pidpysky SET status = 'skasovana' WHERE korystuvach_id = (SELECT id FROM korystuvachi WHERE poshta = 'skasuvav@poshta.ua')`).run();
  const den = () => worker.scheduled({}, env);
  const lystyOsbb = () => env.__LYSTY.filter((l) => /річна оплата/.test(l.tema));

  await den();
  assert.equal(lystyOsbb().length, 0, 'на початку року — нічого');
  const p = sql(env, `SELECT * FROM pidpysky WHERE status = 'aktyvna'`)[0];
  env.krok(p.diie_do - 1_790_000_000 - 4 * 86400);
  await den();
  assert.equal(lystyOsbb().length, 0, 'за 4 дні — ще ні');
  env.krok(86400);
  await den();
  await den();
  env.krok(86400);
  await den();
  const l = lystyOsbb();
  assert.equal(l.length, 1, 'за 3 дні — рівно один лист, хоч розклад спрацював тричі');
  assert.equal(l[0].komu, 'osbb@poshta.ua');
  assert.match(l[0].tekst, /проспект Оболонський, 16/);
  assert.match(l[0].tekst, new RegExp(`спише 1\\s490 грн`));
  assert.match(l[0].tekst, /https:\/\/mv\.test\/kabinet\//);
  assert.match(l[0].tekst, /Скасувати підписку/);

  // Наступне річне списання → новий кінець періоду → за рік — ще один лист.
  const id = p.zamovlennia_id;
  env.krok(3 * 86400);
  const q = { zamovlennia: id, suma: String(TS.tsiny.osbb), podiia: 'oplata', chas: 'c2' };
  await zapyt(env, 'POST', '/api/spovishchennia/test', { forma: { ...q, pidpys: pidpysTestu(env, q) }, origin: null });
  const p2 = sql(env, 'SELECT * FROM pidpysky WHERE id = ?', p.id)[0];
  assert.ok(p2.diie_do > p.diie_do + 360 * 86400);
  env.krok(p2.diie_do - p.diie_do - 2 * 86400);
  await den();
  assert.equal(lystyOsbb().length, 2);
});

test('LiqPay: пісочниця (sandbox = 1) лише з LIQPAY_SANDBOX = tak', async () => {
  const env = { LIQPAY_PUBLIC_KEY: 'sandbox_i1', LIQPAY_PRIVATE_KEY: 'sandbox_p1' };
  const zam = { id: 'zabc', suma: TS.tsiny.dovidka, stvoreno: 1_790_000_000 };
  const dani = async (e) => JSON.parse(Buffer.from((await PEREKHIDNYKY.liqpay.stvoryty({ zam, opys: 'x', adresa: SAIT, env: e })).forma.polia.data, 'base64').toString());
  assert.equal((await dani(env)).sandbox, undefined);
  assert.equal((await dani({ ...env, LIQPAY_SANDBOX: 'tak' })).sandbox, '1');
});

test('оплату ввімкнено — «Судова практика» без даних генератора (ZAVDANNYA-150, п. 11) — «Скоро», не оплата', async () => {
  const env = seredovyshche(PRODAZH);
  for (const tovar of ['spdovidka', 'spyurist']) {
    assert.ok(!TS.prodaietsia.includes(tovar), `${tovar}: не продається, доки немає генератора й файла даних`);
    const { text } = await zapyt(env, 'GET', `/oplata/?tovar=${tovar}&dzherelo=sp`);
    assert.match(text, /action="\/api\/skoro"/, tovar);
    const z = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar, stattia: 'kupap-130', poshta: 'a@b.ua', zghoda: 'tak', odrazu: 'tak', ne_dopomoga: 'tak' } });
    assert.equal(z.r.status, 400, `${tovar}: замовлення без даних не створюється`);
  }
  assert.match((await zapyt(env, 'GET', '/oplata/?tovar=sudova&dzherelo=sp')).text, /action="\/api\/skoro"/);
  assert.match((await zapyt(env, 'GET', '/oplata/?tovar=dovidka&budynok=/budynok/zhylianska/5/')).text, /action="\/api\/zamovlennia"/);
  const v = await zapyt(env, 'POST', '/api/skoro', { forma: { tovar: 'spyurist', poshta: 'yurist@b.ua', zghoda: 'tak' } });
  assert.equal(v.r.status, 303);
  assert.equal(sql(env, 'SELECT tovar FROM skoro')[0].tovar, 'spyurist');
});
