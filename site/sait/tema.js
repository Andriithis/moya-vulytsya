// День і ніч сайту «Моя вулиця» (ZAVDANNYA-45, MV-58). Підключається в <head> до стилів, щоб сторінка одразу
// малювалася в обраній темі без спалаху. Світла — головна (MV-55); вибір людини пам'ятаємо в цьому браузері.
// Кнопки з атрибутом data-tema-perem перемикають тему; карта слухає подію «mv-tema» і перемальовує підкладку.
(function () {
  'use strict';
  var KLYUCH = 'mv-tema';
  var d = document.documentElement;
  function zberezhena() { try { return localStorage.getItem(KLYUCH); } catch (e) { return null; } }
  function postavyty(t) {
    d.setAttribute('data-t', t === 'temna' ? 'temna' : 'svitla');
  }
  postavyty(zberezhena());

  function pidpysy() {
    var temna = d.getAttribute('data-t') === 'temna';
    var t = temna ? 'Денна тема' : 'Нічна тема';
    document.querySelectorAll('[data-tema-perem]').forEach(function (b) {
      b.setAttribute('aria-label', t); b.title = t;
    });
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute('content', getComputedStyle(d).getPropertyValue('--ground').trim() || m.getAttribute('content'));
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
