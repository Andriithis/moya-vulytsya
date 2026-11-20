// Карта підписника зі сховища Cloudflare R2 (ZAVDANNYA-133, п. 1; MV-40, MV-104; docs/PLATNA-CHASTYNA.md).
//
// Карта підписника — та сама тека, яку збирає dani-edrsr/src/karta_pidpysnyka.py (index.html, dani/, spravy/<клітинка>.json,
// adresy/, vendor/, shryfty/). У ній адреси й описи подій, тому вона НІКОЛИ не лежить серед файлів сайту: лише в
// приватному сховищі R2 (прив'язка KARTA), а віддає її цей скрипт — і лише людині з дійсною підпискою.
// Тека в сховищі — karta/<версія>/…; яка версія чинна — файл karta/potochna.json (пише site/prodazh/karta_r2.py останнім,
// тож нова версія вмикається одним записом, а не «половина файлів нова, половина стара»).
//
//   GET /pidpysnyk/                       сторінка карти (index.html чинної версії)
//   GET /pidpysnyk/<файл>                 файли карти (dani/…, spravy/…, adresy/…, vendor/…, shryfty/…)
//   GET /pidpysnyk/api/podii?la=…&lo=…    «події адреси»: JSON з адресою й подіями точки (клітинка → покажчик → справи)
//   GET  /pidpysnyk/api/stezhu            «Стежу» з кабінету: { adresy: [{ budynok, adresa }] } (ZAVDANNYA-151)
//   POST /pidpysnyk/api/stezhu            { dia: 'dodaty', adresa } | { dia: 'prybraty', budynok } — кнопка «Стежити»
//                                         у картці адреси пише в ту саму таблицю stezhu, що й кабінет, і лист «Нове біля дому»
//
// Без входу — на вхід у кабінет; з входом, але без дійсної підписки — сторінка «Карта — для підписників» (403).
// Відповіді — private, noindex: їх не кешує Cloudflare і не бачать пошуковики.
import * as L from './logika.js';
import * as S from './storinky.js';
import TS from './tsiny.js';

export const KOREN = '/pidpysnyk/';
const POTOCHNA = 'karta/potochna.json';
const R_TOCHKY_M = 30;                 // «події адреси»: найближча точка покажчика не далі за це
const TYPY = {
  html: 'text/html; charset=utf-8', json: 'application/json; charset=utf-8', js: 'text/javascript; charset=utf-8',
  css: 'text/css; charset=utf-8', woff2: 'font/woff2', woff: 'font/woff', png: 'image/png', svg: 'image/svg+xml',
  txt: 'text/plain; charset=utf-8', pbf: 'application/x-protobuf',
};
const PRYVATNO = { 'cache-control': 'private, max-age=300', 'x-robots-tag': 'noindex, nofollow', 'referrer-policy': 'no-referrer',
  'x-content-type-options': 'nosniff', 'x-frame-options': 'DENY' };

/** Клітинка справ — як dani-edrsr/src/map_adresy.kl_spravy (KLITYNKA / 4; Math.floor, як там math.floor). */
export const KLITYNKA = [0.018 / 4, 0.028 / 4];
export const klitynka = (la, lo) => `${Math.floor(la / KLITYNKA[0])}_${Math.floor(lo / KLITYNKA[1])}`;

let keshPotochnoi = null;   // { do_, m } — маніфест у пам'яті скрипта на хвилину (одне читання R2 на хвилину, а не на кожен файл)

export async function potochna(env) {
  const t = Date.now();
  if (keshPotochnoi && keshPotochnoi.do_ > t && keshPotochnoi.env === env) return keshPotochnoi.m;
  const o = await env.KARTA.get(POTOCHNA);
  const m = o ? JSON.parse(await o.text()) : null;
  keshPotochnoi = { do_: t + 60_000, m, env };
  return m;
}

