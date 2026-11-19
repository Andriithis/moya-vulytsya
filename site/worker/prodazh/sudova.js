// «Судова практика» на сервері продажу (ZAVDANNYA-135; MV-122; docs/SUDOVA-PRAKTYKA-PRODUKT.md).
//
//  Довідка людині (spdovidka):  /oplata/?tovar=spdovidka&stattia=kupap-130 → вибір суду й частини → оплата →
//    черга D1 (rezhym 'sp', parametry) → видавач (dani-edrsr/src/sp_dovidka.py) → R2 → лист. Той самий шлях, що й довідка
//    про будинок; будинку немає.
//  Підписка юристу (spyurist, щомісяця):  /pidpysnyk/praktyka/ — усі статті й суди: фільтри (стаття, суд, частина, роки),
//    таблиці по судах і роках, вивантаження CSV (до VYVANTAZHEN_NA_DEN на добу), 3 довідки «стаття × суд» на місяць.
//
// Що можна вибрати — /sudova-praktyka/dovidnyk.json сайту (статті, суди, частини — без жодного числа; пише збирач сайту).
// Числа для юриста — лише в приватному сховищі R2 (прив'язка DOVIDKY): praktyka/potochna.json → { versiia },
// praktyka/<versiia>/<kodeks>-<nomer>.json — стаття з рядками зведення (site/prodazh/praktyka_r2.py). Імен суддів немає ніде.
import * as L from './logika.js';
import * as S from './storinky.js';
import TS from './tsiny.js';

