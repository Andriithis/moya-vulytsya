// «Для бізнесу» (ZAVDANNYA-157; MV-3, MV-92): база в користування за договором-ліцензією — копія за особистим посиланням.
//
// Як це працює:
//   1) компанія лишає запит на сторінці /biznes/ (POST /api/forma/biznes → таблиця biznes_zapyty, лист партнеру);
//   2) партнер (Микита) укладає договір і заводить клієнта: POST /api/admin/biznes/klient (site/prodazh/biznes_klienty.py);
//   3) щомісяця — копія з нового випуску окремо на клієнта (dani-edrsr/src/kopiia_biznesu.py) у приватне сховище R2
//      (прив'язка BIZNES, ключі biznes/<клієнт>/<версія>/…, останнім — biznes/<клієнт>/potochna.json; site/prodazh/biznes_r2.py);
//   4) партнер видає посилання на N днів: POST /api/admin/biznes/posylannia → https://<сайт>/kopiia/<ключ>/;
//      ключ показується один раз, у базі — лише його хеш;
//   5) вимкнення: POST /api/admin/biznes/vymknuty — клієнт і всі його посилання перестають діяти одразу.
//
// Чому власні посилання через скрипт, а не «підписані посилання» самого R2 (S3): ті не відкликати до кінця строку (до 7 днів)
// і для них потрібен ще один ключ доступу до сховища; тут вимкнення діє миттєво, кожне завантаження записано, а строк і
// ліміт завантажень перевіряє сервер (docs/BIZNES-DOSTUP.md, розд. 3).
//
//   GET  /kopiia/<ключ>/            сторінка клієнта: що в копії, файли, до якого дня діє посилання
//   GET  /kopiia/<ключ>/<файл>      файл копії (baza.db, csv.zip, OPYS.md, SHA256SUMS) — з лічильником завантажень
// Невідомий, прострочений чи вимкнений ключ — однакова відповідь «Посилання не діє» (не підказуємо, які ключі були).
import * as L from './logika.js';
import * as S from './storinky.js';
import { vypadkovyi, sha256 } from './bezpeka.js';
import { nadislaty } from './poshta.js';
import { csvKlityna } from './formy.js';

export const KOREN = '/kopiia/';
export const FAJLY = { 'baza.db': ['application/vnd.sqlite3', 'База SQLite — усі таблиці'],
  'csv.zip': ['application/zip', 'Ті самі таблиці у форматі CSV (Excel, Google Таблиці)'],
  'OPYS.md': ['text/markdown; charset=utf-8', 'Опис полів і умови коротко'],
  'SHA256SUMS': ['text/plain; charset=utf-8', 'Контрольні суми файлів'] };
export const MAKS_DNIV = 31;                 // посилання — не довше за місяць; на рік — нове щомісяця з новою копією
export const ZAVANTAZHEN_ZA_ZAMOVCHUVANNIAM = 20;
const NAHADATY_ZA_DNIV = 14;                 // лист партнеру: строк договору клієнта спливає
const ZAPYTIV_NA_KONTAKT_ZA_DOBU = 3;
export const META = { nerukhomist: 'нерухомість (забудова, агенція, оцінка)', strakhuvannia: 'страхування чи банк',
  doslidzhennia: 'дослідження чи медіа', mista: 'громада, міська служба', inshe: 'інше' };
export const STROKY = { misiats: 'місяць', rik: 'рік', ne_znaiu: 'ще не знаю' };
const TARYFY = ['misiats', 'rik'];
const KOD = /^k(\d{1,6})$/;
const DEN = 86400;

const tekst = (v, n) => { const t = String(v ?? '').trim().replace(/[\u0000-\u0008\u000b-\u001f]/g, ''); return t ? t.slice(0, n) : null; };
export const kodKlienta = (id) => `k${id}`;
const idKlienta = (kod) => { const m = String(kod ?? '').match(KOD); return m ? Number(m[1]) : null; };
const adresaSaitu = (env, url) => (env.ADRESA_SAITU || new URL(url).origin).replace(/\/$/, '');
const dataVDen = (s) => { const m = String(s ?? '').match(/^(\d{4})-(\d{2})-(\d{2})$/); return m ? Math.floor(Date.UTC(+m[1], +m[2] - 1, +m[3], 23, 59, 59) / 1000) : null; };

// ---------------------------------------------------------------- запит зі сторінки /biznes/

