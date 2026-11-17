// Платіжні сервіси — через ОДИН шар-перехідник (ZAVDANNYA-99). Решта сервера не знає, який сервіс увімкнено.
//
// Кожен перехідник має:
//   stvoryty({zam, pidpyska, opys, adresa, env})  → { pereity: url } або { forma: { url, polia } } — куди вести покупця;
//   perevirka(request, env)  → { podii: [ { zamovlennia_id, suma, valiuta, podiia, kliuch } ], vidpovid(rezultat) → Response }
//                              кидає PomylkaPidpysu, якщо підпис не той (тоді сервер нічого не змінює);
//                              podiia: 'oplata' | 'vidmova' | 'povernennia' | 'skasuvannia'; suma — у гривнях;
//   skasuvaty({ zamovlennia_id, env })  → скасувати регулярне списання в сервісі.
// Ключі — лише змінні середовища Workers (wrangler secret put …), ніколи у файлах.
//
// Сервіси (docs/PRODAZH-SERVER.md, розд. 2): LiqPay і plata by mono — перехідники-заглушки, написані за документацією,
// на справжніх ключах НЕ перевірені. «test» — оплата без грошей, працює лише в тестовому режимі.
import { hmac, hesh, rivni } from './bezpeka.js';
import { createVerify } from 'node:crypto';

export class PomylkaPidpysu extends Error {}
export class NePidtrymano extends Error {}

const ok = () => new Response('ok', { headers: { 'content-type': 'text/plain; charset=utf-8' } });

// ---------------------------------------------------------------- тестова оплата (без грошей)
// Сторінка /oplata/test/<замовлення> показує кнопки «Оплата пройшла», «Відмова», «Списання наступного періоду»,
// «Повернення». Кожна кнопка надсилає сповіщення, підписане TEST_KLIUCH, — тим самим шляхом, що й справжній сервіс.
export function pidpysTestu(env, polia) {
  return hmac('sha256', env.TEST_KLIUCH, [polia.zamovlennia, polia.suma, polia.podiia, polia.chas].join(';'));
}

const test = {
  nazva: 'test',
  async stvoryty({ zam }) {
    return { pereity: `/oplata/test/${zam.id}/` };
  },
  async perevirka(request, env) {
    const f = Object.fromEntries(await request.formData());
    if (!env.TEST_KLIUCH || !rivni(f.pidpys, pidpysTestu(env, f))) throw new PomylkaPidpysu('test');
    return {
      podii: [{ zamovlennia_id: f.zamovlennia, suma: Number(f.suma), valiuta: 'UAH', podiia: f.podiia,
                kliuch: `${f.zamovlennia};${f.podiia};${f.chas}` }],
      vidpovid: (r) => Response.redirect(new URL(r.ok ? `/oplata/dyakuiemo/?z=${f.zamovlennia}` : '/oplata/', request.url).toString(), 303),
    };
  },
  async skasuvaty() { return true; },
};

// ---------------------------------------------------------------- LiqPay (ПриватБанк)
// Документація: https://www.liqpay.ua/doc — checkout: форма POST на https://www.liqpay.ua/api/3/checkout з полями
// data = base64(JSON), signature = base64(hash(private_key + data + private_key)).
// Алгоритм: текст документації (17.11.2026) — sha3-256, приклади коду там же — sha1. Тому — змінна LIQPAY_HESH
// ('sha1' за замовчуванням або 'sha3-256'); перевірити на тестових ключах LiqPay в день Х.
// Підписка: action 'subscribe', subscribe_periodicity 'month' | 'year'; скасування — action 'unsubscribe' (api/request).
// Не перевірено: чи приходять щомісячні списання з тим самим order_id (від цього залежить продовження підписки).
function liqpayPidpys(env, data) {
  return hesh(env.LIQPAY_HESH || 'sha1', env.LIQPAY_PRIVATE_KEY + data + env.LIQPAY_PRIVATE_KEY, 'base64');
}
function liqpayData(obj) {
  return Buffer.from(JSON.stringify(obj), 'utf8').toString('base64');
}
function liqpayChas(t) { // 'YYYY-MM-DD HH:MM:SS' UTC
  return new Date(t * 1000).toISOString().slice(0, 19).replace('T', ' ');
}
const LIQPAY_STATUS = { success: 'oplata', subscribed: 'oplata', failure: 'vidmova', error: 'vidmova',
                        reversed: 'povernennia', unsubscribed: 'skasuvannia' };

