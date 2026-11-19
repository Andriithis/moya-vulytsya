// Тести входу через Google (ZAVDANNYA-142). Запуск: node --test site/worker/testy/
// Google підроблено: свій ключ RSA, свої «сторінка ключів» і «обмін коду» (globalThis.fetch). Решта — справжній сервер
// (site/worker/index.js) на справжній схемі бази в SQLite.
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPairSync, createSign, createHash } from 'node:crypto';
import worker from '../index.js';
import * as G from '../prodazh/google.js';
import { d1, r2 } from './pidminy.mjs';

const SAIT = 'https://mv.test';
const KLIIENT = '123-mv.apps.googleusercontent.com';
const SEKRET = 'pidroblenyi-sekret';
const BUDYNKY = { '/budynok/zhylianska/5/': 'вулиця Жилянська, 5' };

// ---------------------------------------------------------------- підроблений Google

function paraKliuchiv(kid) {
  const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  return { kid, privateKey, jwk: { ...publicKey.export({ format: 'jwk' }), kid, alg: 'RS256', use: 'sig' } };
}
const b64 = (o) => Buffer.from(typeof o === 'string' ? o : JSON.stringify(o)).toString('base64url');
function jwt(vmist, { kliuch, alg = 'RS256', kid = kliuch?.kid } = {}) {
  const h = b64({ alg, kid, typ: 'JWT' }), p = b64(vmist);
  if (alg === 'none') return `${h}.${p}.`;
  const s = createSign('RSA-SHA256').update(`${h}.${p}`).sign(kliuch.privateKey).toString('base64url');
  return `${h}.${p}.${s}`;
}

const google = {
  kliuchi: [paraKliuchiv('k1')],
  chuzhyi: paraKliuchiv('k1'),           // той самий kid, інший ключ — підпис не зійдеться
  kody: new Map(),                        // код → { nonce, challenge, vmist, kliuch, alg }
  zapyty: { token: 0, kliuchi: 0 },
  vydatyKod(nonce, challenge, dod = {}) {
    const kod = `kod-${Math.random().toString(36).slice(2)}`;
    this.kody.set(kod, { nonce, challenge, ...dod });
    return kod;
  },
};

globalThis.fetch = async (url, opts = {}) => {
  const u = String(url);
  if (u === G.KLIUCHI) {
    google.zapyty.kliuchi++;
    return Response.json({ keys: google.kliuchi.map((k) => k.jwk) }, { headers: { 'cache-control': 'public, max-age=20000' } });
  }
  if (u === G.TOKEN) {
    google.zapyty.token++;
    const f = new URLSearchParams(opts.body);
    const z = google.kody.get(f.get('code'));
    google.kody.delete(f.get('code'));      // код — разовий, як у Google
    const challenge = createHash('sha256').update(f.get('code_verifier') || '').digest('base64url');
    if (!z || f.get('client_id') !== KLIIENT || f.get('client_secret') !== SEKRET || f.get('grant_type') !== 'authorization_code'
        || f.get('redirect_uri') !== `${SAIT}/kabinet/google/povernennia/` || challenge !== z.challenge) {
      return Response.json({ error: 'invalid_grant' }, { status: 400 });
    }
    const zaraz = chas();
    const vmist = { iss: 'https://accounts.google.com', aud: KLIIENT, azp: KLIIENT, sub: '1100', email: 'ana@gmail.com',
      email_verified: true, iat: zaraz, exp: zaraz + 3600, nonce: z.nonce, ...(z.vmist || {}) };
    return Response.json({ id_token: z.token || jwt(vmist, { kliuch: z.kliuch || google.kliuchi[0], alg: z.alg }), access_token: 'x' });
  }
  throw new Error(`неочікуваний запит: ${u}`);
};

// ---------------------------------------------------------------- сервер

let chasZaraz = 1_790_000_000;
const chas = () => chasZaraz;

