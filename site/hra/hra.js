// Гра «Вгадай, де це було» — сторінка (ZAVDANNYA-07).
// Розрахунки — у hra-yadro.js, карта — у hra-karta.js, картинка «Поділитися» — у hra-kartka.js.
//
// Що зберігаємо на пристрої (localStorage, з try/catch — якщо пам'ять браузера недоступна,
// гра однаково йде): лише найкращий результат раунду і зіграну «подію дня».
// Жодних кукі, ідентифікаторів чи облікових записів. Рахунок — через nadsylannya.js:
// лише назва події (hra_start, hra_vidpovid, hra_kinets, hra_podilytysia, den_zihrano) і канал.
(function () {
  'use strict';

  var Y = window.MvHraYadro;
  var $ = function (id) { return document.getElementById(id); };
  var parametry = new URLSearchParams(window.location.search);
  var dzherelo = parametry.get('dzherelo');
  var KLYUCH_REKORD = 'mv-hra-naikrashchyi';
  var KLYUCH_DEN = 'mv-hra-den';
  var U_RAUNDI = 10;

  var stan = {
    koloda: { demo: false, podii: [] },
    rezhym: 'raund',
    spysok: [],
    i: 0,
    vidpovidi: [],
    vybrane: null,
    karta: null,
    data: null
  };

  // ---------- Пам'ять пристрою (може не працювати — тоді просто без неї) ----------
  function prochytaty(klyuch) {
    try { var s = window.localStorage.getItem(klyuch); return s ? JSON.parse(s) : null; } catch (e) { return null; }
  }
  function zapysaty(klyuch, znachennya) {
    try { window.localStorage.setItem(klyuch, JSON.stringify(znachennya)); } catch (e) { /* без пам'яті — гра йде далі */ }
  }

  function nadislaty(nazva) {
    var N = window.MvNadsylannya;
    if (N && N.nadislatyPodiyu) N.nadislatyPodiyu(nazva, dzherelo);
  }

  // ---------- Екрани ----------
  function ekran(id) {
    ['ekran-menyu', 'ekran-hra', 'ekran-kinets'].forEach(function (e) { $(e).hidden = e !== id; });
    $('do-menyu').hidden = id === 'ekran-menyu';
    window.scrollTo(0, 0);
    if (id === 'ekran-hra' && stan.karta) requestAnimationFrame(function () { stan.karta.rozmir(); });
  }

  function napysOchky(el, n) {
    el.textContent = Y.chyslo(n);
    el.setAttribute('data-slovo', Y.slovoOchky(n));
  }

  function klasRezultatu(ochky) { return ochky >= 500 ? 'zrobleno' : ochky > 0 ? 'blyzko' : 'mymo'; }

  function suma() { return stan.vidpovidi.reduce(function (s, v) { return s + v.ochky; }, 0); }

  function nadpys() {
    if (stan.rezhym === 'den') return 'Подія дня · ' + window.MvHraKartka.dataTekstom(stan.data);
    return 'Вгадай, де це було · ' + (stan.i + 1) + ' / ' + stan.spysok.length;
  }

  // ---------- Меню ----------
  function onovytyMenyu() {
    var rekord = prochytaty(KLYUCH_REKORD);
    $('naikrashchyi').innerHTML = '';
    if (rekord && typeof rekord.ochky === 'number') {
      var s = document.createElement('strong');
      s.textContent = Y.chyslo(rekord.ochky) + ' ' + Y.slovoOchky(rekord.ochky);
      $('naikrashchyi').appendChild(s);
    } else {
      $('naikrashchyi').textContent = 'ще не грали';
    }
    var den = prochytaty(KLYUCH_DEN);
    var syohodni = Y.dataKyiv();
    var p = Y.podiyaDnya(stan.koloda.podii, syohodni);
    if (den && p && den.data === syohodni && den.id === p.id) {
      $('den-opys').textContent = 'Сьогодні зіграно: ' + Y.chyslo(den.ochky) + ' ' + Y.slovoOchky(den.ochky) + '. Наступна — завтра';
    } else {
      $('den-opys').textContent = window.MvHraKartka.dataTekstom(syohodni) + ' · одна подія на добу, та сама для всіх';
    }
  }

  // ---------- Карта ----------
  function karta() {
    if (stan.karta) return stan.karta;
    stan.karta = window.MvHraKarta.stvoryty($('karta'), {
      pryTorkanni: function (t) {
        stan.vybrane = t;
        $('vidpovisty').disabled = false;
        $('pidkazka').textContent = 'Можна пересунути позначку — торкніться в іншому місці';
      },
      pryZboiPidkladky: function () { $('karta-zboi').hidden = false; }
    });
    return stan.karta;
  }

  // ---------- Раунд ----------
  function pochatyRaund() {
    var vypadkove = parametry.get('nasinnya') ? Y.generator(Y.kheshRyadka(parametry.get('nasinnya'))) : Math.random;
    stan.rezhym = 'raund';
    stan.spysok = Y.raund(stan.koloda.podii, U_RAUNDI, vypadkove);
    stan.i = 0;
    stan.vidpovidi = [];
    nadislaty('hra_start');
    ekran('ekran-hra');
    karta();
    pokazatyZavdannya();
  }

  function pochatyDen() {
    stan.rezhym = 'den';
    stan.data = Y.dataKyiv();
    var p = Y.podiyaDnya(stan.koloda.podii, stan.data);
    if (!p) return;
    stan.spysok = [p];
    stan.i = 0;
    stan.vidpovidi = [];
    ekran('ekran-hra');
    karta();
    var den = prochytaty(KLYUCH_DEN);
    if (den && den.data === stan.data && den.id === p.id) {
      // Результат дня — один раз: показуємо вже зігране.
      var vasha = typeof den.lat === 'number' ? { lat: den.lat, lng: den.lng } : null;
      stan.vidpovidi = [{ podiya: p, vasha: vasha, vidstan: den.vidstan, ochky: den.ochky }];
      pokazatyVidpovid(true);
      return;
    }
    nadislaty('hra_start');
    pokazatyZavdannya();
  }

  function pokazatyZavdannya() {
    var p = stan.spysok[stan.i];
    stan.vybrane = null;
    $('ekran-hra').classList.remove('hra--vidpovid');
    $('zavdannya').hidden = false;
    $('vidpovid').hidden = true;
    $('lehenda').hidden = true;
    $('nadpys').textContent = nadpys();
    napysOchky($('rakhunok-zahalnyi'), suma());
    $('rakhunok-zahalnyi').hidden = stan.rezhym === 'den';
    $('opys-korotkyi').textContent = p.opys_korotkyi;
    $('meta-vyd').textContent = p.vyd;
    $('meta-rik').textContent = p.rik + ' рік';
    namaluvatyKroky();
    $('pidkazka').textContent = 'Торкніться карти там, де це могло бути';
    $('pidkazka').hidden = false;
    $('vidpovisty').hidden = false;
    $('vidpovisty').disabled = true;
    $('dali').hidden = true;
    $('podilytysia-den').hidden = true;
    karta().skynuty();
  }

  function namaluvatyKroky() {
    var k = $('kroky');
    k.innerHTML = '';
    k.hidden = stan.rezhym === 'den';
    for (var j = 0; j < stan.spysok.length; j++) {
      var i = document.createElement('i');
      if (j < stan.vidpovidi.length) i.className = klasRezultatu(stan.vidpovidi[j].ochky);
      else if (j === stan.i) i.className = 'zaraz';
      k.appendChild(i);
    }
  }

  function vidpovisty() {
    if (!stan.vybrane) return;
    var p = stan.spysok[stan.i];
    var d = Y.vidstan(stan.vybrane.lat, stan.vybrane.lng, p.lat, p.lon);
    var o = Y.ochky(d);
    stan.vidpovidi.push({ podiya: p, vasha: stan.vybrane, vidstan: d, ochky: o });
    nadislaty('hra_vidpovid');
    if (stan.rezhym === 'den') {
      zapysaty(KLYUCH_DEN, { data: stan.data, id: p.id, ochky: o, vidstan: Math.round(d),
        lat: +stan.vybrane.lat.toFixed(5), lng: +stan.vybrane.lng.toFixed(5) });
      nadislaty('den_zihrano');
    }
    pokazatyVidpovid(false);
  }

  function pokazatyVidpovid(vzheZihrano) {
    var v = stan.vidpovidi[stan.vidpovidi.length - 1];
    var p = v.podiya;
    $('ekran-hra').classList.add('hra--vidpovid');
    $('zavdannya').hidden = true;
    $('vidpovid').hidden = false;
    $('lehenda').hidden = false;
    $('nadpys-vidpovid').textContent = nadpys();
    napysOchky($('rakhunok-vidpovid'), suma());
    $('rakhunok-vidpovid').hidden = stan.rezhym === 'den';
    $('vidstan').textContent = v.vidstan <= Y.BLYZKO_M ? 'Влучно' : 'за ' + Y.vidstanTekstom(v.vidstan);
    $('ochky').textContent = (v.ochky > 0 ? '+' : '') + Y.chyslo(v.ochky);
    $('ochky-slovo').textContent = Y.slovoOchky(v.ochky) + ' із 1 000';
    var blok = $('ochky').parentNode;
    blok.classList.toggle('vluchno', v.ochky >= 500);
    blok.classList.toggle('mymo', v.ochky === 0);
    $('adresa').textContent = p.adresa;
    $('opys-povnyi').textContent = p.opys_povnyi;
    $('meta-vyd-2').textContent = p.vyd;
    $('meta-rik-2').textContent = p.rik + ' рік';
    var r = $('rishennya');
    r.innerHTML = '';
    if (p.rishennya_url && /^https:\/\//.test(p.rishennya_url)) {
      var a = document.createElement('a');
      a.href = p.rishennya_url; a.target = '_blank'; a.rel = 'noopener noreferrer';
      a.textContent = 'Рішення суду' + (p.rishennya_nomer ? ' № ' + p.rishennya_nomer : '');
      r.appendChild(document.createTextNode('Джерело: '));
      r.appendChild(a);
    } else {
      r.textContent = 'Демо-подія: рішення суду за нею немає. Справжні посилання з\'являться разом зі справжньою колодою.';
    }
    $('den-zihrano').hidden = !(stan.rezhym === 'den');
    $('den-zihrano').textContent = vzheZihrano ? 'Ви вже зіграли подію дня. Наступна — завтра.' : 'Подію дня зараховано. Наступна — завтра.';
    $('pidkazka').hidden = true;
    $('vidpovisty').hidden = true;
    $('dali').hidden = false;
    if (stan.rezhym === 'den') {
      $('dali').textContent = 'До меню';
      $('podilytysia-den').hidden = false;
    } else {
      $('dali').textContent = stan.i + 1 < stan.spysok.length ? 'Далі' : 'Підсумок раунду';
      $('podilytysia-den').hidden = true;
    }
    karta().pokazatyRezultat(v.vasha, p, vzheZihrano);
    $('dali').focus({ preventScroll: true });
  }

  function dali() {
    if (stan.rezhym === 'den') { onovytyMenyu(); ekran('ekran-menyu'); return; }
    stan.i += 1;
    if (stan.i < stan.spysok.length) {
      window.scrollTo(0, 0);
      pokazatyZavdannya();
    } else {
      kinets();
    }
  }

  // ---------- Кінець раунду ----------
  function sotaSvg(klas) {
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 28 31');
    var path = document.createElementNS(ns, 'path');
    path.setAttribute('d', 'M14 1.5 L26.5 8.75 L26.5 22.25 L14 29.5 L1.5 22.25 L1.5 8.75 Z');
    path.setAttribute('class', 'sota sota--' + klas);
    svg.appendChild(path);
    return svg;
  }

  function kinets() {
    var s = suma();
    var maks = stan.spysok.length * Y.MAKS_OCHOK;
    var rekord = prochytaty(KLYUCH_REKORD);
    var novyi = !rekord || typeof rekord.ochky !== 'number' || s > rekord.ochky;
    if (novyi) zapysaty(KLYUCH_REKORD, { ochky: s });
    nadislaty('hra_kinets');

    $('suma').textContent = Y.chyslo(s);
    $('suma-pidpys').textContent = Y.slovoOchky(s) + ' із ' + Y.chyslo(maks);
    var r = $('rekord');
    r.innerHTML = '';
    if (novyi && rekord) { r.innerHTML = '<strong>Новий найкращий результат.</strong> Попередній — '; r.appendChild(document.createTextNode(Y.chyslo(rekord.ochky) + '.')); }
    else if (novyi) r.textContent = 'Перший раунд на цьому пристрої — це ваш найкращий результат.';
    else r.textContent = 'Найкраще на цьому пристрої — ' + Y.chyslo(rekord.ochky) + ' ' + Y.slovoOchky(rekord.ochky) + '.';

    var soty = $('soty-raundu');
    soty.innerHTML = '';
    stan.vidpovidi.forEach(function (v) { soty.appendChild(sotaSvg(klasRezultatu(v.ochky))); });

    var poVidstani = stan.vidpovidi.slice().sort(function (a, b) { return a.vidstan - b.vidstan; });
    var bl = poVidstani[0], dl = poVidstani[poVidstani.length - 1];
    $('naiblyzhche-vidstan').textContent = 'за ' + Y.vidstanTekstom(bl.vidstan);
    $('naiblyzhche-opys').textContent = bl.podiya.vyd + ' · ' + bl.podiya.adresa;
    $('naidali-vidstan').textContent = 'за ' + Y.vidstanTekstom(dl.vidstan);
    $('naidali-opys').textContent = dl.podiya.vyd + ' · ' + dl.podiya.adresa;

    var sp = $('spysok-raundu');
    sp.innerHTML = '';
    stan.vidpovidi.forEach(function (v, j) {
      var li = document.createElement('li');
      var n = document.createElement('span'); n.className = 'n'; n.textContent = String(j + 1);
      var shcho = document.createElement('span'); shcho.className = 'shcho'; shcho.textContent = v.podiya.vyd;
      var dr = document.createElement('small'); dr.textContent = v.podiya.adresa; shcho.appendChild(dr);
      var sk = document.createElement('span'); sk.className = 'skilky'; sk.textContent = Y.chyslo(v.ochky);
      var dv = document.createElement('small'); dv.textContent = 'за ' + Y.vidstanTekstom(v.vidstan); sk.appendChild(dv);
      li.appendChild(n); li.appendChild(shcho); li.appendChild(sk);
      sp.appendChild(li);
    });
    $('podilytysia-stan').textContent = '';
    ekran('ekran-kinets');
  }

  // ---------- Поділитися ----------
  function sait() {
    var s = document.body.getAttribute('data-sait') || '';
    return s.trim() || '[САЙТ]';
  }

  function daniKartky() {
    var s = suma();
    var v = stan.vidpovidi[stan.vidpovidi.length - 1];
    return {
      rezhym: stan.rezhym,
      suma: s,
      maks: stan.spysok.length * Y.MAKS_OCHOK,
      rezultaty: stan.vidpovidi.map(function (x) { return x.ochky; }),
      vidstanTekst: v ? (v.vidstan <= Y.BLYZKO_M ? '' : Y.vidstanTekstom(v.vidstan)) : '',
      data: stan.data,
      demo: stan.koloda.demo,
      sait: sait()
    };
  }

  function podilytysia(stanEl) {
    nadislaty('hra_podilytysia');
    if (stanEl) stanEl.textContent = 'Готуємо картинку…';
    window.MvHraKartka.podilytysia(daniKartky()).then(function (rez) {
      if (!stanEl) return;
      stanEl.textContent = rez === 'zavantazheno' ? 'Картинку збережено у «Завантаження».' : rez === 'podilylysia' ? 'Готово.' : '';
    }, function () { if (stanEl) stanEl.textContent = 'Не вдалося створити картинку.'; });
  }

  // ---------- Старт ----------
  function zavantazhytyKolodu() {
    var vziaty = function (imya) {
      return fetch(imya, { credentials: 'omit', cache: 'no-cache' }).then(function (v) {
        if (!v.ok) throw new Error(imya + ': ' + v.status);
        return v.json();
      });
    };
    // Зібраний сайт кладе колоду в koloda.json; без збирання — демо-колода.
    return vziaty('koloda.json').catch(function () { return vziaty('koloda-demo.json'); });
  }

  function pochatok() {
    $('pochaty-raund').addEventListener('click', pochatyRaund);
    $('pochaty-den').addEventListener('click', pochatyDen);
    $('vidpovisty').addEventListener('click', vidpovisty);
    $('dali').addEventListener('click', dali);
    $('hraty-shche').addEventListener('click', pochatyRaund);
    $('podilytysia').addEventListener('click', function () { podilytysia($('podilytysia-stan')); });
    $('podilytysia-den').addEventListener('click', function () { podilytysia(null); });
    $('do-menyu').addEventListener('click', function () { onovytyMenyu(); ekran('ekran-menyu'); });

    zavantazhytyKolodu().then(function (fail) {
      stan.koloda = Y.pidhotuvatyKolodu(fail);
      $('zavantazhennya').hidden = true;
      if (!stan.koloda.podii.length) throw new Error('Порожня колода');
      $('mitka-demo').hidden = !stan.koloda.demo;
      $('demo-pidkazka').hidden = !stan.koloda.demo;
      onovytyMenyu();
      if (parametry.get('rezhym') === 'den') pochatyDen();
      else if (parametry.get('rezhym') === 'raund') pochatyRaund();
    }).catch(function () {
      $('zavantazhennya').hidden = false;
      $('zavantazhennya').textContent = 'Не вдалося завантажити гру. Спробуйте оновити сторінку.';
    });
  }

  // Робота без мережі: той самий файл кешу, що й у заглушки (../sw.js).
  if ('serviceWorker' in navigator &&
      (location.protocol === 'https:' || location.hostname === '127.0.0.1' || location.hostname === 'localhost')) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('../sw.js', { scope: '../' }).catch(function () { /* без кешу гра теж працює */ });
    });
  }

  window.MvHra = { stan: stan, daniKartky: daniKartky };
  pochatok();
})();
