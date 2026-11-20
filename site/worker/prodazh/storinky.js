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

export function storinka(title, tilo, { status = 200, zaholovky = {}, kabinet = true, css = [], skrypty = [] } = {}) {
  const html = `<!doctype html>
<html lang="uk" data-koren="/">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="same-origin">
<meta name="robots" content="noindex, nofollow">
<title>${e(title)} | Моя вулиця</title>
<script src="/sait/tema.js"></script>
<link rel="stylesheet" href="/sait/sait.css">
<link rel="stylesheet" href="/prodazh/prodazh.css">
${css.map((c) => `<link rel="stylesheet" href="${e(c)}">`).join('')}
${skrypty.map((c) => `<script src="${e(c)}" defer></script>`).join('')}
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
      // same-origin, а не no-referrer (ZAVDANNYA-143): з no-referrer браузер шле формам «Origin: null», і перевірка
      // zNashohoSaitu відхиляла кожне замовлення й вхід у кабінет. Чужим сайтам адреса сторінки однаково не йде.
      'x-content-type-options': 'nosniff', 'referrer-policy': 'same-origin', 'x-robots-tag': 'noindex', ...zaholovky,
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

// ZAVDANNYA-150, п. 6: будинок — адресою словами з підказками (як пошук «Мій будинок»; скрипт /sait/budynok-pole.js
// заповнює підказки з /vulytsi/budynky.json). Без скриптів — просто поле: адресу однаково розбирає сервер (znaityBudynok).
export const SKRYPT_POLIA = '/sait/budynok-pole.js';
export function poleBudynku({ id = 'budynok', napys = 'Будинок — вулиця й номер', vvedeno = '', holovne = true } = {}) {
  return `<label for="${id}">${napys}</label>
<input id="${id}" name="budynok" required maxlength="200" autocomplete="off" list="${id}-pidkazky" data-budynky placeholder="Наприклад: Оболонський 16"${vvedeno ? ` value="${e(vvedeno)}"` : ''}>
<datalist id="${id}-pidkazky"></datalist>${holovne ? '\n<p class="prymitka">Почніть писати вулицю й номер і оберіть будинок із підказок. Посилання на сторінку будинку — теж можна.</p>' : ''}`;
}

export function formaZamovlennia({ tovar, budynok, adresa, pomylka = '', poshtaSesii = '', google = false, zalyshok = 0, vvedeno = '' }) {
  const nazva = TS.nazvy[tovar];
  const shcho = tovar === 'zvit' ? 'звіт' : 'довідку';      // ZVIT-167, п. 9: форма повного звіту — «звіт», не «довідку»
  const potribenBudynok = !['pidpyska', 'rieltor', ...TS.sudova].includes(tovar);
  const proYurysta = tovar === 'spyurist'
    ? `<div class="kartka"><p><b>Що дає підписка:</b> усі статті й суди міста — таблиці по судах і роках, фільтри (суд, частина
статті, роки), вивантаження CSV (до 50 на добу), 3 довідки «стаття × суд» на місяць для клієнтів. Імен суддів немає.</p>
<p class="prymitka">Це статистика минулих рішень, а не юридична допомога. Скасувати можна в кабінеті будь-коли — доступ лишиться до кінця оплаченого місяця.</p></div>` : '';
  const pro = budynok
    ? `<p>Будинок: <b>${e(adresa)}</b> (<a href="${e(budynok)}">сторінка будинку</a>).</p>`
    : (potribenBudynok ? '<p>Вкажіть будинок — вулицю й номер.</p>' : '');
  // ZAVDANNYA-143, ZAVDANNYA-150 (п. 6): без будинку — поле адреси з підказками; будинок однаково шукає й перевіряє сервер
  // (znaityBudynok → perevirytyBudynok), адресу беремо з його сторінки, а не з форми.
  const pole = potribenBudynok && !budynok ? poleBudynku({ vvedeno }) : '';
  // ZAVDANNYA-150, п. 3: залишок довідок (пакет «3 довідки», підписка) — головна дія; оплата — нижче, другою.
  const zZalyshku = zalyshok > 0 && budynok
    ? `<div class="kartka zalyshok"><p><b>У вас є довідки без оплати: ${zalyshok}.</b> Візьміть одну на цей будинок — платити вдруге не треба.</p>
<form class="forma" method="post" action="/kabinet/dovidka"><input type="hidden" name="budynok" value="${e(budynok)}">
<button class="knopka knopka--holovna" type="submit">Використати залишок (${zalyshok})</button></form></div>
<h2 class="abo-oplata">Або купити окремо</h2>` : '';
  const knopka = `<form class="forma" method="post" action="/api/zamovlennia">
<input type="hidden" name="tovar" value="${e(tovar)}">${budynok ? `<input type="hidden" name="budynok" value="${e(budynok)}">` : ''}${pole}
${google ? `<div class="vkhid-google">${knopkaGoogle(`/oplata/?tovar=${tovar}${budynok ? `&budynok=${budynok}` : ''}`)}
<p class="prymitka">Пошта підставиться сама, і все куплене буде у вашому кабінеті. Або впишіть пошту нижче.</p></div>` : ''}
<label for="poshta">Пошта — на неї прийде ${TS.period_misiatsiv[tovar] ? 'вхід у кабінет' : `посилання на ${shcho} і вхід у кабінет`}</label>
<input id="poshta" name="poshta" type="email" autocomplete="email" required maxlength="254" placeholder="name@poshta.ua"${poshtaSesii ? ` value="${e(poshtaSesii)}"` : ''}>
${pomylka ? `<p class="pomylka" role="alert">${e(pomylka)}</p>` : ''}
<label class="pravyla"><input type="checkbox" name="zghoda" value="tak" required> Погоджуюсь з <a href="/zahlushka/oferta.html">офертою</a> і <a href="/zahlushka/polityka.html">політикою конфіденційності</a></label>
${GALOCHKA_ODRAZU}
<button class="knopka${zZalyshku ? '' : ' knopka--holovna'}" type="submit">Перейти до оплати — ${tsina(tovar)}</button>
</form>`;
  return storinka(`${nazva} — оплата`, `<section class="zaholovok"><h1>${e(nazva)}</h1>${pro}<p class="tsina">${tsina(tovar)}</p></section>
<section class="rozdil">${zZalyshku}${proYurysta}${SHCHO_DAIE[tovar] || ''}${knopka}
<p class="prymitka">${TS.period_misiatsiv[tovar] ? 'Доступ відкривається одразу після оплати.' : `Посилання на ${shcho} прийде на пошту за кілька хвилин після оплати.`} Номер картки ми не бачимо й не зберігаємо — оплату приймає платіжний сервіс партнера.</p></section>`,
  { skrypty: pole ? [SKRYPT_POLIA] : [] });
}

// ZAVDANNYA-143: що саме отримує людина — ОСББ і рієлтор (ціни й кількість — з таблиці цін).
// ZAVDANNYA-150, п. 4–5: підписка — те саме, що в оферті й на вітрині (site/tsiny.py, PIDPYSKA_DAIE): лише те, що працює.
const SHCHO_DAIE = {
  pidpyska: `<div class="kartka"><p><b>Що дає підписка:</b></p><ul class="spysok-tekst">${TS.pidpyska_daie.map((x) => `<li>${e(x)}</li>`).join('')}</ul>
<p class="prymitka">Довідка — не оцінка будинку й не порада, де жити. Скасувати можна в кабінеті будь-коли — доступ лишиться до кінця оплаченого місяця.</p></div>`,
  osbb: `<div class="kartka"><p><b>Що отримує правління:</b> щомісячну довідку про свій будинок — сама приходить на пошту раз на
місяць: звернення мешканців до 1551 за останній місяць поруч зі звичайним місяцем будинку й сусідніми будинками, теми й статуси
за рік, події з рішень судів біля будинку. Усі довідки — у кабінеті.</p>
<p class="prymitka">Оплата — раз на рік. За 3 дні до наступного списання надішлемо лист; скасувати можна в кабінеті будь-коли —
оплачений рік діє до кінця. Довідки — лише про цей будинок.</p></div>`,
  rieltor: `<div class="kartka"><p><b>Що дає підписка:</b> ${TS.dovidok.rieltor} довідок про будинки на місяць — на будь-які адреси
(показ, клієнт, перевірка перед угодою); понад ${TS.dovidok.rieltor} — по ${TS.tsiny.dodatkova}${NBSP}грн. У кабінеті — «Мої об'єкти»: усі
будинки й довідки до них, скільки лишилось цього місяця.</p>
<p class="prymitka">Довідка — не оцінка будинку й не порада клієнту, де жити. Скасувати можна в кабінеті будь-коли — доступ лишиться до кінця оплаченого місяця.</p></div>`,
};

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

// ZAVDANNYA-172 (ZVIT-166, З-8; ZVIT-167, п. 9): «Дякуємо» — за тим, що купили. Підписка не «готує довідку», а відкриває карту.
const DYAKUIEMO = {
  pidpyska: ['Щойно платіжний сервіс підтвердить оплату (зазвичай кілька хвилин), відкриється карта підписника. На пошту прийде лист із входом у кабінет; кнопка «Відкрити карту» — і там.', 'karta'],
  rieltor: ['Щойно платіжний сервіс підтвердить оплату (зазвичай кілька хвилин), відкриються карта підписника й «Мої об\'єкти» в кабінеті — там і довідки на ваші адреси. На пошту прийде лист із входом.', 'karta'],
  osbb: ['Щойно платіжний сервіс підтвердить оплату, почнемо готувати першу щомісячну довідку про ваш будинок. Коли буде готова — надішлемо посилання на пошту; далі довідка приходить сама раз на місяць.', ''],
  zvit: ['Щойно платіжний сервіс підтвердить оплату, звіт почнемо готувати. Коли буде готовий — надішлемо посилання на пошту (зазвичай кілька хвилин). Звіт — також у кабінеті.', ''],
  try: ['Щойно платіжний сервіс підтвердить оплату, першу довідку почнемо готувати. Дві інші візьмете в кабінеті на будь-які будинки — кнопкою «Довідка».', ''],
};
const DYAKUIEMO_DOVIDKA = 'Щойно платіжний сервіс підтвердить оплату, довідку почнемо готувати. Коли буде готова — надішлемо посилання на пошту (зазвичай кілька хвилин). Усі довідки — також у кабінеті.';

export function dyakuiemo(tovar = '') {
  const [tekst, dod] = DYAKUIEMO[tovar] || [DYAKUIEMO_DOVIDKA, ''];
  const dii = dod === 'karta'
    ? '<div class="diyi"><a class="knopka knopka--holovna" href="/pidpysnyk/">Відкрити карту</a><a class="knopka" href="/kabinet/">Кабінет</a></div>'
    : '<div class="diyi"><a class="knopka knopka--holovna" href="/kabinet/">Кабінет</a></div>';
  return povidomlennia('Дякуємо!', tekst, 200, dii);
}

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

/** ZAVDANNYA-161, п. 1: сторінка за посиланням із листа — вхід лише натисканням (поштові сканери посилання не спалюють). */
export function knopkaVkhodu(t) {
  return storinka('Вхід у кабінет', `<section class="zaholovok"><h1>Вхід у кабінет</h1>
<p>Натисніть «Увійти», щоб відкрити кабінет. Посилання з листа діє 30 хвилин і лише один раз.</p></section>
<section class="rozdil"><form class="forma" method="post" action="/kabinet/vkhid/uviity">
<input type="hidden" name="t" value="${e(t)}">
<button class="knopka knopka--holovna" type="submit">Увійти</button></form>
<p class="prymitka">Якщо ви не просили посилання — просто закрийте сторінку.</p></section>`,
  { zaholovky: { 'cache-control': 'no-store', 'referrer-policy': 'no-referrer' } });
}

const STATUS_DOVIDKY = { v_cherzi: 'готується', hotuietsia: 'готується', hotova: 'готова', vydaleno: 'файл видалено за строком зберігання', pomylka: 'не вдалося — напишіть партнеру, повернемо гроші або зробимо ще раз' };
const NAZVA_PIDPYSKY = { pidpyska: 'Підписка', rieltor: 'Підписка для рієлтора', osbb: 'Будинок для ОСББ', spyurist: 'Підписка юриста «Практика»' };
const VYD_DOVIDKY = { povnyi: 'повний звіт', dovidka: 'довідка', sp: 'судова практика', osbb: 'щомісячна довідка ОСББ' };

// «готується» сама не оновлюється (сторінка без скриптів) — поруч посилання «оновити» (ZVIT-167)
const posylannia = (d) => (d.status === 'hotova' ? `<a href="/dovidka/${e(d.id)}/">відкрити</a>`
  : ['v_cherzi', 'hotuietsia'].includes(d.status) ? `${e(STATUS_DOVIDKY[d.status])} (<a href="/kabinet/">оновити</a>)` : e(STATUS_DOVIDKY[d.status]));

/** ZAVDANNYA-143: правлінню ОСББ — свій будинок, довідки приходять самі щомісяця; лист за 3 дні до річного списання. */
function rozdilOsbb(p, dovidky) {
  const svoi = dovidky.filter((d) => d.pidpyska_id === p.id);
  const tsei = p.zalyshok > 0 ? 'довідка цього місяця ставиться в чергу сама протягом доби' : `наступна — ${data(p.misiats_do)}`;
  const spysok = svoi.length ? svoi.map((d) => `<li>${data(d.stvoreno)} — ${posylannia(d)}</li>`).join('') : '<li>Перша довідка готується.</li>';
  return `<section class="rozdil" id="osbb"><h2>Мій будинок (ОСББ)</h2><div class="kartka">
<p><b>${p.budynok ? `<a href="${e(p.budynok)}">${e(p.adresa)}</a>` : e(p.adresa)}</b></p>
<p>Щомісячна довідка приходить сама на пошту — нічого натискати не треба; ${tsei}.</p>
<ul class="spysok-tekst">${spysok}</ul>
<p class="prymitka">Рік оплачено до ${data(p.diie_do)}.${p.status === 'aktyvna' ? ' За 3 дні до наступного списання надішлемо лист.' : ' Підписку скасовано — нових списань не буде.'}</p></div></section>`;
}

/** ZAVDANNYA-143: рієлтору — «Мої об'єкти»: будинки, на які брав довідки, лічильник місяця, нова довідка за посиланням. */
function rozdilRieltora(p, dovidky) {
  const obiekty = new Map();
  for (const d of dovidky) {
    if (!d.budynok || d.rezhym === 'sp') continue;
    if (!obiekty.has(d.budynok)) obiekty.set(d.budynok, { adresa: d.adresa, dovidky: [] });
    obiekty.get(d.budynok).dovidky.push(d);       // новіші перші (dovidky — за датою, новіші згори)
  }
  const ryadky = obiekty.size ? [...obiekty].map(([b, o]) => `<li><a href="${e(b)}">${e(o.adresa)}</a> — ${o.dovidky.length}${NBSP}${
    o.dovidky.length === 1 ? 'довідка' : o.dovidky.length < 5 ? 'довідки' : 'довідок'}, остання ${data(o.dovidky[0].stvoreno)}: ${posylannia(o.dovidky[0])}
<form class="v-riadok" method="post" action="/kabinet/dovidka"><input type="hidden" name="budynok" value="${e(b)}"><button class="knopka" type="submit">Нова довідка</button></form></li>`).join('')
    : '<li>Поки немає. Додайте перший об\'єкт нижче.</li>';
  return `<section class="rozdil" id="obiekty"><h2>Мої об'єкти</h2><div class="kartka">
<p class="lichylnyk"><b>${p.vziato} з ${p.dovidok}</b> довідок цього місяця використано · лишилось <b>${p.zalyshok}</b> · нові ${p.dovidok} — з ${data(p.misiats_do)}</p>
<ul class="spysok-tekst">${ryadky}</ul>
<form class="forma" method="post" action="/kabinet/dovidka">${poleBudynku({ id: 'obiekt', napys: 'Новий об\'єкт — вулиця й номер', holovne: false })}
<button class="knopka knopka--holovna" type="submit">Довідка на цей будинок</button></form>
<p class="prymitka">Понад ${p.dovidok} на місяць — ${tsina('dodatkova')} за довідку (спершу спитаємо). Почніть писати адресу й оберіть будинок із підказок.</p></div></section>`;
}

/** ZAVDANNYA-150, п. 4: «Стежу» — що з адресами робимо (лист раз на місяць для підписки) і перемикач листа. */
function lystStezhu(lyst) {
  if (!lyst?.pidpyska) {
    return '<p class="prymitka">З підпискою раз на місяць, після оновлення даних, надсилаємо лист: що нового в радіусі 300\u00a0м від цих адрес.</p>';
  }
  return `<p class="prymitka">${lyst.vymkneno ? 'Лист «Нове біля дому» вимкнено.' : 'Раз на місяць, після оновлення даних, надсилаємо лист: що нового в радіусі 300\u00a0м від цих адрес.'}</p>
<form class="v-riadok" method="post" action="/kabinet/stezhu/lyst"><input type="hidden" name="lyst" value="${lyst.vymkneno ? 'tak' : 'ni'}"><button class="knopka" type="submit">${lyst.vymkneno ? 'Надсилати лист' : 'Не надсилати лист'}</button></form>`;
}

// ZAVDANNYA-172 (ZVIT-167, п. 8): кабінет за роллю. Рієлтор бачить свої довідки в «Мої об'єкти» (без другого списку й
// другого лічильника); ОСББ — у «Мій будинок»; решта — «Мої довідки» з дією «ще одна». «Відкрити карту» — тим, кому вона
// відкрита (ZVIT-166, З-4). «Видалити мої дані» — окрема сторінка з переліком, що зникне (ZVIT-167, п. 1).
export function kabinet({ poshta, dovidky, stezhu, pidpysky, dostupno, povidomlennia: pov = '', bali = null, lyst = null, partner = false, karta = false }) {
  const rieltor = pidpysky.find((p) => p.tovar === 'rieltor');
  const maieOsbb = pidpysky.some((p) => p.tovar === 'osbb');
  // довідки, які вже показано в розділі ролі, у «Мої довідки» не повторюємо
  const inshi = dovidky.filter((d) => !(rieltor && d.budynok && d.rezhym !== 'sp') && !(maieOsbb && d.rezhym === 'osbb'));
  const ryadky = inshi.map((d) => `<li><b>${e(d.adresa)}</b> — ${VYD_DOVIDKY[d.rezhym] || 'довідка'}, ${data(d.stvoreno)}: ${posylannia(d)}</li>`).join('');
  const zalyshok = dostupno.opys !== 'немає';
  // Узяти ще: є залишок — поле адреси тут же (а не «кнопкою біля адреси нижче», коли нижче нічого); немає — купити одну.
  const shche = zalyshok
    ? `<p class="prymitka">Можна взяти без оплати: ${e(dostupno.opys)}.</p>
<form class="forma" method="post" action="/kabinet/dovidka">${poleBudynku({ id: 'shche', napys: 'Довідка на будинок — вулиця й номер', holovne: false })}
<button class="knopka knopka--holovna" type="submit">Взяти довідку</button></form>`
    : `<div class="diyi"><a class="knopka" href="/oplata/?tovar=dovidka">Ще одна довідка — ${tsina('dovidka')}</a></div>`;
  const mojiDovidky = rieltor
    ? (ryadky ? `<section class="rozdil"><h2>Інші довідки</h2><div class="kartka"><ul class="spysok-tekst">${ryadky}</ul></div></section>` : '')
    : (maieOsbb && !ryadky ? ''
      : `<section class="rozdil"><h2>Мої довідки</h2><div class="kartka"><ul class="spysok-tekst">${ryadky || '<li>Поки немає довідок.</li>'}</ul>${shche}</div></section>`);
  const stezh = stezhu.length ? stezhu.map((s) => `<li><a href="${e(s.budynok)}">${e(s.adresa)}</a>
<form class="v-riadok" method="post" action="/kabinet/stezhu/prybraty"><input type="hidden" name="budynok" value="${e(s.budynok)}"><button class="knopka" type="submit">Прибрати</button></form>
<form class="v-riadok" method="post" action="/kabinet/dovidka"><input type="hidden" name="budynok" value="${e(s.budynok)}"><button class="knopka" type="submit">Довідка</button></form></li>`).join('')
    : '<li>Додайте адресу — тут будуть будинки, за якими стежите.</li>';
  const pidp = pidpysky.length ? pidpysky.map((p) => `<li><b>${e(NAZVA_PIDPYSKY[p.tovar])}</b>${p.adresa ? ` (${e(p.adresa)})` : ''} — ${
    p.status === 'aktyvna' ? `діє до ${data(p.diie_do)}${
      p.tovar === 'osbb' ? ', довідка приходить сама щомісяця' : p.tovar === 'rieltor' ? ' — довідки в «Мої об\'єкти»' : `, довідок цього місяця лишилось: ${p.zalyshok}`}${p.tovar === 'spyurist' ? ' — <a href="/pidpysnyk/praktyka/">відкрити практику</a>' : ''}
<form class="v-riadok" method="post" action="/kabinet/skasuvaty"><input type="hidden" name="pidpyska" value="${e(p.id)}"><button class="knopka" type="submit">Скасувати підписку</button></form>`
      : p.zaBali ? `за бали, діє до ${data(p.diie_do)}, без продовження` : p.status === 'skasovana' ? `скасована, діє до ${data(p.diie_do)}` : 'очікує оплати'}</li>`).join('')
    : `<li>Немає. <a href="/oplata/?tovar=pidpyska">Підписка — ${tsina('pidpyska')}</a></li>`;
  const vidkrytyKartu = karta ? '<div class="diyi"><a class="knopka knopka--holovna" href="/pidpysnyk/">Відкрити карту</a></div>' : '';
  const osbb = pidpysky.filter((p) => p.tovar === 'osbb').map((p) => rozdilOsbb(p, dovidky)).join('');
  return storinka('Кабінет', `<section class="zaholovok"><h1>Кабінет</h1><p>${e(poshta)}</p>
${pov ? `<p class="prymitka" role="status">${e(pov)}</p>` : ''}${vidkrytyKartu}${partner ? '<p><a class="knopka" href="/kabinet/zvernennia/">Звернення людей (для партнера)</a></p>' : ''}</section>
${osbb}${rieltor ? rozdilRieltora(rieltor, dovidky) : ''}
${mojiDovidky}
<section class="rozdil" id="stezhu"><h2>Стежу</h2><div class="kartka"><ul class="spysok-tekst">${stezh}</ul>${lystStezhu(lyst)}
<form class="forma" method="post" action="/kabinet/stezhu">${poleBudynku({ napys: 'Додати будинок — вулиця й номер', holovne: false })}
<button class="knopka" type="submit">Стежити</button></form></div></section>
<section class="rozdil" id="pidpyska"><h2>Підписка</h2><div class="kartka"><ul class="spysok-tekst">${pidp}</ul>${vidkrytyKartu}</div></section>
${bali ? rozdilBaliv(bali, stezhu) : ''}
<section class="rozdil"><h2>Вийти</h2><form method="post" action="/kabinet/vyhid"><button class="knopka" type="submit">Вийти з кабінету</button></form></section>
<section class="rozdil"><h2>Мої дані</h2><p class="prymitka">Зберігаємо пошту, замовлення, довідки й адреси «Стежу» — <a href="/zahlushka/polityka.html">політика конфіденційності</a>.
Видалити все можна тут: <a href="/kabinet/vydalyty/">видалити мої дані…</a> — спершу покажемо, що саме зникне.</p></section>`,
  { skrypty: [SKRYPT_POLIA] });
}

/** ZAVDANNYA-172 (ZVIT-167, п. 1): підтвердження перед видаленням — що зникне назавжди, кнопка іншого вигляду, «Не видаляти» — головна. */
export function pidtverdytyVydalennia(z) {
  const chysla = (n, a, b, c) => `${n}${NBSP}${n % 10 === 1 && n % 100 !== 11 ? a : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? b : c}`;
  const punkty = [`пошта й вхід у кабінет`];
  if (z.dovidok) punkty.push(`${chysla(z.dovidok, 'довідка', 'довідки', 'довідок')} і посилання на них — відкрити їх більше не вийде${z.vCherzi ? ` (з них ${z.vCherzi} ще готуються — їх не буде)` : ''}`);
  if (z.zalyshok) punkty.push(`${chysla(z.zalyshok, 'оплачена довідка', 'оплачені довідки', 'оплачених довідок')}, яких ще не взяли`);
  for (const p of z.pidpysky) {
    punkty.push(`${NAZVA_PIDPYSKY[p.tovar] || 'Підписка'}${p.adresa ? ` (${e(p.adresa)})` : ''}, оплачена до ${data(p.diie_do)} — ${p.status === 'aktyvna' ? 'скасуємо, і доступ закінчиться одразу' : 'доступ закінчиться одразу'}`);
  }
  if (z.stezhu) punkty.push(`${chysla(z.stezhu, 'адреса', 'адреси', 'адрес')} у «Стежу» і лист «Нове біля дому»`);
  return storinka('Видалити мої дані?', `<section class="zaholovok"><h1>Видалити мої дані?</h1>
<p>Це назавжди: повернути не зможемо — ні довідки, ні оплачений час. Гроші за невикористане видалення не повертає.</p></section>
<section class="rozdil"><h2>Що зникне</h2><div class="kartka"><ul class="spysok-tekst">${punkty.map((x) => `<li>${x}</li>`).join('')}</ul>
<p class="prymitka">Записи про оплату (сума, дата, товар) партнер зберігає для обліку — без пошти.</p></div>
<div class="diyi"><a class="knopka knopka--holovna" href="/kabinet/">Не видаляти — назад у кабінет</a></div>
<form class="forma vydalennia" method="post" action="/kabinet/vydalyty"><input type="hidden" name="pidtverdzhuiu" value="tak">
<label class="pravyla"><input type="checkbox" name="rozumiiu" value="tak" required> Розумію, що це не повернути</label>
<button class="knopka knopka--nebezpechna" type="submit">Так, видалити все</button></form></section>`);
}

/** ZAVDANNYA-172 (ZVIT-167): той самий будинок за добу — спершу спитати, а не мовчки витратити ще одну довідку. */
export function povtorDovidky({ budynok, adresa, dovidka }) {
  return storinka('Довідка вже є', `<section class="zaholovok"><h1>На цей будинок довідка вже є</h1>
<p><b>${e(adresa)}</b> — довідку брали ${data(dovidka.stvoreno)}: ${posylannia(dovidka)}. Дані між оновленнями не змінюються — друга довідка буде такою самою.</p></section>
<section class="rozdil"><div class="diyi"><a class="knopka knopka--holovna" href="/kabinet/">Назад у кабінет</a></div>
<form class="forma" method="post" action="/kabinet/dovidka"><input type="hidden" name="budynok" value="${e(budynok)}"><input type="hidden" name="shche" value="tak">
<button class="knopka" type="submit">Однаково взяти ще одну</button></form></section>`);
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

// ---------------------------------------------------------------- кабінет звернень партнера (ZAVDANNYA-161, п. 5)

const SHCHO_NE_TAK = { mistse: 'не те місце', opys: 'неточний опис', vydalyty: 'прибрати подію', inshe: 'інше' };
const PRYCHYNY = [['zvernennya', 'за зверненням людини'], ['skasovano', 'рішення скасоване чи змінене'],
  ['vpiznaty', 'людину можна впізнати'], ['inshe', 'інше']];
const posyl = (t) => (/^https:\/\/[^\s"<>]+$/.test(t || '') ? `<a href="${e(t)}" target="_blank" rel="noopener noreferrer">${e(t)}</a>` : e(t));
const den = (t) => (t ? data(t) : '—');

function formaPrybraty(z = null) {
  const id = z ? `zv${e(z.id)}` : 'zv0';
  return `<form class="forma" method="post" action="/kabinet/zvernennia/prybraty">
${z ? `<input type="hidden" name="zvernennya" value="${e(z.id)}">` : ''}
<label for="${id}-p">Посилання на рішення суду або його номер</label>
<input id="${id}-p" name="posylannia" required maxlength="500" value="${e(z && /reyestr\.court\.gov\.ua|^\d{5,12}$/.test(z.posylannya) ? z.posylannya : '')}" placeholder="https://reyestr.court.gov.ua/Review/…">
<label for="${id}-ch">Чому</label>
<select id="${id}-ch" name="prychyna">${PRYCHYNY.map(([k, n]) => `<option value="${k}"${(z ? 'zvernennya' : 'skasovano') === k ? ' selected' : ''}>${n}</option>`).join('')}</select>
<button class="knopka knopka--holovna" type="submit">Прибрати подію зараз</button></form>`;
}

/** Сторінка партнера: звернення (відкриті — зверху), прибрати подію одразу, закрити звернення, журнал прибраних. */
export function zvernenniaPartnera({ vidkryti, zakryti, zhurnal, povidomlennia: pov = '' }) {
  const zv = (z) => `<li class="kartka"><p><b>№${e(z.id)}</b> · ${den(z.stvoreno)} · ${e(SHCHO_NE_TAK[z.shcho_ne_tak] || z.shcho_ne_tak)}${z.zakryto ? ` · закрито ${den(z.zakryto)}` : ' · <b>чекає відповіді</b>'}</p>
<p>Що: ${posyl(z.posylannya)}</p>${z.poyasnennya ? `<p>Пояснення: ${e(z.poyasnennya)}</p>` : ''}<p>Контакт: ${e(z.kontakt)}</p>
${z.zakryto ? '' : `${formaPrybraty(z)}
<form class="v-riadok" method="post" action="/kabinet/zvernennia/zakryty"><input type="hidden" name="zvernennya" value="${e(z.id)}"><button class="knopka" type="submit">Відповіли — закрити</button></form>`}</li>`;
  const zh = zhurnal.length ? zhurnal.map((p) => `<li>${den(p.prybrano)} — ${posyl(p.posylannia)}${p.zvernennya_id ? ` (звернення №${e(p.zvernennya_id)})` : ''}${p.prychyna ? `, ${e((PRYCHYNY.find(([k]) => k === p.prychyna) || [0, p.prychyna])[1])}` : ''}${p.khto ? `, ${e(p.khto)}` : ''}: ${
    p.povernuto ? `повернуто ${den(p.povernuto)}` : `<b>прибрано</b> <form class="v-riadok" method="post" action="/kabinet/zvernennia/povernuty"><input type="hidden" name="id" value="${e(p.id)}"><button class="knopka" type="submit">Повернути</button></form>`}</li>`).join('')
    : '<li>Поки нічого не прибирали.</li>';
  return storinka('Звернення', `<section class="zaholovok"><h1>Звернення людей</h1>
<p>Строк — 10 робочих днів від звернення. «Прибрати подію зараз» прибирає її одразу з карти підписника й ігор сайту — без перезбірки.
Сторінки будинків і вулиць показують лише числа: число стане меншим з наступним оновленням даних. Уже надіслані довідки — знімок на дату.</p>
${pov ? `<p class="prymitka" role="status">${e(pov)}</p>` : ''}</section>
<section class="rozdil"><h2>Чекають відповіді</h2><ul class="spysok-tekst">${vidkryti.length ? vidkryti.map(zv).join('') : '<li>Немає.</li>'}</ul></section>
<section class="rozdil"><h2>Прибрати подію без звернення</h2><div class="kartka">${formaPrybraty()}</div></section>
<section class="rozdil"><h2>Журнал прибраних подій</h2><div class="kartka"><ul class="spysok-tekst">${zh}</ul></div></section>
<section class="rozdil"><h2>Закриті звернення</h2><ul class="spysok-tekst">${zakryti.length ? zakryti.map(zv).join('') : '<li>Немає.</li>'}</ul>
<p class="prymitka">Закрите звернення сервер стирає через рік після закриття (політика, розд. 5). Журнал прибраних подій лишається — у ньому немає даних людини.</p></section>`);
}

export const CSS = `/* Сервер продажу (ZAVDANNYA-99): форми в стилі сайту (docs/STYL.md) */
.forma{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;max-width:460px}
.forma label{font-weight:600;font-size:14px;line-height:20px}
.lichylnyk{font-variant-numeric:tabular-nums}
.forma input[type=email],.forma input[name=budynok]{width:100%;box-sizing:border-box;font:inherit;padding:10px 12px;border:1.5px solid var(--mezha);border-radius:var(--radius-m);background:var(--surface);color:var(--ink);box-shadow:0 3px 0 var(--bort)}
.forma .pravyla{font-weight:400;font-size:13px}
.forma select{font:inherit;width:100%;min-width:0;padding:10px 12px;border:1.5px solid var(--mezha);border-radius:var(--radius-m);background:var(--surface);color:var(--ink);box-shadow:0 3px 0 var(--bort)}
.pomylka{color:var(--vyd);font-weight:700}
.zalyshok{margin:0 0 20px}
.abo-oplata{font-size:18px;line-height:24px;margin:8px 0 12px}
#stezhu form.forma{margin-top:16px}
.tsina{font-size:34px;line-height:40px;font-weight:800;font-variant-numeric:tabular-nums}
.v-riadok{display:inline-block;margin-left:8px}
.vkhid-google{max-width:460px;margin:0 0 16px}
.knopka-google{display:inline-flex;align-items:center;justify-content:center;gap:10px;width:100%;box-sizing:border-box;background:#fff;color:#1f1f1f;border-color:#747775}
.knopka-google__logo{flex:none}
.vkhid-google .prymitka{margin:8px 0 0}
.abo{display:flex;align-items:center;gap:10px;color:var(--ink-2,inherit);font-size:13px;margin:16px 0 0}
.abo::before,.abo::after{content:"";flex:1;border-top:1px solid var(--mezha)}
.vydalennia{margin-top:28px}
.knopka--nebezpechna{background:var(--surface);color:var(--vyd);border-color:var(--vyd)}
`;