/** POST /api/forma/biznes (JSON). Перевірки — ті самі, що в site/sait/biznes.js. Повертає Response. */
export async function zapyt(request, env) {
  let d;
  try { d = await request.json(); } catch { return new Response('ne json', { status: 400 }); }
  if (!d || typeof d !== 'object') return new Response('ne json', { status: 400 });
  if (d.zghoda !== true) return new Response('zghoda', { status: 400 });
  const kompaniia = tekst(d.kompaniia, 160), kontakt = tekst(d.kontakt, 160);
  if (!kompaniia || !kontakt) return new Response('polia', { status: 400 });
  if (!META[d.meta] || !STROKY[d.strok]) return new Response('polia', { status: 400 });
  const t = L.teper(env);
  const n = (await L.odyn(env, 'SELECT COUNT(*) AS n FROM biznes_zapyty WHERE kontakt = ? AND stvoreno > ?', kontakt, t - DEN)).n;
  if (n >= ZAPYTIV_NA_KONTAKT_ZA_DOBU) return new Response(null, { status: 201 });     // мовчки: захист від засмічення
  const kanal = /^[a-z0-9-]{1,40}$/.test(String(d.kanal ?? '')) ? d.kanal : 'priamo';
  await L.zrobyty(env, `INSERT INTO biznes_zapyty (kompaniia, kontakt, meta, terytoriia, strok, komentar, kanal, stvoreno)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)`, kompaniia, kontakt, d.meta, tekst(d.terytoriia, 200), d.strok,
  tekst(d.komentar, 2000), kanal, t);
  if (env.POSHTA_PARTNERA) {
    try {
      await nadislaty(env, { komu: env.POSHTA_PARTNERA, tema: 'Новий запит «Для бізнесу»',
        tekst: `Компанія лишила запит на доступ до бази (${META[d.meta]}, строк: ${STROKY[d.strok]}).\n` +
          'Відповісти — протягом 2 робочих днів. Контакт і подробиці — у списку запитів (docs/BIZNES-DOSTUP.md, розд. 5).' });
    } catch (err) { console.log(`бізнес: лист партнеру не пішов: ${err.message}`); }
  }
  return new Response(null, { status: 201 });
}

// ---------------------------------------------------------------- для партнера (Authorization: Bearer ADMIN_KLIUCH)

async function json(request) {
  try { const d = await request.json(); return d && typeof d === 'object' ? d : {}; } catch { return {}; }
}

async function manifest(env, kod) {
  if (!env.BIZNES) return null;
  const o = await env.BIZNES.get(`biznes/${kod}/potochna.json`);
  if (!o) return null;
  try { return JSON.parse(await o.text()); } catch { return null; }
}

/** Клієнт діє: не вимкнений і строк договору не минув. */
const diie = (k, t) => !!k && !k.vymkneno && k.diie_do >= t;

