// Сторінка гри «Вулиця дня» (ZAVDANNYA-101, прототип). Дані — vulytsia-dnia.json (site/hra/vulytsia_dnia.py).
// Карта — та сама, що в «Де це було?» (hra-karta.js); спроби — точки-середини вулиць із номером.
(function () {
  'use strict';

  var Y = window.MvVulytsiaYadro;
  var H = window.MvHraYadro;
  var $ = function (id) { return document.getElementById(id); };
  var SAIT = document.body.getAttribute('data-sait') || '';
  if (SAIT.charAt(0) === '[') SAIT = '';

  var dani = null, vulytsi = [], zaSlug = {}, zahadka = null, zahadana = null;
  var sproby = [], kinets = false, data = H.dataKyiv(), poradok = 0;
  var karta = null, vybrana = null, vybirIndeks = -1;

  // ---------- Пам'ять пристрою (без облікового запису) ----------
  function prochytaty(k) { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } }
  function zapysaty(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* без пам'яті теж грається */ } }
  var KLYUCH = function () { return 'mv-vd-' + data + (poradok ? '-' + poradok : ''); };

  // ---------- Карта ----------
  function tochky() {
    var f = sproby.map(function (s, i) {
      var v = zaSlug[s.slug];
      return { type: 'Feature', properties: { n: String(i + 1), tak: s.p.tak ? 1 : 0 }, geometry: { type: 'Point', coordinates: [v.lon, v.lat] } };
    });
    return { type: 'FeatureCollection', features: f };
  }

  function sharyKarty(k) {
    var m = k.karta;
    var kol = function (n) { return getComputedStyle(document.documentElement).getPropertyValue('--' + n).trim(); };
    if (!m.getSource('sproby')) {
      m.addSource('sproby', { type: 'geojson', data: tochky() });
      m.addLayer({ id: 'sproby-kolo', type: 'circle', source: 'sproby', paint: {
        'circle-radius': 13, 'circle-color': ['case', ['==', ['get', 'tak'], 1], kol('accent'), kol('surface')],
        'circle-stroke-color': kol('accent'), 'circle-stroke-width': 2 } });
      m.addLayer({ id: 'sproby-n', type: 'symbol', source: 'sproby', layout: {
        'text-field': ['get', 'n'], 'text-font': ['Noto Sans Bold'], 'text-size': 13, 'text-allow-overlap': true },
        paint: { 'text-color': ['case', ['==', ['get', 'tak'], 1], kol('on-accent'), kol('accent')] } });
    } else {
      m.getSource('sproby').setData(tochky());
    }
  }

  function onovytyKartu(rozkryty) {
    if (!karta) return;
    var m = karta.karta;
    var z = function () {
      sharyKarty(karta);
      if (rozkryty && zahadana) {
        karta.pokazatyRezultat(null, { lat: zahadana.lat, lon: zahadana.lon }, false);
        return;
      }
      if (sproby.length) {
        var b = new maplibregl.LngLatBounds();
        sproby.forEach(function (s) { var v = zaSlug[s.slug]; b.extend([v.lon, v.lat]); });
        if (sproby.length === 1) m.easeTo({ center: b.getCenter(), zoom: 11.5, duration: 500 });
        else m.fitBounds(b, { padding: 70, maxZoom: 13, duration: 500 });
      }
    };
    if (m.isStyleLoaded()) z(); else m.once('idle', z);
  }

  // ---------- Підказки ----------
  function pidkazky() {
    var nevdali = sproby.filter(function (s) { return !s.p.tak; }).length;
    var vidkr = kinets ? Y.PIDKAZKY.map(function (p) { return p.pole; }) : Y.vidkryti(nevdali);
    var ol = $('pidkazky');
    ol.textContent = '';
    Y.PIDKAZKY.forEach(function (p, i) {
      var li = document.createElement('li');
      li.className = 'pidkazka';
      var mitka = document.createElement('span');
      mitka.className = 'pidkazka__mitka';
      mitka.textContent = 'Підказка ' + (i + 1);
      var tekst = document.createElement('p');
      tekst.className = 'pidkazka__tekst';
      if (vidkr.indexOf(p.pole) === -1) {
        li.classList.add('pidkazka--zakryta');
        tekst.textContent = 'Відкриється після ' + p.pislia + '-ї невдалої спроби';
      } else if (p.pole === 'rayon') {
        tekst.textContent = zahadana.rayon + ' район';
      } else if (p.pole === 'typ') {
        tekst.textContent = 'Це ' + zahadana.typ;
      } else {
        var pd = zahadka.podiia;
        var em = document.createElement('span');
        em.className = 'pidkazka__dzherelo';
        em.textContent = 'Одна з подій на цій вулиці · ' + pd.vyd + ' · ' + pd.rik;
        tekst.appendChild(document.createTextNode('«' + pd.opys + '»'));
        li.appendChild(mitka); li.appendChild(em); li.appendChild(tekst);
        ol.appendChild(li);
        return;
      }
      li.appendChild(mitka); li.appendChild(tekst);
      ol.appendChild(li);
    });
  }

  // ---------- Таблиця спроб ----------
  function klitynka(tekst, tak, pidpys) {
    var s = document.createElement('span');
    s.className = 'kl' + (tak ? ' kl--tak' : '');
    s.textContent = tekst;
    if (pidpys) s.setAttribute('aria-label', pidpys + ': ' + tekst + (tak ? ', збігається' : ', не збігається'));
    return s;
  }

  function ryadok(s, i) {
    var v = zaSlug[s.slug], p = s.p;
    var li = document.createElement('li');
    li.className = 'sproba-ryadok' + (p.tak ? ' sproba-ryadok--tak' : '');
    var nazva = document.createElement('span');
    nazva.className = 'sproba-ryadok__nazva';
    var nom = document.createElement('b');
    nom.textContent = (i + 1) + '';
    nazva.appendChild(nom);
    nazva.appendChild(document.createTextNode(v.nazva));
    li.appendChild(nazva);

    var vid = document.createElement('span');
    vid.className = 'kl kl--vidstan' + (p.tak ? ' kl--tak' : '');
    if (p.tak) { vid.textContent = 'тут'; } else {
      var str = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      str.setAttribute('viewBox', '0 0 24 24'); str.setAttribute('width', '16'); str.setAttribute('height', '16');
      str.setAttribute('aria-hidden', 'true');
      var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', 'M12 20V5M6 11l6-6 6 6');
      str.appendChild(path);
      str.style.transform = 'rotate(' + p.azymut + 'deg)';   // CSSOM — дозволено політикою безпеки
      vid.appendChild(str);
      vid.appendChild(document.createTextNode(H.vidstanTekstom(p.vidstanM)));
      vid.setAttribute('aria-label', 'Загадана — за ' + H.vidstanTekstom(p.vidstanM) + ' ' + p.napryamPovnyi);
    }
    li.appendChild(vid);
    li.appendChild(klitynka(v.rayon.replace(/ський$|цький$/, function (x) { return x === 'цький' ? 'цьк.' : 'ськ.'; }), p.rayon, 'Район'));
    var n = klitynka(H.chyslo(v.n) + (p.n > 0 ? ' ↑' : p.n < 0 ? ' ↓' : ''), p.n === 0, 'Подій');
    if (p.n !== 0) n.setAttribute('aria-label', 'Подій: ' + v.n + ', у загаданої ' + (p.n > 0 ? 'більше' : 'менше'));
    li.appendChild(n);
    li.appendChild(klitynka(v.typ, p.typ, 'Тип'));
    var vz = klitynka(v.vyrizn || 'нічим особливим', p.vyrizn, 'Вирізняє');
    vz.classList.add('kl--vyrizn');
    li.appendChild(vz);
    return li;
  }

  function tablytsia() {
    var ol = $('sproby');
    ol.textContent = '';
    sproby.forEach(function (s, i) { ol.appendChild(ryadok(s, i)); });
    $('tablytsia').hidden = !sproby.length;
  }

  // ---------- Кінець ----------
  function kolektsiia() {
    var k = prochytaty('mv-vd-kolektsiia') || [];
    if (k.indexOf(zahadana.slug) === -1) { k.push(zahadana.slug); zapysaty('mv-vd-kolektsiia', k); }
    return k.length;
  }

  function pokazatyKinets() {
    var rozghadano = sproby.length && sproby[sproby.length - 1].p.tak;
    $('kinets').hidden = false;
    $('sproba').hidden = true;
    $('kinets-nadpys').textContent = rozghadano ? 'Розгадано' : 'Цього разу ні — загадана вулиця';
    $('kinets-vulytsia').textContent = zahadana.nazva;
    $('kinets-rayon').textContent = zahadana.rayon + ' район';
    $('kinets-n').textContent = H.chyslo(zahadana.n);
    $('kinets-n-pidpys').textContent = 'подій у даних за ' + dani.roky;
    $('kinets-sproby').textContent = rozghadano ? sproby.length + ' з ' + dani.sprob : '—';
    $('kinets-vyrizn').textContent = 'Що вирізняє вулицю: ' + zahadana.vyrizn.toLowerCase() + ' — частка вища, ніж по місту.';
    var zv = zahadka.zvuzhennia;
    $('kinets-detektyv').textContent = 'Як вивести відповідь: у грі ' + H.chyslo(zv.vsi) + ' вулиць; у цьому районі — ' + zv.rayon +
      '; з тим самим «вирізняє» — ' + zv.vyrizn + '; і з таким числом подій — ' + zv.n + '. Відповідь одна — це перевіряє програма.';
    var pd = zahadka.podiia;
    var box = $('kinets-podiia');
    box.textContent = '';
    var t = document.createElement('p');
    t.textContent = '«' + pd.opys + '»';
    var m = document.createElement('p');
    m.className = 'kinets-vd__meta';
    m.appendChild(document.createTextNode(pd.vyd + ' · ' + pd.rik + ' · '));
    var a = document.createElement('a');
    a.href = pd.url; a.target = '_blank'; a.rel = 'noopener';
    a.textContent = 'рішення суду № ' + pd.nomer;
    m.appendChild(a);
    box.appendChild(t); box.appendChild(m);
    var storinka = '/vulytsia/' + zahadana.slug + '/';
    $('kinets-storinka').href = storinka + '?dzherelo=hra-vulytsia';
    $('pidpyska').href = storinka + '?dzherelo=hra-vulytsia#stezhyty';
    $('pidpyska-opys').textContent = 'Усі ' + H.chyslo(zahadana.n) + ' подій з адресами й описами і нове щотижня — у підписці, 399 грн/міс.';
    var n = kolektsiia();
    $('kolektsiia').textContent = 'Вулиця додана до вашої колекції: відкрито ' + n + ' ' + (n % 10 === 1 && n % 100 !== 11 ? 'вулицю' : (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)) ? 'вулиці' : 'вулиць') + '.';
    onovytyKartu(true);
    if (window.matchMedia('(min-width: 900px)').matches) $('kinets').scrollIntoView({ block: 'start' });
  }

  // ---------- Спроба ----------
  function zrobytySprobu(slug) {
    if (kinets || !zaSlug[slug] || sproby.some(function (s) { return s.slug === slug; })) return;
    var p = Y.porivnyaty(zaSlug[slug], zahadana);
    sproby.push({ slug: slug, p: p });
    kinets = p.tak || sproby.length >= dani.sprob;
    zapysaty(KLYUCH(), sproby.map(function (s) { return s.slug; }));
    $('pole').value = ''; vybrana = null; $('vidpravyty').disabled = true; zakrytyVybir();
    var zalyshylos = dani.sprob - sproby.length;
    $('sproba-stan').textContent = p.tak ? '' : 'Ні, загадана — за ' + H.vidstanTekstom(p.vidstanM) + ' ' + p.napryamPovnyi +
      '. Лишилось спроб: ' + zalyshylos + '.';
    vse();
    if (kinets) pokazatyKinets(); else onovytyKartu(false);
  }

  // ---------- Вибір зі списку ----------
  function zakrytyVybir() { $('vybir').hidden = true; $('pole').setAttribute('aria-expanded', 'false'); vybirIndeks = -1; }

  function pokazatyVybir() {
    var krim = {};
    sproby.forEach(function (s) { krim[s.slug] = true; });
    var znaideno = Y.shukaty(vulytsi, $('pole').value, krim, 8);
    var ul = $('vybir');
    ul.textContent = '';
    vybrana = null;
    $('vidpravyty').disabled = true;
    znaideno.forEach(function (v, i) {
      var li = document.createElement('li');
      li.setAttribute('role', 'option');
      li.id = 'vybir-' + i;
      li.className = 'vybir__ryadok';
      var n = document.createElement('span'); n.textContent = v.nazva;
      var r = document.createElement('small'); r.textContent = v.rayon;
      li.appendChild(n); li.appendChild(r);
      li.addEventListener('mousedown', function (e) { e.preventDefault(); obraty(v); });
      ul.appendChild(li);
    });
    if (!znaideno.length && $('pole').value.trim().length > 1) {
      var li = document.createElement('li');
      li.className = 'vybir__porozhnio';
      li.textContent = 'Такої вулиці в грі немає — у грі вулиці, де в даних щонайменше 5 подій.';
      ul.appendChild(li);
    }
    ul.hidden = !ul.children.length;
    $('pole').setAttribute('aria-expanded', ul.hidden ? 'false' : 'true');
    if (znaideno.length === 1) obraty(znaideno[0], true);
  }

  function obraty(v, lysheVybraty) {
    vybrana = v;
    $('vidpravyty').disabled = false;
    if (!lysheVybraty) { $('pole').value = v.nazva; zakrytyVybir(); }
  }

  function klavishi(e) {
    var ryadky = $('vybir').querySelectorAll('.vybir__ryadok');
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!ryadky.length) return;
      e.preventDefault();
      vybirIndeks = (vybirIndeks + (e.key === 'ArrowDown' ? 1 : -1) + ryadky.length) % ryadky.length;
      ryadky.forEach(function (r, i) { r.classList.toggle('vybir__ryadok--aktyvnyi', i === vybirIndeks); });
      $('pole').setAttribute('aria-activedescendant', ryadky[vybirIndeks].id);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (vybirIndeks >= 0 && ryadky[vybirIndeks]) ryadky[vybirIndeks].dispatchEvent(new MouseEvent('mousedown'));
      else if (vybrana) zrobytySprobu(vybrana.slug);
    } else if (e.key === 'Escape') { zakrytyVybir(); }
  }

  // ---------- Поділитися ----------
  function podilytysia() {
    var rozghadano = sproby.length && sproby[sproby.length - 1].p.tak;
    var tekst = Y.tekstPodilytysia(data, sproby.map(function (s) { return s.p; }), rozghadano, dani.sprob,
      (SAIT || 'moya-vulytsya') + '/hra/vulytsia.html');
    var stan = $('podilytysia-stan');
    if (navigator.share) {
      navigator.share({ text: tekst }).catch(function () { /* скасовано */ });
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(tekst).then(function () { stan.textContent = 'Скопійовано — вставте в чат чи допис.'; },
        function () { stan.textContent = tekst; });
    } else { stan.textContent = tekst; }
  }

  // ---------- Запуск ----------
  function vse() {
    pidkazky();
    tablytsia();
    $('vd-sprob').textContent = dani.sprob;
  }

  function pochaty() {
    var p = new URLSearchParams(location.search);
    if (/^\d{4}-\d{2}-\d{2}$/.test(p.get('data') || '')) data = p.get('data');
    var vybir = Y.zahadkaDnya(dani.zahadky, data);
    var i = (vybir.i + poradok) % dani.zahadky.length;
    zahadka = dani.zahadky[i];
    zahadana = zaSlug[zahadka.slug];
    sproby = []; kinets = false;
    $('kinets').hidden = true; $('sproba').hidden = false; $('sproba-stan').textContent = '';
    $('podilytysia-stan').textContent = '';
    var d = new Date(data + 'T12:00:00');
    $('vd-data').textContent = 'Вулиця дня · ' + d.toLocaleDateString('uk-UA', { day: 'numeric', month: 'long' }) + (poradok ? ' · ще одна' : '');
    (prochytaty(KLYUCH()) || []).forEach(function (s) {
      if (zaSlug[s] && !kinets) {
        var pp = Y.porivnyaty(zaSlug[s], zahadana);
        sproby.push({ slug: s, p: pp });
        kinets = pp.tak || sproby.length >= dani.sprob;
      }
    });
    vse();
    if (karta) { karta.skynuty(); }
    if (kinets) pokazatyKinets(); else onovytyKartu(false);
  }

  fetch('vulytsia-dnia.json', { credentials: 'omit' })
    .then(function (v) { if (!v.ok) throw new Error(v.status); return v.json(); })
    .then(function (d) {
      dani = d;
      vulytsi = d.vulytsi.map(Y.vulytsia);
      vulytsi.forEach(function (v) { zaSlug[v.slug] = v; });
      $('vd-roky').textContent = d.roky;
      $('zavantazhennya').hidden = true;
      karta = window.MvHraKarta.stvoryty($('karta'), { bezTorkannia: true, pryZboiPidkladky: function () { $('karta-zboi').hidden = false; } });
      pochaty();
    })
    .catch(function () {
      $('zavantazhennya').textContent = 'Не вдалося завантажити гру. Спробуйте оновити сторінку.';
    });

  // Для знімків і перевірок (tests/znimky_hry_vulytsia.py): що загадано і які спроби.
  window.MvVulytsia = { stan: function () { return { zahadana: zahadana, sproby: sproby, vulytsi: vulytsi, kinets: kinets }; } };

  $('pole').addEventListener('input', pokazatyVybir);
  $('pole').addEventListener('keydown', klavishi);
  $('pole').addEventListener('blur', function () { setTimeout(zakrytyVybir, 150); });
  $('vidpravyty').addEventListener('click', function () { if (vybrana) zrobytySprobu(vybrana.slug); });
  $('podilytysia').addEventListener('click', podilytysia);
  $('shche').addEventListener('click', function () { poradok += 1; pochaty(); });
})();