function seredovyshche(dod = {}) {
  return {
    PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', TEST_KLIUCH: 'test-kliuch', ADRESA_SAITU: SAIT,
    GOOGLE_KLIIENT_ID: KLIIENT, GOOGLE_SEKRET: SEKRET,
    BAZA: d1(), DOVIDKY: r2(), __LYSTY: [], __CHAS: chas,
    ASSETS: { async fetch(req) {
      const p = new URL(req.url).pathname;
      return BUDYNKY[p] ? new Response(`<!doctype html><h1>${BUDYNKY[p]}</h1>`) : new Response('немає', { status: 404 });
    } },
    ...dod,
  };
}

async function zapyt(env, metod, shliakh, { forma, kuka, origin = SAIT } = {}) {
  const h = {};
  if (origin) h.origin = origin;
  if (kuka) h.cookie = kuka;
  const r = await worker.fetch(new Request(SAIT + shliakh, { method: metod, headers: h, body: forma ? new URLSearchParams(forma) : undefined, redirect: 'manual' }), env);
  return { r, text: await r.text(), kudy: r.headers.get('location'), kuky: r.headers.getSetCookie() };
}
const kukaZ = (kuky, nazva) => kuky.map((k) => k.split(';')[0]).find((k) => k.startsWith(`${nazva}=`) && k.length > nazva.length + 1);

/** Почати вхід: що сервер передав Google і яку куку поставив. */
async function pochaty(env, kudy = '/kabinet/') {
  const v = await zapyt(env, 'GET', `/kabinet/google/?kudy=${encodeURIComponent(kudy)}`);
  assert.equal(v.r.status, 303);
  const u = new URL(v.kudy);
  return { u, q: u.searchParams, kuka: kukaZ(v.kuky, G.KUKA), kuky: v.kuky };
}

/** Повний вхід; dod — що «Google» зробить інакше (vmist, kliuch, alg, token). */
async function uviity(env, { kudy, dod = {}, kukaStanu, stan } = {}) {
  const p = await pochaty(env, kudy);
  const kod = google.vydatyKod(p.q.get('nonce'), p.q.get('code_challenge'), dod);
  const s = stan ?? p.q.get('state');
  const v = await zapyt(env, 'GET', `/kabinet/google/povernennia/?state=${encodeURIComponent(s)}&code=${kod}`, { kuka: kukaStanu ?? p.kuka });
  return { ...v, p, sesiia: kukaZ(v.kuky, 'mv_sesiia') };
}

beforeEach(() => { G.skynutyKesh(); chasZaraz += 7 * 86400; });

// ---------------------------------------------------------------- тести

