// Пошук на головній і /karta/ прощає помилку й знає народні назви (ZAVDANNYA-177; ZVIT-165, п. 3).
// Саме поле й підказки малює karta.js (його тут не змінюємо — ним займається ZAVDANNYA-174). Цей скрипт лише дописує
// в той самий список #pidkazky те, чого karta.js не вміє:
//  * «Такої назви немає» → «Можливо, ви мали на увазі:» з вулицями й будинками, схожими з точністю до 1–2 літер;
//  * народна назва місцевості («Троєщина») → її район — з будь-якими іншими підказками.
// Ті самі правила, що в «Мій будинок» і входах: sait/poshuk-spilne.js. Коли karta.js візьме MVPoshuk сам, цей файл зайвий.
(function () {
  'use strict';
  var P = window.MVPoshuk;
  var pole = document.getElementById('poshuk-karty');
  var ul = document.getElementById('pidkazky');
  var konteiner = document.getElementById('karta-mista');
  if (!P || !pole || !ul) return;
  var KOREN = document.documentElement.getAttribute('data-koren') || '/';
  // ZVIT-165, п. 9: на телефоні підказка поля каже, що можна ввести й вулицю, і район (karta.js ставить «Ваша адреса»).
  if (window.matchMedia && window.matchMedia('(max-width: 700px)').matches) pole.placeholder = 'Адреса, вулиця або район';
  var VULYTSI = null, BUDYNKY = null;

  function vulytsi() {
    if (VULYTSI) return Promise.resolve(VULYTSI);
    var url = (konteiner && konteiner.getAttribute('data-poshuk')) || KOREN + 'karta/poshuk.json';
    return fetch(url, { credentials: 'omit' }).then(function (v) { return v.ok ? v.json() : { vulytsi: [] }; })
      .catch(function () { return { vulytsi: [] }; })
      .then(function (d) {
        VULYTSI = (d.vulytsi || []).map(function (v) {
          return { nazva: v[0], dod: v[1] ? v[1] + ' район' : 'вулиця', url: KOREN + 'vulytsia/' + v[2] + '/', n: v[5], p: P.norm(v[0] + ' ' + (v[6] || '')) };
        });
        return VULYTSI;
      });
  }
  function budynky() {
    if (BUDYNKY) return Promise.resolve(BUDYNKY);
    return fetch(KOREN + 'vulytsi/budynky.json', { credentials: 'omit' })
      .then(function (v) { return v.ok ? v.json() : []; }).catch(function () { return []; })
      .then(function (d) { BUDYNKY = d.map(function (v) { return { n: v[0], p: P.norm(v[0] + ' ' + (v[2] || '')), b: v[3] }; }); return BUDYNKY; });
  }

  function li(nazva, dod, url) {
    var x = document.createElement('li');
    x.className = 'pd'; x.setAttribute('role', 'option'); x.setAttribute('aria-selected', 'false'); x.setAttribute('data-url', url);
    // як пункти karta.js: назва жирно, під нею дрібно — що це
    var sp = document.createElement('span'), b = document.createElement('b'); b.textContent = nazva; sp.appendChild(b);
    var s = document.createElement('small'); s.textContent = dod;
    x.appendChild(sp); x.appendChild(s);
    return x;
  }
  function zaholovok(t) { var x = document.createElement('li'); x.className = 'porozh pd'; x.textContent = t; return x; }

  function doplnyty() {
    if (ul.hidden) return;
    var z = pole.value;
    if (P.norm(z).length < 2) return;
    var porozh = ul.querySelector('.porozh:not(.pd)');
    var adr = /\d/.test(z) ? P.rozibraty(z) : null;
    Promise.all([P.mistsevosti(), porozh ? vulytsi() : [], porozh && adr ? budynky() : []]).then(function (r) {
      if (pole.value !== z) return;
      var ms = adr ? [] : P.znaityMistsevosti(z, r[0]);
      var dodaty = [];
      ms.slice(0, 3).forEach(function (m) {
        m.rayony.forEach(function (rr) { dodaty.push(li(m.nazva + ' — ' + rr[0] + ' район', 'місцевість', rr[1])); });
      });
      if (porozh) {
        var shozhi = [];
        if (adr) {
          var bb = P.budynky(adr, r[2], 5);
          bb.tochni.concat(bb.shozhi).forEach(function (x) { shozhi.push(li(x.nazva, 'будинок', x.url)); });
        }
        var slova = P.norm(adr ? adr.nazva : z).split(' ').filter(Boolean);
        r[1].filter(function (v) { return P.zbih(slova, v.p) === 1; }).sort(function (a, b) { return b.n - a.n; })
          .slice(0, 6 - shozhi.length).forEach(function (v) { shozhi.push(li(v.nazva, v.dod, v.url)); });
        if (shozhi.length) dodaty = dodaty.concat([zaholovok('Можливо, ви мали на увазі:')], shozhi);
      }
      if (!dodaty.length) return;
      Array.prototype.forEach.call(ul.querySelectorAll('.pd'), function (x) { x.remove(); });
      if (porozh) porozh.remove();
      dodaty.forEach(function (x) { ul.appendChild(x); });
    });
  }
  // Реагуємо лише на зміни від karta.js: наші власні пункти (.pd) і видалення не рахуються — інакше нескінченне коло.
  function chuzhyi(n) { return n.nodeType === 1 && !n.classList.contains('pd'); }
  new MutationObserver(function (zapysy) {
    if (zapysy.some(function (z) { return Array.prototype.some.call(z.addedNodes, chuzhyi); })) doplnyty();
  }).observe(ul, { childList: true });

  // Натиск — одразу на сторінку (до того, як karta.js сховає список після втрати фокуса).
  ul.addEventListener('pointerdown', function (e) {
    var x = e.target.closest('.pd[data-url]');
    if (x) { e.preventDefault(); window.location.href = x.getAttribute('data-url'); }
  });
  // Enter без власних підказок карти — перша наша; стрілки — по наших пунктах.
  pole.addEventListener('keydown', function (e) {
    var nashi = ul.querySelectorAll('.pd[data-url]');
    if (ul.hidden || !nashi.length || ul.querySelector('[data-j]')) return;
    var i = Array.prototype.findIndex.call(nashi, function (x) { return x.getAttribute('aria-selected') === 'true'; });
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      i = e.key === 'ArrowDown' ? Math.min(i + 1, nashi.length - 1) : Math.max(i - 1, 0);
      Array.prototype.forEach.call(nashi, function (x, j) { x.setAttribute('aria-selected', String(j === i)); });
    } else if (e.key === 'Enter') {
      e.preventDefault();
      window.location.href = nashi[Math.max(i, 0)].getAttribute('data-url');
    }
  });
})();
