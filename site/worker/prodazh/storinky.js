// Сторінки сервера продажу: замовлення, оплата, «дякуємо», кабінет (ZAVDANNYA-99).
// Вигляд — стилі сайту (/sait/sait.css: змінні MV-58, кнопки-клавіші, картки) + кілька правил для форм (/prodazh/prodazh.css).
// Без вбудованих скриптів і стилів: політика безпеки сторінок та сама, що й на сайті.
import TS from './tsiny.js';

export const e = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const NBSP = ' ';
export function tsina(kl) {
  const t = TS.tsiny[kl];
  const s = String(t).replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
  const strok = { pidpyska: ' на місяць', rieltor: ' на місяць', osbb: ' на рік', spyurist: ' на місяць' }[kl] || '';
  return `${s}${NBSP}грн${strok}`;
}

export function data(t) {
  if (!t) return '';
  const d = new Date(t * 1000);
  return `${String(d.getUTCDate()).padStart(2, '0')}.${String(d.getUTCMonth() + 1).padStart(2, '0')}.${d.getUTCFullYear()}`;
}

export const CSP = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; " +
  "form-action 'self' https://www.liqpay.ua; frame-ancestors 'none'; base-uri 'none'";

export function storinka(title, tilo, { status = 200, zaholovky = {}, kabinet = true, css = [] } = {}) {
  const html = `<!doctype html>
<html lang="uk" data-koren="/">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="robots" content="noindex, nofollow">
<title>${e(title)} | Моя вулиця</title>
<script src="/sait/tema.js"></script>
<link rel="stylesheet" href="/sait/sait.css">
<link rel="stylesheet" href="/prodazh/prodazh.css">
${css.map((c) => `<link rel="stylesheet" href="${e(c)}">`).join('')}
</head>
<body>
<header class="shapka"><div class="shapka__vnutri"><a class="lohotyp" href="/"><span class="lohotyp__nazva">Моя вулиця</span></a>
<nav class="menyu" aria-label="Розділи"><a href="/miy-budynok/">Мій будинок</a>${kabinet ? '<a href="/kabinet/">Кабінет</a>' : '<a href="/karta/">Карта</a>'}</nav></div></header>
<main class="storinka">
${tilo}
</main>
<footer class="pidval"><div class="pidval__vnutri">
<p>Платежі, договори й підтримку оформлює партнер проєкту. <a href="/zahlushka/oferta.html">Оферта</a> · <a href="/zahlushka/polityka.html">Політика конфіденційності</a></p>
</div></footer>
</body>
</html>
`;
  return new Response(html, {
    status,
    headers: {
      'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'content-security-policy': CSP,
      'x-content-type-options': 'nosniff', 'referrer-policy': 'no-referrer', 'x-robots-tag': 'noindex', ...zaholovky,
    },
  });
}

export const povidomlennia = (title, tekst, status = 200, dii = '', kabinet = true) =>
  storinka(title, `<section class="zaholovok"><h1>${e(title)}</h1><p>${tekst}</p>${dii}</section>`, { status, kabinet });

export const nemaie = () => povidomlennia('Сторінки немає', 'Такої сторінки немає або посилання застаріло.', 404,
  '<div class="diyi"><a class="knopka" href="/kabinet/">Кабінет</a></div>');

// ---------------------------------------------------------------- замовлення

// MV-155, П6: без цієї галочки не оплатити (сервер перевіряє поле odrazu). 14 днів на відмову (ЗУ «Про захист прав
// споживачів») не діють, якщо людина сама попросила надіслати цифровий вміст одразу — оферта, розд. про відмову.
export const NAPYS_ODRAZU = 'Прошу надіслати одразу; після надсилання відмовитися не можна';
export const GALOCHKA_ODRAZU = `<label class="pravyla"><input type="checkbox" name="odrazu" value="tak" required> ${NAPYS_ODRAZU}</label>`;

// Вхід через Google (ZAVDANNYA-142): кнопка-посилання, без скриптів. Логотип «G» — за правилами оформлення кнопок Google.
const LOGO_G = `<svg class="knopka-google__logo" viewBox="0 0 18 18" width="18" height="18" aria-hidden="true">
<path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"/>
<path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"/>
<path fill="#FBBC05" d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.05l3.01-2.33z"/>
<path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.9 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"/></svg>`;
export const knopkaGoogle = (kudy) => `<a class="knopka knopka-google" href="/kabinet/google/?kudy=${e(encodeURIComponent(kudy))}">${LOGO_G}<span>Увійти через Google</span></a>`;