export async function admin(request, env, url, shliakh) {
  const m = request.method;
  const t = L.teper(env);
  if (shliakh === 'klient' && m === 'POST') {
    const d = await json(request);
    const nazva = tekst(d.nazva, 160), kontakt = tekst(d.kontakt, 160), diie_do = dataVDen(d.diie_do);
    if (!nazva || !kontakt) return Response.json({ pomylka: 'потрібні nazva і kontakt' }, { status: 400 });
    if (!TARYFY.includes(d.tarif)) return Response.json({ pomylka: 'tarif — misiats або rik' }, { status: 400 });
    if (!diie_do || diie_do < t) return Response.json({ pomylka: 'diie_do — дата кінця договору РРРР-ММ-ДД, не в минулому' }, { status: 400 });
    await L.zrobyty(env, `INSERT INTO biznes_klienty (nazva, kontakt, dohovir, tarif, diie_do, stvoreno) VALUES (?, ?, ?, ?, ?, ?)`,
      nazva, kontakt, tekst(d.dohovir, 80), d.tarif, diie_do, t);
    const k = await L.odyn(env, 'SELECT id FROM biznes_klienty WHERE rowid = last_insert_rowid()');
    return Response.json({ klient: kodKlienta(k.id) }, { status: 201 });
  }
  let r = shliakh.match(/^klient\/(k\d{1,6})$/);
  if (r && m === 'POST') {
    // продовжити договір (новий строк, тариф, номер договору); вмикає знову лише явне uvimknuty: true
    const id = idKlienta(r[1]);
    const k = await L.odyn(env, 'SELECT * FROM biznes_klienty WHERE id = ?', id);
    if (!k) return Response.json({ pomylka: 'такого клієнта немає' }, { status: 404 });
    const d = await json(request);
    const diie_do = d.diie_do ? dataVDen(d.diie_do) : k.diie_do;
    if (!diie_do) return Response.json({ pomylka: 'diie_do — РРРР-ММ-ДД' }, { status: 400 });
    const tarif = d.tarif ? (TARYFY.includes(d.tarif) ? d.tarif : null) : k.tarif;
    if (!tarif) return Response.json({ pomylka: 'tarif — misiats або rik' }, { status: 400 });
    await L.zrobyty(env, `UPDATE biznes_klienty SET diie_do = ?, tarif = ?, dohovir = ?, nahadano = NULL,
                          vymkneno = CASE WHEN ? THEN NULL ELSE vymkneno END, prychyna = CASE WHEN ? THEN NULL ELSE prychyna END WHERE id = ?`,
    diie_do, tarif, tekst(d.dohovir, 80) ?? k.dohovir, d.uvimknuty === true ? 1 : 0, d.uvimknuty === true ? 1 : 0, id);
    return Response.json({ klient: r[1], diie_do });
  }
  if (shliakh === 'posylannia' && m === 'POST') {
    const d = await json(request);
    const id = idKlienta(d.klient);
    const k = id && await L.odyn(env, 'SELECT * FROM biznes_klienty WHERE id = ?', id);
    if (!k) return Response.json({ pomylka: 'такого клієнта немає' }, { status: 404 });
    if (!diie(k, t)) return Response.json({ pomylka: 'клієнта вимкнено або строк договору минув — спершу продовжте' }, { status: 409 });
    const dniv = Number.isInteger(d.dniv) ? d.dniv : 7;
    if (dniv < 1 || dniv > MAKS_DNIV) return Response.json({ pomylka: `dniv — від 1 до ${MAKS_DNIV}` }, { status: 400 });
    const maks = Number.isInteger(d.maks) ? d.maks : ZAVANTAZHEN_ZA_ZAMOVCHUVANNIAM;
    if (maks < 1 || maks > 200) return Response.json({ pomylka: 'maks — від 1 до 200 завантажень' }, { status: 400 });
    const man = await manifest(env, kodKlienta(id));
    if (!man) return Response.json({ pomylka: 'копії для клієнта ще немає в сховищі (site/prodazh/biznes_r2.py)' }, { status: 409 });
    const kliuch = vypadkovyi(32);
    const do_ = Math.min(t + dniv * DEN, k.diie_do);                   // не довше за договір
    await L.zrobyty(env, 'INSERT INTO biznes_posylannia (hash, klient_id, do_, maks, stvoreno) VALUES (?, ?, ?, ?, ?)',
      sha256(kliuch), id, do_, maks, t);
    return Response.json({ posylannia: `${adresaSaitu(env, url)}${KOREN}${kliuch}/`, do_, versiia: man.versiia }, { status: 201 });
  }
  if (shliakh === 'vymknuty' && m === 'POST') {
    const d = await json(request);
    const id = idKlienta(d.klient);
    const k = id && await L.odyn(env, 'SELECT * FROM biznes_klienty WHERE id = ?', id);
    if (!k) return Response.json({ pomylka: 'такого клієнта немає' }, { status: 404 });
    const n = (await L.zrobyty(env, 'UPDATE biznes_posylannia SET vymkneno = ? WHERE klient_id = ? AND vymkneno IS NULL', t, id)).meta?.changes ?? 0;
    if (d.lyshe_posylannia !== true) {
      await L.zrobyty(env, 'UPDATE biznes_klienty SET vymkneno = ?, prychyna = ? WHERE id = ?', t, tekst(d.prychyna, 200) || 'вимкнено', id);
    }
    return Response.json({ klient: kodKlienta(id), posylan_vymkneno: n, klienta_vymkneno: d.lyshe_posylannia !== true });
  }
  if (shliakh === 'klienty' && m === 'GET') {
    const ks = await L.vsi(env, `SELECT k.*, (SELECT COUNT(*) FROM biznes_posylannia p WHERE p.klient_id = k.id AND p.vymkneno IS NULL AND p.do_ >= ?) AS posylan_diie,
                                        (SELECT COUNT(*) FROM biznes_zavantazhennia z WHERE z.klient_id = k.id) AS zavantazhen
                                 FROM biznes_klienty k ORDER BY k.id`, t);
    const out = [];
    for (const k of ks) {
      out.push({ klient: kodKlienta(k.id), nazva: k.nazva, kontakt: k.kontakt, dohovir: k.dohovir, tarif: k.tarif,
        diie_do: new Date(k.diie_do * 1000).toISOString().slice(0, 10), diie: diie(k, t), prychyna: k.prychyna,
        posylan_diie: k.posylan_diie, zavantazhen: k.zavantazhen, kopiia: (await manifest(env, kodKlienta(k.id)))?.versiia || null });
    }
    return Response.json({ klienty: out });
  }
  r = shliakh.match(/^(zapyty|zavantazhennia)\.csv$/);
  if (r && m === 'GET') {
    const [sql, nazvy] = r[1] === 'zapyty'
      ? ['SELECT id, kompaniia, kontakt, meta, terytoriia, strok, komentar, kanal, stvoreno FROM biznes_zapyty ORDER BY id',
        ['id', 'kompaniia', 'kontakt', 'meta', 'terytoriia', 'strok', 'komentar', 'kanal', 'stvoreno']]
      : ['SELECT z.id, z.klient_id, z.fail, z.chas, substr(z.posylannia_hash, 1, 8) AS posylannia FROM biznes_zavantazhennia z ORDER BY z.id',
        ['id', 'klient_id', 'fail', 'chas', 'posylannia']];
    const ryadky = await L.vsi(env, sql);
    const csv = '﻿' + [nazvy.join(','), ...ryadky.map((x) => nazvy.map((k) => csvKlityna(x[k])).join(','))].join('\r\n') + '\r\n';
    return new Response(csv, { headers: { 'content-type': 'text/csv; charset=utf-8', 'cache-control': 'no-store',
      'content-disposition': `attachment; filename="biznes-${r[1]}.csv"` } });
  }
  return new Response('ні', { status: 404 });
}

