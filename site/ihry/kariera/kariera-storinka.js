// Окрема сторінка «Кваліфікуй: кар'єра» (ZAVDANNYA-146; з ZAVDANNYA-152 сама гра — модуль kariera.js, той самий, що в панелі
// «Ігри» карти). Бали йдуть у ту саму скарбничку ігор на пристрої, що й у карті (налаштування — ../nalashtuvannia.json).
(function () {
  'use strict';
  var Y = window.MvIhryYadro, K = null;
  function bali(ochky) {
    if (!Y || !K) return 0;
    var data = Y.chasKyiv().data, s;
    try { s = Y.naDen(JSON.parse(localStorage.getItem('mv-ihry-bali')), data); } catch (e) { s = Y.naDen(null, data); }
    var b = Y.zarakhuvaty(s, ochky, K, data);
    try { localStorage.setItem('mv-ihry-bali', JSON.stringify(s)); } catch (e) { /* без пам'яті */ }
    return b;
  }
  function pusk() {
    window.MvKariera.zapustyty({ korin: document.getElementById('hra'), dani: 'kariera.json', zapasni: '../kvalifikuy.json',
      bali: bali, ochky: K && K.kariera_ochky });
  }
  fetch('../nalashtuvannia.json', { credentials: 'omit' }).then(function (v) { return v.ok ? v.json() : null; })
    .then(function (k) { K = k; }).catch(function () { /* без балів */ }).then(pusk);
})();