export function formaZamovlennia({ tovar, budynok, adresa, pomylka = '', poshtaSesii = '', google = false }) {
  const nazva = TS.nazvy[tovar];
  const potribenBudynok = !['pidpyska', 'rieltor', ...TS.sudova].includes(tovar);
  const proYurysta = tovar === 'spyurist'
    ? `<div class="kartka"><p><b>Що дає підписка:</b> усі статті й суди міста — таблиці по судах і роках, фільтри (суд, частина
статті, роки), вивантаження CSV (до 50 на добу), 3 довідки «стаття × суд» на місяць для клієнтів. Імен суддів немає.</p>
<p class="prymitka">Це статистика минулих рішень, а не юридична допомога. Скасувати можна в кабінеті будь-коли — доступ лишиться до кінця оплаченого місяця.</p></div>` : '';
  const pro = budynok
    ? `<p>Будинок: <b>${e(adresa)}</b> (<a href="${e(budynok)}">сторінка будинку</a>).</p>`
    : (potribenBudynok ? '<p>Спершу оберіть будинок: знайдіть його на сайті й натисніть кнопку замовлення на його сторінці.</p>' : '');
  const knopka = (!potribenBudynok || budynok)
    ? `<form class="forma" method="post" action="/api/zamovlennia">
<input type="hidden" name="tovar" value="${e(tovar)}">${budynok ? `<input type="hidden" name="budynok" value="${e(budynok)}">` : ''}
${google ? `<div class="vkhid-google">${knopkaGoogle(`/oplata/?tovar=${tovar}${budynok ? `&budynok=${budynok}` : ''}`)}
<p class="prymitka">Пошта підставиться сама, і довідка буде у вашому кабінеті. Або впишіть пошту нижче.</p></div>` : ''}
<label for="poshta">Пошта — на неї прийде посилання на довідку і вхід у кабінет</label>
<input id="poshta" name="poshta" type="email" autocomplete="email" required maxlength="254" placeholder="name@poshta.ua"${poshtaSesii ? ` value="${e(poshtaSesii)}"` : ''}>
${pomylka ? `<p class="pomylka" role="alert">${e(pomylka)}</p>` : ''}
<label class="pravyla"><input type="checkbox" name="zghoda" value="tak" required> Погоджуюсь з <a href="/zahlushka/oferta.html">офертою</a> і <a href="/zahlushka/polityka.html">політикою конфіденційності</a></label>
${GALOCHKA_ODRAZU}
<button class="knopka knopka--holovna" type="submit">Перейти до оплати — ${tsina(tovar)}</button>
</form>` : '<div class="diyi"><a class="knopka knopka--holovna" href="/miy-budynok/">Знайти будинок</a></div>';
  return storinka(`${nazva} — оплата`, `<section class="zaholovok"><h1>${e(nazva)}</h1>${pro}<p class="tsina">${tsina(tovar)}</p></section>
<section class="rozdil">${proYurysta}${knopka}
<p class="prymitka">Ціну бере сервер з таблиці цін, а не з адреси сторінки. Номер картки ми не бачимо й не зберігаємо — оплату приймає платіжний сервіс партнера.</p></section>`);
}

/** Перехід до сервісу формою (LiqPay приймає POST): кнопка без скриптів. */
export function formaServisu({ url, polia }) {
  const p = Object.entries(polia).map(([k, v]) => `<input type="hidden" name="${e(k)}" value="${e(v)}">`).join('');
  return storinka('Перехід до оплати', `<section class="zaholovok"><h1>Перехід до оплати</h1>
<p>Оплату приймає платіжний сервіс партнера. Після оплати повернетеся сюди, а посилання на довідку прийде на пошту.</p>
<form method="post" action="${e(url)}">${p}<button class="knopka knopka--holovna" type="submit">Оплатити</button></form></section>`);
}

export function testovaOplata(zam, polia) {
  // polia: [{ podiia, napys, pidpys, chas }] — підписані кнопки (лише тестовий режим)
  const knopky = polia.map((p) => `<form method="post" action="/api/spovishchennia/test">
<input type="hidden" name="zamovlennia" value="${e(zam.id)}"><input type="hidden" name="suma" value="${e(p.suma ?? zam.suma)}">
<input type="hidden" name="podiia" value="${e(p.podiia)}"><input type="hidden" name="chas" value="${e(p.chas)}">
<input type="hidden" name="pidpys" value="${e(p.pidpys)}"><button class="knopka${p.podiia === 'oplata' ? ' knopka--holovna' : ''}" type="submit">${e(p.napys)}</button></form>`).join('');
  return storinka('Тестова оплата', `<section class="zaholovok"><span class="mitka">Тест</span><h1>Тестова оплата</h1>
<p>Грошей не списуємо. Замовлення: ${e(TS.nazvy[zam.tovar])}, ${tsina(zam.tovar)}.</p><div class="diyi">${knopky}</div></section>`);
}