test('початок: Google отримує лише «openid email», стан, nonce і PKCE S256; кука стану — лише для /kabinet/google/', async () => {
  const env = seredovyshche();
  const { u, q, kuky } = await pochaty(env);
  assert.equal(`${u.origin}${u.pathname}`, G.AVTORYZATSIIA);
  assert.equal(q.get('client_id'), KLIIENT);
  assert.equal(q.get('scope'), 'openid email');
  assert.equal(q.get('response_type'), 'code');
  assert.equal(q.get('redirect_uri'), `${SAIT}/kabinet/google/povernennia/`);
  assert.equal(q.get('code_challenge_method'), 'S256');
  assert.ok(q.get('state').length >= 30 && q.get('nonce').length >= 30 && q.get('state') !== q.get('nonce'));
  assert.ok(!u.search.includes(SEKRET), 'секрет не йде в браузер');
  const k = kuky.find((x) => x.startsWith(`${G.KUKA}=`));
  assert.match(k, /HttpOnly/); assert.match(k, /Secure/); assert.match(k, /SameSite=Lax/); assert.match(k, /Path=\/kabinet\/google\//);
  const ryadok = env.BAZA.db.prepare('SELECT * FROM google_stany').all();
  assert.equal(ryadok.length, 1);
  assert.notEqual(ryadok[0].hash, q.get('state'), 'у базі — лише хеш стану');
});

test('вхід: нова пошта — новий кабінет; сесія, кука стану стерта; кабінет показує пошту', async () => {
  const env = seredovyshche();
  const v = await uviity(env);
  assert.equal(v.r.status, 303);
  assert.equal(v.kudy, `${SAIT}/kabinet/`);
  assert.ok(v.sesiia, 'має бути сесія');
  assert.ok(v.kuky.some((k) => k.startsWith(`${G.KUKA}=;`) && /Max-Age=0/.test(k)));
  const { text } = await zapyt(env, 'GET', '/kabinet/', { kuka: v.sesiia });
  assert.match(text, /ana@gmail\.com/);
  assert.match(text, /Мої довідки/);
});

test('той самий кабінет, якщо пошта збігається (і великі літери в Google не заважають)', async () => {
  const env = seredovyshche();
  // купив раніше з поштою ana@gmail.com: замовлення → оплата
  const z = await zapyt(env, 'POST', '/api/zamovlennia', { forma: { tovar: 'dovidka', budynok: '/budynok/zhylianska/5/', poshta: 'ana@gmail.com', zghoda: 'tak', odrazu: 'tak' } });
  assert.equal(z.r.status, 303);
  const pered = env.BAZA.db.prepare('SELECT id FROM korystuvachi').all();
  assert.equal(pered.length, 1);
  const v = await uviity(env, { dod: { vmist: { email: 'Ana@Gmail.com' } } });
  assert.equal(v.r.status, 303);
  assert.deepEqual(env.BAZA.db.prepare('SELECT id FROM korystuvachi').all(), pered, 'новий користувач не з\'явився');
  const s = env.BAZA.db.prepare('SELECT korystuvach_id FROM sesii').all();
  assert.equal(s.at(-1).korystuvach_id, pered[0].id);
});

test('повторне використання: те саме повернення вдруге — відмова; Google вдруге не питаємо', async () => {
  const env = seredovyshche();
  const p = await pochaty(env);
  const kod = google.vydatyKod(p.q.get('nonce'), p.q.get('code_challenge'));
  const shliakh = `/kabinet/google/povernennia/?state=${p.q.get('state')}&code=${kod}`;
  assert.equal((await zapyt(env, 'GET', shliakh, { kuka: p.kuka })).r.status, 303);
  const bulo = google.zapyty.token;
  const v2 = await zapyt(env, 'GET', shliakh, { kuka: p.kuka });
  assert.equal(v2.r.status, 400);
  assert.ok(!kukaZ(v2.kuky, 'mv_sesiia'));
  assert.equal(google.zapyty.token, bulo, 'з використаним станом до Google не йдемо');
});

test('стан: без куки, з чужою кукою, вигаданий або прострочений (10 хв) — відмова, сесії немає', async () => {
  const env = seredovyshche();
  for (const vypadok of [{ kukaStanu: '' }, { kukaStanu: `${G.KUKA}=chuzhyi` }, { stan: 'vyhadanyi' }]) {
    const v = await uviity(env, vypadok);
    assert.equal(v.r.status, 400, JSON.stringify(vypadok));
    assert.ok(!v.sesiia);
  }
  // кука й стан — від нападника (його власний початок входу), браузер жертви — інший: стан не збігається з кукою жертви
  const napadnyk = await pochaty(env);
  const zhertva = await pochaty(env);
  const kod = google.vydatyKod(napadnyk.q.get('nonce'), napadnyk.q.get('code_challenge'), { vmist: { email: 'zlyi@gmail.com' } });
  const v = await zapyt(env, 'GET', `/kabinet/google/povernennia/?state=${napadnyk.q.get('state')}&code=${kod}`, { kuka: zhertva.kuka });
  assert.equal(v.r.status, 400, 'підставлений вхід у чужий кабінет');
  // прострочений
  const p = await pochaty(env);
  chasZaraz += G.STAN_S + 1;
  const kod2 = google.vydatyKod(p.q.get('nonce'), p.q.get('code_challenge'));
  const v2 = await zapyt(env, 'GET', `/kabinet/google/povernennia/?state=${p.q.get('state')}&code=${kod2}`, { kuka: p.kuka });
  assert.equal(v2.r.status, 400);
  assert.match(v2.text, /застарів/);
});

test('токен: не той nonce, адресат, видавець, строк, непідтверджена пошта — відмова', async () => {
  const env = seredovyshche();
  const vypadky = {
    'nonce': { nonce: 'inshyi-nonce' },
    'адресат': { aud: 'inshyi-kliient.apps.googleusercontent.com', azp: 'inshyi' },
    'видавець': { iss: 'https://zlyi.example' },
    'строк': { exp: chasZaraz - 3600, iat: chasZaraz - 7200 },
    'з майбутнього': { iat: chasZaraz + 3600, exp: chasZaraz + 7200 },
    'пошта не підтверджена': { email_verified: false },
    'без пошти': { email: undefined },
  };
  for (const [nazva, vmist] of Object.entries(vypadky)) {
    const v = await uviity(env, { dod: { vmist } });
    assert.equal(v.r.status, 400, nazva);
    assert.ok(!v.sesiia, nazva);
  }
  assert.equal(env.BAZA.db.prepare('SELECT COUNT(*) AS n FROM sesii').get().n, 0);
});

test('підпис: чужий ключ, «none», HS256, зіпсований токен — відмова', async () => {
  const env = seredovyshche();
  const vmist = { iss: 'https://accounts.google.com', aud: KLIIENT, email: 'ana@gmail.com', email_verified: true, iat: chasZaraz, exp: chasZaraz + 600 };
  const vypadky = {
    'чужий ключ': { kliuch: google.chuzhyi },
    'alg none': { alg: 'none' },
    'зіпсований': { token: 'abc.def' },
  };
  for (const [nazva, dod] of Object.entries(vypadky)) {
    const v = await uviity(env, { dod });
    assert.equal(v.r.status, 400, nazva);
    assert.ok(!v.sesiia, nazva);
  }
  // HS256 з відкритим ключем Google як «секретом» — класичний напад на змішування алгоритмів
  const h = b64({ alg: 'HS256', kid: 'k1' }), p = b64({ ...vmist, nonce: 'x' });
  await assert.rejects(G.perevirytyToken({ GOOGLE_KLIIENT_ID: KLIIENT }, `${h}.${p}.AAAA`, { nonce: 'x', teper: chasZaraz }), /алгоритм/);
});

test('Google змінив ключі: невідомий kid — один повторний запит ключів, далі з кешу', async () => {
  const env = seredovyshche();
  assert.equal((await uviity(env)).r.status, 303);
  const bulo = google.zapyty.kliuchi;
  assert.equal((await uviity(env)).r.status, 303);
  assert.equal(google.zapyty.kliuchi, bulo, 'ключі — з кешу');
  const novyi = paraKliuchiv('k2');
  google.kliuchi.push(novyi);
  assert.equal((await uviity(env, { dod: { kliuch: novyi } })).r.status, 303);
  assert.equal(google.zapyty.kliuchi, bulo + 1);
  google.kliuchi.pop();
});

test('Google відмовив або скасовано: зрозуміле повідомлення, сесії немає', async () => {
  const env = seredovyshche();
  const p = await pochaty(env);
  const v = await zapyt(env, 'GET', `/kabinet/google/povernennia/?state=${p.q.get('state')}&error=access_denied`, { kuka: p.kuka });
  assert.equal(v.r.status, 400);
  assert.match(v.text, /скасовано/);
  // обмін коду не вдався (неправильний код)
  const p2 = await pochaty(env);
  const v2 = await zapyt(env, 'GET', `/kabinet/google/povernennia/?state=${p2.q.get('state')}&code=vyhadanyi`, { kuka: p2.kuka });
  assert.equal(v2.r.status, 400);
  assert.match(v2.text, /не відповів/);
});

test('«куди повернутися» — лише наші /kabinet/ і /oplata/', async () => {
  for (const [kudy, ochikuiemo] of [
    ['/oplata/?tovar=dovidka&budynok=/budynok/zhylianska/5/', '/oplata/?tovar=dovidka&budynok=/budynok/zhylianska/5/'],
    ['/kabinet/', '/kabinet/'],
    ['https://zlyi.example/', '/kabinet/'], ['//zlyi.example/kabinet/', '/kabinet/'], ['/\\zlyi.example/kabinet/', '/kabinet/'],
    ['/budynok/zhylianska/5/', '/kabinet/'], ['/kabinet/../api/admin/', '/kabinet/'], ['/oplata/%2e%2e/api/', '/kabinet/'],
    ['javascript:alert(1)', '/kabinet/'], ['', '/kabinet/'],
  ]) assert.equal(G.chystyiKudy(kudy), ochikuiemo, kudy);
  const env = seredovyshche();
  const v = await uviity(env, { kudy: 'https://zlyi.example/' });
  assert.equal(v.kudy, `${SAIT}/kabinet/`);
});

test('форма замовлення: кнопка Google веде назад на ту саму форму, після входу пошта підставлена', async () => {
  const env = seredovyshche();
  const shliakh = '/oplata/?tovar=dovidka&budynok=/budynok/zhylianska/5/';
  const { text } = await zapyt(env, 'GET', shliakh);
  const m = text.match(/href="(\/kabinet\/google\/\?kudy=[^"]+)"/);
  assert.ok(m, 'кнопки Google немає у формі замовлення');
  const kudy = new URL(m[1].replace(/&amp;/g, '&'), SAIT).searchParams.get('kudy');
  assert.equal(kudy, shliakh);
  const v = await uviity(env, { kudy });
  assert.equal(v.kudy, SAIT + shliakh);
  const { text: t2 } = await zapyt(env, 'GET', shliakh, { kuka: v.sesiia });
  assert.match(t2, /name="poshta"[^>]*value="ana@gmail\.com"/);
  assert.ok(!t2.includes('/kabinet/google/'), 'після входу кнопки вже немає');
});

