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
