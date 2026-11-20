// Симулятор темпу «Літопису міста» (ZAVDANNYA-141, крок 3). Лише перевірка балансу — у гру не входить.
//
//   node site/ihry/litopys/symuliatsiia.js [litopys.json] [--dniv 60] [--sesii 2] [--khv 5] [--json]
//
// Модель гравця (як у ZVIT-140, але довше): щодня N сесій по K хвилин (за Києвом 08:00 і 20:00), 1 дотик на секунду;
// раз на 10 с купує найвигідніше: вулицю з новою карткою (або найбільшу), якщо вистачає сторінок, інакше — помічника
// з найкращим «сторінок за секунду на сторінку ціни»; новий район — щойно можна; задачі дня — усі (відповідь правильна);
// «нове видання» — коли воно дасть щонайменше 2 пункти авторитету; «Пошта архіву» — на початку кожної сесії. Між сесіями помічники читають самі (межа й половина).
// Без випадковості: той самий файл даних — ті самі числа (як і в самій грі).
'use strict';
var fs = require('fs');
var path = require('path');
var Y = require('./litopys-yadro.js');

function argumenty(argv) {
  var a = { fail: path.join(__dirname, 'litopys.json'), dniv: 60, sesii: 2, khv: 5, json: false };
  for (var i = 0; i < argv.length; i++) {
    var x = argv[i];
    if (x === '--dniv') a.dniv = Number(argv[++i]);
    else if (x === '--sesii') a.sesii = Number(argv[++i]);
    else if (x === '--khv') a.khv = Number(argv[++i]);
    else if (x === '--json') a.json = true;
    else a.fail = x;
  }
  return a;
}

function pidhotuvaty(D) {
  D.vulytsi = D.vulytsi.map(function (v) { return { slug: v[0], nazva: v[1], rayon: v[2], n: v[3], podii: v[7] }; });
  return D;
}

// Найбільший район за кількістю вулиць — «дім» гравця (як більшість киян: живуть у великому районі).
function domashnii(D) {
  var r = Object.keys(D.rayony).sort(function (a, b) { return D.rayony[b].vulyts - D.rayony[a].vulyts || (a < b ? -1 : 1); });
  return r[0];
}

