// Вхід у кабінет через Google (ZAVDANNYA-142): OAuth 2.0 / OpenID Connect, «код авторизації» з PKCE.
// Працює, лише коли задано обидві змінні Workers: GOOGLE_KLIIENT_ID і GOOGLE_SEKRET (секрети — `npx wrangler secret put`,
// покроково — docs/SPYSOK-DLIA-MYKYTY.md, розд. «Вхід через Google»). Без них кнопки немає, адреси — «сторінки немає».
//
//   GET /kabinet/google/?kudy=<шлях>        почати: разовий «стан», nonce і PKCE → перехід на сторінку Google
//   GET /kabinet/google/povernennia/        Google повертає сюди ?code&state → обмін коду → перевірка токена → сесія
//
// Безпека:
//   - стан (state) — випадковий, разовий, 10 хвилин, прив'язаний до браузера кукою (захист від підставленого входу);
//     у базі лише його хеш; повторне повернення з тим самим станом — відмова;
//   - nonce — у запиті до Google і має бути в підписаному токені (захист від повторного використання токена);
//   - PKCE (S256) — код без секрету перевірки нічого не дає, навіть якщо його перехоплено;
//   - токен перевіряємо сами: підпис RS256 ключем Google (JWKS), видавець, адресат = наш клієнт, строк, nonce,
//     підтверджена пошта;
//   - «куди повернутися» — лише наші /kabinet/ і /oplata/, і береться з бази, а не з адреси повернення.
// Дозволи — лише `openid email`: пошта (і що Google її підтвердив). Ім'я не просимо й не зберігаємо — ніде не потрібне.
// Той самий кабінет, якщо пошта збігається (таблиця korystuvachi, пошта нижнім регістром); нова пошта — новий кабінет.
import { vypadkovyi, sha256, rivni } from './bezpeka.js';
import { createHash } from 'node:crypto';
import * as L from './logika.js';

export const AVTORYZATSIIA = 'https://accounts.google.com/o/oauth2/v2/auth';
export const TOKEN = 'https://oauth2.googleapis.com/token';
export const KLIUCHI = 'https://www.googleapis.com/oauth2/v3/certs';
const VYDAVTSI = ['https://accounts.google.com', 'accounts.google.com'];
export const DOZVOLY = 'openid email';
export const STAN_S = 10 * 60;
export const KUKA = 'mv_google';
const ZAZOR_S = 60;              // різниця годинників із Google, яку прощаємо

export const uvimkneno = (env) => !!(env.GOOGLE_KLIIENT_ID && env.GOOGLE_SEKRET);

const b64url = (buf) => Buffer.from(buf).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const zB64url = (t) => Buffer.from(String(t).replace(/-/g, '+').replace(/_/g, '/'), 'base64');

/** Куди повернутися після входу: лише наш кабінет або форма замовлення. Інакше — кабінет. */
export function chystyiKudy(kudy) {
  const t = String(kudy ?? '');
  if (t.length > 300 || !t.startsWith('/') || t.startsWith('//') || /[\\\s]/.test(t)) return '/kabinet/';
  try {
    const u = new URL(t, 'https://mv.invalid');
    // перевіряємо вже нормалізований шлях: «/kabinet/../api/…» сюди не пройде
    if (u.origin !== 'https://mv.invalid' || !/^\/(kabinet|oplata)\//.test(u.pathname)) return '/kabinet/';
    return u.pathname + u.search;
  } catch { return '/kabinet/'; }
}

export const adresaPovernennia = (adresa) => `${adresa}/kabinet/google/povernennia/`;

/** Початок входу: запис стану в базу, кука, перехід на Google. */
export async function pochaty(env, url, adresa) {
  const t = L.teper(env);
  await L.zrobyty(env, 'DELETE FROM google_stany WHERE do_ < ?', t);     // прострочені — геть (і без щоденного прибирання)
  const stan = vypadkovyi(24), nonce = vypadkovyi(24), perevirka = vypadkovyi(40);
  await L.zrobyty(env, 'INSERT INTO google_stany (hash, nonce, perevirka, kudy, do_) VALUES (?, ?, ?, ?, ?)',
    sha256(stan), nonce, perevirka, chystyiKudy(url.searchParams.get('kudy')), t + STAN_S);
  const q = new URLSearchParams({
    client_id: env.GOOGLE_KLIIENT_ID, redirect_uri: adresaPovernennia(adresa), response_type: 'code', scope: DOZVOLY,
    state: stan, nonce, code_challenge: b64url(createHash('sha256').update(perevirka).digest()), code_challenge_method: 'S256',
    prompt: 'select_account',
  });
  return new Response(null, { status: 303, headers: {
    location: `${AVTORYZATSIIA}?${q}`, 'cache-control': 'no-store', 'referrer-policy': 'no-referrer',
    'set-cookie': `${KUKA}=${stan}; Path=/kabinet/google/; Max-Age=${STAN_S}; HttpOnly; Secure; SameSite=Lax`,
  } });
}

export const STERTY_KUKU = `${KUKA}=; Path=/kabinet/google/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`;

/**
 * Повернення від Google. → { korystuvach_id, kudy } або { pomylka: текст для людини }.
 * kukaStanu — значення куки mv_google цього браузера.
 */
export async function povernennia(env, url, adresa, kukaStanu) {
  const stan = url.searchParams.get('state') || '';
  const kod = url.searchParams.get('code') || '';
  if (!stan || !kukaStanu || !rivni(stan, kukaStanu)) return { pomylka: 'Вхід не вдався: почніть ще раз з цієї сторінки.' };
  const t = L.teper(env);
  const z = await L.odyn(env, 'SELECT * FROM google_stany WHERE hash = ?', sha256(stan));
  if (!z || z.vykorystano || z.do_ < t) return { pomylka: 'Вхід застарів або вже використаний. Почніть ще раз.' };
  const r = await L.zrobyty(env, 'UPDATE google_stany SET vykorystano = ? WHERE hash = ? AND vykorystano IS NULL', t, z.hash);
  if (!r.meta?.changes) return { pomylka: 'Вхід уже використаний. Почніть ще раз.' };
  if (url.searchParams.get('error')) return { pomylka: 'Вхід через Google скасовано.' };
  if (!kod) return { pomylka: 'Вхід не вдався: почніть ще раз.' };

  let tokeny;
  try {
    const v = await fetch(TOKEN, {
      method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ code: kod, client_id: env.GOOGLE_KLIIENT_ID, client_secret: env.GOOGLE_SEKRET,
        redirect_uri: adresaPovernennia(adresa), grant_type: 'authorization_code', code_verifier: z.perevirka }),
    });
    if (!v.ok) throw new Error(`обмін коду: ${v.status}`);
    tokeny = await v.json();
  } catch (err) {
    console.log(`google: ${err.message}`);
    return { pomylka: 'Google не відповів. Спробуйте ще раз за хвилину.' };
  }
  let dani;
  try {
    dani = await perevirytyToken(env, tokeny?.id_token, { nonce: z.nonce, teper: t });
  } catch (err) {
    console.log(`google: токен не прийнято — ${err.message}`);
    return { pomylka: 'Вхід не вдався: Google не підтвердив пошту. Спробуйте ще раз або увійдіть за посиланням на пошту.' };
  }
  const poshta = L.chystaPoshta(dani.email);
  if (!poshta) return { pomylka: 'Ця пошта нам не підходить. Увійдіть за посиланням на пошту.' };
  const k = await L.korystuvach(env, poshta);
  return { korystuvach_id: k.id, kudy: chystyiKudy(z.kudy) };
}