/** Дійсна підписка (місяць, рієлтор, ОСББ — оплачений період ще триває, і скасована теж до кінця періоду). */
export async function maieDostup(env, ja) {
  if (!ja) return false;
  // підписка юриста («Судова практика», ZAVDANNYA-135) карти подій не дає — лише таблиці практики
  return (await L.stanPidpysok(env, ja.id)).some((p) => p.diie && !TS.sudova.includes(p.tovar));
}

function bezpechnyiShliakh(s) {
  // лише латиниця, цифри, крапка, дефіс, підкреслення й скісна; без «..» і без початкової скісної
  return /^[A-Za-z0-9._\-/]{1,200}$/.test(s) && !s.includes('..') && !s.startsWith('/') && !s.includes('//');
}

async function chytatyJson(env, kliuch) {
  const o = await env.KARTA.get(kliuch);
  return o ? JSON.parse(await o.text()) : null;
}

function vidstanM(a, b) {
  return Math.hypot((a[0] - b[0]) * 111320, (a[1] - b[1]) * 111320 * Math.cos((a[0] * Math.PI) / 180));
}

/** «Події адреси»: { adresa, la, lo, podii: [{ data, stattia, opys, rishennia }] } або null. */
export async function podiiAdresy(env, la, lo) {
  const m = await potochna(env);
  if (!m) return null;
  const kl = klitynka(la, lo);
  const indeks = await chytatyJson(env, `karta/${m.versiia}/indeks/${kl}.json`);
  if (!indeks) return null;
  let naikrashcha = null;
  for (const [pla, plo, i, adresa] of indeks) {
    const d = vidstanM([la, lo], [pla, plo]);
    if (d <= R_TOCHKY_M && (!naikrashcha || d < naikrashcha.d)) naikrashcha = { d, pla, plo, i, adresa };
  }
  if (!naikrashcha) return null;
  const spravy = await chytatyJson(env, `karta/${m.versiia}/spravy/${kl}.json`);
  const ryadky = (spravy && spravy[naikrashcha.i]) || [];
  const podii = ryadky.map((r) => ({
    data: r[1], stattia: (m.kategorii || [])[r[0]] ?? null, opys: r[5] || '',
    // посилання на рішення (AGENTS.md, розд. 7): клітинка зберігає «тека + відбиток» файла ЄДРСР
    rishennia: (r[4] || []).map((ref) => `https://od.reyestr.court.gov.ua/files/${ref.slice(0, 2)}/${ref.slice(2)}.rtf`),
  }));
  return { adresa: naikrashcha.adresa, la: naikrashcha.pla, lo: naikrashcha.plo, versiia: m.versiia, podii };
}

const MAKS_STEZHU = 50;                 // адрес «Стежу» на людину — запобіжник від скрипта, не обмеження для людини

/** «Стежу» з картки адреси (ZAVDANNYA-151): ті самі таблиця й пошук будинку, що в кабінеті (index.js, diiaKabinetu). */
async function stezhu(request, env, url, ja) {
  const spysok = async () => L.vsi(env, 'SELECT budynok, adresa FROM stezhu WHERE korystuvach_id = ? ORDER BY stvoreno', ja.id);
  const h = { ...PRYVATNO, 'cache-control': 'private, no-store' };
  if (request.method === 'GET') return Response.json({ adresy: await spysok() }, { headers: h });
  // запис — лише з нашого сайту (як форми кабінету): чужа сторінка не додасть адрес у чужий кабінет
  const o = request.headers.get('origin');
  if (!o || o !== new URL(env.ADRESA_SAITU || url.origin).origin) return Response.json({ pomylka: 'origin' }, { status: 403, headers: h });
  let f = {};
  try { f = await request.json(); } catch { f = {}; }
  if (f.dia === 'prybraty') {
    await L.zrobyty(env, 'DELETE FROM stezhu WHERE korystuvach_id = ? AND budynok = ?', ja.id, String(f.budynok || ''));
    return Response.json({ ok: true, adresy: await spysok() }, { headers: h });
  }
  if (f.dia !== 'dodaty') return Response.json({ pomylka: 'dia' }, { status: 400, headers: h });
  const z = await L.znaityBudynok(env, url, String(f.adresa || '').slice(0, 200));
  if (!z.budynok) return Response.json({ ok: false, chomu: L.chomuNeZnaideno(z) }, { status: 404, headers: h });
  const vzhe = await spysok();
  if (!vzhe.some((x) => x.budynok === z.budynok) && vzhe.length >= MAKS_STEZHU) {
    return Response.json({ ok: false, chomu: `У «Стежу» вже ${MAKS_STEZHU} адрес — приберіть зайві в кабінеті.` }, { status: 409, headers: h });
  }
  await L.zrobyty(env, 'INSERT OR IGNORE INTO stezhu (korystuvach_id, budynok, adresa, stvoreno) VALUES (?, ?, ?, ?)', ja.id, z.budynok, z.adresa, L.teper(env));
  return Response.json({ ok: true, budynok: z.budynok, adresa: z.adresa, adresy: await spysok() }, { headers: h });
}

