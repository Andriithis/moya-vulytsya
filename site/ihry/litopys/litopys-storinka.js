// Перевірочна сторінка «Літопису міста» (ZAVDANNYA-141): карта на весь екран і гра в панелі — так само, як у карті сайту,
// але без збирання сайту. Бали йдуть у ту саму скарбничку ігор на пристрої (налаштування — ../nalashtuvannia.json).
(function () {
  'use strict';
  var karta = null;
  function zminna(n) { return getComputedStyle(document.documentElement).getPropertyValue('--' + n).trim(); }
  function kolory() {
    var k = {};
    ['ground', 'surface', 'ink', 'ink-2', 'muted', 'line', 'line-strong', 'accent', 'accent-soft', 'mezha', 'pk-2', 'data-1', 'data-3', 'data-5',
      'karta-voda', 'karta-zelen', 'karta-zabudova', 'karta-vulytsia', 'karta-vulytsia-ramka', 'karta-za-mezhamy'].forEach(function (n) { k[n] = zminna(n); });
    return k;
  }
  function porozhnio() { return { type: 'FeatureCollection', features: [] }; }
  function styl() {
    var st = window.MvHraKarta.styl(kolory(), null, { liniya: porozhnio(), spravzhnie: porozhnio(), vasha: porozhnio() });
    st.layers = st.layers.filter(function (l) { return ['liniya', 'spravzhnie-oreol', 'spravzhnie', 'vasha', 'za-mezhamy', 'mezha'].indexOf(l.id) < 0; });
    return st;
  }
  if (window.maplibregl && window.MvHraKarta) {
    maplibregl.setWorkerUrl('../../hra/biblioteka/maplibre-gl-csp-worker.js');
    try {
      karta = new maplibregl.Map({ container: 'karta', style: styl(), bounds: window.MvHraKarta.KYIV, minZoom: 8.5, maxZoom: 17,
        dragRotate: false, pitchWithRotate: false, touchPitch: false, attributionControl: false, renderWorldCopies: false, fadeDuration: 0 });
      karta.touchZoomRotate.disableRotation();
      karta.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© учасники OpenStreetMap</a>' }), 'bottom-left');
      karta.on('error', function () { /* без підкладки гра працює: райони й вулиці — шари гри */ });
      // День/ніч: нова підкладка (шари гри перемальовує сама гра, як і в карті сайту).
      document.addEventListener('mv-tema', function () { setTimeout(function () { karta.setStyle(styl(), { diff: false }); }, 30); });
    } catch (e) { karta = null; }
  }
  var Y = window.MvIhryYadro, K = null;
  fetch('../nalashtuvannia.json', { credentials: 'omit' }).then(function (v) { return v.ok ? v.json() : null; }).then(function (k) { K = k; }).catch(function () { /* без балів */ });
  function bali(ochky) {
    if (!Y || !K) return 0;
    var data = Y.chasKyiv().data, s;
    try { s = Y.naDen(JSON.parse(localStorage.getItem('mv-ihry-bali')), data); } catch (e) { s = Y.naDen(null, data); }
    var b = Y.zarakhuvaty(s, ochky, K, data);
    try { localStorage.setItem('mv-ihry-bali', JSON.stringify(s)); } catch (e) { /* без пам'яті */ }
    return b;
  }
  window.MvLitopys.zapustyty({ korin: document.getElementById('panel'), karta: karta, dani: 'litopys.json',
    panel: document.getElementById('panel'), bali: bali, vlasnyiKlik: true,
    ochky: null });
})();