test('сторінка входу: кнопка Google є з ключами; без ключів — немає, адреси Google — «сторінки немає»', async () => {
  const z = await zapyt(seredovyshche(), 'GET', '/kabinet/');
  assert.match(z.text, /Увійти через Google/);
  assert.match(z.text, /action="\/kabinet\/vkhid"/, 'вхід за посиланням на пошту лишається');
  const bez = seredovyshche({ GOOGLE_KLIIENT_ID: '', GOOGLE_SEKRET: '' });
  const b = await zapyt(bez, 'GET', '/kabinet/');
  assert.ok(!b.text.includes('Google'));
  assert.equal((await zapyt(bez, 'GET', '/kabinet/google/')).r.status, 404);
  assert.ok(!(await zapyt(bez, 'GET', '/oplata/?tovar=dovidka&budynok=/budynok/zhylianska/5/')).text.includes('Google'));
  // лише ідентифікатор без секрету — теж вимкнено
  assert.equal((await zapyt(seredovyshche({ GOOGLE_SEKRET: '' }), 'GET', '/kabinet/google/')).r.status, 404);
});

test('прострочені стани стираються під час наступного входу', async () => {
  const env = seredovyshche();
  await pochaty(env); await pochaty(env);
  chasZaraz += G.STAN_S + 1;
  await pochaty(env);
  assert.equal(env.BAZA.db.prepare('SELECT COUNT(*) AS n FROM google_stany').get().n, 1);
});
