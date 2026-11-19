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
<meta name="referrer" content="same-origin">
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

export function formaZamovlennia({ tovar, budynok, adresa, pomylka = '' }) {
  const nazva = TS.nazvy[tovar];
  const potribenBudynok = !['pidpyska', 'rieltor', ...TS.sudova].includes(tovar);
  const proYurysta = tovar === 'spyurist'
    ? `<div class="kartka"><p><b>Що дає підписка:</b> усі статті й суди міста — таблиці по судах і роках, фільтри (суд, частина
статті, роки), вивантаження CSV (до 50 на добу), 3 довідки «стаття × суд» на місяць для клієнтів. Імен суддів немає.</p>
<p class="prymitka">Це статистика минулих рішень, а не юридична допомога. Скасувати можна в кабінеті будь-коли — доступ лишиться до кінця оплаченого місяця.</p></div>` : '';
  const pro = budynok
    ? `<p>Будинок: <b>${e(adresa)}</b> (<a href="${e(budynok)}">сторінка будинку</a>).</p>`
    : (potribenBudynok ? '<p>Вкажіть будинок: знайдіть його сторінку на сайті (<a href="/vulytsi/">покажчик вулиць</a>) і вставте посилання на неї нижче.</p>' : '');
  // ZAVDANNYA-143: без будинку — поле для посилання на сторінку будинку (раніше тут був глухий кут: на сторінках будинків
  // немає кнопки ОСББ); будинок однаково перевіряє сервер (perevirytyBudynok), адресу з форми не беремо.
  const poleBudynku = potribenBudynok && !budynok
    ? `<label for="budynok">Посилання на сторінку будинку</label>
<input id="budynok" name="budynok" required maxlength="200" placeholder="https://…/budynok/vulytsia/1/">` : '';
  const knopka = `<form class="forma" method="post" action="/api/zamovlennia">
<input type="hidden" name="tovar" value="${e(tovar)}">${budynok ? `<input type="hidden" name="budynok" value="${e(budynok)}">` : ''}${poleBudynku}
<label for="poshta">Пошта — на неї прийде посилання на довідку і вхід у кабінет</label>
<input id="poshta" name="poshta" type="email" autocomplete="email" required maxlength="254" placeholder="name@poshta.ua">
${pomylka ? `<p class="pomylka" role="alert">${e(pomylka)}</p>` : ''}
<label class="pravyla"><input type="checkbox" name="zghoda" value="tak" required> Погоджуюсь з <a href="/zahlushka/oferta.html">офертою</a> і <a href="/zahlushka/polityka.html">політикою конфіденційності</a></label>
${GALOCHKA_ODRAZU}
<button class="knopka knopka--holovna" type="submit">Перейти до оплати — ${tsina(tovar)}</button>
</form>`;
  return storinka(`${nazva} — оплата`, `<section class="zaholovok"><h1>${e(nazva)}</h1>${pro}<p class="tsina">${tsina(tovar)}</p></section>
<section class="rozdil">${proYurysta}${SHCHO_DAIE[tovar] || ''}${knopka}
<p class="prymitka">Ціну бере сервер з таблиці цін, а не з адреси сторінки. Номер картки ми не бачимо й не зберігаємо — оплату приймає платіжний сервіс партнера.</p></section>`);
}

