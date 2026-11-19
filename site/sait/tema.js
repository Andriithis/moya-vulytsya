// День і ніч сайту «Моя вулиця» (ZAVDANNYA-45, MV-58). Підключається в <head> до стилів, щоб сторінка одразу
// малювалася в обраній темі без спалаху. Вибір людини пам'ятаємо в цьому браузері; поки людина не обирала —
// тема як у налаштуваннях телефона чи комп'ютера (Д-3, ZAVDANNYA-114), а без них — світла (MV-55).
// Кнопки з атрибутом data-tema-perem перемикають тему; карта слухає подію «mv-tema» і перемальовує підкладку.
(function () {
  'use strict';
  var KLYUCH = 'mv-tema';
  var d = document.documentElement;
  function zberezhena() { try { return localStorage.getItem(KLYUCH); } catch (e) { return null; } }
  function postavyty(t) {
    d.setAttribute('data-t', t === 'temna' ? 'temna' : 'svitla');
  }
  var systemna = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  function pochatkova() { return zberezhena() || (systemna && systemna.matches ? 'temna' : 'svitla'); }
  postavyty(pochatkova());

  function pidpysy() {
    var temna = d.getAttribute('data-t') === 'temna';
    var t = temna ? 'Денна тема' : 'Нічна тема';
    document.querySelectorAll('[data-tema-perem]').forEach(function (b) {
      b.setAttribute('aria-label', t); b.title = t;
    });
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute('content', getComputedStyle(d).getPropertyValue('--ground').trim() || m.getAttribute('content'));
  }
  // Людина змінила тему телефона, а на сайті сама не обирала — сайт іде слідом.
  function pryZmini() {
    if (zberezhena()) return;
    var t = pochatkova();
    postavyty(t); pidpysy();
    document.dispatchEvent(new CustomEvent('mv-tema', { detail: t }));
  }
  if (systemna) {
    if (systemna.addEventListener) systemna.addEventListener('change', pryZmini);
    else if (systemna.addListener) systemna.addListener(pryZmini);
  }

  document.addEventListener('DOMContentLoaded', function () {
    pidpysy();
    document.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('[data-tema-perem]');
      if (!b) return;
      var nova = d.getAttribute('data-t') === 'temna' ? 'svitla' : 'temna';
      postavyty(nova);
      try { localStorage.setItem(KLYUCH, nova); } catch (x) { /* приватний режим — лише до кінця сторінки */ }
      pidpysy();
      document.dispatchEvent(new CustomEvent('mv-tema', { detail: nova }));
    });
  });
})();

// Застосунок Android (MV-126, ZAVDANNYA-144): у застосунку нічого не продаємо — купують на сайті, а в застосунку
// лише дивляться куплене. Застосунок відкриває сайт з ?dzherelo=dodatok (старт і ярлики, android/twa-manifest.json),
// а Chrome при запуску оболонки дає document.referrer = android-app://ua.moyavulytsya.app. Позначку пам'ятаємо
// лише в цій вкладці (sessionStorage): у звичайному Chrome на тому ж телефоні ціни лишаються.
// Що ховаємо: блоки цін (.tsiny), кнопки й посилання на оплату (/oplata/), рядки «… — 199 грн»; сторінка /oplata/
// у застосунку — лише «у застосунку нічого не продаємо», без посилань на оплату (правила оплати Google Play, розд. 4).
// Поки сторінку не очищено, вона невидима (sait.css, html[data-dodatok="hotuiu"]) — без спалаху цін.
(function () {
  'use strict';
  var d = document.documentElement;
  var u = false;
  try {
    u = /[?&]dzherelo=dodatok(&|$)/.test(location.search) || document.referrer.indexOf('android-app://ua.moyavulytsya.app') === 0;
    if (u) sessionStorage.setItem('mv-dodatok', '1');
    else u = sessionStorage.getItem('mv-dodatok') === '1';
  } catch (e) { /* без сховища — лише ця сторінка */ }
  if (!u) return;
  d.setAttribute('data-dodatok', 'hotuiu');
  // «; довідка — 199 грн», « — 399 грн на місяць», «1 490 грн»: ціну разом зі своїм уривком речення.
  var TSINA = /(?:\s*[;,]\s*[^;,]*?|\s*[—–-]\s*)?\d[\d\s]*\s?грн(?:\s(?:на|за)\s[а-яіїєґ']+)?/gi;
  function ochystyty() {
    if (/^\/oplata\//.test(location.pathname)) {
      var m = document.querySelector('main') || document.body;
      m.innerHTML = '<section class="rozdil"><h1>У застосунку нічого не продаємо</h1>' +
        '<p>Тут — карта, сторінки будинків і вулиць, ігри й ваш кабінет. Довідки й підписку, куплені раніше, видно в кабінеті.</p>' +
        '<p><a class="knopka knopka--holovna" href="/">На головну</a> <a class="knopka" href="/kabinet/">Кабінет</a></p></section>';
    }
    document.querySelectorAll('.tsiny, .tovar__tsina, .knopka__skoro, a[href*="/oplata/"]').forEach(function (el) { el.remove(); });
    // Вітрини: увесь розділ «Що можна замовити» з картками товарів і примітки про оплату.
    document.querySelectorAll('.tovary').forEach(function (el) { (el.closest('section') || el).hidden = true; });
    document.querySelectorAll('.prymitka').forEach(function (el) { if (/оплат/i.test(el.textContent)) el.hidden = true; });
    var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    var vuzly = [];
    while (w.nextNode()) if (w.currentNode.nodeValue.indexOf('грн') >= 0) vuzly.push(w.currentNode);
    vuzly.forEach(function (v) {
      v.nodeValue = v.nodeValue.replace(TSINA, '');
      var b = v.parentElement;
      if (b && b !== document.body && !b.textContent.trim()) b.hidden = true;
    });
    // Розділ, у якому після цього лишився сам заголовок («Повідомити про запуск»), — теж геть.
    document.querySelectorAll('main section').forEach(function (s) {
      var t = s.textContent, h = s.querySelector('h1, h2');
      if (h && !t.replace(h.textContent, '').trim()) s.hidden = true;
    });
  }
  document.addEventListener('DOMContentLoaded', function () {
    try { ochystyty(); } finally { d.setAttribute('data-dodatok', 'tak'); }
  });
})();
