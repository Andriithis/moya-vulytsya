// Ігри в карті (ZAVDANNYA-117; MV-129, MV-130, MV-26): «Детектив тижня», «Вгадай, де це було», «Вулиця дня»,
// «Кваліфікуй», бали. Граються на самій карті: панель — «в повітрі» праворуч (телефон — шторка на половину екрана),
// карта під нею живе. Кнопка «Ігри» — у рядку пошуку (людина сама запускає будь-яку гру будь-коли); кожна гра ще й
// пропонує себе сама — одне тихе запрошення за відвідування (≈ 40 с або 3-й дотик), «×», не поверх відкритого.
// Усе — на пристрої (localStorage), поки немає кабінету (ZAVDANNYA-99). Нічого не надсилає.
// Вигляд — docs/STYL.md, «зовні гра»: клавіші, без емодзі, без червоного.
(function () {
  'use strict';
  var Y = window.MvIhryYadro, H = window.MvHraYadro, V = window.MvVulytsiaYadro;
  var ekran = document.querySelector('.ekran-karty');
  var panel = document.getElementById('ihry');
  var knopka = document.getElementById('fihry');
  var zapr = document.getElementById('ihry-zaproshennia');
  if (!ekran || !panel || !knopka || !Y || !H) return;
  var $ = function (s, k) { return (k || panel).querySelector(s); };
  var DZH = {
    spravy: panel.getAttribute('data-spravy'), koloda: panel.getAttribute('data-koloda'),
    vulytsia: panel.getAttribute('data-vulytsia'), kvalifikuy: panel.getAttribute('data-kvalifikuy'),
    nalashtuvannia: panel.getAttribute('data-nalashtuvannia')
  };
  var MITKY = { rishennia: 'з рішення суду', vyhadka: 'вигадка', karta: 'з карти', pidkazka: 'підказка гри', dovidnyk: 'з довідника' };
  var NAZVY_DNIV = ['', 'понеділок', 'вівторок', 'середа', 'четвер', "п'ятниця", 'субота', 'неділя'];

  // ---------- час (для перевірки й знімків: ?ihry-den=1..7&ihry-hodyna=0..23 — лише перегляд, бали тоді не йдуть) ----------
  var q = new URLSearchParams(location.search);
  var PROBA = q.has('ihry-den');
  function chas() {
    var c = Y.chasKyiv();
    if (PROBA) {
      var d = Math.max(1, Math.min(7, Number(q.get('ihry-den')) || 1));
      c = { data: Y.dodatyDni(Y.ponedilok(c.data), d - 1), den: d, hodyna: Number(q.get('ihry-hodyna') || 12) };
    }
    return c;
  }

  // ---------- сховище на пристрої ----------
  function chytaty(k, typ) { try { var v = JSON.parse(localStorage.getItem(k)); return v == null ? typ : v; } catch (e) { return typ; } }
  function pysaty(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* приватний режим — гра без пам'яті */ } }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function chyslo(n) { return H.chyslo(n); }
  function slovoBaly(n) { n = Math.abs(n) % 100; var d = n % 10; return (n > 10 && n < 15) ? 'балів' : d === 1 ? 'бал' : (d >= 2 && d <= 4) ? 'бали' : 'балів'; }

  var dani = {};
  function zavantazhyty(k) {
    if (!DZH[k]) return Promise.resolve(null);
    if (!dani[k]) dani[k] = fetch(DZH[k], { credentials: 'omit' }).then(function (v) { return v.ok ? v.json() : null; }).catch(function () { return null; });
    return dani[k];
  }
  var K = null;   // налаштування балів
  function bali() { return Y.naDen(chytaty('mv-ihry-bali', null), chas().data); }
  function zberehtyBali(s) { pysaty('mv-ihry-bali', s); }
  function narakhuvaty(ochky) {
    if (PROBA || !K) return 0;
    var s = bali(); var b = Y.zarakhuvaty(s, ochky, K, chas().data); zberehtyBali(s); return b;
  }

  // ---------- карта ----------
  var MV = window.MvKarta || {};
  var REZHYM = null;            // функція(lngLat) → true, якщо дотик забрала гра
  var MARKERY = [];
  function karta() { return (window.MvKarta || {}).karta; }
  function marker(lat, lon, klas, pidpys) {
    var m = karta(); if (!m || !window.maplibregl) return null;
    var el = document.createElement('div'); el.className = 'i-mitka ' + (klas || '');
    if (pidpys) { var s = document.createElement('span'); s.textContent = pidpys; el.appendChild(s); }
    var mk = new maplibregl.Marker({ element: el, anchor: 'center' }).setLngLat([lon, lat]).addTo(m);
    MARKERY.push(mk); return mk;
  }
  function prybratyMitky() { MARKERY.forEach(function (m) { m.remove(); }); MARKERY = []; }
  function letity(lat, lon, zum) { var m = karta(); if (m) m.flyTo({ center: [lon, lat], zoom: zum || 14, pitch: 0, duration: MV.tykho ? 600 : 1400 }); }
  function toast(t) { var p = document.getElementById('pidkazka'); if (!p) return; p.textContent = t; p.classList.add('vyd'); clearTimeout(toast.t); toast.t = setTimeout(function () { p.classList.remove('vyd'); }, 2600); }
  // Дотик по карті в режимі гри — гра забирає його собі (karta.js питає MvKarta.perekhopyty).
  function pidkliuchyty() {
    if (!window.MvKarta) return false;
    window.MvKarta.perekhopyty = function (ll) { return REZHYM ? REZHYM(ll) : false; };
    return true;
  }
  if (!pidkliuchyty()) { var t0 = setInterval(function () { if (pidkliuchyty()) clearInterval(t0); }, 300); }
  function rezhym(f, pidkaz) { REZHYM = f; ekran.classList.toggle('ihry-tsil', !!f); if (f && pidkaz) toast(pidkaz); }

  // ---------- панель ----------
  var ZARAZ = 'menyu';
  function vidkryty(gra) {
    panel.hidden = false; knopka.setAttribute('aria-expanded', 'true'); ekran.classList.add('ihry-vidkryto');
    if (window.MvKarta && window.MvKarta.zakryty) window.MvKarta.zakryty();
    hovatyZaproshennia(false);
    pokazaty(gra || 'menyu');
  }
  function zakryty() { panel.hidden = true; knopka.setAttribute('aria-expanded', 'false'); ekran.classList.remove('ihry-vidkryto'); rezhym(null); prybratyMitky(); }
  knopka.addEventListener('click', function () { if (panel.hidden) vidkryty(); else zakryty(); });
  panel.addEventListener('click', function (e) {
    if (panel.classList.contains('zghornuta') && e.target.closest('.i-shap') && !e.target.closest('[data-i]')) { panel.classList.remove('zghornuta'); return; }
    var t = e.target.closest('[data-i]'); if (!t) return;
    var dia = t.getAttribute('data-i');
    if (dia === 'x') zakryty();
    else if (dia === 'nazad') { rezhym(null); prybratyMitky(); pokazaty('menyu'); }
    else if (DII[dia]) DII[dia](t);
  });
  function ramka(nazva, tilo, bezNazad) {
    panel.innerHTML = '<div class="i-ruchka" aria-hidden="true"></div><div class="i-shap">' +
      (bezNazad ? '' : '<button type="button" class="i-nazad" data-i="nazad" aria-label="До списку ігор">‹</button>') +
      '<h2>' + esc(nazva) + '</h2><button type="button" class="i-x" data-i="x" aria-label="Закрити ігри">×</button></div>' +
      '<div class="i-tilo">' + tilo + '</div>';
    panel.scrollTop = 0;
  }
  function pokazaty(gra) {
    ZARAZ = gra;
    var f = { menyu: menyu, detektyv: detektyv, vgadai: vgadai, vulytsia: vulytsia, kvalifikuy: kvalifikuy, bali: baliEkran, nalashtuvannia: nalashtuvannia }[gra] || menyu;
    Promise.resolve(K || zavantazhyty('nalashtuvannia').then(function (k) { K = k; })).then(f);
  }

  // ---------- меню ----------
  function menyu() {
    Promise.all([zavantazhyty('spravy'), zavantazhyty('kvalifikuy')]).then(function (r) {
      var c = chas(), s = bali();
      var st = r[0] && Y.spravaTyzhnia(r[0].spravy, c.data);
      var det = st ? 'день ' + c.den + ' з 7 · «' + esc(st.sprava.nazva) + '»' : 'справа тижня — скоро';
      var den = chytaty('mv-ihry-den-' + c.data, {});
      var kart = function (gra, nazva, opys, stan, vymk) {
        return '<button type="button" class="i-gra klav" data-i="hra" data-gra="' + gra + '"' + (vymk ? ' disabled' : '') + '><b>' + nazva +
          '</b><span>' + opys + '</span><small>' + stan + '</small></button>';
      };
      ramka('Ігри', '<p class="i-bal"><span>' + chyslo(s.bali) + '</span> ' + slovoBaly(s.bali) + ' на цьому пристрої <button type="button" class="i-lnk" data-i="hra" data-gra="bali">Бали й спроби</button></p>' +
        '<div class="i-sitka">' +
        kart('detektyv', 'Детектив тижня', 'щодня слід на карті, у неділю — розкриття', det, !st) +
        kart('vgadai', 'Вгадай, де це було', 'опис події — ваша точка на карті', DZH.koloda ? (den.podiia ? 'подія дня зіграна' : 'подія дня чекає') : 'скоро', !DZH.koloda) +
        (DZH.vulytsia ? kart('vulytsia', 'Вулиця дня', 'одна вулиця на добу — вгадайте за 7 спроб', den.vulytsia ? 'сьогодні зіграно' : 'сьогодні не зіграно') : '') +
        kart('kvalifikuy', 'Кваліфікуй', 'фабула → стаття → як вирішують суди; для студентів і курсантів', r[1] ? Y.sproby(s, 'kvalifikuy', K, c.data).bezkoshtovnykh + ' безкоштовні справи сьогодні' : 'скоро', !r[1]) +
        '</div><p class="i-prym">Справи дня однакові для всіх; очки — лише за точність. <button type="button" class="i-lnk" data-i="hra" data-gra="nalashtuvannia">Налаштування</button></p>', true);
    });
  }

  // ---------- «Детектив тижня» ----------
  var SPRAVA = null;
  function stanSpravy(s) { return chytaty('mv-ihry-detektyv-' + s.id, { znaideni: [], versii: [], vatson: '', vykresleno: {}, naraxovano: false }); }
  function detektyv() {
    zavantazhyty('spravy').then(function (d) {
      var c = chas();
      var st = d && Y.spravaTyzhnia(d.spravy, c.data);
      if (!st) { ramka('Детектив тижня', '<p>Справа тижня з\'явиться згодом.</p>'); return; }
      var s = SPRAVA = st.sprava, ss = stanSpravy(s), t = Y.stanTyzhnia(c);
      var h = '<div class="i-poznachka"><b>' + esc(s.poznachka) + '</b><span>Заклади й свідки вигадані; вулиця, вид події, час і місце — з рішення суду. Гра шукає місце й подію, а не людину.</span></div>';
      h += '<p class="i-den">' + esc(NAZVY_DNIV[c.den]) + ' · день ' + c.den + ' з 7' + (st.demo ? ' · <span class="i-zrazok">зразок</span>' : '') + '</p>';
      h += '<div class="i-kroky" aria-hidden="true">' + [1, 2, 3, 4, 5, 6, 7].map(function (i) {
        return '<i class="' + (i <= 6 && ss.znaideni.indexOf(i) !== -1 ? 'z' : i <= t.slidiv || (i === 7 && t.rozkryttia) ? 'v' : '') + '"></i>'; }).join('') + '</div>';
      h += '<h3>' + esc(s.nazva) + '</h3><p>' + esc(s.vyklyk) + '</p>';
      if (t.rozkryttia) h += rozkryttia(s, ss);
      h += '<h3>Сліди</h3><ol class="i-slidy">';
      s.slidy.forEach(function (sl) {
        if (sl.n > t.slidiv) { h += '<li class="i-zakr">Слід ' + sl.n + ' — ' + esc(NAZVY_DNIV[sl.n]) + '</li>'; return; }
        if (ss.znaideni.indexOf(sl.n) !== -1) {
          h += '<li class="i-znaid"><b>Слід ' + sl.n + '</b>' + sl.rechennia.map(function (r) {
            return '<p><span class="i-mitka-dz i-dz-' + r.dzherelo + '">' + esc(MITKY[r.dzherelo]) + '</span> ' + esc(r.tekst) + '</p>'; }).join('') + '</li>';
          return;
        }
        h += '<li><b>Слід ' + sl.n + '</b><p>' + esc(sl.zahadka) + '</p><div class="i-ryad"><button type="button" class="knopka klav" data-i="shukaty" data-n="' + sl.n + '">Шукати на карті</button>' +
          (ss.vatson === c.data ? '' : '<button type="button" class="knopka klav i-druh" data-i="vatson" data-n="' + sl.n + '">Підказка Ватсона</button>') + '</div></li>';
      });
      h += '</ol>';
      h += blokno(s, ss) + versiiaForma(s, ss, c, t);
      ramka('Детектив тижня', h);
    });
  }
  function blokno(s, ss) {
    return '<h3>Блокнот</h3><p class="i-prym">Торкніться станції, щоб викреслити. Сліди звужують коло — викреслюйте самі.</p><div class="i-chipy">' +
      s.polia.de.kandydaty.map(function (k) { return '<button type="button" class="i-chip' + (ss.vykresleno[k.id] ? ' vykr' : '') + '" data-i="vykreslyty" data-k="' + k.id + '">' + esc(k.nazva) + '</button>'; }).join('') +
      '</div><button type="button" class="i-lnk" data-i="pokazaty-mistsia">Показати станції на карті</button>';
  }
  function versiiaForma(s, ss, c, t) {
    if (t.rozkryttia) return '';
    var ost = ss.versii[ss.versii.length - 1] || {};
    var sel = function (p) {
      return '<label><span>' + esc(s.polia[p].pytannia) + '</span><select data-pole="' + p + '"><option value="">—</option>' +
        s.polia[p].kandydaty.map(function (k) { return '<option value="' + k.id + '"' + (ost[p] === k.id ? ' selected' : '') + '>' + esc(k.nazva.replace(/[«»]/g, '')) + '</option>'; }).join('') + '</select></label>';
    };
    var segodni = ost.data === c.data;
    var vh = '';
    if (ost.data) {
      var v = Y.vidhuk(s, ost, Math.min(t.slidiv, ss.znaideni.length ? Math.max.apply(null, ss.znaideni) : 0));
      vh = '<p class="i-vidhuk">Остання версія (' + esc(NAZVY_DNIV[ost.den]) + '): ' + (v.z ? v.tak + ' з ' + v.z + ' полів, чий слід ви вже знайшли, — правильно.' : 'відгук з\'явиться, коли знайдете сліди про «що», «коли» чи поле справи.') + ' Про «де» гра не каже до неділі.</p>';
    }
    return '<h3>Версія</h3><p class="i-prym">Одна на день; у неділю о 20:00 рахується остання.</p><div class="i-forma">' +
      Y.POLIA.map(sel).join('') + '</div>' + vh +
      '<button type="button" class="knopka klav knopka--holovna" data-i="versiia"' + (segodni ? ' disabled' : '') + '>' + (segodni ? 'Сьогодні версію подано' : 'Подати версію') + '</button>';
  }
  function rozkryttia(s, ss) {
    var o = Y.ochkyDetektyva(s, ss.versii);
    if (!ss.naraxovano && ss.versii.length) { ss.naraxovano = true; ss.bali = narakhuvaty(o.razom); pysaty('mv-ihry-detektyv-' + s.id, ss); }
    var vidp = Y.POLIA.map(function (p) { var k = s.polia[p].kandydaty.filter(function (x) { return x.id === s.polia[p].vidpovid; })[0]; return esc(s.polia[p].pytannia) + ' <b>' + esc(k.nazva) + '</b>'; }).join('<br>');
    return '<section class="i-rozkr"><h3>Розкриття</h3><p>' + vidp + '</p><h4>Що було насправді (з рішення суду)</h4><p>' + esc(s.rozkryttia.spravzhnie) +
      ' <a href="' + esc(s.rishennia.url) + '" target="_blank" rel="noopener noreferrer">Рішення суду</a></p><h4>Що вигадано</h4><p>' + esc(s.rozkryttia.vyhadka) + '</p>' +
      '<p class="i-ochky">' + chyslo(o.razom) + ' ' + H.slovoOchky(o.razom) + ' · Холмс розкрив після сліду ' + s.kholms + '</p></section>';
  }
  var DII = {
    hra: function (t) { pokazaty(t.getAttribute('data-gra')); },
    shukaty: function (t) {
      var n = Number(t.getAttribute('data-n')), s = SPRAVA, sl = s.slidy[n - 1];
      if (window.matchMedia('(max-width: 700px)').matches) panel.classList.add('zghornuta');
      rezhym(function (ll) {
        if (!Y.znaideno(sl, ll.lat, ll.lng)) { toast('Тут сліду немає. Спробуйте ще.'); return true; }
        var ss = stanSpravy(s); if (ss.znaideni.indexOf(n) === -1) ss.znaideni.push(n); pysaty('mv-ihry-detektyv-' + s.id, ss);
        marker(sl.tsil.lat, sl.tsil.lon, 'slid', 'Слід ' + n); rezhym(null); panel.classList.remove('zghornuta');
        toast('Слід ' + n + ' знайдено'); detektyv(); return true;
      }, 'Торкніться карти там, де, на вашу думку, слід ' + n);
    },
    vatson: function (t) {
      var n = Number(t.getAttribute('data-n')), sl = SPRAVA.slidy[n - 1], ss = stanSpravy(SPRAVA);
      ss.vatson = chas().data; pysaty('mv-ihry-detektyv-' + SPRAVA.id, ss);
      // Показує район (≈ 3 км), а не саме місце: центр зсунуто на сталу відстань.
      letity(sl.tsil.lat + 0.008, sl.tsil.lon - 0.012, 12.6); toast('Ватсон: слід десь у цій частині міста'); detektyv();
    },
    vykreslyty: function (t) { var ss = stanSpravy(SPRAVA), k = t.getAttribute('data-k'); ss.vykresleno[k] = !ss.vykresleno[k]; pysaty('mv-ihry-detektyv-' + SPRAVA.id, ss); t.classList.toggle('vykr'); },
    'pokazaty-mistsia': function () {
      prybratyMitky(); var ss = stanSpravy(SPRAVA);
      SPRAVA.polia.de.kandydaty.forEach(function (k) { marker(k.lat, k.lon, 'stantsiia' + (ss.vykresleno[k.id] ? ' vykr' : ''), k.nazva.replace(/[«»]/g, '')); });
      var m = karta(); if (m && window.maplibregl) {
        var b = new maplibregl.LngLatBounds(); SPRAVA.polia.de.kandydaty.forEach(function (k) { b.extend([k.lon, k.lat]); });
        m.fitBounds(b, { padding: { top: 80, bottom: 80, left: 40, right: window.innerWidth > 700 ? 420 : 40 }, duration: MV.tykho ? 600 : 1200 });
      }
    },
    versiia: function () {
      var v = { data: chas().data, den: chas().den };
      panel.querySelectorAll('[data-pole]').forEach(function (x) { v[x.getAttribute('data-pole')] = x.value; });
      if (Y.POLIA.some(function (p) { return !v[p]; })) { toast('Заповніть усі чотири поля'); return; }
      var ss = stanSpravy(SPRAVA); ss.versii.push(v); pysaty('mv-ihry-detektyv-' + SPRAVA.id, ss); detektyv();
    },
    'vgadai-start': function (t) { vgadaiStart(t.getAttribute('data-typ')); },
    'vgadai-dali': function () { vgadaiKrok(); },
    'kv-rezhym': function (t) { pysaty('mv-ihry-kv-rezhym', t.getAttribute('data-r')); kvalifikuy(); },
    'kv-start': function () { kvStart(); },
    'kv-vidpovid': function () { kvVidpovid(); },
    'kv-karta': function (t) { var la = Number(t.getAttribute('data-lat')), lo = Number(t.getAttribute('data-lon')); prybratyMitky(); marker(la, lo, 'kv'); letity(la, lo, 14.5); },
    'v-podilytysia': function () { vPodilytysia(); },
    paket: function () { toast(K.oplata_chomu_ni); },
    obmin: function (t) { var r = Y.obminMozhlyvyi(bali(), K.obmin.filter(function (x) { return x.id === t.getAttribute('data-t'); })[0], K, chas().data); toast(r.mozhna ? 'Обмін — через кабінет.' : r.chomu); },
    skynuty: function () {
      if (!window.confirm('Стерти очки, бали й прогрес ігор на цьому пристрої?')) return;
      Object.keys(localStorage).forEach(function (k) { if (k.indexOf('mv-ihry-') === 0) localStorage.removeItem(k); });
      pokazaty('nalashtuvannia');
    }
  };
  panel.addEventListener('change', function (e) {
    if (e.target.id === 'i-ne-proponuvaty') { var z = chytaty('mv-ihry-zaproshennia', {}); z.ne_proponuvaty = e.target.checked; pysaty('mv-ihry-zaproshennia', z); }
  });

  // ---------- «Вгадай, де це було» на карті ----------
  var VG = null;
  function vgadai() {
    zavantazhyty('koloda').then(function (kol) {
      if (!kol) { ramka('Вгадай, де це було', '<p>Гра з\'явиться з колодою подій.</p>'); return; }
      var c = chas(), s = bali(), p = Y.sproby(s, 'vgadai', K, c.data), den = chytaty('mv-ihry-den-' + c.data, {});
      ramka('Вгадай, де це було', '<p>Читаєте, що сталося, — і торкаєтеся карти там, де, на вашу думку, це було. До 1 000 очок за подію: ≤ 50 м — 1 000, 500 м — 500, 5 км — 0.</p>' +
        (kol.demo ? '<p class="i-prym">Демо-колода: події узагальнені, місця — площі й станції метро.</p>' : '') +
        '<button type="button" class="knopka klav knopka--holovna" data-i="vgadai-start" data-typ="den"' + (den.podiia ? ' disabled' : '') + '>' + (den.podiia ? 'Подію дня зіграно' : 'Подія дня — та сама для всіх') + '</button>' +
        '<button type="button" class="knopka klav" data-i="vgadai-start" data-typ="sproba"' + (p.mozhna ? '' : ' disabled') + '>Спроба: ' + K.vgadai_podii_v_sprobi + ' подій</button>' +
        '<p class="i-prym">Безкоштовних спроб сьогодні: ' + p.bezkoshtovnykh + ' з ' + K.bezkoshtovno_na_den.vgadai + (p.kuplenykh ? ' · куплених: ' + p.kuplenykh : '') + '. Події кожної спроби однакові для всіх у цей день.</p>');
    });
  }
  function vgadaiStart(typ) {
    zavantazhyty('koloda').then(function (kol) {
      var c = chas(), podii = H.pidhotuvatyKolodu(kol).podii, s = bali(), spysok;
      if (typ === 'den') { spysok = [H.podiyaDnya(podii, c.data)]; }
      else {
        var nomer = (s.vykorystano.vgadai || 0) + (s.vykorystano.vgadai_k || 0) + 1;
        if (!PROBA) { var v = Y.vytratyty(s, 'vgadai', K, c.data); if (!v) { toast('Спроби на сьогодні закінчились'); return; } if (v === 'kuplena') s.kuplenoVytracheno = (s.vykorystano.vgadai_k || 0) + 1; zberehtyBali(s); }
        spysok = Y.sprobaVgadai(podii, c.data, nomer, K.vgadai_podii_v_sprobi);
      }
      VG = { typ: typ, podii: spysok, i: -1, ochky: 0 };
      if (window.matchMedia('(max-width: 700px)').matches) panel.classList.add('zghornuta');
      vgadaiKrok();
    });
  }
  function vgadaiKrok() {
    prybratyMitky(); VG.i++;
    if (VG.i >= VG.podii.length) {
      panel.classList.remove('zghornuta'); rezhym(null);
      var b = narakhuvaty(VG.ochky);
      if (VG.typ === 'den') { var c = chas(), den = chytaty('mv-ihry-den-' + c.data, {}); den.podiia = true; pysaty('mv-ihry-den-' + c.data, den); }
      ramka('Вгадай, де це було', '<p class="i-ochky">' + chyslo(VG.ochky) + ' ' + H.slovoOchky(VG.ochky) + (b ? ' · +' + b + ' ' + slovoBaly(b) : '') + '</p><button type="button" class="knopka klav" data-i="hra" data-gra="vgadai">Ще раз</button>');
      return;
    }
    var p = VG.podii[VG.i];
    ramka('Вгадай, де це було', '<p class="i-den">Подія ' + (VG.i + 1) + ' з ' + VG.podii.length + ' · ' + esc(p.vyd) + ', ' + esc(p.rik) + '</p><p class="i-opys">' + esc(p.opys_korotkyi) + '</p><p class="i-prym">Торкніться карти там, де, на вашу думку, це сталося.</p>');
    rezhym(function (ll) {
      var m = H.vidstan(ll.lat, ll.lng, p.lat, p.lon), o = H.ochky(m); VG.ochky += o;
      marker(ll.lat, ll.lng, 'sproba'); marker(p.lat, p.lon, 'pravda', 'тут');
      rezhym(null); panel.classList.remove('zghornuta');
      ramka('Вгадай, де це було', '<p class="i-den">Подія ' + (VG.i + 1) + ' з ' + VG.podii.length + '</p><p class="i-ochky">' + H.vidstanTekstom(m) + ' · ' + chyslo(o) + ' ' + H.slovoOchky(o) + '</p><p>' + esc(p.opys_povnyi) + '</p>' +
        (/^https:\/\//.test(p.rishennya_url || '') ? '<p><a href="' + esc(p.rishennya_url) + '" target="_blank" rel="noopener noreferrer">Рішення суду</a></p>' : '') +
        '<button type="button" class="knopka klav knopka--holovna" data-i="vgadai-dali">' + (VG.i + 1 < VG.podii.length ? 'Далі' : 'Підсумок') + '</button>');
      var mp = karta(); if (mp && window.maplibregl) mp.fitBounds(new maplibregl.LngLatBounds([ll.lng, ll.lat], [ll.lng, ll.lat]).extend([p.lon, p.lat]), { padding: 90, maxZoom: 15, duration: MV.tykho ? 600 : 1000 });
      return true;
    });
  }

  // ---------- «Вулиця дня» на карті — робоча версія ZAVDANNYA-114 (MV-126), дані — site/hra/vulytsia_dnia.py ----------
  // Одна загадка на добу, однакова для всіх (дата за Києвом); підказки — як на сторінці гри (спальні райони — раніше й
  // «частина району»); фінал — сторінка вулиці, «Поділитися» без назви вулиці, підписка. Без даних гри картки в меню немає.
  var VD = null;
  function vulytsia() {
    zavantazhyty('vulytsia').then(function (d) {
      if (!d || !V || !d.zahadky || !d.zahadky.length) { pokazaty('menyu'); return; }
      var c = chas(), vul = d.vulytsi.map(V.vulytsia), za = {}; vul.forEach(function (v) { za[v.slug] = v; });
      var z = V.zahadkaDnya(d.zahadky, c.data), zah = d.zahadky[z.i], tsil = za[zah.slug];
      if (!tsil) { pokazaty('menyu'); return; }
      var kl = 'mv-ihry-vulytsia-' + c.data;
      var st = chytaty(kl, { sproby: [], kin: false });
      st.sproby = (st.sproby || []).filter(function (s, i, a) { return za[s] && a.indexOf(s) === i; });
      VD = { d: d, vul: vul, za: za, zah: zah, tsil: tsil, kl: kl, st: st, data: c.data };
      vMalyuvaty();
    });
  }
  function vRozghadano() { var s = VD.st.sproby; return s.length > 0 && s[s.length - 1] === VD.tsil.slug; }
  function vPidkazky() {
    var zah = VD.zah, tsil = VD.tsil, st = VD.st;
    var nevd = st.sproby.filter(function (s) { return s !== tsil.slug; }).length;
    var spysok = V.pidkazkyDlia(zah), vidkr = st.kin ? spysok.map(function (p) { return p.pole; }) : V.vidkryti(nevd, zah);
    return '<ol class="i-vd-pidk">' + spysok.map(function (p, i) {
      var t;
      if (vidkr.indexOf(p.pole) === -1) return '<li class="zakr"><span>Підказка ' + (i + 1) + '</span>Відкриється після ' + p.pislia + '-ї невдалої спроби</li>';
      if (p.pole === 'rayon') t = esc(tsil.rayon) + ' район';
      else if (p.pole === 'chastyna') t = esc(zah.chastyna.charAt(0).toUpperCase() + zah.chastyna.slice(1));
      else if (p.pole === 'litera') t = 'Назва починається на «' + esc(V.persha(tsil)) + '»';
      else t = '<small>Одна з подій на цій вулиці · ' + esc(zah.podiia.vyd) + ' · ' + esc(zah.podiia.rik) + '</small>«' + esc(zah.podiia.opys) + '»';
      return '<li><span>Підказка ' + (i + 1) + '</span>' + t + '</li>';
    }).join('') + '</ol>';
  }
  function vRyadok(slug, i) {
    var v = VD.za[slug], p = V.porivnyaty(v, VD.tsil);
    var kl = function (t, tak, pidpys) { return '<i class="' + (tak ? 'tak' : '') + '" aria-label="' + pidpys + ': ' + esc(t) + (tak ? ', збігається' : ', не збігається') + '">' + esc(t) + '</i>'; };
    var vid = p.tak ? '<i class="tak">тут</i>' : '<i aria-label="Загадана — за ' + H.vidstanTekstom(p.vidstanM) + ' ' + p.napryamPovnyi + '"><svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true" data-az="' + p.azymut + '"><path d="M12 20V5M6 11l6-6 6 6"/></svg>' + H.vidstanTekstom(p.vidstanM) + '</i>';
    return '<li' + (p.tak ? ' class="tak"' : '') + '><b><span>' + (i + 1) + '</span>' + esc(v.nazva) + '</b><div class="i-kl">' + vid +
      kl(v.rayon.replace(/ський$/, 'ськ.').replace(/цький$/, 'цьк.'), p.rayon, 'Район') +
      kl(chyslo(v.n) + (p.n > 0 ? ' ↑' : p.n < 0 ? ' ↓' : ''), p.n === 0, 'Подій') + kl(v.typ, p.typ, 'Тип') +
      kl(v.vyrizn || 'нічим особливим', p.vyrizn, 'Вирізняє') + '</div></li>';
  }
  function vKolektsiia() {
    var k = chytaty('mv-ihry-vulytsia-kolektsiia', []);
    if (k.indexOf(VD.tsil.slug) === -1) { k.push(VD.tsil.slug); pysaty('mv-ihry-vulytsia-kolektsiia', k); }
    var n = k.length;
    return n + ' ' + (n % 10 === 1 && n % 100 !== 11 ? 'вулицю' : (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)) ? 'вулиці' : 'вулиць');
  }
  function vKinets() {
    var tsil = VD.tsil, zah = VD.zah, d = VD.d, tak = vRozghadano(), zv = zah.zvuzhennia || {}, pd = zah.podiia;
    var h = '<section class="i-rozkr i-vd-kin"><p class="i-den">' + (tak ? 'Розгадано з ' + VD.st.sproby.length + '-ї спроби з ' + d.sprob : 'Цього разу ні — загадана вулиця') + '</p>' +
      '<h3>' + esc(tsil.nazva) + '</h3><p class="i-prym">' + esc(tsil.rayon) + ' район · ' + chyslo(tsil.n) + ' подій у даних' + (d.roky ? ' за ' + esc(d.roky) : '') + '</p>';
    if (tsil.vyrizn) h += '<p>Що вирізняє вулицю: ' + esc(/^[А-ЯІЇЄҐA-Z]{2}/.test(tsil.vyrizn) ? tsil.vyrizn : tsil.vyrizn.charAt(0).toLowerCase() + tsil.vyrizn.slice(1)) + ' — частка вища, ніж по місту.</p>';
    if (zv.vsi) h += '<p class="i-prym">Як вивести відповідь: у грі ' + chyslo(zv.vsi) + ' вулиць; у цьому районі — ' + zv.rayon + '; з тим самим «вирізняє» — ' + zv.vyrizn + '; і з таким числом подій — ' + zv.n + '. Відповідь одна — це перевіряє програма.</p>';
    h += '<p class="i-vd-podiia">«' + esc(pd.opys) + '»<small>' + esc(pd.vyd) + ' · ' + esc(pd.rik) + (pd.url ? ' · <a href="' + esc(pd.url) + '" target="_blank" rel="noopener noreferrer">рішення суду' + (pd.nomer ? ' № ' + esc(pd.nomer) : '') + '</a>' : '') + '</small></p>' +
      '<p class="i-ryad"><a class="knopka klav knopka--holovna" href="/vulytsia/' + esc(tsil.slug) + '/?dzherelo=hra-vulytsia">Сторінка вулиці</a><button type="button" class="knopka klav i-druh" data-i="v-podilytysia">Поділитися</button></p>' +
      '<p class="i-prym" id="i-vd-stan" role="status"></p>' +
      (PROBA || VD.data !== Y.chasKyiv().data ? '' : '<p class="i-prym">Наступна вулиця — завтра.</p>') +
      '<p class="i-prym">Відкрито ' + vKolektsiia() + ' на цьому пристрої.</p></section>' +
      '<h3>А що на вашій вулиці?</h3><p>Сторінка кожної вулиці — числа безкоштовно; <a href="/oplata/?tovar=pidpyska&amp;dzherelo=hra-vulytsia">підписка</a> показує події з адресами і нове біля дому.</p>' +
      '<p class="i-ryad"><a class="knopka klav" href="/vulytsi/?dzherelo=hra-vulytsia">Знайти свою вулицю</a><a class="knopka klav i-druh" href="/oplata/?tovar=pidpyska&amp;dzherelo=hra-vulytsia">Підписка</a></p>';
    return h;
  }
  function vMalyuvaty() {
    var st = VD.st, tsil = VD.tsil;
    var h = '<p class="i-den">' + esc(new Date(VD.data + 'T12:00:00').toLocaleDateString('uk-UA', { day: 'numeric', month: 'long' })) + (VD.d.demo ? ' · <span class="i-zrazok">зразок</span>' : '') + '</p>' +
      '<p>Загадана вулиця Києва — одна на добу, однакова для всіх. Назвіть будь-яку: гра скаже, як далеко й у якому напрямку загадана, чи той самий район, більше чи менше там подій. Спроб — ' + VD.d.sprob + '.</p>' +
      vPidkazky() + (st.sproby.length ? '<ol class="i-sproby">' + st.sproby.map(vRyadok).join('') + '</ol>' : '');
    if (!st.kin) h += '<label class="i-poshuk"><span class="prykhovano">Назва вулиці</span><input id="i-vul" type="search" autocomplete="off" placeholder="Назва вулиці" role="combobox" aria-expanded="false" aria-controls="i-vul-pidk"></label><ul id="i-vul-pidk" class="i-pidk" role="listbox"></ul>' +
      '<p class="i-prym">Лишилось спроб: ' + (VD.d.sprob - st.sproby.length) + '.</p>';
    else h += vKinets();
    ramka('Вулиця дня', h);
    panel.querySelectorAll('svg[data-az]').forEach(function (e) { e.style.transform = 'rotate(' + e.getAttribute('data-az') + 'deg)'; });
    prybratyMitky();
    st.sproby.forEach(function (slug, i) { var v = VD.za[slug]; marker(v.lat, v.lon, slug === tsil.slug ? 'pravda' : 'sproba', (i + 1) + ' · ' + v.nazva); });
    if (st.kin && !(st.sproby.length && st.sproby[st.sproby.length - 1] === tsil.slug)) marker(tsil.lat, tsil.lon, 'pravda', tsil.nazva);
    var inp = $('#i-vul'), ul = $('#i-vul-pidk');
    if (!inp) return;
    var znaid = [];
    inp.addEventListener('input', function () {
      var krim = {}; st.sproby.forEach(function (s) { krim[s] = true; });
      znaid = V.shukaty(VD.vul, inp.value, krim, 6);
      ul.innerHTML = znaid.map(function (v) { return '<li role="option"><button type="button" data-slug="' + esc(v.slug) + '">' + esc(v.nazva) + (v.stara ? ' (кол. ' + esc(v.stara) + ')' : '') + ' <small>' + esc(v.rayon) + '</small></button></li>'; }).join('') +
        (!znaid.length && inp.value.trim().length > 1 ? '<li class="i-pidk-0">Такої вулиці в грі немає — у грі вулиці, де в даних щонайменше 5 подій.</li>' : '');
      inp.setAttribute('aria-expanded', znaid.length ? 'true' : 'false');
    });
    inp.addEventListener('keydown', function (e) { if (e.key === 'Enter' && znaid.length) { e.preventDefault(); vSproba(znaid[0].slug); } });
    ul.addEventListener('click', function (e) { var b = e.target.closest('[data-slug]'); if (b) vSproba(b.getAttribute('data-slug')); });
  }
  function vSproba(slug) {
    var st = VD.st;
    if (st.kin || !VD.za[slug] || st.sproby.indexOf(slug) !== -1) return;
    st.sproby.push(slug);
    var tak = slug === VD.tsil.slug;
    if (tak || st.sproby.length >= VD.d.sprob) {
      st.kin = true;
      if (!PROBA && !st.bali) st.bali = narakhuvaty(tak ? Math.max(0, 1000 - 125 * (st.sproby.length - 1)) : 0) || -1;
      var c = chas(), den = chytaty('mv-ihry-den-' + c.data, {}); den.vulytsia = true; pysaty('mv-ihry-den-' + c.data, den);
      letity(VD.tsil.lat, VD.tsil.lon, 14.5);
    } else {
      var p = V.porivnyaty(VD.za[slug], VD.tsil);
      toast('Ні, загадана — за ' + H.vidstanTekstom(p.vidstanM) + ' ' + p.napryamPovnyi);
      var v = VD.za[slug]; letity(v.lat, v.lon, 12.5);
    }
    pysaty(VD.kl, st); vMalyuvaty();
  }
  function vPodilytysia() {
    var por = VD.st.sproby.map(function (s) { return V.porivnyaty(VD.za[s], VD.tsil); });
    var t = V.tekstPodilytysia(VD.data, por, vRozghadano(), VD.d.sprob, location.origin + '/karta/?hra=vulytsia');   // без ?data= і назви вулиці
    var stan = $('#i-vd-stan');
    var pokaz = function (s) { if (stan) stan.textContent = s; };
    if (navigator.share) navigator.share({ text: t }).catch(function () { /* скасовано */ });
    else if (navigator.clipboard) navigator.clipboard.writeText(t).then(function () { pokaz('Скопійовано — вставте в чат чи допис.'); toast('Скопійовано'); }, function () { pokaz(t); });
    else pokaz(t);
  }

  // ---------- «Кваліфікуй» ----------
  var KV = null;
  function kvalifikuy() {
    zavantazhyty('kvalifikuy').then(function (d) {
      if (!d) { ramka('Кваліфікуй', '<p>Скоро.</p>'); return; }
      var c = chas(), s = bali(), p = Y.sproby(s, 'kvalifikuy', K, c.data), r = chytaty('mv-ihry-kv-rezhym', 'zvychainyi');
      var zihrano = chytaty('mv-ihry-kv-' + c.data, []);
      var spysok = Y.spravyKvalifikuy(d.spravy, c.data);
      var dali = spysok.filter(function (x) { return zihrano.indexOf(x.id) === -1; })[0];
      KV = { d: d, sprava: dali, rezhym: r };
      ramka('Кваліфікуй', '<p>Фабула справжньої справи — ви обираєте статтю й частину — гра показує, як вирішили суди Києва.</p>' +
        '<div class="i-seg" role="group" aria-label="Режим"><button type="button" data-i="kv-rezhym" data-r="zvychainyi" aria-pressed="' + (r === 'zvychainyi') + '">Звичайний</button><button type="button" data-i="kv-rezhym" data-r="student" aria-pressed="' + (r === 'student') + '">Для студентів і курсантів</button></div>' +
        '<p class="i-prym">' + (r === 'student' ? 'Лише номери статей, без назв; після відповіді — чому саме ця кваліфікація.' : 'Назви статей простими словами.') + '</p>' +
        (dali ? '<button type="button" class="knopka klav knopka--holovna" data-i="kv-start"' + (p.mozhna ? '' : ' disabled') + '>Наступна справа</button>' : '<p>Справи на сьогодні закінчились — завтра нові.</p>') +
        '<p class="i-prym">Безкоштовних справ сьогодні: ' + p.bezkoshtovnykh + ' з ' + K.bezkoshtovno_na_den.kvalifikuy + (p.kuplenykh ? ' · куплених спроб: ' + p.kuplenykh : '') + '. Справи дня — однакові для всіх.</p>' +
        (d.zrazok ? '<p class="i-prym">Прототип: 7 справ із перевіреної вибірки рішень.</p>' : ''));
    });
  }
  function kvStart() {
    var c = chas(), s = bali();
    if (!PROBA) { if (!Y.vytratyty(s, 'kvalifikuy', K, c.data)) { toast('Спроби на сьогодні закінчились'); return; } zberehtyBali(s); }
    var sp = KV.sprava, st = KV.d.statti, stud = KV.rezhym === 'student';
    var vars = sp.varianty.slice().sort();
    var h = '<p class="i-den">Справа · ' + esc(sp.rishennia.sud) + '</p><p class="i-opys">' + esc(sp.fabula) + '</p><h3>Стаття</h3><div class="i-varianty">' +
      vars.map(function (v) { return '<label class="i-var"><input type="radio" name="kv-st" value="' + esc(v) + '"><span><b>ст. ' + esc(v.split(' ')[1]) + ' ' + esc(v.split(' ')[0]) + '</b>' + (stud ? '' : ' — ' + esc(st[v].nazva)) + '</span></label>'; }).join('') + '</div>';
    var chs = {}; vars.forEach(function (v) { (st[v].chastyny || []).forEach(function (x) { chs[x] = 1; }); });
    var ch = Object.keys(chs).sort();
    if (ch.length) h += '<h3>Частина</h3><div class="i-seg i-ch">' + ch.map(function (x) { return '<label><input type="radio" name="kv-ch" value="' + x + '"><span>ч. ' + x + '</span></label>'; }).join('') + '<label><input type="radio" name="kv-ch" value=""><span>без частин</span></label></div>';
    h += '<button type="button" class="knopka klav knopka--holovna" data-i="kv-vidpovid">Відповісти</button>';
    if (sp.tochka) h += '<button type="button" class="i-lnk" data-i="kv-karta" data-lat="' + sp.tochka.lat + '" data-lon="' + sp.tochka.lon + '">Де це було — на карті</button>';
    ramka('Кваліфікуй', h);
  }
  function kvVidpovid() {
    var a = panel.querySelector('[name="kv-st"]:checked'), b = panel.querySelector('[name="kv-ch"]:checked');
    if (!a) { toast('Оберіть статтю'); return; }
    var sp = KV.sprava, d = KV.d, r = Y.ochkyKvalifikuy(sp, d.statti, { stattia: a.value, chastyna: b ? b.value : '' });
    var c = chas(), zihr = chytaty('mv-ihry-kv-' + c.data, []); zihr.push(sp.id); pysaty('mv-ihry-kv-' + c.data, zihr);
    var bal = narakhuvaty(r.ochky);
    var v = sp.vidpovid, ch = d.chastky[v.stattia];
    var h = '<p class="i-ochky">' + (r.stattia ? 'Стаття — так' : 'Стаття — ні') + (r.chastyna === null ? '' : r.chastyna ? ' · частина — так' : ' · частина — ні') + ' · ' + chyslo(r.ochky) + ' ' + H.slovoOchky(r.ochky) + (bal ? ' · +' + bal + ' ' + slovoBaly(bal) : '') + '</p>' +
      '<p>Суд: <b>' + (v.chastyna ? 'ч. ' + esc(v.chastyna) + ' ' : '') + 'ст. ' + esc(v.stattia.split(' ')[1]) + ' ' + esc(v.stattia.split(' ')[0]) + '</b> — ' + esc(d.statti[v.stattia].nazva) + '.</p>' +
      '<h3>Чому</h3><p>' + esc(sp.chomu) + '</p><h3>Як вирішують суди Києва</h3>';
    if (ch) {
      h += '<p class="i-prym">' + esc(ch.spravy) + ', ' + esc(d.dzherelo_chastok) + '. Це не прогноз для конкретної справи.</p><ul class="i-smuhy">' + ch.chastky.map(function (x) {
        return '<li><span>' + esc(x[0]) + '</span><i data-shyr="' + x[1] + '"></i><b>' + x[1] + ' %</b></li>'; }).join('') + '</ul>';
    } else h += '<p class="i-prym">Частки для цієї статті ще не пораховано — з\'являться в «Судовій практиці».</p>';
    h += '<p><a href="' + esc(sp.rishennia.url) + '" target="_blank" rel="noopener noreferrer">Рішення суду</a> · <a href="/sudova-praktyka/">Судова практика</a></p><button type="button" class="knopka klav" data-i="hra" data-gra="kvalifikuy">Далі</button>';
    ramka('Кваліфікуй', h);
    panel.querySelectorAll('[data-shyr]').forEach(function (e) { e.style.width = Math.max(2, Number(e.getAttribute('data-shyr'))) + '%'; });
  }

  // ---------- Бали й спроби (MV-130) ----------
  function baliEkran() {
    var c = chas(), s = bali();
    var h = '<p class="i-bal"><span>' + chyslo(s.bali) + '</span> ' + slovoBaly(s.bali) + ' · сьогодні +' + s.baliSohodni + ' з ' + K.stelia_baliv_na_den + '</p>' +
      '<p class="i-prym">' + K.ochok_za_bal + ' очок = 1 бал — з безкоштовних і куплених спроб однаково. Бали не передаються й не виводяться в гроші; очки — лише за точність; справи дня однакові для всіх.</p>' +
      '<h3>Обміняти на</h3>' + K.obmin.map(function (t) {
        var pr = Math.min(100, Math.round(100 * s.bali / t.baliv));
        return '<div class="i-obmin"><div><b>' + esc(t.nazva) + '</b> <span>' + chyslo(t.baliv) + ' балів (замість ' + t.tsina + ' грн)</span></div><div class="i-prohres"><i data-shyr="' + pr + '"></i></div><button type="button" class="knopka klav" data-i="obmin" data-t="' + t.id + '">Обміняти</button></div>';
      }).join('') + '<p class="i-prym">' + esc(K.obmin_chomu_ni) + '</p>' +
      '<h3>Спроби сьогодні</h3><ul class="i-spr">' + ['vgadai', 'kvalifikuy'].map(function (g) {
        var p = Y.sproby(s, g, K, c.data); return '<li>' + (g === 'vgadai' ? 'Вгадай, де це було' : 'Кваліфікуй') + ': безкоштовних ' + p.bezkoshtovnykh + ' з ' + K.bezkoshtovno_na_den[g] + '</li>'; }).join('') +
      '<li>Куплених: ' + (s.kupleni || 0) + '</li></ul>' +
      '<h3>Докупити спроби</h3><div class="i-pakety">' + K.pakety.map(function (p) {
        return '<button type="button" class="i-paket klav' + (p.holovnyi ? ' holovnyi' : '') + '" data-i="paket"' + (K.oplata_uvimknena ? '' : ' aria-disabled="true"') + '><b>' + p.sprob + ' спроб</b><span>' + p.tsina + ' грн</span></button>'; }).join('') +
      '</div><p class="i-prym">' + esc(K.oplata_chomu_ni) + '</p>';
    ramka('Бали й спроби', h);
    panel.querySelectorAll('[data-shyr]').forEach(function (e) { e.style.width = Number(e.getAttribute('data-shyr')) + '%'; });
  }
  function nalashtuvannia() {
    var z = chytaty('mv-ihry-zaproshennia', {});
    ramka('Налаштування ігор', '<label class="i-perem"><input type="checkbox" id="i-ne-proponuvaty"' + (z.ne_proponuvaty ? ' checked' : '') + '><span>Не пропонувати ігри на карті</span></label>' +
      '<h3>Курс балів</h3><p>' + K.ochok_za_bal + ' очок = 1 бал; довідка — ' + chyslo(K.obmin[0].baliv) + ' балів, місяць підписки — ' + chyslo(K.obmin[1].baliv) + '; не більше ' + K.stelia_baliv_na_den + ' балів на день.</p>' +
      '<p class="i-prym">Курс задає «Моя вулиця»; бали й прогрес поки зберігаються лише на цьому пристрої.</p>' +
      '<button type="button" class="knopka klav" data-i="skynuty">Стерти прогрес ігор на пристрої</button>');
  }

  // ---------- тихе запрошення ----------
  var SESIIA = { pokazano: false }, DOTYKY = 0, START = Date.now(), ZAPR_GRA = null;
  try { SESIIA.pokazano = sessionStorage.getItem('mv-ihry-zapr') === '1'; } catch (e) { /* без пам'яті */ }
  function shchosVidkryto() {
    return !panel.hidden || !!(window.MvKarta && window.MvKarta.zaraz && window.MvKarta.zaraz()) ||
      !document.getElementById('info').hidden || !document.getElementById('pidkazky').hidden || ekran.classList.contains('shukayu');
  }
  ekran.addEventListener('pointerdown', function (e) { if (e.target.closest('.maplibregl-canvas')) DOTYKY++; }, true);
  function hovatyZaproshennia(zakryto) {
    if (zapr.hidden) return; zapr.hidden = true;
    var z = chytaty('mv-ihry-zaproshennia', {});
    pysaty('mv-ihry-zaproshennia', zakryto ? Y.zakrylyZaproshennia(z, chas().data) : Y.pryinialyZaproshennia(z));
  }
  function kvPoruch(d) {
    var m = karta(); if (!d || !m || m.getZoom() < 12.5) return null;
    var c = m.getCenter();
    return d.spravy.filter(function (s) { return s.tochka && H.vidstan(c.lat, c.lng, s.tochka.lat, s.tochka.lon) < 1500; })[0] || null;
  }
  function sprobuvatyZaproshennia() {
    if (PROBA && !q.has('ihry-zaproshennia')) return;
    var c = chas();
    var kont = { sekund: (Date.now() - START) / 1000, dotykiv: DOTYKY, vidkryto: shchosVidkryto(), data: c.data };
    if (!Y.chasZaproshuvaty(chytaty('mv-ihry-zaproshennia', {}), SESIIA, kont)) return;
    Promise.all([zavantazhyty('spravy'), zavantazhyty('kvalifikuy'), zavantazhyty('nalashtuvannia')]).then(function (r) {
      if (SESIIA.pokazano || shchosVidkryto()) return;
      K = K || r[2];
      var st = r[0] && Y.spravaTyzhnia(r[0].spravy, c.data), den = chytaty('mv-ihry-den-' + c.data, {});
      var novyi = st && Math.min(c.den, 6) > stanSpravy(st.sprava).znaideni.length;
      var kv = kvPoruch(r[1]);
      var gra = Y.yakaGra({ kvalifikuyPoruch: !!kv, detektyvNovyiSlid: novyi, vulytsiaYe: !!DZH.vulytsia, vulytsiaZihrano: den.vulytsia,
        podiiaYe: !!DZH.koloda, podiiaZihrano: den.podiia, kvalifikuyZalyshylos: !!r[1] && K && Y.sproby(bali(), 'kvalifikuy', K, c.data).bezkoshtovnykh > 0 });
      if (!gra) return;
      var tekst = { 'kvalifikuy-tut': 'Кваліфікуй: тут була справа — яка це стаття?', detektyv: 'Детектив тижня: слід ' + Math.min(c.den, 6) + ' чекає на карті',
        vulytsia: 'Вулиця дня: вгадайте вулицю за 7 спроб', vgadai: 'Подія дня: вгадайте, де це було', kvalifikuy: 'Кваліфікуй: справа дня — яка це стаття?' }[gra];
      ZAPR_GRA = gra === 'kvalifikuy-tut' ? 'kvalifikuy' : gra;
      zapr.querySelector('.z-tekst').textContent = tekst;
      zapr.hidden = false; SESIIA.pokazano = true;
      try { sessionStorage.setItem('mv-ihry-zapr', '1'); } catch (e) { /* без пам'яті */ }
    });
  }
  zapr.addEventListener('click', function (e) {
    if (e.target.closest('.z-x')) { hovatyZaproshennia(true); return; }
    if (e.target.closest('.z-tekst')) { hovatyZaproshennia(false); vidkryty(ZAPR_GRA); }
  });
  setInterval(sprobuvatyZaproshennia, 1000);

  // Запуск з посилання: /karta/?hra=detektyv|vgadai|vulytsia|kvalifikuy або ?ihry
  var hra = q.get('hra');
  if (hra || q.has('ihry')) {
    var pochaty = function () { vidkryty(hra === 'de-tse-bulo' ? 'vgadai' : hra); };
    if (window.MvKarta && window.MvKarta.gotovo) pochaty(); else setTimeout(pochaty, 600);
  }
  window.MvIhry = { vidkryty: vidkryty, zakryty: zakryty, pokazaty: pokazaty, stan: function () { return { zaraz: ZARAZ, rezhym: !!REZHYM, zaproshennia: !zapr.hidden }; } };
})();