export const dyakuiemo = () => povidomlennia('Дякуємо!',
  'Щойно платіжний сервіс підтвердить оплату, довідку почнемо готувати. Коли буде готова — надішлемо посилання на пошту (зазвичай кілька хвилин). Усі довідки — також у кабінеті.',
  200, '<div class="diyi"><a class="knopka knopka--holovna" href="/kabinet/">Кабінет</a></div>');

/** Додаткова довідка підписника з кабінету (оплата 99): та сама галочка П6, що й у звичайному замовленні. */
export function pidtverdytyDodatkovu({ budynok, adresa, pomylka = '' }) {
  return storinka('Додаткова довідка — оплата', `<section class="zaholovok"><h1>${e(TS.nazvy.dodatkova)}</h1>
<p>Будинок: <b>${e(adresa)}</b>. Довідки цього місяця з підписки вже використано.</p><p class="tsina">${tsina('dodatkova')}</p></section>
<section class="rozdil"><form class="forma" method="post" action="/kabinet/dovidka">
<input type="hidden" name="budynok" value="${e(budynok)}">
${pomylka ? `<p class="pomylka" role="alert">${e(pomylka)}</p>` : ''}${GALOCHKA_ODRAZU}
<button class="knopka knopka--holovna" type="submit">Перейти до оплати — ${tsina('dodatkova')}</button></form></section>`);
}

// ---------------------------------------------------------------- «скоро» (PRODAZH = 'skoro', ZAVDANNYA-132)

/** Сторінка «Скоро — залиште пошту»: що обрали (товар, будинок) + пошта. Оплати ще немає — лише заявка. */
export function skoro({ tovar, nazva, budynok, adresa, kanal, pomylka = '', kabinet = false }) {
  const tsinaT = TS.tsiny[tovar] ? `<p class="prymitka">Ціна після запуску: ${tsina(tovar)}.</p>` : '';
  const pro = budynok ? `<p>Будинок: <b>${e(adresa)}</b> (<a href="${e(budynok)}">сторінка будинку</a>).</p>` : '';
  return storinka('Скоро — залиште пошту', `<section class="zaholovok"><span class="mitka">Скоро</span><h1>Скоро — залиште пошту</h1>
<p>Оплату ще не підключено. Залиште пошту — напишемо <b>один раз</b>, коли це можна буде замовити.</p>
<div class="kartka vybir"><p>Ви обрали: <b>${e(nazva)}</b></p>${pro}${tsinaT}</div></section>
<section class="rozdil"><form class="forma" method="post" action="/api/skoro">
<input type="hidden" name="tovar" value="${e(tovar)}">${budynok ? `<input type="hidden" name="budynok" value="${e(budynok)}">` : ''}
<input type="hidden" name="dzherelo" value="${e(kanal)}">
<label for="poshta">Пошта</label>
<input id="poshta" name="poshta" type="email" autocomplete="email" required maxlength="254" placeholder="name@poshta.ua">
${pomylka ? `<p class="pomylka" role="alert">${e(pomylka)}</p>` : ''}
<label class="pravyla"><input type="checkbox" name="zghoda" value="tak" required> Погоджуюсь з <a href="/zahlushka/polityka.html">політикою конфіденційності</a>: пошту використаємо лише для цього листа</label>
<button class="knopka knopka--holovna" type="submit">Залишити пошту</button></form>
<p class="prymitka">Ми не списуємо грошей і не просимо картку. Пошту можна видалити — напишіть на адресу з <a href="/zahlushka/pro-nas.html">«Хто ми»</a>.</p></section>`,
  { kabinet });     // у режимі «скоро» кабінету ще немає — у шапці «Карта» замість «Кабінет»
}

export const skoroDyakuiemo = () => povidomlennia('Дякуємо!', 'Записали. Напишемо один раз, коли оплату буде підключено.', 200,
  '<div class="diyi"><a class="knopka knopka--holovna" href="/">На головну</a><a class="knopka" href="/karta/">Карта</a></div>', false);

// ---------------------------------------------------------------- кабінет