const e = S.e;
const NBSP = '\u00a0';
export const KOREN = '/pidpysnyk/praktyka/';
export const VYVANTAZHEN_NA_DEN = 50;
const MIN_N = 20;
const SLUG = /^(kupap|kk)-\d{1,4}(?:-\d{1,2})?$/;
const SUD = /^[\p{L}\p{M}'’ʼ -]{2,60}$/u;
const CHASTYNA = /^\d{1,2}$/;
const ZASTEREZHENNIA = 'Це статистика минулих рішень, а не юридична допомога і не відповідь, чим закінчиться конкретна справа.';

// ---------------------------------------------------------------- довідник статей (публічний файл сайту)

let keshDovidnyka = null;
export async function dovidnyk(env, url) {
  const t = Date.now();
  if (keshDovidnyka && keshDovidnyka.do_ > t && keshDovidnyka.env === env) return keshDovidnyka.d;
  let d = null;
  try {
    const r = await env.ASSETS.fetch(new Request(new URL('/sudova-praktyka/dovidnyk.json', url)));
    if (r && r.ok) d = await r.json();
  } catch { d = null; }
  keshDovidnyka = { do_: t + 300_000, d, env };
  return d;
}

/** Параметри з форми → { parametry, opys } лише якщо стаття, суд і частина є в довіднику; інакше null. */
export async function perevirytyParametry(env, url, { stattia, sud, chastyna }) {
  const d = await dovidnyk(env, url);
  const slug = String(stattia ?? '');
  if (!d || !SLUG.test(slug) || !d.statti[slug]) return null;
  const st = d.statti[slug];
  const s = String(sud ?? '').trim(), ch = String(chastyna ?? '').trim();
  if (s && (!SUD.test(s) || !st.sudy.includes(s))) return null;
  if (ch && (!CHASTYNA.test(ch) || !st.chastyny.includes(ch))) return null;
  const parametry = { stattia: st.stattia, sud: s, chastyna: ch };
  const [nomer, kodeks] = st.stattia.replace(/^ст\.\s*/, '').split(' ');
  const opys = `ст.${NBSP}${nomer}${ch ? ` ч.${NBSP}${ch}` : ''} ${kodeks} — ${s ? `${s} районний суд` : 'усі суди міста'}`;
  return { parametry, opys, slug };
}

// ---------------------------------------------------------------- форма замовлення довідки

function vybir(nazva, id, opts, vybrano, porozhnie) {
  return `<label for="${id}">${e(nazva)}</label><select id="${id}" name="${id}">`
    + (porozhnie ? `<option value="">${e(porozhnie)}</option>` : '')
    + opts.map(([v, n]) => `<option value="${e(v)}"${v === vybrano ? ' selected' : ''}>${e(n)}</option>`).join('') + '</select>';
}

/** Крок 1 — стаття (без скриптів: вибір статті перезавантажує сторінку), крок 2 — суд, частина, пошта, оплата. */
export function formaDovidky({ d, slug, sud = '', chastyna = '', pomylka = '', kabinet = false, zalyshok = null }) {
  const nazva = TS.nazvy.spdovidka;
  if (!d) return S.povidomlennia('Не вдалося', 'Довідник статей тимчасово недоступний. Спробуйте за хвилину.', 503);
  const statti = Object.entries(d.statti).map(([k, s]) => [k, `${s.stattia} — ${s.nazva}`]);
  const st = d.statti[slug];
  const krok1 = `<form class="forma" method="get" action="${kabinet ? `${KOREN}dovidka/` : '/oplata/'}">
${kabinet ? '' : '<input type="hidden" name="tovar" value="spdovidka">'}
${vybir('Стаття — з протоколу чи обвинувального акта', 'stattia', statti, slug, st ? '' : 'оберіть статтю')}
<button class="knopka" type="submit">${st ? 'Змінити статтю' : 'Далі'}</button></form>`;
  if (!st) {
    return S.storinka(`${nazva}`, `<section class="zaholovok"><span class="mitka">Судова практика</span><h1>${e(nazva)}</h1>
<p class="tsina">${S.tsina('spdovidka')}</p><p>Як закінчувались такі справи у вашому суді за 3 роки, поруч з усім містом.</p></section>
<section class="rozdil">${krok1}<p class="prymitka">Не знаєте статтю? <a href="/sudova-praktyka/#poshuk">Знайти за словами</a>.</p></section>`);
  }
  const sudy = st.sudy.map((s) => [s, `${s} районний суд`]);
  const chastyny = st.chastyny.map((c) => [c, `частина ${c}`]);
  const dii = kabinet
    ? `<button class="knopka knopka--holovna" type="submit">Отримати довідку${zalyshok !== null ? ` (лишилось цього місяця: ${zalyshok})` : ''}</button>`
    : `<label for="poshta">Пошта — на неї прийде посилання на довідку</label>
<input id="poshta" name="poshta" type="email" autocomplete="email" required maxlength="254" placeholder="name@poshta.ua">
<label class="pravyla"><input type="checkbox" name="zghoda" value="tak" required> Погоджуюсь з <a href="/zahlushka/oferta.html">офертою</a> і <a href="/zahlushka/polityka.html">політикою конфіденційності</a></label>
<label class="pravyla"><input type="checkbox" name="ne_dopomoga" value="tak" required> Розумію: це статистика минулих рішень, а не юридична допомога</label>
${S.GALOCHKA_ODRAZU}
<button class="knopka knopka--holovna" type="submit">Перейти до оплати — ${S.tsina('spdovidka')}</button>`;
  return S.storinka(`${nazva} — ${st.stattia}`, `<section class="zaholovok"><span class="mitka">Судова практика</span><h1>${e(nazva)}</h1>
<p><b>${e(st.stattia)}</b> — ${e(st.nazva)}</p>${kabinet ? '' : `<p class="tsina">${S.tsina('spdovidka')}</p>`}</section>
<section class="rozdil">${krok1}</section>
<section class="rozdil"><form class="forma" method="post" action="${kabinet ? `${KOREN}dovidka` : '/api/zamovlennia'}">
<input type="hidden" name="tovar" value="spdovidka"><input type="hidden" name="stattia" value="${e(slug)}">
${vybir('Суд, де розглядають справу', 'sud', sudy, sud, 'не знаю — усі суди міста')}
${vybir('Частина статті', 'chastyna', chastyny, chastyna, 'не знаю — усі частини')}
${pomylka ? `<p class="pomylka" role="alert">${e(pomylka)}</p>` : ''}
${dii}</form>
<div class="kartka"><p><b>Що буде в довідці:</b> скільки таких справ було за 3 роки у вибраному суді й частині; чим закінчувались
(поруч — усі суди міста); які покарання й разом з чим; скільки часу від події до рішення (де дата точна); як змінювалось за
роками; до 12 останніх схожих рішень з посиланням на оригінал у реєстрі. Без імен суддів.</p>
<p class="prymitka">${e(ZASTEREZHENNIA)} Імені, обставин і номера своєї справи не вводьте — вони не потрібні.</p></div></section>`);
}

// ---------------------------------------------------------------- кабінет юриста: дані з R2

let keshPotochnoi = null;
async function potochna(env) {
  const t = Date.now();
  if (keshPotochnoi && keshPotochnoi.do_ > t && keshPotochnoi.env === env) return keshPotochnoi.m;
  const o = await env.DOVIDKY.get('praktyka/potochna.json');
  const m = o ? JSON.parse(await o.text()) : null;
  keshPotochnoi = { do_: t + 60_000, m, env };
  return m;
}

const keshStatei = new Map();
async function dani(env, slug) {
  const m = await potochna(env);
  if (!m || !SLUG.test(slug)) return null;
  const k = `praktyka/${m.versiia}/${slug}.json`;
  if (keshStatei.has(k) && keshStatei.get(k).env === env) return keshStatei.get(k).d;
  const o = await env.DOVIDKY.get(k);
  const d = o ? { ...JSON.parse(await o.text()), versiia: m.versiia } : null;
  if (keshStatei.size > 30) keshStatei.clear();
  keshStatei.set(k, { d, env });
  return d;
}

/** Активна підписка юриста (і скасована — до кінця оплаченого періоду). */
export async function pidpyskaYurysta(env, ja) {
  if (!ja) return null;
  return (await L.stanPidpysok(env, ja.id)).find((p) => p.diie && p.tovar === 'spyurist') || null;
}

const vids = (x) => (x >= 0.995 && x < 1 ? `>99${NBSP}%` : x >= 0.01 || x === 0 ? `${Math.round(x * 100)}${NBSP}%` : `<1${NBSP}%`);
const chyslo = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);