function symuliuvaty(D, o) {
  var t0 = Date.parse('2026-12-01T06:00:00Z');   // 08:00 за Києвом
  var s = Y.novyi(t0, domashnii(D));
  var vydy = D.vydy;
  var poDniakh = [];
  var vSesiiu = o.khv * 60;
  var mizhSesiiamy = 12 * 3600 * 1000;

  function naikrashchaVulytsia() {
    var kr = null, krBal = -1;
    for (var i = 0; i < D.vulytsi.length; i++) {
      var v = D.vulytsi[i];
      if (s.rayony.indexOf(v.rayon) < 0 || s.vulytsi.indexOf(v.slug) >= 0) continue;
      var novi = v.podii.filter(function (id) { return !s.karty[D.podii[id][0]]; }).length;
      var bal = novi * 1e6 + v.podii.length * 1e4 + v.n;
      if (bal > krBal) { krBal = bal; kr = v; }
    }
    return kr;
  }
  function kupuvaty(t) {
    var zminy = true, k = 0;
    while (zminy && k++ < 200) {
      zminy = false;
      if (s.rayony.length < Y.skilkyRayoniv(s, Object.keys(D.rayony).length)) {
        var vilni = Object.keys(D.rayony).filter(function (r) { return s.rayony.indexOf(r) < 0; })
          .sort(function (a, b) { return D.rayony[b].vulyts - D.rayony[a].vulyts || (a < b ? -1 : 1); });
        if (vilni.length) { Y.vidkrytyRayon(s, vilni[0]); zminy = true; }
      }
      var v = naikrashchaVulytsia();
      if (v && s.storinky >= Y.tsinaVulytsi(s)) { Y.vidkrytyVulytsiu(s, v, D.podii); Y.perevirytyVulytsi(s, t); zminy = true; continue; }
      // помічник: найкраща віддача, але лише якщо вулиця зараз недосяжна за ~30 с дотиків і читання
      var najk = null, najkV = 0;
      Y.vydniPomichnyky(s).forEach(function (p) {
        var c = Y.tsinaPomichnyka(s, p); if (c > s.storinky) return;
        var vid = p.za_sek / c; if (vid > najkV) { najkV = vid; najk = p; }
      });
      if (najk) { Y.naiaty(s, najk.id); zminy = true; }
    }
    if (Y.avtorytetZa(s) >= 2) Y.noveVydannia(s);
  }

  var t = t0;
  for (var den = 1; den <= o.dniv; den++) {
    var vulPochatok = s.vulytsi.length, kartPochatok = Object.keys(s.karty).length;
    for (var ses = 0; ses < o.sesii; ses++) {
      var pochatok = t0 + (den - 1) * 864e5 + ses * mizhSesiiamy;
      Y.plyn(s, vydy, pochatok); t = pochatok;
      Y.poshta(s, t);
      if (ses === 0) {   // задачі дня — на початку першої сесії (так роблять більшість гравців)
        var d = Y.den(s, t), sp = Y.spravaDnia(d.data, D);
        if (sp) { Y.vidpovisty(s, t, 'sprava', sp.vyd, sp.vyd); if (sp.rayon) Y.vidpovisty(s, t, 'rayon', sp.rayon, sp.rayon); else d.zrobleno.rayon = true; }
      }
      for (var sek = 0; sek < vSesiiu; sek++) {
        t = pochatok + sek * 1000;
        Y.plyn(s, vydy, t);
        Y.dotyk(s, vydy, t);
        if (sek % 10 === 9) kupuvaty(t);
      }
      kupuvaty(t);
      if (den === 1 && ses === 0) poDniakh.push({ den: 0, mitka: '10 хв', vulyts: s.vulytsi.length, rayoniv: s.rayony.length, kartok: Object.keys(s.karty).length, vydan: s.vydannia });
    }
    poDniakh.push({ den: den, vulyts: s.vulytsi.length, rayoniv: s.rayony.length, kartok: Object.keys(s.karty).length,
      vydan: s.vydannia, novykh: s.vulytsi.length - vulPochatok, novykhKartok: Object.keys(s.karty).length - kartPochatok,
      seriia: s.seriia.dniv });
  }
  return { dni: poDniakh, vsogo_vulyts: D.vulytsi.length, vsogo_kartok: Object.keys(D.vydy).length };
}

if (require.main === module) {
  var o = argumenty(process.argv.slice(2));
  var D = pidhotuvaty(JSON.parse(fs.readFileSync(o.fail, 'utf8')));
  var r = symuliuvaty(D, o);
  if (o.json) { console.log(JSON.stringify(r)); process.exit(0); }
  console.log('Гравець: ' + o.sesii + ' сесії на день по ' + o.khv + ' хв, 1 дотик/с. Вулиць у грі: ' + r.vsogo_vulyts + ', карток: ' + r.vsogo_kartok);
  console.log('день | вулиць | нових за день | районів | карток | видань');
  r.dni.forEach(function (d) {
    if (d.mitka || [1, 2, 3, 4, 5, 6, 7, 10, 14, 21, 30, 45, 60, 90].indexOf(d.den) >= 0 || d.den === o.dniv)
      console.log((d.mitka || d.den) + ' | ' + d.vulyts + ' | ' + (d.novykh == null ? '' : d.novykh) + ' | ' + d.rayoniv + ' | ' + d.kartok + ' | ' + d.vydan);
  });
  var min = Math.min.apply(null, r.dni.filter(function (d) { return d.den >= 2; }).map(function (d) { return d.novykh; }));
  console.log('Найменше нових вулиць за день (дні 2–' + o.dniv + '): ' + min);
}

module.exports = { symuliuvaty: symuliuvaty, pidhotuvaty: pidhotuvaty };
