// «Судова практика» (ZAVDANNYA-111): розміри з даних — через CSSOM (CSP без style): ширина смуг, висота стовпчиків років.
// Платних чисел у сторінці немає — фільтри за замком лише показують, що буде в платній частині.
// ZAVDANNYA-135: пошук у покажчику — за номером статті («130», «ст 130», «173-2») і своїми словами («п'яний за кермом»).
(function () {
  'use strict';
  document.querySelectorAll('[data-vys],[data-shyr]').forEach(function (e) {
    if (e.hasAttribute('data-vys')) e.style.height = e.getAttribute('data-vys') + 'px';
    if (e.hasAttribute('data-shyr')) e.style.width = e.getAttribute('data-shyr') + '%';
  });

  var pole = document.getElementById('sp-poshuk');
  if (!pole) return;
  var rez = document.getElementById('sp-poshuk-rez');
  var statti = Array.prototype.slice.call(document.querySelectorAll('.sp-stattia'));
  var ZAIVI = { 'за': 1, 'в': 1, 'у': 1, 'на': 1, 'з': 1, 'із': 1, 'і': 1, 'й': 1, 'та': 1, 'ст': 1, 'стаття': 1, 'статті': 1,
    'частина': 1, 'ч': 1, 'купап': 1, 'кк': 1, 'мене': 1, 'мені': 1, 'що': 1, 'буде': 1, 'якщо': 1, 'по': 1 };
  function norm(t) {
    return String(t || '').toLowerCase().replace(/[ʼ’'`"«»]/g, '').replace(/ё/g, 'е').replace(/[^0-9a-zа-яіїєґ\- ]+/g, ' ');
  }
  function osnova(s) { return s.length > 5 ? s.slice(0, Math.max(4, s.length - 2)) : s; }
  var slova = statti.map(function (li) {
    return norm(li.getAttribute('data-slova')).split(/[\s,-]+/).filter(Boolean);
  });
  function shukaty() {
    var q = norm(pole.value).trim();
    if (!q) {
      statti.forEach(function (li) { li.hidden = false; });
      document.querySelectorAll('.sp-kodeks').forEach(function (s) { s.hidden = false; });
      rez.textContent = '';
      return;
    }
    var nomer = (q.match(/\d+(?:-\d+)?/) || [''])[0];
    var tokeny = q.replace(/\d+(?:-\d+)?/g, ' ').split(/\s+/).filter(function (t) { return t && !ZAIVI[t]; });
    var znaideno = 0;
    statti.forEach(function (li, i) {
      var tak;
      if (nomer) tak = li.getAttribute('data-nomer') === nomer || li.getAttribute('data-nomer').indexOf(nomer + '-') === 0;
      else {
        var bal = 0;
        tokeny.forEach(function (t) {
          var o = osnova(t);
          if (slova[i].some(function (s) { return s.indexOf(o) === 0 || (s.length >= 4 && o.indexOf(osnova(s)) === 0); })) bal++;
        });
        tak = tokeny.length > 0 && bal >= Math.max(1, Math.ceil(tokeny.length / 2));
      }
      li.hidden = !tak;
      if (tak) znaideno++;
    });
    document.querySelectorAll('.sp-kodeks').forEach(function (s) { s.hidden = !s.querySelector('.sp-stattia:not([hidden])'); });
    rez.textContent = znaideno ? 'Знайдено статей: ' + znaideno + '.' :
      'Не знайшли. Спробуйте номер статті з протоколу чи обвинувального акта або інші слова. Поки що тут 11 найчастіших статей.';
  }
  pole.addEventListener('input', shukaty);
  var q = new URLSearchParams(location.search).get('q');
  if (q) { pole.value = q; shukaty(); }
})();