/** Рядки [суд, рік, частина, категорія, поєднання, справ, {днів: справ}] за фільтром → підсумок по групі. */
export function pidsumok(st, ryadky) {
  const kat = {}, dni = [];
  let n = 0, pokarano = 0;
  for (const [, , , k, , k_n, d] of ryadky) {
    n += k_n; kat[k] = (kat[k] || 0) + k_n;
    if (st.pokarano.includes(k)) pokarano += k_n;
    for (const [dd, kk] of Object.entries(d || {})) dni.push([Number(dd), kk]);
  }
  let polovyna = null;
  const vsogo = dni.reduce((s, x) => s + x[1], 0);
  if (st.strok && vsogo >= MIN_N) {
    dni.sort((a, b) => a[0] - b[0]);
    let c = 0;
    for (const [d, k] of dni) { c += k; if (c * 2 >= vsogo) { polovyna = d; break; } }
  }
  return { n, kat, pokarano, polovyna };
}

export function filtr(ryadky, f) {
  return ryadky.filter((r) => (!f.sud || r[0] === f.sud) && (!f.chastyna || r[2] === f.chastyna)
    && (!f.z || r[1] >= f.z) && (!f.do_ || r[1] <= f.do_));
}

function chytatyFiltr(url, st) {
  const q = url.searchParams;
  const roky = [...new Set(st.ryadky.map((r) => r[1]))].sort();
  const f = { sud: q.get('sud') || '', chastyna: q.get('chastyna') || '', z: q.get('z') || '', do_: q.get('do') || '' };
  if (!st.ryadky.some((r) => r[0] === f.sud)) f.sud = '';
  if (!st.ryadky.some((r) => r[2] === f.chastyna)) f.chastyna = '';
  if (!roky.includes(f.z)) f.z = '';
  if (!roky.includes(f.do_)) f.do_ = '';
  return { f, roky };
}

function dniv(d) {
  if (d === null) return '—';
  return d < 60 ? `${d}${NBSP}дн.` : `${(d / 30.44).toFixed(1).replace('.', ',')}${NBSP}міс.`;
}

/** Таблиця для юриста: по судах і по роках; частки — лише на ≥ 20 справах. Повертає [{ nazva, ryady }] — і для HTML, і для CSV. */
export function tablytsi(st, f) {
  const ryadky = filtr(st.ryadky, f);
  const golovni = Object.entries(pidsumok(st, ryadky).kat).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([k]) => k);
  const shapka = ['Справ', st.kodeks === 'КК' ? 'Обвинувальний вирок' : 'Стягнення', ...golovni].concat(st.strok ? ['Половина справ — до'] : []);
  const ryad = (nazva, rr) => {
    const p = pidsumok(st, rr);
    const malo = p.n < MIN_N;
    return [nazva, p.n, malo ? null : p.pokarano / p.n, ...golovni.map((k) => (malo ? null : (p.kat[k] || 0) / p.n))]
      .concat(st.strok ? [malo ? null : p.polovyna] : []);
  };
  const sudy = [...new Set(ryadky.map((r) => r[0]))].sort((a, b) => a.localeCompare(b, 'uk'));
  const roky = [...new Set(ryadky.map((r) => r[1]))].sort();
  return {
    shapka, golovni,
    razom: ryad('Разом за фільтром', ryadky),
    sudy: sudy.map((s) => ryad(s, ryadky.filter((r) => r[0] === s))),
    roky: roky.map((r) => ryad(r, ryadky.filter((x) => x[1] === r))),
  };
}

