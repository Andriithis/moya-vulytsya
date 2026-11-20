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

// ---------------------------------------------------------------- кабінет (ZVIT-166 З-4, ZVIT-167 пп. 1, 8)

test('кабінет: підписнику — «Відкрити карту» (коли карту викладено); без підписки — ні', async () => {
  const env = seredovyshche({ KARTA: r2() });
  await oplatyty(env, await zamovyty(env, 'pidpyska'));
  const kuka = await uviity(env);
  const { text } = await zapyt(env, 'GET', '/kabinet/', { kuka });
  assert.match(text, /href="\/pidpysnyk\/">Відкрити карту</);
  const env2 = seredovyshche({ KARTA: r2() });
  await oplatyty(env2, await zamovyty(env2, 'dovidka', '/budynok/zhylianska/5/'));
  const { text: t2 } = await zapyt(env2, 'GET', '/kabinet/', { kuka: await uviity(env2) });
  assert.doesNotMatch(t2, /Відкрити карту/);
});

test('«Видалити мої дані»: спершу сторінка «Що зникне» з довідками, підпискою й залишком; без підтвердження нічого не стирається', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'try', '/budynok/zhylianska/5/'));
  await oplatyty(env, await zamovyty(env, 'pidpyska'));
  const kuka = await uviity(env);
  let { text } = await zapyt(env, 'GET', '/kabinet/', { kuka });
  assert.match(text, /href="\/kabinet\/vydalyty\/"/);
  assert.doesNotMatch(text, /action="\/kabinet\/vydalyty"/, 'у кабінеті — не кнопка, що стирає одразу, а перехід на підтвердження');
  // натискання старої кнопки (лише pidtverdzhuiu) — на підтвердження, дані на місці
  let v = await zapyt(env, 'POST', '/kabinet/vydalyty', { kuka, forma: { pidtverdzhuiu: 'tak' } });
  assert.equal(v.r.status, 303);
  assert.equal(new URL(v.kudy).pathname, '/kabinet/vydalyty/');
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM korystuvachi')[0].n, 1);
  ({ text } = await zapyt(env, 'GET', '/kabinet/vydalyty/', { kuka }));
  assert.match(text, /Що зникне/);
  assert.match(text, /1\sдовідка/);
  assert.match(text, /3\sоплачені довідки, яких ще не взяли/);      // 2 з пакета + 1 з підписки
  assert.match(text, /Підписка, оплачена до \d\d\.\d\d\.\d{4}/);
  assert.match(text, /Не видаляти/);
  assert.match(text, /name="rozumiiu"/);
  // підтвердили — стерто; довідка в черзі знята, видавач її не бере
  v = await zapyt(env, 'POST', '/kabinet/vydalyty', { kuka, forma: { pidtverdzhuiu: 'tak', rozumiiu: 'tak' } });
  assert.match(v.text, /Дані видалено/);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM korystuvachi')[0].n, 0);
  assert.deepEqual(await vydavach(env), [], 'черга порожня — видавач не падає на довідці без адреси');
  // без входу сторінки підтвердження немає
  v = await zapyt(env, 'GET', '/kabinet/vydalyty/');
  assert.equal(v.r.status, 303);
});

test('кабінет за роллю: рієлтор — без другого списку довідок; людина без залишку — «Ще одна довідка — 199»; із залишком — поле адреси', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'rieltor', null, 'r@b.ua'));
  const kr = await uviity(env, 'r@b.ua');
  await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: kr, forma: { budynok: '/budynok/zhylianska/5/' } });
  let { text } = await zapyt(env, 'GET', '/kabinet/', { kuka: kr });
  assert.match(text, /Мої об'єкти/);
  assert.doesNotMatch(text, /<h2>Мої довідки/);
  assert.equal((text.match(/лишилось/g) || []).length, 1, 'лічильник — один раз');

  await oplatyty(env, await zamovyty(env, 'dovidka', '/budynok/zhylianska/5/', 'o@b.ua'));
  ({ text } = await zapyt(env, 'GET', '/kabinet/', { kuka: await uviity(env, 'o@b.ua') }));
  assert.match(text, /Ще одна довідка — 199/);
  assert.doesNotMatch(text, /кнопкою «Довідка» біля адреси нижче/);
  assert.match(text, /готується \(<a href="\/kabinet\/">оновити<\/a>\)/);

  await oplatyty(env, await zamovyty(env, 'try', '/budynok/zhylianska/5/', 't@b.ua'));
  ({ text } = await zapyt(env, 'GET', '/kabinet/', { kuka: await uviity(env, 't@b.ua') }));
  assert.match(text, /Можна взяти без оплати: 2 з пакета/);
  assert.match(text, /Взяти довідку/);
});

