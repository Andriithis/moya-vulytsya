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

  function norm(t) {
    return (t || '').toLowerCase().replace(/[ʼ’'`]/g, '').replace(/ґ/g, 'г').replace(/[-.,]/g, ' ').replace(/\s+/g, ' ').trim();
  }
  // «2а», «2-А», «2 а» — один номер; «15/5» лишається з рискою.
  function normNomer(t) { return (t || '').toLowerCase().replace(/[\s-]/g, '').replace(/\\/g, '/'); }
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

  // «Гоголівська 2а», «Хрещатик, буд. 22», «вул. Лесі Українки 28/2» → назва й номер.
  function rozibraty(z) {
    var m = /^(.*?)[\s,]+(?:буд(?:инок)?\.?\s*)?(?:№\s*)?(\d+[^\s,]*(?:\s?[а-яіїєa-z])?)$/i.exec(z.trim());
    return m && m[1].trim() ? { nazva: m[1], nomer: m[2] } : null;
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
  function zbih(slova, p) { return slova.every(function (s) { return p.indexOf(s) !== -1; }); }

  function pokazaty() {
    var syryi = pole.value;
    var z = norm(syryi);
    spysok.textContent = '';
    if (z.length < 2) { spysok.hidden = true; return; }
    var adr = /\d/.test(syryi) ? rozibraty(syryi) : null;
    var obitsianka = adr ? Promise.all([zavantazhyty(), zavantazhytyBudynky()]) : zavantazhyty().then(function (vs) { return [vs, []]; });
    obitsianka.then(function (r) {
      if (norm(pole.value) !== z) return;
      var vs = r[0], bs = r[1];
      spysok.textContent = '';
      var slova = norm(adr ? adr.nazva : syryi).split(' ').filter(Boolean);
      var znaideni = vs.filter(function (v) { return zbih(slova, v.p); }).sort(function (a, b) { return b.k - a.k; });
      var pokazano = 0;
      if (adr) {
        var nn = normNomer(adr.nomer);
        bs.filter(function (v) { return zbih(slova, v.p); }).forEach(function (v) {
          v.b.forEach(function (x) {
            if (pokazano < 8 && normNomer(x[0]) === nn) { punkt(x[1], v.n + ', ' + x[0], 'будинок'); pokazano++; }
          });
        });
        if (!pokazano && znaideni.length) {
          nemaye('Будинку ' + adr.nomer + ' в даних немає: без скарг 1551 і подій сторінки будинку немає. Ось вулиця:');
        }
      }
      znaideni.slice(0, 8 - pokazano).forEach(function (v) {
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