const liqpay = {
  nazva: 'liqpay',
  async stvoryty({ zam, pidpyska, opys, adresa, env }) {
    const p = {
      version: 3, public_key: env.LIQPAY_PUBLIC_KEY, action: pidpyska ? 'subscribe' : 'pay',
      amount: zam.suma, currency: 'UAH', description: opys, order_id: zam.id, language: 'uk',
      result_url: `${adresa}/oplata/dyakuiemo/?z=${zam.id}`, server_url: `${adresa}/api/spovishchennia/liqpay`,
    };
    if (pidpyska) {
      p.subscribe = '1';
      p.subscribe_date_start = liqpayChas(zam.stvoreno);
      p.subscribe_periodicity = pidpyska.period_misiatsiv === 12 ? 'year' : 'month';
    }
    const data = liqpayData(p);
    return { forma: { url: 'https://www.liqpay.ua/api/3/checkout', polia: { data, signature: liqpayPidpys(env, data) } } };
  },
  async perevirka(request, env) {
    const f = Object.fromEntries(await request.formData());
    if (!env.LIQPAY_PRIVATE_KEY || !f.data || !rivni(f.signature, liqpayPidpys(env, f.data))) throw new PomylkaPidpysu('liqpay');
    const d = JSON.parse(Buffer.from(f.data, 'base64').toString('utf8'));
    const podiia = LIQPAY_STATUS[d.status];
    const podii = podiia ? [{ zamovlennia_id: String(d.order_id), suma: Number(d.amount), valiuta: d.currency, podiia,
                              kliuch: `${d.payment_id ?? d.transaction_id ?? ''};${d.status};${d.end_date ?? d.create_date ?? ''}` }] : [];
    return { podii, vidpovid: ok };
  },
  async skasuvaty({ zamovlennia_id, env }) {
    const data = liqpayData({ version: 3, public_key: env.LIQPAY_PUBLIC_KEY, action: 'unsubscribe', order_id: zamovlennia_id });
    const r = await fetch('https://www.liqpay.ua/api/request', {
      method: 'POST', body: new URLSearchParams({ data, signature: liqpayPidpys(env, data) }),
    });
    const v = await r.json().catch(() => ({}));
    return r.ok && (v.status === 'unsubscribed' || v.result === 'ok');
  },
};

// ---------------------------------------------------------------- plata by mono (monobank)
// Документація: https://monobank.ua/api-docs/acquiring — рахунок: POST https://api.monobank.ua/api/merchant/invoice/create,
// заголовок X-Token (MONO_TOKEN), сума в копійках, ccy 980, merchantPaymInfo.reference = номер нашого замовлення,
// webHookUrl; відповідь — pageUrl. Сповіщення підписане ECDSA (заголовок X-Sign, base64), відкритий ключ —
// GET /api/merchant/pubkey (кладемо в MONO_PUBKEY: він не секретний, але змінюється лише з токеном).
// Регулярні платежі в mono є (розділ «Регулярні платежі»), але поля не звірено — перехідник їх НЕ підтримує:
// підписку з mono увімкнути після звірки з документацією на ключах партнера (NePidtrymano → зрозуміла відмова).
const MONO_STATUS = { success: 'oplata', failure: 'vidmova', expired: 'vidmova', reversed: 'povernennia' };

const mono = {
  nazva: 'mono',
  async stvoryty({ zam, pidpyska, opys, adresa, env }) {
    if (pidpyska) throw new NePidtrymano('Підписка через mono ще не підключена.');
    const r = await fetch('https://api.monobank.ua/api/merchant/invoice/create', {
      method: 'POST',
      headers: { 'X-Token': env.MONO_TOKEN, 'content-type': 'application/json' },
      body: JSON.stringify({
        amount: zam.suma * 100, ccy: 980,
        merchantPaymInfo: { reference: zam.id, destination: opys },
        redirectUrl: `${adresa}/oplata/dyakuiemo/?z=${zam.id}`, webHookUrl: `${adresa}/api/spovishchennia/mono`,
      }),
    });
    const v = await r.json().catch(() => ({}));
    if (!r.ok || !v.pageUrl) throw new Error(`mono: рахунок не створено (${r.status})`);
    return { pereity: v.pageUrl };
  },
  async perevirka(request, env) {
    const tilo = await request.text();
    const pidpys = request.headers.get('x-sign') || '';
    let dobre = false;
    try {
      const v = createVerify('SHA256');
      v.update(tilo);
      dobre = !!env.MONO_PUBKEY && v.verify(Buffer.from(env.MONO_PUBKEY, 'base64').toString('utf8'), Buffer.from(pidpys, 'base64'));
    } catch { dobre = false; }
    if (!dobre) throw new PomylkaPidpysu('mono');
    const d = JSON.parse(tilo);
    const podiia = MONO_STATUS[d.status];
    const kop = Number(d.finalAmount ?? d.amount);
    const podii = podiia ? [{ zamovlennia_id: String(d.reference ?? ''), suma: kop / 100, valiuta: d.ccy === 980 || d.ccy === undefined ? 'UAH' : String(d.ccy),
                              podiia, kliuch: `${d.invoiceId};${d.status};${d.modifiedDate ?? ''}` }] : [];
    return { podii, vidpovid: ok };
  },
  async skasuvaty() { throw new NePidtrymano('Підписка через mono ще не підключена.'); },
};

export const PEREKHIDNYKY = { test, liqpay, mono };

/** Увімкнений перехідник. Тестовий — лише коли ОБИДВІ змінні кажуть «тест» (щоб не ввімкнути випадково на живому). */
export function perekhidnyk(env, nazva = env.PLATIZHNYI_SERVIS) {
  const p = PEREKHIDNYKY[nazva];
  if (!p) return null;
  if (nazva === 'test' && env.TESTOVA_OPLATA !== 'tak') return null;
  return p;
}
