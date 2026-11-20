// Пошук вулиці й будинку (ZAVDANNYA-10; будинок і старі назви — ZAVDANNYA-110, Т-2): покажчик і «Мій будинок».
// Вулиці — vulytsi/pokazhchyk.json; будинки — vulytsi/budynky.json (вантажиться, лише коли в запиті є номер).
// Без запитів назовні: шукаємо у власних файлах; без скриптів працює покажчик за абеткою.
(function () {
  'use strict';
  var pole = document.getElementById('poshuk-vulytsi');
  var spysok = document.getElementById('poshuk-spysok');
  if (!pole || !spysok) return;
  var KOREN = document.documentElement.getAttribute('data-koren') || '/';
  var vulytsi = null;
  var budynky = null;

  var P = window.MVPoshuk;   // спільне ядро — sait/poshuk-spilne.js (ZAVDANNYA-177): помилка в літері, народні назви
  var norm = P.norm;
  function chyslo(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }

  function zavantazhyty() {
    if (vulytsi) return Promise.resolve(vulytsi);
    return fetch(KOREN + 'vulytsi/pokazhchyk.json', { credentials: 'omit' }).then(function (v) { return v.json(); })
      .then(function (d) { vulytsi = d.map(function (v) { return { s: v[0], n: v[1], r: v[2], k: v[3], p: norm(v[1] + ' ' + (v[4] || '')) }; }); return vulytsi; });
  }
  function zavantazhytyBudynky() {
    if (budynky) return Promise.resolve(budynky);
    return fetch(KOREN + 'vulytsi/budynky.json', { credentials: 'omit' })
      .then(function (v) { return v.ok ? v.json() : []; })
      .catch(function () { return []; })
      .then(function (d) { budynky = d.map(function (v) { return { n: v[0], p: norm(v[0] + ' ' + (v[2] || '')), b: v[3] }; }); return budynky; });
  }

  function punkt(href, tekst, dribno) {
    var li = document.createElement('li');
    var a = document.createElement('a');
    a.href = href;
    a.appendChild(document.createTextNode(tekst));
    if (dribno) { var m = document.createElement('small'); m.textContent = dribno; a.appendChild(m); }
    li.appendChild(a);
    spysok.appendChild(li);
  }
  function nemaye(tekst) {
    var li0 = document.createElement('li'); li0.className = 'poshuk__nema';
    li0.textContent = tekst;
    spysok.appendChild(li0);
  }
  function pokazaty() {
    var syryi = pole.value;
    var z = norm(syryi);
    spysok.textContent = '';
    if (z.length < 2) { spysok.hidden = true; return; }
    var adr = /\d/.test(syryi) ? P.rozibraty(syryi) : null;
    Promise.all([zavantazhyty(), adr ? zavantazhytyBudynky() : [], P.mistsevosti()]).then(function (r) {
      if (norm(pole.value) !== z) return;
      var vs = r[0], bs = r[1], ms = adr ? [] : P.znaityMistsevosti(syryi, r[2]);
      spysok.textContent = '';
      var slova = norm(adr ? adr.nazva : syryi).split(' ').filter(Boolean);
      var tochni = [], shozhi = [];
      vs.forEach(function (v) { var k = P.zbih(slova, v.p); if (k === 0) tochni.push(v); else if (k === 1) shozhi.push(v); });
      var vuh = function (a, b) { return b.k - a.k; };
      tochni.sort(vuh); shozhi.sort(vuh);
      var pokazano = 0;
      ms.slice(0, 3).forEach(function (m) {   // «Троєщина» → район (народна назва з даних)
        m.rayony.forEach(function (rr) { if (pokazano < 8) { punkt(rr[1], m.nazva + ' — ' + rr[0] + ' район', 'місцевість'); pokazano++; } });
      });
      var znaideni = tochni.length ? tochni : shozhi;
      var budynky = adr ? P.budynky(adr, bs, 8) : { tochni: [], shozhi: [] };
      var bud = budynky.tochni.length ? budynky.tochni : budynky.shozhi;
      if (!tochni.length && !budynky.tochni.length && (shozhi.length || bud.length)) nemaye('Можливо, ви мали на увазі:');
      bud.forEach(function (x) { if (pokazano < 8) { punkt(x.url, x.nazva, 'будинок'); pokazano++; } });
      if (adr && !bud.length && znaideni.length) {
        nemaye('Будинку ' + adr.nomer + ' в даних немає: без скарг 1551 і подій сторінки будинку немає. Ось вулиця:');
      }
      znaideni.slice(0, Math.max(0, 8 - pokazano)).forEach(function (v) {
        punkt(KOREN + 'vulytsia/' + v.s + '/', v.n, (v.r ? v.r + ' · ' : '') + chyslo(v.k) + ' под.');
      });
      if (!pokazano && !znaideni.length) {
        nemaye('Такої вулиці в даних немає. Перевірте назву або подивіться покажчик.');
      }
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
