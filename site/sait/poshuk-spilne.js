// Спільне ядро пошуку сайту (ZAVDANNYA-177; ZVIT-165, п. 3): одна поведінка на головній, «Мій будинок» і входах.
//  * «хрещятик 22» — помилка в одній літері (у слові від 8 літер — у двох) прощається: «Можливо, ви мали на увазі…»;
//  * народні назви місцевостей («Оболонь», «Троєщина», «Борщагівка») ведуть на район — словник у даних
//    (dani-edrsr/config/mistsevosti-<місто>.csv → /karta/mistsevosti.json), не в коді;
//  * без запитів назовні — лише власні файли сайту.
// Підключається перед poshuk.js і poshuk-holovna.js; karta.js може взяти window.MVPoshuk тим самим рядком.
(function () {
  'use strict';
  var KOREN = document.documentElement.getAttribute('data-koren') || '/';
  var P = window.MVPoshuk = {};

  P.norm = function (t) {
    return (t || '').toLowerCase().replace(/[ʼ’'`]/g, '').replace(/ґ/g, 'г').replace(/ё/g, 'е')
      .replace(/[-.,«»"]/g, ' ').replace(/\s+/g, ' ').trim();
  };
  // «2а», «2-А», «2 а» — один номер; «15/5» лишається з рискою.
  P.normNomer = function (t) { return (t || '').toLowerCase().replace(/[\s-]/g, '').replace(/\\/g, '/'); };
  // «Гоголівська 2а», «Хрещатик, буд. 22», «вул. Лесі Українки 28/2» → назва й номер.
  P.rozibraty = function (z) {
    var m = /^(.*?)[\s,]+(?:буд(?:инок)?\.?\s*)?(?:№\s*)?(\d+[^\s,]*(?:\s?[а-яіїєa-z])?)$/i.exec((z || '').trim());
    return m && m[1].trim() ? { nazva: m[1], nomer: m[2] } : null;
  };

  // Відстань Левенштейна з межею: більше за mezha — повертаємо mezha + 1 (швидко).
  function vidstan(a, b, mezha) {
    if (Math.abs(a.length - b.length) > mezha) return mezha + 1;
    var p = [], i, j;
    for (j = 0; j <= b.length; j++) p.push(j);
    for (i = 1; i <= a.length; i++) {
      var c = [i], min = i;
      for (j = 1; j <= b.length; j++) {
        c.push(Math.min(p[j] + 1, c[j - 1] + 1, p[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)));
        if (c[j] < min) min = c[j];
      }
      if (min > mezha) return mezha + 1;
      p = c;
    }
    return p[b.length];
  }
  P.vidstan = vidstan;
  function dopusk(s) { return s.length >= 8 ? 2 : s.length >= 4 ? 1 : 0; }

  // Слово запиту схоже на якесь слово назви: ціле слово або його початок (людина ще друкує) — з допуском помилки.
  function slovoShozhe(s, slovaNazvy) {
    var d = dopusk(s);
    if (!d) return false;
    return slovaNazvy.some(function (w) {
      if (vidstan(s, w, d) <= d) return true;
      for (var k = -1; k <= 1; k++) {
        var n = s.length + k;
        if (n >= 3 && n < w.length && vidstan(s, w.slice(0, n), d) <= d) return true;
      }
      return false;
    });
  }
  // 0 — кожне слово запиту є в назві як є (як було й раніше); 1 — лише з допуском помилки; -1 — не схоже.
  P.zbih = function (slova, p) {
    if (slova.every(function (s) { return p.indexOf(s) !== -1; })) return 0;
    var sn = p.split(' ');
    return slova.every(function (s) { return p.indexOf(s) !== -1 || slovoShozhe(s, sn); }) ? 1 : -1;
  };

  // Народні назви місцевостей: [назва, [інші назви], [[район, адреса], …]].
  var MISTSEVOSTI = null;
  P.mistsevosti = function () {
    if (MISTSEVOSTI) return Promise.resolve(MISTSEVOSTI);
    return fetch(KOREN + 'karta/mistsevosti.json', { credentials: 'omit' })
      .then(function (v) { return v.ok ? v.json() : []; }).catch(function () { return []; })
      .then(function (d) {
        MISTSEVOSTI = d.map(function (m) {
          return { nazva: m[0], formy: [m[0]].concat(m[1] || []).map(P.norm), rayony: m[2] };
        });
        return MISTSEVOSTI;
      });
  };
  // «Оболонь», «оболоні», «троещина» → місцевість; слово запиту коротше за 3 літери — ні.
  P.znaityMistsevosti = function (z, ms) {
    var q = P.norm(z);
    if (q.length < 3 || /\d/.test(q)) return [];
    var slova = q.split(' ');
    return (ms || []).filter(function (m) {
      return m.formy.some(function (f) { return P.zbih(slova, f) >= 0; });
    });
  };
  P.pidpysMistsevosti = function (m) {
    return 'місцевість · ' + m.rayony.map(function (r) { return r[0]; }).join(' і ') + (m.rayony.length > 1 ? ' райони' : ' район');
  };

  // Будинки з vulytsi/budynky.json: [{n: назва вулиці, p: norm(назва + старі назви), b: [[номер, адреса сторінки], …]}].
  // Повертає {tochni: […], shozhi: […]} — однакові номери на точно й на приблизно знайдених вулицях.
  P.budynky = function (adr, bs, maks) {
    var slova = P.norm(adr.nazva).split(' ').filter(Boolean), nn = P.normNomer(adr.nomer), rez = { tochni: [], shozhi: [] };
    (bs || []).forEach(function (v) {
      var z = P.zbih(slova, v.p);
      if (z < 0) return;
      v.b.forEach(function (x) {
        var kudy = z === 0 ? rez.tochni : rez.shozhi;
        if (kudy.length < (maks || 8) && P.normNomer(x[0]) === nn) kudy.push({ nazva: v.n + ', ' + x[0], url: x[1] });
      });
    });
    return rez;
  };
})();