// ---------------------------------------------------------------- сторінка й файли клієнта

const MISIATSI = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня'];
/** «2026-11-08» → «8 листопада 2026» (ZVIT-169: дата людською мовою); не дата — як є. */
const dataSlovamy = (d) => { const m = String(d || '').match(/^(\d{4})-(\d{2})-(\d{2})/); return m ? `${Number(m[3])}\u00a0${MISIATSI[Number(m[2]) - 1]} ${m[1]}` : String(d || ''); };

const PRYVATNO = { 'cache-control': 'private, no-store', 'x-robots-tag': 'noindex, nofollow', 'referrer-policy': 'no-referrer',
  'x-content-type-options': 'nosniff', 'x-frame-options': 'DENY' };

const neDiie = () => {
  const r = S.povidomlennia('Посилання не діє', 'Посилання не діє: строк минув, його вимкнено або в адресі помилка. ' +
    'Напишіть партнеру проєкту — надішле нове.', 404,
    '<div class="diyi"><a class="knopka" href="/zahlushka/pro-nas.html">Як написати партнеру</a></div>', false);
  r.headers.set('referrer-policy', 'no-referrer');
  r.headers.set('x-robots-tag', 'noindex, nofollow');
  return r;
};

async function dijsne(env, kliuch) {
  if (!/^[a-z2-7]{40,60}$/.test(kliuch)) return null;
  const p = await L.odyn(env, `SELECT p.*, k.nazva, k.vymkneno AS k_vymkneno, k.diie_do AS k_diie_do FROM biznes_posylannia p
                              JOIN biznes_klienty k ON k.id = p.klient_id WHERE p.hash = ?`, sha256(kliuch));
  const t = L.teper(env);
  if (!p || p.vymkneno || p.do_ < t || p.k_vymkneno || p.k_diie_do < t) return null;
  return p;
}

const rozmir = (b) => (b >= 1e6 ? `${(b / 1e6).toFixed(1).replace('.', ',')} МБ` : `${Math.max(1, Math.round(b / 1e3))} КБ`);