test('той самий будинок за добу — спершу питаємо, а не мовчки витрачаємо ще одну довідку', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'rieltor', null, 'r@b.ua'));
  const kr = await uviity(env, 'r@b.ua');
  await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: kr, forma: { budynok: '/budynok/zhylianska/5/' } });
  let { text } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: kr, forma: { budynok: '/budynok/zhylianska/5/' } });
  assert.match(text, /довідка вже є/);
  assert.match(text, /name="shche" value="tak"/);
  assert.equal(sql(env, 'SELECT COUNT(*) n FROM dovidky')[0].n, 1);
  ({ text } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: kr, forma: { budynok: '/budynok/zhylianska/5/', shche: 'tak' } }));
  assert.match(text, /готуємо/);
  env.krok(86400 + 1);
  ({ text } = await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: kr, forma: { budynok: '/budynok/zhylianska/5/' } }));
  assert.match(text, /готуємо/, 'наступного дня — без питання');
});

// ---------------------------------------------------------------- листи (ZVIT-167, п. 9)

test('листи: у листі довідки — перший висновок; рієлтору — «лишилось» на момент кожної довідки; лист оплати рієлтору — «Мої об\'єкти»', async () => {
  const env = seredovyshche();
  await oplatyty(env, await zamovyty(env, 'rieltor', null, 'r@b.ua'));
  const oplata = env.__LYSTY.find((l) => l.komu === 'r@b.ua' && l.tema.startsWith('Оплату отримано'));
  assert.match(oplata.tekst, /5 довідок про будинки на місяць/);
  assert.match(oplata.tekst, /Мої об'єкти/);
  const kr = await uviity(env, 'r@b.ua');
  for (const b of ['/budynok/zhylianska/5/', '/budynok/obolonskyi/16/', '/budynok/zhylianska/5/']) {
    await zapyt(env, 'POST', '/kabinet/dovidka', { kuka: kr, forma: { budynok: b, shche: 'tak' } });
  }
  // видавач віддає всі три разом — уже після того, як узято всі три
  const { text } = await zapyt(env, 'GET', '/api/vnutr/cherha?n=10', { zaholovky: AVT });
  for (const d of JSON.parse(text).dovidky) {
    await zapyt(env, 'PUT', `/api/vnutr/dovidka/${d.id}`, { zaholovky: AVT,
      tilo: '<!doctype html><h2>Головне — 3 висновки</h2><ol class="holovne"><li><b>226</b> скарг до 1551 &mdash; найчастіше <b>вода</b> (21; у сусідніх — 15).</li><li>друге</li></ol>' });
  }
  const lysty = env.__LYSTY.filter((l) => l.komu === 'r@b.ua' && l.tema.startsWith('Довідка'));
  assert.equal(lysty.length, 3);
  assert.deepEqual(lysty.map((l) => l.tekst.match(/лишилось довідок: (\d) з 5/)[1]).sort(), ['2', '3', '4']);
  assert.match(lysty[0].tekst, /Головне: 226 скарг до 1551 — найчастіше вода \(21; у сусідніх — 15\)\./);
  assert.doesNotMatch(lysty[0].tekst, /<b>|друге/);
});

// ---------------------------------------------------------------- логотип і підвал (ZVIT-171, п. 2 і 10)

test('сторінки сервера: логотип зі значком і назвою для читалки, як на сайті; кнопка теми; у підвалі — «Доступність» і «Хто ми»', async () => {
  const { readFileSync } = await import('node:fs');
  const env = seredovyshche();
  for (const s of ['/kabinet/', '/oplata/?tovar=pidpyska', '/oplata/zapysaly/']) {
    const { text } = await zapyt(env, 'GET', s);
    assert.match(text, /<a class="lohotyp" href="\/" aria-label="Моя вулиця — на головну"><svg aria-hidden="true"/, s);
    assert.match(text, /data-tema-perem/, s);
    assert.match(text, /href="\/dostupnist\/">Доступність</, s);
    assert.match(text, /href="\/zahlushka\/pro-nas.html">Хто ми/, s);
  }
  // значок той самий, що на сайті (site/zibraty_sait.py, ZNAK)
  const py = readFileSync(new URL('../../zibraty_sait.py', import.meta.url), 'utf8');
  const d = py.match(/'d="(M13 1 L25 8[^"]+)"/)[1];
  const { text } = await zapyt(env, 'GET', '/kabinet/');
  assert.ok(text.includes(d), 'значок сервера = значок сайту');
});

// ---------------------------------------------------------------- «скоро» для «Судової практики» (ZVIT-169, п. 9)

test('«скоро» довідки СП: стаття, суд і частина видно на сторінці й ідуть з формою; у базу — лише лічильник без пошти', async () => {
  const DOVIDNYK = { statti: { 'kupap-130': { stattia: 'ст.130 КУпАП', nazva: 'Керування', sudy: ['Голосіївський'], chastyny: ['1', '2'] } } };
  for (const PRODAZH of ['tak', 'skoro']) {
    const env = seredovyshche({ PRODAZH, ADMIN_KLIUCH: 'admin', ASSETS: { async fetch(req) {
      return new URL(req.url).pathname === '/sudova-praktyka/dovidnyk.json' ? Response.json(DOVIDNYK) : new Response('немає', { status: 404 });
    } } });
    const { text } = await zapyt(env, 'GET', '/oplata/?tovar=spdovidka&stattia=kupap-130&sud=Голосіївський&chastyna=1');
    assert.match(text, /Скоро — залиште пошту/);
    assert.match(text, /Стаття й суд: <b>ст.\s130 ч.\s1 КУпАП — Голосіївський районний суд<\/b>/);
    assert.match(text, /name="stattia" value="kupap-130"/);
    // вигаданий суд — без вибору, але сторінка працює
    const { text: t2 } = await zapyt(env, 'GET', '/oplata/?tovar=spdovidka&stattia=kupap-130&sud=Вигаданий');
    assert.doesNotMatch(t2, /Стаття й суд/);
    for (const poshta of ['a@b.ua', 'c@b.ua']) {
      const v = await zapyt(env, 'POST', '/api/skoro', { forma: { tovar: 'spdovidka', poshta, zghoda: 'tak', stattia: 'kupap-130', sud: 'Голосіївський', chastyna: '1' } });
      assert.equal(v.r.status, 303);
    }
    const r = sql(env, 'SELECT stattia, sud, chastyna, n FROM skoro_sp').map((x) => ({ ...x }));
    assert.deepEqual(r, [{ stattia: 'ст.130 КУпАП', sud: 'Голосіївський', chastyna: '1', n: 2 }], PRODAZH);
    const { text: csv } = await zapyt(env, 'GET', '/api/admin/vyvantazhennia/skoro_sp', { zaholovky: { authorization: 'Bearer admin' } });
    assert.match(csv, /den,stattia,sud,chastyna,n/);
    assert.match(csv, /ст.130 КУпАП,Голосіївський,1,2/);
    assert.doesNotMatch(csv, /@/, 'без пошти');
  }
});

// ---------------------------------------------------------------- звернення (ZVIT-169, п. 10)

test('звернення: людина одразу отримує номер; партнер — лист з тим самим номером, без контакту людини', async () => {
  for (const PRODAZH of ['skoro', 'tak']) {
    const env = seredovyshche({ PRODAZH });
    const tilo = JSON.stringify({ posylannya: 'Адреса: вулиця Жилянська, 5', shcho_ne_tak: 'vydalyty', kontakt: 'a@b.ua', zghoda: true });
    const v = await zapyt(env, 'POST', '/api/forma/zvernennya', { tilo, zaholovky: { 'content-type': 'application/json' } });
    assert.equal(v.r.status, 201);
    const { nomer } = JSON.parse(v.text);
    assert.equal(nomer, sql(env, 'SELECT id FROM zvernennya')[0].id);
    const lyst = env.__LYSTY.find((l) => l.komu === 'partner@mv.test');
    assert.match(lyst.tema, new RegExp(`№${nomer}`));
    assert.doesNotMatch(lyst.tekst, /a@b\.ua/);
  }
});

test('стирання за строками: запит «Для бізнесу» і журнал завантажень копії — через рік (політика, розд. 5)', async () => {
  const { styratyZaStrokom } = await import('../prodazh/logika.js');
  const env = seredovyshche();
  const t0 = env.__CHAS();
  const db = env.BAZA.db;
  db.prepare(`INSERT INTO biznes_zapyty (kompaniia, kontakt, meta, strok, kanal, stvoreno) VALUES ('Стара', '+380', 'м', 'misiats', 'priamo', ?)`).run(t0);
  db.prepare(`INSERT INTO biznes_zavantazhennia (posylannia_hash, klient_id, fail, chas) VALUES ('h', 1, 'f', ?)`).run(t0);
  env.krok(200 * 86400);
  db.prepare(`INSERT INTO biznes_zapyty (kompaniia, kontakt, meta, strok, kanal, stvoreno) VALUES ('Нова', 'a@b.ua', 'м', 'rik', 'priamo', ?)`).run(env.__CHAS());
  assert.equal((await styratyZaStrokom(env)).biznes, 0, 'пів року — ще рано');
  env.krok(170 * 86400);
  assert.equal((await styratyZaStrokom(env)).biznes, 2);
  assert.deepEqual(sql(env, 'SELECT kompaniia FROM biznes_zapyty').map((x) => x.kompaniia), ['Нова']);
});
