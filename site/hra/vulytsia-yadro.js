// Ядро гри «Вулиця дня» (ZAVDANNYA-101, прототип): без карти й сторінки — лише розрахунки.
// Перевіряє tests/test_hra_vulytsia.py (через Node.js). Спільне з першою грою (дата за Києвом, «подія дня»,
// відстань) — з hra-yadro.js, щоб обидві гри рахували однаково.
(function (korin) {
  'use strict';

  var Y = korin.MvHraYadro || (typeof require === 'function' ? require('./hra-yadro.js') : null);

  var NAPRYAMY = ['пн', 'пн-сх', 'сх', 'пд-сх', 'пд', 'пд-зх', 'зх', 'пн-зх'];
  var NAPRYAMY_POVNI = ['на північ', 'на північний схід', 'на схід', 'на південний схід', 'на південь',
    'на південний захід', 'на захід', 'на північний захід'];

  // Рядок файлу → об'єкт вулиці.
  function vulytsia(r) {
    return { slug: r[0], nazva: r[1], typ: r[2], rayon: r[3], n: r[4], vyrizn: r[5], lat: r[6], lon: r[7] };
  }

  // Азимут від спроби до загаданої, градуси за годинниковою (0 — північ).
  function azymut(a, b) {
    var f1 = a.lat * Math.PI / 180, f2 = b.lat * Math.PI / 180;
    var dl = (b.lon - a.lon) * Math.PI / 180;
    var y = Math.sin(dl) * Math.cos(f2);
    var x = Math.cos(f1) * Math.sin(f2) - Math.sin(f1) * Math.cos(f2) * Math.cos(dl);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  }

  function napryam(gradusy) { return Math.round(gradusy / 45) % 8; }

  // Порівняння спроби з загаданою: усе, що гравець бачить у рядку.
  function porivnyaty(sproba, zahadana) {
    var tak = sproba.slug === zahadana.slug;
    var m = Y.vidstan(sproba.lat, sproba.lon, zahadana.lat, zahadana.lon);
    var az = azymut(sproba, zahadana);
    return {
      tak: tak,
      vidstanM: tak ? 0 : Math.round(m),
      azymut: Math.round(az),
      napryam: tak ? null : NAPRYAMY[napryam(az)],
      napryamPovnyi: tak ? null : NAPRYAMY_POVNI[napryam(az)],
      rayon: sproba.rayon === zahadana.rayon,
      n: sproba.n === zahadana.n ? 0 : (zahadana.n > sproba.n ? 1 : -1),   // 1 — у загаданої більше
      vyrizn: (sproba.vyrizn || '') === (zahadana.vyrizn || ''),
      typ: sproba.typ === zahadana.typ
    };
  }

  // Пошук назви: без регістру, апострофів і лапок; «ґ» = «г»; кожне слово запиту — початок слова назви.
  function normalizuvaty(t) {
    return String(t || '').toLowerCase().replace(/[’'ʼ`«»"]/g, '').replace(/ґ/g, 'г').replace(/-/g, ' ')
      .replace(/\s+/g, ' ').trim();
  }

  function shukaty(vulytsi, zapyt, krim, skilky) {
    var z = normalizuvaty(zapyt);
    if (!z) return [];
    var slova = z.split(' ');
    var vykhid = [];
    for (var i = 0; i < vulytsi.length; i++) {
      var v = vulytsi[i];
      if (krim && krim[v.slug]) continue;
      var nz = ' ' + normalizuvaty(v.nazva);
      var vse = slova.every(function (s) { return nz.indexOf(' ' + s) !== -1; });
      if (vse) vykhid.push(v);
    }
    // Спершу ті, де запит — початок назви без типу, потім коротші.
    vykhid.sort(function (a, b) {
      var pa = normalizuvaty(a.nazva).replace(normalizuvaty(a.typ), '').trim().indexOf(z) === 0 ? 0 : 1;
      var pb = normalizuvaty(b.nazva).replace(normalizuvaty(b.typ), '').trim().indexOf(z) === 0 ? 0 : 1;
      return pa - pb || a.nazva.length - b.nazva.length || (a.nazva < b.nazva ? -1 : 1);
    });
    return vykhid.slice(0, skilky || 8);
  }

  // Які підказки відкриті після k невдалих спроб (сталий порядок; перевіряє тест).
  // 0 — район; 3 — подія з колоди на цій вулиці; 5 — тип вулиці.
  var PIDKAZKY = [{ pislia: 0, pole: 'rayon' }, { pislia: 3, pole: 'podiia' }, { pislia: 5, pole: 'typ' }];
  function vidkryti(nevdali) {
    return PIDKAZKY.filter(function (p) { return nevdali >= p.pislia; }).map(function (p) { return p.pole; });
  }

  // Загадка дня — так само, як «подія дня» першої гри: коло по всіх загадках, однакова для всіх.
  function zahadkaDnya(zahadky, data) { return Y.podiyaDnya(zahadky.map(function (z, i) { return { id: z.slug, i: i }; }), data); }

  // Текст «Поділитися» без назви вулиці (спойлер-захист): клітинки район · подій · вирізняє · тип.
  function tekstPodilytysia(data, sproby, rozghadano, maks, sait) {
    var ryadky = sproby.map(function (p) {
      return [p.rayon, p.n === 0, p.vyrizn, p.typ].map(function (b) { return b ? '■' : '□'; }).join('') +
        (p.tak ? ' так' : ' ' + Y.vidstanTekstom(p.vidstanM) + ' ' + p.napryam);
    });
    var d = /^(\d{4})-(\d{2})-(\d{2})$/.exec(data);
    var dd = d ? d[3] + '.' + d[2] : data;
    var pidsumok = rozghadano ? 'з ' + sproby.length + '-ї спроби з ' + maks : 'не розгадав за ' + maks + ' спроб';
    return 'Моя вулиця · Вулиця дня ' + dd + ' — ' + pidsumok + '\n' + ryadky.join('\n') + (sait ? '\n' + sait : '');
  }

  var Yadro = {
    vulytsia: vulytsia, azymut: azymut, porivnyaty: porivnyaty, normalizuvaty: normalizuvaty, shukaty: shukaty,
    PIDKAZKY: PIDKAZKY, vidkryti: vidkryti, zahadkaDnya: zahadkaDnya, tekstPodilytysia: tekstPodilytysia
  };
  if (typeof module === 'object' && module.exports) module.exports = Yadro;
  korin.MvVulytsiaYadro = Yadro;
})(typeof window !== 'undefined' ? window : this);