function tablytsiaHtml(t, pershyi, ryady) {
  const kom = (v, i) => {
    if (i === 0) return `<td class="ch">${chyslo(v)}</td>`;
    if (v === null) return '<td class="sp-malo">замало</td>';
    if (t.shapka[i] === 'Половина справ — до') return `<td class="ch">${dniv(v)}</td>`;
    return `<td class="ch">${vids(v)}</td>`;
  };
  return `<div class="sp-tablytsia-ramka"><table class="sp-tablytsia"><thead><tr><th scope="col">${e(pershyi)}</th>${t.shapka.map((h) => `<th scope="col">${e(h)}</th>`).join('')}</tr></thead>
<tbody>${ryady.map(([n, ...x]) => `<tr><th scope="row">${e(n)}</th>${x.map(kom).join('')}</tr>`).join('')}</tbody></table></div>`;
}

export function csv(st, f, t) {
  const kom = (v) => { const s = v === null ? '' : typeof v === 'number' && !Number.isInteger(v) ? v.toFixed(4) : String(v); return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const ryadky = [['розріз', 'назва', ...t.shapka.map((h, i) => (i === 0 || h === 'Половина справ — до' ? h : `${h} (частка)`))]];
  ryadky.push(['разом', ...t.razom]);
  for (const r of t.sudy) ryadky.push(['суд', ...r]);
  for (const r of t.roky) ryadky.push(['рік', ...r]);
  const pro = `# ${st.stattia}${f.chastyna ? ` ч.${f.chastyna}` : ''}; суд: ${f.sud || 'усі'}; роки: ${f.z || 'усі'}–${f.do_ || 'усі'}; дані на ${st.versiia}; частки — від справ з рішенням по суті; менше ${MIN_N} справ — порожньо; «Половина справ — до» — днів від події до рішення. ${ZASTEREZHENNIA}\n`;
  return '﻿' + pro + ryadky.map((r) => r.map(kom).join(';')).join('\n') + '\n';
}

async function lichylnykVyvantazhen(env, korystuvach_id) {
  const den = new Date(L.teper(env) * 1000).toISOString().slice(0, 10);
  const r = await L.odyn(env, 'SELECT n FROM sp_vyvantazhennia WHERE korystuvach_id = ? AND den = ?', korystuvach_id, den);
  return { den, n: r ? r.n : 0 };
}

/** /pidpysnyk/praktyka/… → Response або null (не наша адреса). ja — з сесії. */
export async function praktyka(request, env, url, ja) {
  const s = url.pathname;
  if (!(s === KOREN.slice(0, -1) || s.startsWith(KOREN))) return null;
  if (!ja) return new Response(null, { status: 303, headers: { location: new URL('/kabinet/', url).toString() } });
  const p = await pidpyskaYurysta(env, ja);
  if (!p) {
    return S.povidomlennia('Практика — для підписників', `Таблиці по судах, фільтри й вивантаження — у підписці юриста (${S.tsina('spyurist')}).`, 403,
      `<div class="diyi">${(TS.prodaietsia || []).includes('spyurist') ? `<a class="knopka knopka--holovna" href="/oplata/?tovar=spyurist">Оформити підписку</a>` : '<a class="knopka knopka--holovna" href="/oplata/?tovar=spyurist">Скоро — залиште пошту</a>'}<a class="knopka" href="/sudova-praktyka/">Безкоштовні сторінки статей</a></div>`);
  }
  const d = await dovidnyk(env, url);
  if (s === `${KOREN}dovidka/` && request.method === 'GET') {
    return formaDovidky({ d, slug: url.searchParams.get('stattia') || '', kabinet: true, zalyshok: p.zalyshok });
  }
  if (s === `${KOREN}dovidka` && request.method === 'POST') return null;      // обробляє index.js (потрібна перевірка походження)
  const slug = url.searchParams.get('stattia') || (d ? Object.keys(d.statti)[0] : '');
  const st = await dani(env, slug);
  if (!st) return S.povidomlennia('Дані ще не завантажено', 'Таблиці практики з’являться після завантаження даних. Спробуйте пізніше.', 503);
  const { f, roky } = chytatyFiltr(url, st);
  const t = tablytsi(st, f);
  if (s === `${KOREN}csv`) {
    const l = await lichylnykVyvantazhen(env, ja.id);
    if (l.n >= VYVANTAZHEN_NA_DEN) return S.povidomlennia('Ліміт вивантажень', `На добу — до ${VYVANTAZHEN_NA_DEN} вивантажень. Завтра можна знову.`, 429);
    await L.zrobyty(env, `INSERT INTO sp_vyvantazhennia (korystuvach_id, den, n) VALUES (?, ?, 1)
      ON CONFLICT (korystuvach_id, den) DO UPDATE SET n = n + 1`, ja.id, l.den);
    return new Response(csv(st, f, t), { headers: { 'content-type': 'text/csv; charset=utf-8', 'cache-control': 'private, no-store',
      'content-disposition': `attachment; filename="praktyka-${slug}${f.sud ? '-sud' : ''}.csv"`, 'x-robots-tag': 'noindex' } });
  }
  if (s !== KOREN) return S.nemaie();
  const opts = (xs, v) => xs.map(([k, n]) => `<option value="${e(k)}"${k === v ? ' selected' : ''}>${e(n)}</option>`).join('');
  const statti = d ? Object.entries(d.statti).map(([k, x]) => [k, `${x.stattia} — ${x.nazva}`]) : [[slug, st.stattia]];
  const sudy = [...new Set(st.ryadky.map((r) => r[0]))].sort((a, b) => a.localeCompare(b, 'uk')).map((x) => [x, x]);
  const chastyny = [...new Set(st.ryadky.map((r) => r[2]).filter(Boolean))].sort((a, b) => a - b).map((x) => [x, `ч. ${x}`]);
  const qs = new URLSearchParams({ stattia: slug, ...(f.sud && { sud: f.sud }), ...(f.chastyna && { chastyna: f.chastyna }), ...(f.z && { z: f.z }), ...(f.do_ && { do: f.do_ }) });
  const dovidka = new URLSearchParams({ stattia: slug, ...(f.sud && { sud: f.sud }), ...(f.chastyna && { chastyna: f.chastyna }) });
  return S.storinka(`Практика — ${st.stattia}`, `<section class="zaholovok"><span class="mitka">Підписка юриста</span>
<h1>${e(st.stattia)} — ${e(st.nazva)}</h1><p class="prymitka">Дані на ${e(st.versiia)}. Імен суддів немає; суди між собою не оцінюємо: різні суди отримують різні справи.</p></section>
<section class="rozdil"><form class="sp-filtry" method="get" action="${KOREN}">
<label>Стаття<select name="stattia">${opts(statti, slug)}</select></label>
<label>Суд<select name="sud"><option value="">усі суди</option>${opts(sudy, f.sud)}</select></label>
<label>Частина<select name="chastyna"><option value="">усі частини</option>${opts(chastyny, f.chastyna)}</select></label>
<label>З року<select name="z"><option value="">усі</option>${opts(roky.map((r) => [r, r]), f.z)}</select></label>
<label>До року<select name="do"><option value="">усі</option>${opts(roky.map((r) => [r, r]), f.do_)}</select></label>
<button class="knopka knopka--holovna" type="submit">Показати</button></form></section>
<section class="rozdil"><h2>Разом: ${chyslo(t.razom[1])} справ</h2>
<div class="diyi"><a class="knopka" href="${KOREN}csv?${e(qs.toString())}">Вивантажити CSV</a>
<a class="knopka" href="${KOREN}dovidka/?${e(dovidka.toString())}">Довідка для клієнта за цим вибором (лишилось: ${p.zalyshok})</a></div>
<h3>По судах</h3>${tablytsiaHtml(t, 'Суд', [t.razom, ...t.sudy])}
<h3>По роках</h3>${tablytsiaHtml(t, 'Рік', t.roky)}
<p class="prymitka">Частки — від справ з рішенням по суті в першій інстанції; менше ${MIN_N} справ — «замало». Апеляцію не враховано.${st.kodeks === 'КК' ? ' Справи КК, закриті ухвалою, ще не входять — частки серед вироків.' : ''}
Старші роки неповні (тексти рішень ще докачуються). Вивантажень на добу — до ${VYVANTAZHEN_NA_DEN}. ${e(ZASTEREZHENNIA)}</p></section>`);
}
