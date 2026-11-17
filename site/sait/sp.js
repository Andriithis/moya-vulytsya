// «Судова практика» (ZAVDANNYA-111): розміри з даних — через CSSOM (CSP без style): ширина смуг, висота стовпчиків років.
// Платних чисел у сторінці немає — фільтри за замком лише показують, що буде в платній частині.
(function () {
  'use strict';
  document.querySelectorAll('[data-vys],[data-shyr]').forEach(function (e) {
    if (e.hasAttribute('data-vys')) e.style.height = e.getAttribute('data-vys') + 'px';
    if (e.hasAttribute('data-shyr')) e.style.width = e.getAttribute('data-shyr') + '%';
  });
})();