// ---------------------------------------------------------------- перевірка токена Google (id_token, JWT RS256)

let keshKliuchiv = { do_: 0, kliuchi: [] };
export const skynutyKesh = () => { keshKliuchiv = { do_: 0, kliuchi: [] }; };

async function kliuchiGoogle(teper, novi = false) {
  if (!novi && keshKliuchiv.do_ > teper) return keshKliuchiv.kliuchi;
  const v = await fetch(KLIUCHI);
  if (!v.ok) throw new Error(`ключі Google: ${v.status}`);
  const kliuchi = (await v.json()).keys || [];
  const maxAge = parseInt(((v.headers.get('cache-control') || '').match(/max-age=(\d+)/) || [])[1] || '3600', 10);
  keshKliuchiv = { do_: teper + Math.min(maxAge, 86400), kliuchi };
  return kliuchi;
}

/** Перевіряє id_token. Повертає вміст (email тощо) або кидає помилку. */
export async function perevirytyToken(env, token, { nonce, teper }) {
  const chastyny = String(token ?? '').split('.');
  if (chastyny.length !== 3) throw new Error('не JWT');
  const [h64, p64, s64] = chastyny;
  let zaholovok, vmist;
  try { zaholovok = JSON.parse(zB64url(h64).toString('utf8')); vmist = JSON.parse(zB64url(p64).toString('utf8')); } catch { throw new Error('не JSON'); }
  if (zaholovok.alg !== 'RS256') throw new Error(`алгоритм ${zaholovok.alg}`);   // «none», HS256 тощо — ні
  let jwk = (await kliuchiGoogle(teper)).find((k) => k.kid === zaholovok.kid);
  if (!jwk) jwk = (await kliuchiGoogle(teper, true)).find((k) => k.kid === zaholovok.kid);     // Google змінив ключі
  if (!jwk || jwk.kty !== 'RSA') throw new Error('невідомий ключ');
  const kliuch = await crypto.subtle.importKey('jwk', { kty: 'RSA', n: jwk.n, e: jwk.e, alg: 'RS256', ext: true },
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']);
  const ok = await crypto.subtle.verify('RSASSA-PKCS1-v1_5', kliuch, zB64url(s64), new TextEncoder().encode(`${h64}.${p64}`));
  if (!ok) throw new Error('підпис не той');
  if (!VYDAVTSI.includes(vmist.iss)) throw new Error('видавець');
  const aud = Array.isArray(vmist.aud) ? vmist.aud : [vmist.aud];
  if (!aud.includes(env.GOOGLE_KLIIENT_ID)) throw new Error('адресат');
  if (Array.isArray(vmist.aud) && aud.length > 1 && vmist.azp !== env.GOOGLE_KLIIENT_ID) throw new Error('azp');
  if (!(Number(vmist.exp) > teper - ZAZOR_S)) throw new Error('строк минув');
  if (!(Number(vmist.iat) < teper + ZAZOR_S)) throw new Error('виданий у майбутньому');
  if (!nonce || !rivni(vmist.nonce, nonce)) throw new Error('nonce');
  if (vmist.email_verified !== true && vmist.email_verified !== 'true') throw new Error('пошта не підтверджена');
  if (!vmist.email) throw new Error('немає пошти');
  return vmist;
}
