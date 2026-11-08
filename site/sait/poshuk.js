// Пошук вулиці (ZAVDANNYA-10): головна і покажчик. Покажчик вулиць — файл vulytsi/pokazhchyk.json.
// Без запитів назовні: шукаємо у власному файлі; без скриптів працює покажчик за абеткою.
(function () {
  'use strict';
  var pole = document.getElementById('poshuk-vulytsi');
  var spysok = document.getElementById('poshuk-spysok');
  if (!pole || !spysok) return;
  var KOREN = document.documentElement.getAttribute('data-koren') || '/';
  var vulytsi = null;

  function norm(t) {
    return (t || '').toLowerCase().replace(/[ʼ’'`]/g, '').replace(/ґ/g, 'г').replace(/[-.,]/g, ' ').replace(/\s+/g, ' ').trim();
  }
  function chyslo(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }

  function zavantazhyty() {
    if (vulytsi) return Promise.resolve(vulytsi);
    return fetch(KOREN + 'vulytsi/pokazhchyk.json', { credentials: 'omit' }).then(function (v) { return v.json(); })
      .then(function (d) { vulytsi = d.map(function (v) { return { s: v[0], n: v[1], r: v[2], k: v[3], p: norm(v[1] + ' ' + (v[4] || '')) }; }); return vulytsi; });
  }

  function pokazaty() {
    var z = norm(pole.value);
    spysok.textContent = '';
    if (z.length < 2) { spysok.hidden = true; return; }
    zavantazhyty().then(function (vs) {
      var slova = z.split(' ');
      var znaideni = vs.filter(function (v) { return slova.every(function (s) { return v.p.indexOf(s) !== -1; }); })
        .sort(function (a, b) { return b.k - a.k; }).slice(0, 8);
      spysok.textContent = '';
      if (!znaideni.length) {
        var li0 = document.createElement('li'); li0.className = 'poshuk__nema';
        li0.textContent = 'Такої вулиці в даних немає. Перевірте назву або подивіться покажчик.';
        spysok.appendChild(li0);
      }
      znaideni.forEach(function (v) {
        var li = document.createElement('li');
        var a = document.createElement('a');
        a.href = KOREN + 'vulytsia/' + v.s + '/';
        a.appendChild(document.createTextNode(v.n));
        var m = document.createElement('small');
        m.textContent = (v.r ? v.r + ' · ' : '') + chyslo(v.k) + ' под.';
        a.appendChild(m);
        li.appendChild(a);
        spysok.appendChild(li);
      });
      spysok.hidden = false;
    });
  }
  pole.addEventListener('input', pokazaty);
  pole.form && pole.form.addEventListener('submit', function (e) {
    e.preventDefault();
    var pershe = spysok.querySelector('a');
    if (pershe) window.location.href = pershe.href;
  });
})();
