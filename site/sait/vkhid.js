// Мітки джерела (ZAVDANNYA-153): який вхід і який ролик привели покупця.
// Реклама веде на вхід з міткою: /orenda/?dzherelo=tt0412. На вході (<div class="vkhid" data-vkhid="or">) мітка стає
// «or-tt0412», без мітки — «or». Ролик, що веде прямо на сторінку будинку з ?dzherelo=…, — мітка як є.
// Мітку пам'ятаємо лише в цій вкладці (перша мітка не з входу не затирається внутрішніми посиланнями) (sessionStorage, без кукі) і ставимо в кнопки оплати й форми на будь-якій сторінці,
// тож у заявці (канал «oplata-dovidka-or-tt0412») видно, звідки людина прийшла. Канал обмежено 40 знаками.
(function () {
  'use strict';
  var KLYUCH = 'mv-dzherelo';
  var MAKS_MITKY = 16;
  function chystyty(t, maks) {
    var k = String(t || '').toLowerCase().replace(/[^a-z0-9-]/g, '').replace(/-+/g, '-').replace(/^-|-$/g, '');
    return k.slice(0, maks).replace(/-$/, '');
  }
  var mitka = '';
  try { mitka = chystyty(new URLSearchParams(location.search).get('dzherelo'), MAKS_MITKY); } catch (e) { mitka = ''; }
  if (mitka === 'dodatok') mitka = '';   // ознака застосунку (tema.js), не реклама
  var vkhid = document.querySelector('[data-vkhid]');
  var kod = vkhid ? chystyty(vkhid.getAttribute('data-vkhid'), 3) : '';
  var dzherelo = kod ? kod + (mitka ? '-' + mitka : '') : mitka;
  var skhovyshche = null;
  try { skhovyshche = window.sessionStorage; } catch (e) { skhovyshche = null; }
  if (skhovyshche) {
    try {
      // Вхід — завжди нова мітка. Інша сторінка з ?dzherelo= (ролик веде прямо на будинок) — лише якщо мітки ще немає:
      // внутрішні посилання сайту теж мають ?dzherelo= (holovna, budynok…), вони не мають затирати рекламу.
      var bula = chystyty(skhovyshche.getItem(KLYUCH), 20);
      if (dzherelo && (kod || !bula)) skhovyshche.setItem(KLYUCH, dzherelo);
      else dzherelo = bula;
    } catch (e) { /* приватний режим — лише ця сторінка */ }
  }
  // На /oplata/ мітка вже в адресі сторінки, а канал форми («oplata-<товар>-<мітка>») складає oplata.js — не чіпаємо.
  if (!dzherelo || /^\/oplata\//.test(location.pathname)) return;
  var posylannia = document.querySelectorAll('a[href*="/oplata/"], a[href*="/zahlushka/?"]');
  for (var i = 0; i < posylannia.length; i++) {
    var a = posylannia[i];
    var u;
    try { u = new URL(a.getAttribute('href'), location.href); } catch (e) { continue; }
    if (u.origin !== location.origin) continue;
    u.searchParams.set('dzherelo', dzherelo);
    a.setAttribute('href', u.pathname + u.search + u.hash);
  }
})();
