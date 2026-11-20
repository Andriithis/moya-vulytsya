// Поле «Будинок — вулиця й номер» у формах сервера продажу (ZAVDANNYA-150, п. 6): ОСББ, пакет, рієлтор «Мої об'єкти»,
// «Стежу». Підказки — з того самого файлу, що пошук «Мій будинок» (vulytsi/budynky.json), у <datalist> поля.
// Без скрипта поле теж працює: адресу словами розбирає сервер (site/worker/prodazh/logika.js, znaityBudynok).
(function () {
  'use strict';
  var KOREN = document.documentElement.getAttribute('data-koren') || '/';
  var budynky = null;
  function norm(t) {
    return (t || '').toLowerCase().replace(/[ʼ’'`]/g, '').replace(/ґ/g, 'г').replace(/[-.,«»"]/g, ' ').replace(/\s+/g, ' ').trim();
  }
  function normNomer(t) { return (t || '').toLowerCase().replace(/[\s-]/g, '').replace(/\\/g, '/'); }
  function zavantazhyty() {
    if (budynky) return Promise.resolve(budynky);
    return fetch(KOREN + 'vulytsi/budynky.json', { credentials: 'omit' })
      .then(function (v) { return v.ok ? v.json() : []; }).catch(function () { return []; })
      .then(function (d) { budynky = d.map(function (v) { return { n: v[0], p: norm(v[0] + ' ' + (v[2] || '')), b: v[3] }; }); return budynky; });
  }
  // «Оболонський 16» → назва й початок номера; без номера — лише назва
  function rozibraty(z) {
    var m = /^(.*?)[\s,]+(?:буд(?:инок)?\.?\s*)?(?:№\s*)?(\d+[^\s,]*(?:\s?[а-яіїєa-z])?)?$/i.exec(z.trim());
    return m && m[1].trim() ? { nazva: m[1], nomer: m[2] || '' } : { nazva: z, nomer: '' };
  }
  function pidkazky(pole, spysok) {
    var z = pole.value;
    if (norm(z).length < 3) { spysok.textContent = ''; return; }
    zavantazhyty().then(function (bs) {
      if (pole.value !== z) return;
      var a = /\d/.test(z) ? rozibraty(z) : { nazva: z, nomer: '' };
      var slova = norm(a.nazva).split(' ').filter(Boolean), nn = normNomer(a.nomer), vyhid = [];
      bs.forEach(function (v) {
        if (vyhid.length >= 12 || !slova.every(function (s) { return v.p.indexOf(s) !== -1; })) return;
        v.b.forEach(function (x) {
          if (vyhid.length < 12 && (!nn || normNomer(x[0]).indexOf(nn) === 0)) vyhid.push(v.n + ', ' + x[0]);
        });
      });
      spysok.textContent = '';
      vyhid.forEach(function (t) { var o = document.createElement('option'); o.value = t; spysok.appendChild(o); });
    });
  }
  document.querySelectorAll('input[data-budynky]').forEach(function (pole) {
    var spysok = document.getElementById(pole.getAttribute('list'));
    if (!spysok) return;
    pole.addEventListener('input', function () { pidkazky(pole, spysok); });
  });
})();