// ZAVDANNYA-143: що саме отримує людина — ОСББ і рієлтор (ціни й кількість — з таблиці цін).
const SHCHO_DAIE = {
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

export function vkhid(povidomlennia_ = '') {
  return storinka('Вхід у кабінет', `<section class="zaholovok"><h1>Кабінет</h1>
<p>Без пароля: надішлемо на пошту посилання для входу. Воно діє 30 хвилин і лише один раз.</p></section>
<section class="rozdil"><form class="forma" method="post" action="/kabinet/vkhid">
<label for="poshta">Пошта, з якою купували</label>
<input id="poshta" name="poshta" type="email" autocomplete="email" required maxlength="254" placeholder="name@poshta.ua">
<button class="knopka knopka--holovna" type="submit">Надіслати посилання</button></form>
${povidomlennia_ ? `<p class="prymitka" role="status">${e(povidomlennia_)}</p>` : ''}</section>`);
}

const STATUS_DOVIDKY = { v_cherzi: 'готується', hotuietsia: 'готується', hotova: 'готова', vydaleno: 'файл видалено за строком зберігання', pomylka: 'не вдалося — напишіть партнеру, повернемо гроші або зробимо ще раз' };
const NAZVA_PIDPYSKY = { pidpyska: 'Підписка', rieltor: 'Підписка для рієлтора', osbb: 'Будинок для ОСББ', spyurist: 'Підписка юриста «Практика»' };
const VYD_DOVIDKY = { povnyi: 'повний звіт', dovidka: 'довідка', sp: 'судова практика', osbb: 'щомісячна довідка ОСББ' };

const posylannia = (d) => (d.status === 'hotova' ? `<a href="/dovidka/${e(d.id)}/">відкрити</a>` : e(STATUS_DOVIDKY[d.status]));

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
<form class="forma" method="post" action="/kabinet/dovidka"><label for="obiekt">Новий об'єкт — посилання на сторінку будинку</label>
<input id="obiekt" name="budynok" required maxlength="200" placeholder="https://…/budynok/vulytsia/1/">
<button class="knopka knopka--holovna" type="submit">Довідка на цей будинок</button></form>
<p class="prymitka">Понад ${p.dovidok} на місяць — ${tsina('dodatkova')} за довідку (спершу спитаємо). Сторінку будинку знайдете в <a href="/vulytsi/">покажчику вулиць</a>.</p></div></section>`;
}

export function kabinet({ poshta, dovidky, stezhu, pidpysky, dostupno, povidomlennia: pov = '', bali = null }) {
  const ryadky = dovidky.length ? dovidky.map((d) => `<li><b>${e(d.adresa)}</b> — ${VYD_DOVIDKY[d.rezhym] || 'довідка'}, ${data(d.stvoreno)}: ${posylannia(d)}</li>`).join('')
    : '<li>Поки немає довідок.</li>';
  const stezh = stezhu.length ? stezhu.map((s) => `<li><a href="${e(s.budynok)}">${e(s.adresa)}</a>
<form class="v-riadok" method="post" action="/kabinet/stezhu/prybraty"><input type="hidden" name="budynok" value="${e(s.budynok)}"><button class="knopka" type="submit">Прибрати</button></form>
<form class="v-riadok" method="post" action="/kabinet/dovidka"><input type="hidden" name="budynok" value="${e(s.budynok)}"><button class="knopka" type="submit">Довідка</button></form></li>`).join('')
    : '<li>Додайте адресу — тут будуть будинки, за якими стежите.</li>';
  const pidp = pidpysky.length ? pidpysky.map((p) => `<li><b>${e(NAZVA_PIDPYSKY[p.tovar])}</b>${p.adresa ? ` (${e(p.adresa)})` : ''} — ${
    p.status === 'aktyvna' ? `діє до ${data(p.diie_do)}, ${p.tovar === 'osbb' ? 'довідка приходить сама щомісяця' : `довідок цього місяця лишилось: ${p.zalyshok}`}${p.tovar === 'spyurist' ? ' — <a href="/pidpysnyk/praktyka/">відкрити практику</a>' : ''}
<form class="v-riadok" method="post" action="/kabinet/skasuvaty"><input type="hidden" name="pidpyska" value="${e(p.id)}"><button class="knopka" type="submit">Скасувати підписку</button></form>`
      : p.zaBali ? `за бали, діє до ${data(p.diie_do)}, без продовження` : p.status === 'skasovana' ? `скасована, діє до ${data(p.diie_do)}` : 'очікує оплати'}</li>`).join('')
    : `<li>Немає. <a href="/oplata/?tovar=pidpyska">Підписка — ${tsina('pidpyska')}</a></li>`;
  const osbb = pidpysky.filter((p) => p.tovar === 'osbb').map((p) => rozdilOsbb(p, dovidky)).join('');
  const rieltor = pidpysky.find((p) => p.tovar === 'rieltor');
  return storinka('Кабінет', `<section class="zaholovok"><h1>Кабінет</h1><p>${e(poshta)}</p>
${pov ? `<p class="prymitka" role="status">${e(pov)}</p>` : ''}</section>
${osbb}${rieltor ? rozdilRieltora(rieltor, dovidky) : ''}
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
.lichylnyk{font-variant-numeric:tabular-nums}
.forma input[type=email],.forma input[name=budynok]{font:inherit;padding:10px 12px;border:1.5px solid var(--mezha);border-radius:var(--radius-m);background:var(--surface);color:var(--ink);box-shadow:0 3px 0 var(--bort)}
.forma .pravyla{font-weight:400;font-size:13px}
.forma select{font:inherit;width:100%;min-width:0;padding:10px 12px;border:1.5px solid var(--mezha);border-radius:var(--radius-m);background:var(--surface);color:var(--ink);box-shadow:0 3px 0 var(--bort)}
.pomylka{color:var(--vyd);font-weight:700}
.tsina{font-size:34px;line-height:40px;font-weight:800;font-variant-numeric:tabular-nums}
.v-riadok{display:inline-block;margin-left:8px}
`;
