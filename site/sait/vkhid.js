// Мітка входу з реклами (ZAVDANNYA-153): /dlia/<людина>/?dzherelo=<мітка ролика> → «vh-<людина>-<мітка>» у цій вкладці;
// далі кожна кнопка оплати (/oplata/?…) несе її як dzherelo, і сервер продажу пише її каналом пошти «скоро» чи замовлення
// (site/worker/prodazh/formy.js, kanal: [a-z0-9-], ≤ 40). Лише мітка джерела — без пошти, імені чи адреси; не cookie.
(function () {
  'use strict';
  var KLYUCH = 'mv-vkhid';
  var mitka = '';
  var vkhid = document.querySelector('[data-vkhid]');
  try {
    if (vkhid) {
      var d = (new URLSearchParams(window.location.search).get('dzherelo') || '').toLowerCase().replace(/[^a-z0-9-]/g, '');
      mitka = (vkhid.getAttribute('data-vkhid') + (d ? '-' + d : '')).slice(0, 25).replace(/-+$/, '');
      window.sessionStorage.setItem(KLYUCH, mitka);
    } else {
      mitka = window.sessionStorage.getItem(KLYUCH) || '';
    }
  } catch (e) { mitka = ''; }
  if (!/^[a-z0-9-]{1,25}$/.test(mitka)) return;
  Array.prototype.forEach.call(document.querySelectorAll('a[href*="/oplata/"]'), function (a) {
    var u = new URL(a.getAttribute('href'), window.location.href);
    if (u.origin !== window.location.origin || u.pathname !== '/oplata/') return;
    u.searchParams.set('dzherelo', mitka);
    a.setAttribute('href', u.pathname + u.search + u.hash);
  });
})();