const dlyaPidpysnykiv = () => S.povidomlennia('Карта — для підписників',
  'Адреси й описи подій на карті — у підписці. Оформіть її або увійдіть тією поштою, на яку оформили.', 403,
  `<p><a class="knopka" href="/oplata/?tovar=pidpyska">Оформити підписку</a> <a href="/kabinet/">Кабінет</a></p>`);

/** Відповідь на /pidpysnyk/… або null (не наша адреса чи немає сховища KARTA — тоді звичайний сайт). */
export async function karta(request, env, url, ja) {
  const s = url.pathname;
  if (!(s === KOREN.slice(0, -1) || s.startsWith(KOREN))) return null;
  if (!env.KARTA) return null;                         // сховище карти не прив'язано — карти підписника ще немає
  const zapysStezhu = request.method === 'POST' && s === `${KOREN}api/stezhu`;
  if (request.method !== 'GET' && request.method !== 'HEAD' && !zapysStezhu) return new Response('ні', { status: 405 });
  if (s === KOREN.slice(0, -1)) return Response.redirect(new URL(KOREN, url).toString(), 301);
  if (!ja) return Response.redirect(new URL('/kabinet/', url).toString(), 303);
  if (!(await maieDostup(env, ja))) return dlyaPidpysnykiv();

  const shliakh = s.slice(KOREN.length) || 'index.html';
  if (shliakh === 'api/stezhu') return stezhu(request, env, url, ja);
  if (shliakh === 'api/podii') {
    const la = Number(url.searchParams.get('la')), lo = Number(url.searchParams.get('lo'));
    if (!Number.isFinite(la) || !Number.isFinite(lo) || Math.abs(la) > 90 || Math.abs(lo) > 180) {
      return Response.json({ pomylka: 'la, lo' }, { status: 400, headers: PRYVATNO });
    }
    const v = await podiiAdresy(env, la, lo);
    return Response.json(v || { adresa: null, podii: [] }, { status: v ? 200 : 404, headers: { ...PRYVATNO, 'cache-control': 'private, no-store' } });
  }
  if (!bezpechnyiShliakh(shliakh)) return S.nemaie();
  const m = await potochna(env);
  if (!m) return S.povidomlennia('Карта готується', 'Карту підписника ще не викладено. Спробуйте трохи згодом.', 503);
  const o = await env.KARTA.get(`karta/${m.versiia}/${shliakh}`);
  if (!o) return S.nemaie();
  const typ = TYPY[shliakh.split('.').pop()] || 'application/octet-stream';
  // Файли з відбитком у назві (dani/meta.<хеш>.json) не міняються — браузер може тримати їх довше; решта — 5 хвилин.
  const dovgo = /\.[0-9a-f]{10}\.json$/.test(shliakh) || shliakh.startsWith('vendor/') || shliakh.startsWith('shryfty/');
  return new Response(request.method === 'HEAD' ? null : o.body, {
    headers: { ...PRYVATNO, 'content-type': typ, ...(dovgo ? { 'cache-control': 'private, max-age=86400' } : {}) },
  });
}