export function vkhid(povidomlennia_ = '', google = false, status = 200) {
  return storinka('Вхід у кабінет', `<section class="zaholovok"><h1>Кабінет</h1>
<p>Без пароля: ${google ? 'увійдіть через Google або ' : ''}надішлемо на пошту посилання для входу. Воно діє 30 хвилин і лише один раз.</p></section>
<section class="rozdil">${google ? `<div class="vkhid-google">${knopkaGoogle('/kabinet/')}
<p class="prymitka">Беремо від Google лише пошту. Якщо ви вже купували з цією поштою — відкриється той самий кабінет.</p>
<p class="abo"><span>або</span></p></div>` : ''}<form class="forma" method="post" action="/kabinet/vkhid">
<label for="poshta">Пошта, з якою купували</label>
<input id="poshta" name="poshta" type="email" autocomplete="email" required maxlength="254" placeholder="name@poshta.ua">
<button class="knopka knopka--holovna" type="submit">Надіслати посилання</button></form>
${povidomlennia_ ? `<p class="prymitka" role="status">${e(povidomlennia_)}</p>` : ''}</section>`, { status });
}

const STATUS_DOVIDKY = { v_cherzi: 'готується', hotuietsia: 'готується', hotova: 'готова', vydaleno: 'файл видалено за строком зберігання', pomylka: 'не вдалося — напишіть партнеру, повернемо гроші або зробимо ще раз' };
const NAZVA_PIDPYSKY = { pidpyska: 'Підписка', rieltor: 'Підписка для рієлтора', osbb: 'Будинок для ОСББ', spyurist: 'Підписка юриста «Практика»' };
const VYD_DOVIDKY = { povnyi: 'повний звіт', dovidka: 'довідка', sp: 'судова практика' };

export function kabinet({ poshta, dovidky, stezhu, pidpysky, dostupno, povidomlennia: pov = '', bali = null }) {
  const ryadky = dovidky.length ? dovidky.map((d) => `<li><b>${e(d.adresa)}</b> — ${VYD_DOVIDKY[d.rezhym] || 'довідка'}, ${data(d.stvoreno)}: ${
    d.status === 'hotova' ? `<a href="/dovidka/${e(d.id)}/">відкрити</a>` : e(STATUS_DOVIDKY[d.status])}</li>`).join('')
    : '<li>Поки немає довідок.</li>';
  const stezh = stezhu.length ? stezhu.map((s) => `<li><a href="${e(s.budynok)}">${e(s.adresa)}</a>
<form class="v-riadok" method="post" action="/kabinet/stezhu/prybraty"><input type="hidden" name="budynok" value="${e(s.budynok)}"><button class="knopka" type="submit">Прибрати</button></form>
<form class="v-riadok" method="post" action="/kabinet/dovidka"><input type="hidden" name="budynok" value="${e(s.budynok)}"><button class="knopka" type="submit">Довідка</button></form></li>`).join('')
    : '<li>Додайте адресу — тут будуть будинки, за якими стежите.</li>';
  const pidp = pidpysky.length ? pidpysky.map((p) => `<li><b>${e(NAZVA_PIDPYSKY[p.tovar])}</b>${p.adresa ? ` (${e(p.adresa)})` : ''} — ${
    p.status === 'aktyvna' ? `діє до ${data(p.diie_do)}, довідок цього періоду лишилось: ${p.zalyshok}${p.tovar === 'spyurist' ? ' — <a href="/pidpysnyk/praktyka/">відкрити практику</a>' : ''}
<form class="v-riadok" method="post" action="/kabinet/skasuvaty"><input type="hidden" name="pidpyska" value="${e(p.id)}"><button class="knopka" type="submit">Скасувати підписку</button></form>`
      : p.zaBali ? `за бали, діє до ${data(p.diie_do)}, без продовження` : p.status === 'skasovana' ? `скасована, діє до ${data(p.diie_do)}` : 'очікує оплати'}</li>`).join('')
    : `<li>Немає. <a href="/oplata/?tovar=pidpyska">Підписка — ${tsina('pidpyska')}</a></li>`;
  return storinka('Кабінет', `<section class="zaholovok"><h1>Кабінет</h1><p>${e(poshta)}</p>
${pov ? `<p class="prymitka" role="status">${e(pov)}</p>` : ''}</section>
<section class="rozdil"><h2>Мої довідки</h2><div class="kartka"><ul class="spysok-tekst">${ryadky}</ul></div>
<p class="prymitka">Можна взяти ще: ${dostupno.opys}. Довідку на будинок — кнопкою «Довідка» біля адреси нижче.</p></section>
<section class="rozdil"><h2>Стежу</h2><div class="kartka"><ul class="spysok-tekst">${stezh}</ul>
<form class="forma" method="post" action="/kabinet/stezhu"><label for="budynok">Адреса сторінки будинку</label>
<input id="budynok" name="budynok" required maxlength="200" placeholder="/budynok/vulytsia/1/">
<button class="knopka" type="submit">Стежити</button></form></div></section>
<section class="rozdil"><h2>Підписка</h2><div class="kartka"><ul class="spysok-tekst">${pidp}</ul></div></section>
${bali ? rozdilBaliv(bali, stezhu) : ''}
<section class="rozdil"><h2>Мої дані</h2><p class="prymitka">Зберігаємо пошту, замовлення, довідки й адреси «Стежу» (docs/PRODAZH-SERVER.md). Видалення — одразу; записи про оплату партнер зберігає для обліку без пошти.</p>
<div class="diyi"><form method="post" action="/kabinet/vyhid"><button class="knopka" type="submit">Вийти</button></form>
<form method="post" action="/kabinet/vydalyty"><input type="hidden" name="pidtverdzhuiu" value="tak"><button class="knopka" type="submit">Видалити мої дані</button></form></div></section>`);
}