export async function kopiia(request, env, url) {
  if (request.method !== 'GET' && request.method !== 'HEAD') return new Response('ні', { status: 405 });
  const m = url.pathname.match(/^\/kopiia\/([^/]+)\/([^/]*)$/);
  if (!m || !env.BIZNES) return neDiie();
  const p = await dijsne(env, m[1]);
  if (!p) return neDiie();
  const kod = kodKlienta(p.klient_id);
  const man = await manifest(env, kod);
  if (!man) return neDiie();
  const fail = m[2];
  if (!fail) {
    const zalyshok = Math.max(0, p.maks - p.vykorystano);
    const ryadky = (man.fajly || []).filter((f) => FAJLY[f.imia]).map((f) => `<li><a class="knopka${f.imia === 'csv.zip' ? ' knopka--holovna' : ''}" href="${S.e(f.imia)}" download>${S.e(f.imia)}</a> ${S.e(FAJLY[f.imia][1])} · ${rozmir(f.bait)}</li>`).join('');
    const r = S.storinka('Копія бази для компанії', `<section class="zaholovok"><span class="mitka">Для бізнесу</span>
<h1>Копія бази для «${S.e(p.nazva)}»</h1>
<p>Випуск від ${S.e(dataSlovamy(man.versiia))}. Посилання діє до ${S.data(p.do_)} включно; завантажень лишилось: ${zalyshok}.</p></section>
<section class="rozdil"><h2>Файли</h2><ul class="spysok-fajliv">${ryadky}</ul>
<p class="prymitka">Що в кожному полі й чого в копії немає — у файлі OPYS.md (він є й в архіві CSV).</p></section>
<section class="rozdil"><h2>Умови коротко</h2><div class="kartka"><ul class="spysok-tekst">
<li>Лише для вашої компанії: не перепродавати й не передавати іншим.</li>
<li>Не намагатися впізнати людей і не відновлювати те, що суд приховав.</li>
<li>Події, видалені за зверненням людей, зникають і з вашої копії: замініть попередню копію новою.</li>
<li>Подія — окремий випадок, установлений судом; концентрація подій — статистика, а не оцінка місця й не прогноз.</li>
</ul></div><p class="prymitka">Повністю — у вашому договорі. Посилання особисте: не пересилайте його.</p></section>`, { kabinet: false });
    for (const [k, v] of Object.entries(PRYVATNO)) r.headers.set(k, v);
    return r;
  }
  const f = (man.fajly || []).find((x) => x.imia === fail);
  if (!FAJLY[fail] || !f) return neDiie();
  if (request.method === 'HEAD') return new Response(null, { headers: { ...PRYVATNO, 'content-type': FAJLY[fail][0] } });
  // лічильник — до віддачі файла і одним запитом з умовою: два одночасні завантаження не перевищать ліміт
  const v = await L.zrobyty(env, 'UPDATE biznes_posylannia SET vykorystano = vykorystano + 1 WHERE hash = ? AND vykorystano < maks', p.hash);
  if (!v.meta?.changes) {
    return S.povidomlennia('Завантаження вичерпано', 'За цим посиланням завантажено вже стільки разів, скільки дозволено. ' +
      'Напишіть партнеру проєкту — надішле нове.', 429, '', false);
  }
  const o = await env.BIZNES.get(`biznes/${kod}/${man.versiia}/${fail}`);
  if (!o) return neDiie();
  await L.zrobyty(env, 'INSERT INTO biznes_zavantazhennia (posylannia_hash, klient_id, fail, chas) VALUES (?, ?, ?, ?)',
    p.hash, p.klient_id, fail, L.teper(env));
  const imia = fail === 'OPYS.md' || fail === 'SHA256SUMS' ? fail : `moya-vulytsya-${man.versiia}-${fail}`;
  return new Response(o.body, { headers: { ...PRYVATNO, 'content-type': FAJLY[fail][0],
    'content-disposition': `attachment; filename="${imia}"` } });
}

// ---------------------------------------------------------------- щодня (Cron)

/** Лист партнеру: у клієнта за 14 днів спливає договір (раз на строк) — продовжити або попрощатися. */
export async function nahadaty(env) {
  if (!env.POSHTA_PARTNERA) return 0;
  const t = L.teper(env);
  const ks = await L.vsi(env, `SELECT * FROM biznes_klienty WHERE vymkneno IS NULL AND diie_do BETWEEN ? AND ?
                               AND (nahadano IS NULL OR nahadano != diie_do)`, t, t + NAHADATY_ZA_DNIV * DEN);
  for (const k of ks) {
    try {
      await nadislaty(env, { komu: env.POSHTA_PARTNERA, tema: `«Для бізнесу»: договір ${kodKlienta(k.id)} спливає ${S.data(k.diie_do)}`,
        tekst: `Клієнт ${kodKlienta(k.id)} («${k.nazva}»): доступ до бази діє до ${S.data(k.diie_do)}. Продовжити — ` +
          'site/prodazh/biznes_klienty.py prodovzhyty; інакше після цієї дати посилання перестануть діяти самі.' });
      await L.zrobyty(env, 'UPDATE biznes_klienty SET nahadano = ? WHERE id = ?', k.diie_do, k.id);
    } catch (err) { console.log(`бізнес: нагадування не пішло: ${err.message}`); }
  }
  return ks.length;
}
