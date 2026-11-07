// Ядро гри «Вгадай, де це було» (ZAVDANNYA-07): лише розрахунки, без сторінки й карти.
// Працює і в браузері (window.MvHraYadro), і в Node для перевірок (tests/test_hra.py).
// Нічого не надсилає і нічого не зберігає.
(function (korin) {
  'use strict';

  // ---------- Очки ----------
  // 1 000 очок — якщо відповідь не далі 50 м від справжнього місця;
  // 0 очок — якщо 5 км і далі;
  // між ними — плавно, за логарифмом відстані: кожне зменшення відстані вдесятеро
  // дає +500 очок. Тобто 500 м → 500 очок, 1 км → 349, 200 м → 699, 2 км → 199.
  // Формула: очки = 1000 × ln(5000 / d) / ln(5000 / 50), округлено до цілого.
  // Та сама формула записана в docs/IHRY.md.
  var MAKS_OCHOK = 1000;
  var BLYZKO_M = 50;
  var DALEKO_M = 5000;

  function ochky(vidstanM) {
    var d = Number(vidstanM);
    if (!isFinite(d) || d < 0) return 0;
    if (d <= BLYZKO_M) return MAKS_OCHOK;
    if (d >= DALEKO_M) return 0;
    return Math.round(MAKS_OCHOK * Math.log(DALEKO_M / d) / Math.log(DALEKO_M / BLYZKO_M));
  }

  // Відстань між двома точками на Землі, у метрах (формула гаверсинусів).
  function vidstan(lat1, lon1, lat2, lon2) {
    var R = 6371008.8;
    var rad = Math.PI / 180;
    var dLat = (lat2 - lat1) * rad;
    var dLon = (lon2 - lon1) * rad;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
  }

  // ---------- Числа людською мовою ----------
  // Пробіл у тисячах (12 400), кома в дробах (1,2) — як у системі дизайну.
  function chyslo(n) {
    var s = String(Math.round(Math.abs(n)));
    var z = '';
    while (s.length > 3) { z = ' ' + s.slice(-3) + z; s = s.slice(0, -3); }
    return (n < 0 ? '−' : '') + s + z;
  }

  // «за 340 м», «за 1,2 км», «за 12 км».
  function vidstanTekstom(m) {
    if (m < 995) return chyslo(Math.max(10, Math.round(m / 10) * 10)) + ' м';
    if (m < 9950) return (Math.round(m / 100) / 10).toFixed(1).replace('.', ',') + ' км';
    return chyslo(Math.round(m / 1000)) + ' км';
  }

  // 1 очко, 2 очки, 5 очок, 11 очок, 21 очко.
  function slovoOchky(n) {
    n = Math.abs(Math.round(n));
    var d = n % 10, s = n % 100;
    if (d === 1 && s !== 11) return 'очко';
    if (d >= 2 && d <= 4 && (s < 12 || s > 14)) return 'очки';
    return 'очок';
  }

  // ---------- Колода ----------
  // MV-12 / MV-4: найважчі справи в гру не беремо ніколи — навіть якщо трапляться у файлі.
  var ZABORONENI_KATEHORII = ['statevi_zlochyny', 'shchodo_ditei', 'domashnie_nasylstvo'];
  // Межі Києва з запасом (для відсіву явно хибних координат).
  var MEZHI = { pivden: 50.21, pivnich: 50.60, zakhid: 30.23, skhid: 30.83 };
  var POLYA = ['id', 'vyd', 'kategoriia', 'rik', 'opys_korotkyi', 'opys_povnyi', 'adresa', 'lat', 'lon'];

  function zaboronena(podiya) {
    var k = String(podiya && podiya.kategoriia || '').trim().toLowerCase();
    return ZABORONENI_KATEHORII.indexOf(k) !== -1;
  }

  function prydatna(p) {
    if (!p || typeof p !== 'object') return false;
    for (var i = 0; i < POLYA.length; i++) {
      var v = p[POLYA[i]];
      if (v === undefined || v === null || v === '') return false;
    }
    var lat = Number(p.lat), lon = Number(p.lon);
    if (!(lat >= MEZHI.pivden && lat <= MEZHI.pivnich && lon >= MEZHI.zakhid && lon <= MEZHI.skhid)) return false;
    return !zaboronena(p);
  }

  // Повертає {demo, podii}: лише придатні події, без заборонених категорій, без повторів id,
  // упорядковані за id (щоб «подія дня» не залежала від порядку у файлі).
  function pidhotuvatyKolodu(fail) {
    var syri = (fail && Array.isArray(fail.podii)) ? fail.podii : [];
    var bachyly = {};
    var podii = [];
    for (var i = 0; i < syri.length; i++) {
      var p = syri[i];
      if (!prydatna(p) || bachyly[p.id]) continue;
      bachyly[p.id] = true;
      podii.push(p);
    }
    podii.sort(function (a, b) { return a.id < b.id ? -1 : a.id > b.id ? 1 : 0; });
    var demo = !!(fail && fail.demo) || podii.some(function (p) { return p.demo === true; });
    return { demo: demo, podii: podii };
  }

  // ---------- Випадковість із зерном ----------
  function kheshRyadka(s) {          // FNV-1a, 32 біти
    var h = 0x811c9dc5;
    s = String(s);
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return h >>> 0;
  }

  function generator(zerno) {        // mulberry32
    var a = zerno >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function peremishaty(spysok, vypadkove) {
    var a = spysok.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(vypadkove() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  // Раунд: до 10 різних подій. vypadkove — Math.random або генератор із зерном.
  function raund(podii, skilky, vypadkove) {
    return peremishaty(podii, vypadkove || Math.random).slice(0, skilky || 10);
  }

  // ---------- Подія дня ----------
  // Сьогоднішня дата за київським часом, «РРРР-ММ-ДД».
  function dataKyiv(teper) {
    var d = teper || new Date();
    try {
      var chastyny = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Kyiv', year: 'numeric', month: '2-digit', day: '2-digit' })
        .formatToParts(d);
      var z = {};
      chastyny.forEach(function (c) { z[c.type] = c.value; });
      if (z.year && z.month && z.day) return z.year + '-' + z.month + '-' + z.day;
    } catch (e) { /* старий браузер — беремо місцеву дату */ }
    var m = d.getMonth() + 1, dd = d.getDate();
    return d.getFullYear() + '-' + (m < 10 ? '0' : '') + m + '-' + (dd < 10 ? '0' : '') + dd;
  }

  // Одна подія на добу, однакова для всіх: без сервера, лише з дати й колоди.
  // Дні йдуть «колами» по колоді: за одне коло кожна подія буде рівно раз,
  // порядок у колі — перемішування з зерном «номер кола».
  function podiyaDnya(podii, data) {
    if (!podii.length) return null;
    var ch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(data));
    if (!ch) return null;
    var den = Math.floor(Date.UTC(+ch[1], +ch[2] - 1, +ch[3]) / 86400000);
    var n = podii.length;
    var kolo = Math.floor(den / n);
    var poryadok = peremishaty(podii, generator(kheshRyadka('mv-den-' + kolo + '-' + n)));
    return poryadok[((den % n) + n) % n];
  }

  var Yadro = {
    MAKS_OCHOK: MAKS_OCHOK, BLYZKO_M: BLYZKO_M, DALEKO_M: DALEKO_M,
    ZABORONENI_KATEHORII: ZABORONENI_KATEHORII,
    ochky: ochky, vidstan: vidstan, chyslo: chyslo, vidstanTekstom: vidstanTekstom, slovoOchky: slovoOchky,
    zaboronena: zaboronena, prydatna: prydatna, pidhotuvatyKolodu: pidhotuvatyKolodu,
    kheshRyadka: kheshRyadka, generator: generator, peremishaty: peremishaty, raund: raund,
    dataKyiv: dataKyiv, podiyaDnya: podiyaDnya
  };
  if (typeof module === 'object' && module.exports) module.exports = Yadro;
  korin.MvHraYadro = Yadro;
})(typeof window !== 'undefined' ? window : this);