/** Бали ігор (ZAVDANNYA-123) — лише коли обмін увімкнено (OBMIN_BALIV). Разовий номер форми — захист від повторного надсилання. */
function rozdilBaliv({ balans, kurs, zapyt }, stezhu) {
  const d = kurs.obmin.dovidka, m = kurs.obmin['pidpyska-misiats'];
  const vybir = stezhu.length ? `<select name="budynok" aria-label="Будинок">${stezhu.map((s) => `<option value="${e(s.budynok)}">${e(s.adresa)}</option>`).join('')}</select>` : '';
  return `<section class="rozdil"><h2>Бали ігор</h2><div class="kartka"><p><b>${balans}</b> балів на акаунті.</p>
<form class="forma" method="post" action="/kabinet/obmin"><input type="hidden" name="tovar" value="dovidka"><input type="hidden" name="zapyt" value="${e(zapyt)}d">
${vybir || '<p class="prymitka">Щоб обміняти на довідку, спершу додайте будинок у «Стежу».</p>'}
<button class="knopka" type="submit"${balans >= d.baliv && vybir ? '' : ' disabled'}>Довідка — ${d.baliv} балів</button></form>
<form class="forma" method="post" action="/kabinet/obmin"><input type="hidden" name="tovar" value="pidpyska-misiats"><input type="hidden" name="zapyt" value="${e(zapyt)}m">
<button class="knopka" type="submit"${balans >= m.baliv ? '' : ' disabled'}>Місяць підписки — ${m.baliv} балів</button></form></div>
<p class="prymitka">Обмін — раз на 30 днів. Бали не передаються й не виводяться в гроші; бали з телефона до акаунта не переносяться.</p></section>`;
}

export const CSS = `/* Сервер продажу (ZAVDANNYA-99): форми в стилі сайту (docs/STYL.md) */
.forma{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;max-width:460px}
.forma label{font-weight:600;font-size:14px;line-height:20px}
.forma input[type=email],.forma input[name=budynok]{font:inherit;padding:10px 12px;border:1.5px solid var(--mezha);border-radius:var(--radius-m);background:var(--surface);color:var(--ink);box-shadow:0 3px 0 var(--bort)}
.forma .pravyla{font-weight:400;font-size:13px}
.forma select{font:inherit;width:100%;min-width:0;padding:10px 12px;border:1.5px solid var(--mezha);border-radius:var(--radius-m);background:var(--surface);color:var(--ink);box-shadow:0 3px 0 var(--bort)}
.pomylka{color:var(--vyd);font-weight:700}
.tsina{font-size:34px;line-height:40px;font-weight:800;font-variant-numeric:tabular-nums}
.v-riadok{display:inline-block;margin-left:8px}
.vkhid-google{max-width:460px;margin:0 0 16px}
.knopka-google{display:inline-flex;align-items:center;justify-content:center;gap:10px;width:100%;box-sizing:border-box;background:#fff;color:#1f1f1f;border-color:#747775}
.knopka-google__logo{flex:none}
.abo{display:flex;align-items:center;gap:10px;color:var(--ink-2,inherit);font-size:13px;margin:16px 0 0}
.abo::before,.abo::after{content:"";flex:1;border-top:1px solid var(--mezha)}
`;
