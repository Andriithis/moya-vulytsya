// «Кваліфікуй: кар'єра» — показ і дотики (ZAVDANNYA-146; ZAVDANNYA-152: у карті, кабінет викладача, соковитість).
// Обчислення — у kariera-yadro.js. Один модуль на два місця: панель «Ігри» карти сайту (site/ihry/ihry.js) і окрема сторінка
// (index.html + kariera-storinka.js):
//   MvKariera.zapustyty({ korin, dani, zapasni, bali, ochky, tost, prokrutka, posylannia }) → { zupynyty() }
//     korin — куди малювати гру; dani — адреса kariera.json (або вже готовий об'єкт); zapasni — адреса зачатку kvalifikuy.json;
//     bali(очки) → нараховані бали спільної скарбнички ігор (немає — без балів); ochky — {sprava_dnia, den} з nalashtuvannia.json;
//     tost(t, мс) — повідомлення (немає — свій); prokrutka() — нагору; posylannia(код, назва) — посилання на заняття для групи.
// Прогрес — лише на пристрої (localStorage «mv-kariera-1»), бали — у скарбничку ігор лише за «Справи дня». Нічого не надсилає.
// Звук вимкнений, доки людина не ввімкне (MV-169); відгук на дотик — рух і коротка вібрація.
// Для перевірки й знімків: ?den=РРРР-ММ-ДД — дата гри; ?nabir=… — заняття за посиланням викладача.
(function (korin) {
  'use strict';
  var Y = korin.MvKarieraYadro;
  var KLIUCH = 'mv-kariera-1', KLIUCH_ZVUK = 'mv-kariera-zvuk', KLIUCH_NABORY = 'mv-kariera-nabory';
  var MIS = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня'];
  var TYKHO = korin.matchMedia && korin.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var KROK_NAZVA = { 1: 'кодекс', 2: 'стаття', 3: 'частина' }, KROK_LITERA = { 1: 'К', 2: 'С', 3: 'Ч' };

  function esc(t) {
    return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function el(teg, klas, html) { var e = document.createElement(teg); if (klas) e.className = klas; if (html != null) e.innerHTML = html; return e; }
  function knopka(klas, html, dia) { var b = el('button', klas, html); b.type = 'button'; if (dia) b.addEventListener('click', dia); return b; }
  function chytaty(k, typ) { try { var v = JSON.parse(localStorage.getItem(k)); return v == null ? typ : v; } catch (e) { return typ; } }
  function pysaty(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* приватний режим — без пам'яті */ } }
  function datyLiudsku(d) { var c = d.split('-'); return Number(c[2]) + ' ' + MIS[Number(c[1]) - 1]; }
  function dniv(n) { var a = n % 10, b = n % 100; return a === 1 && b !== 11 ? 'день' : a >= 2 && a <= 4 && (b < 12 || b > 14) ? 'дні' : 'днів'; }
  function baliv(n) { var a = n % 10, b = n % 100; return a === 1 && b !== 11 ? 'бал' : a >= 2 && a <= 4 && (b < 12 || b > 14) ? 'бали' : 'балів'; }
  function chyslo(n, f) { var a = n % 10, b = n % 100; return n + ' ' + (a === 1 && b !== 11 ? f[0] : a >= 2 && a <= 4 && (b < 12 || b > 14) ? f[1] : f[2]); }
  var SPRAV = ['справа', 'справи', 'справ'], STUD = ['студент', 'студенти', 'студентів'];
  function zirky(n) { var s = ''; for (var i = 1; i <= 5; i++) s += i <= n ? '●' : '○'; return s; }
  function fabulaHtml(t) { return esc(t).replace(/\[стаття\]/g, '<mark>стаття прихована</mark>'); }
  function statt(k) { var c = k.split(' '); return 'ст. ' + c[1] + ' ' + c[0]; }

  function zapustyty(o) {
    var parametry = new URLSearchParams(location.search);
    var D = null, S = null, vkladka = 'den', pidvkladka = 'temy';
    var lichylnyk = 0, potochna = null, zaniattia = null, poruch = 0, zhyvyi = true;
    var OCHKY = o.ochky || { sprava_dnia: 100, den: 300 };

    // ---------- каркас ----------
    var kar = el('div', 'kar');
    kar.innerHTML = '<div class="kar-shapka">' +
      '<div class="plashka plashka--seriia" title="Серія днів: щодня 5 справ"><small>серія</small><b data-k="seriia">0</b></div>' +
      '<button class="plashka plashka--riven" type="button" data-k="riven" title="Рівень і досвід"><span class="riven-nazva" data-k="riven-nazva">—</span>' +
      '<span class="smuha" aria-hidden="true"><span data-k="smuha"></span></span><small data-k="dosvid">0</small></button>' +
      '<span class="kar-poruch" data-k="poruch" hidden></span>' +
      '<button class="plashka kar-zvuk" type="button" data-k="zvuk" aria-pressed="false" aria-label="Звук"></button></div>' +
      '<nav class="vkladky" role="tablist">' +
      '<button role="tab" data-v="den" aria-selected="true">Справи дня</button>' +
      '<button role="tab" data-v="trenuvannia" aria-selected="false">Тренування</button>' +
      '<button role="tab" data-v="plutaiu" aria-selected="false">Де плутаю</button>' +
      '<button role="tab" data-v="vykladachu" aria-selected="false">Викладачу</button></nav>' +
      '<div class="vmist" data-k="vmist"></div>' +
      '<p class="pidval">Навчання, не юридична допомога. Справи — справжні рішення судів Києва, знеособлені; статтю в тексті приховано.</p>' +
      '<div class="vikno" data-k="vikno" hidden></div>' + (o.tost ? '' : '<div class="tost" data-k="tost" role="status" aria-live="polite"></div>');
    o.korin.innerHTML = '';
    o.korin.appendChild(kar);
    var $ = function (k) { return kar.querySelector('[data-k="' + k + '"]'); };
    function tost(t, ms) {
      if (o.tost) return o.tost(t, ms);
      var e = $('tost'); e.textContent = t; e.classList.add('vydno');
      clearTimeout(tost.t); tost.t = setTimeout(function () { e.classList.remove('vydno'); }, ms || 2600);
    }
    function nagoru() { if (o.prokrutka) o.prokrutka(); else korin.scrollTo(0, 0); }

    // ---------- звук (вимкнений за замовчуванням) і дотик ----------
    var ZVUK = chytaty(KLIUCH_ZVUK, 'ni') === 'tak', audio = null;
    var IK_ZVUK = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z"/>';
    function zvukKnopka() {
      var b = $('zvuk'); b.setAttribute('aria-pressed', ZVUK ? 'true' : 'false');
      b.title = ZVUK ? 'Звук увімкнено' : 'Звук вимкнено — увімкнути';
      b.innerHTML = IK_ZVUK + (ZVUK ? '<path d="M16.5 9a4 4 0 0 1 0 6M19 6.5a7.5 7.5 0 0 1 0 11"/>' : '<path d="m17 9 5 6M22 9l-5 6"/>') + '</svg>';
    }
    $('zvuk').addEventListener('click', function () {
      ZVUK = !ZVUK; pysaty(KLIUCH_ZVUK, ZVUK ? 'tak' : 'ni'); zvukKnopka();
      if (ZVUK) grai('tak');
      tost(ZVUK ? 'Звук увімкнено' : 'Звук вимкнено', 1400);
    });
    zvukKnopka();
    function ton(c, f, poch, tryv, typ, guchn) {
      var g = c.createGain(), osc = c.createOscillator(), t = c.currentTime + poch;
      osc.type = typ || 'sine'; osc.frequency.value = f;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(guchn || 0.05, t + 0.015);
      g.gain.exponentialRampToValueAtTime(0.0001, t + tryv);
      osc.connect(g); g.connect(c.destination); osc.start(t); osc.stop(t + tryv + 0.02);
    }
    var NOTY = {
      dotyk: function (c) { ton(c, 520, 0, 0.05, 'triangle', 0.03); },
      tak: function (c) { ton(c, 660, 0, 0.14, 'triangle'); ton(c, 880, 0.09, 0.2, 'triangle'); },
      ni: function (c) { ton(c, 330, 0, 0.2, 'sine', 0.04); },
      riven: function (c) { [523, 659, 784, 1047, 1319].forEach(function (f, i) { ton(c, f, i * 0.09, 0.32, 'triangle', 0.05); }); },
      den: function (c) { [587, 740, 880].forEach(function (f, i) { ton(c, f, i * 0.1, 0.3, 'sine', 0.05); }); }
    };
    function grai(n) {
      if (!ZVUK) return;
      try {
        audio = audio || new (korin.AudioContext || korin.webkitAudioContext)();
        if (audio.state === 'suspended') audio.resume();
        NOTY[n](audio);
      } catch (e) { /* без звуку */ }
    }
    function vibro(p) { if (navigator.vibrate) { try { navigator.vibrate(p); } catch (e) { /* немає */ } } }

    // ---------- сховище ----------
    function zberehty() { pysaty(KLIUCH, S); }
    function zavantazhytyStan() { var s = chytaty(KLIUCH, null); return s && s.v === Y.N.versiia ? s : null; }
    function sohodni() { var d = parametry.get('den'); return /^\d{4}-\d{2}-\d{2}$/.test(d || '') ? d : Y.den(Date.now()); }

    // ---------- шапка ----------
    function shapka() {
      var r = Y.riven(S);
      $('riven-nazva').textContent = r.nazva;
      $('dosvid').textContent = S.dosvid + (r.do ? ' / ' + r.do : '');
      $('smuha').style.width = (r.do ? Math.round(100 * (S.dosvid - r.vid) / (r.do - r.vid)) : 100) + '%';
      $('seriia').textContent = S.seriia;
    }
    function blysk(e) { if (!e) return; e.classList.remove('blysk'); void e.offsetWidth; e.classList.add('blysk'); }
    function balLetyt(vid, tekst, klas) {
      var r = vid.getBoundingClientRect();
      var b = el('div', 'kar-letyt' + (klas ? ' ' + klas : ''), tekst);
      b.style.left = (r.left + r.width / 2 - 20) + 'px'; b.style.top = (r.top - 8) + 'px';
      document.body.appendChild(b); setTimeout(function () { b.remove(); }, 1100);
    }
    function pokazatyPoruch() {
      var e = $('poruch');
      if (poruch < 3) { e.hidden = true; return; }
      e.hidden = false; e.textContent = poruch + ' поспіль'; blysk(e);
    }

    // ---------- справа: кодекс → стаття → частина → як вирішив суд ----------
    function sprava(kont, x, opts) {
      var k = el('article', 'kartka');
      var rik = (x.data || '').slice(0, 4);
      k.innerHTML = '<div class="kartka-meta">' + (opts.mitka ? '<span class="znachok' + (opts.povtor ? ' znachok--povtor' : '') + '">' + esc(opts.mitka) + '</span>' : '') +
        '<span>Рішення суду' + (rik ? ', ' + rik : '') + '</span><span class="zirky" title="Складність ' + x.skladnist + ' з 5">' + zirky(x.skladnist) + '</span></div>' +
        '<p class="fabula">' + fabulaHtml(x.fabula) + '</p>';
      var chastyny = Y.variantyChastyny(D, x);
      var kroky = el('div', 'kroky');
      var nKrokiv = chastyny.length ? 3 : 2;
      for (var i = 0; i < nKrokiv; i++) kroky.appendChild(el('span', 'krok' + (i === 0 ? ' ye' : '')));
      k.appendChild(kroky);
      var zona = el('div');
      k.appendChild(zona);
      kont.appendChild(k);
      var vybir = {};
      var pravKodeks = x.stattia.split(' ')[0];

      function poznachyty(i, tak) { kroky.children[i].className = 'krok ' + (tak ? 'tak' : 'ni'); if (kroky.children[i + 1]) kroky.children[i + 1].className = 'krok ye'; }
      function knopky(pytannia, varianty, klas, prav, dali) {
        zona.innerHTML = '';
        zona.appendChild(el('p', 'pytannia', esc(pytannia)));
        var hrupa = el('div', 'variant ' + (klas || ''));
        varianty.forEach(function (v) {
          var b = knopka('klavisha', v.html, function () {
            var tak = v.id === prav;
            Array.prototype.forEach.call(hrupa.children, function (c) { c.disabled = true; if (c !== b && c.dataset.id !== prav) c.classList.add('tyho'); });
            b.classList.add(tak ? 'tak' : 'ni');
            if (!tak) Array.prototype.forEach.call(hrupa.children, function (c) { if (c.dataset.id === prav) c.classList.add('tak', 'pidkazka'); });
            grai(tak ? 'tak' : 'ni'); vibro(tak ? 12 : [10, 40, 10]);
            setTimeout(function () { if (zhyvyi) dali(v.id, tak); }, tak ? 450 : 1100);
          });
          b.dataset.id = v.id;
          b.addEventListener('pointerdown', function () { if (!b.disabled) grai('dotyk'); });
          hrupa.appendChild(b);
        });
        zona.appendChild(hrupa);
      }
      function krokKodeks() {
        knopky('Який кодекс?', [
          { id: 'КУпАП', html: 'КУпАП<small>адміністративне правопорушення</small>' },
          { id: 'КК', html: 'КК<small>кримінальне правопорушення</small>' }
        ], '', pravKodeks, function (id, tak) { vybir.kodeks = id; poznachyty(0, tak); krokStattia(); });
      }
      function krokStattia() {
        var v = Y.variantyStatti(D, x).map(function (s) {
          var st = D.statti[s];
          return { id: s, html: 'ст. ' + esc(s.split(' ')[1]) + ' ' + esc(st.kodeks) + '<small>' + esc(st.korotko || st.nazva) + '</small>' };
        });
        knopky('Яка стаття ' + pravKodeks + '?', v, '', x.stattia, function (id, tak) {
          vybir.stattia = id; poznachyty(1, tak);
          if (chastyny.length) krokChastyna(); else pidsumok();
        });
      }
      function krokChastyna() {
        knopky('Яка частина ст. ' + x.stattia.split(' ')[1] + ' ' + pravKodeks + '?', chastyny.map(function (c) { return { id: c, html: 'ч. ' + esc(c) }; }),
          'variant--chastyny', x.chastyna, function (id, tak) { vybir.chastyna = id; poznachyty(2, tak); pidsumok(); });
      }
      function pidsumok() {
        var d = sohodni();
        var bulo = S.dni[d] && S.dni[d].zrobleno[x.doc] !== undefined, denBuv = S.ostanniiDen === d;
        var r = Y.vidpovisty(S, x, vybir, d, opts.rezhym, D);
        // бали — у спільну скарбничку ігор: лише за «Справи дня» (однакові для всіх), раз на справу й раз на день
        var b = 0;
        if (opts.rezhym === 'den' && !bulo && o.bali) {
          if (r.otsinka.vse) b += o.bali(OCHKY.sprava_dnia || 0) || 0;
          if (!denBuv && S.ostanniiDen === d) b += o.bali(OCHKY.den || 0) || 0;
        }
        poruch = r.otsinka.vse ? poruch + 1 : 0;
        zberehty();
        shapka(); pokazatyPoruch();
        var st = D.statti[x.stattia];
        var p = el('div', 'pidsumok');
        var bezChastyny = !x.chastyna && st.chastyny && st.chastyny.length;
        p.innerHTML = '<div class="kar-shtamp ' + (r.otsinka.vse ? 'tak' : 'ni') + '">' + (r.otsinka.vse ? 'як суд' : 'суд — інакше') + '</div>' +
          '<div class="vidpovid">' + (r.otsinka.vse ? 'Так, як суд: ' : 'Суд кваліфікував: ') + esc(Y.povna(x.stattia, x.chastyna)) +
          '<small>' + esc(st.nazva) + (bezChastyny ? ' · частину в рішенні не названо' : '') + '</small></div>' +
          (x.chomu ? '<div class="tsytata"><b>Як написав суд</b>' + esc(x.chomu) + '</div>' : '<p class="tykho">Чому саме так — суд пояснює в самому рішенні (посилання нижче).</p>') + chastkyHtml(st, x.chastyna) +
          '<p class="tykho"><a href="' + esc(x.url) + '" target="_blank" rel="noopener">Рішення повністю — у реєстрі суду</a> · +' + r.bal + ' досвіду' +
          (b ? ' · +' + b + ' ' + baliv(b) + ' у скарбничку ігор' : '') + '</p>';
        p.appendChild(knopka('klavisha klavisha--holovna klavisha--shyroka', opts.daliTekst || 'Далі', function () { opts.dali(r); }));
        zona.innerHTML = '';
        zona.appendChild(p);
        Array.prototype.forEach.call(p.querySelectorAll('[data-w]'), function (e) { setTimeout(function () { e.style.width = e.dataset.w + '%'; }, 30); });
        balLetyt($('riven'), '+' + r.bal);
        if (b) setTimeout(function () { balLetyt($('riven'), '+' + b + ' ' + baliv(b), 'kar-letyt--bal'); }, 350);
        blysk($('riven'));
        if (opts.pislia) opts.pislia(r);
        if (r.novyiRiven) setTimeout(function () { if (zhyvyi) viknoRiven(r.novyiRiven); }, 700);
      }
      krokKodeks();
    }

    function chastkyHtml(st, ch) {
      var ch_ = Object.keys(st.chastky || {});
      if (ch_.length < 2) return '';
      var vsogo = ch_.reduce(function (a, k) { return a + st.chastky[k]; }, 0);
      var h = '<div class="chastky"><small class="tykho">Як суди Києва кваліфікували цю статтю (рішення, з яких зібрано гру):</small>';
      ch_.slice(0, 5).forEach(function (k) {
        var pct = Math.round(100 * st.chastky[k] / vsogo);
        h += '<div class="chastka' + ((k === ch || (k === '—' && !ch)) ? ' tsia' : '') + '"><span>' + (k === '—' ? 'без частини' : 'ч. ' + esc(k)) + '</span>' +
          '<span><span class="s" data-w="' + Math.max(pct, 2) + '"></span></span><span>' + pct + ' %</span></div>';
      });
      return h + '</div>';
    }

    // ---------- вікна ----------
    function vikno(html, knopky_) {
      var v = $('vikno');
      v.innerHTML = '';
      var t = el('div', 'vikno-tilo', html);
      (knopky_ || []).forEach(function (k) { t.appendChild(k); });
      v.appendChild(t); v.hidden = false;
      return t;
    }
    function zakrytyVikno() { $('vikno').hidden = true; }
    // Новий рівень: смуга добігає до кінця, звання «підноситься», під ним — що відкрилось.
    function viknoRiven(r) {
      var novi = Object.keys(D.statti).filter(function (k) { return D.statti[k].riven === r.maksSkladnist; }).map(statt);
      var shliakh = Y.N.treky[S.trek].rivni.map(function (n, i) {
        return '<li class="' + (i < r.indeks ? 'buv' : i === r.indeks ? 'tse' : '') + '">' + esc(n) + '</li>';
      }).join('');
      var t = vikno('<div class="kar-riven"><p class="tykho">Новий рівень</p><div class="kar-riven-smuha"><span></span></div>' +
        '<h2 class="kar-riven-nazva">' + esc(r.nazva) + '</h2><ol class="kar-shliakh">' + shliakh + '</ol>' +
        '<p>Тепер у тренуванні — справи складності до ' + r.maksSkladnist + ' з 5' +
        (novi.length ? ': рідші статті (' + esc(novi.slice(0, 6).join(', ')) + (novi.length > 6 ? '…' : '') + ') і рідші частини.' : '.') + '</p></div>',
        [knopka('klavisha klavisha--holovna klavisha--shyroka', 'Далі', zakrytyVikno)]);
      t.classList.add('vikno-tilo--riven');
      grai('riven'); vibro([15, 60, 15, 60, 30]);
    }

    // ---------- вкладки ----------
    function pokazaty(v) {
      vkladka = v;
      Array.prototype.forEach.call(kar.querySelectorAll('.vkladky button'), function (b) { b.setAttribute('aria-selected', b.dataset.v === v ? 'true' : 'false'); });
      var m = $('vmist'); m.innerHTML = '';
      ({ den: vDen, trenuvannia: vTrenuvannia, plutaiu: vPlutaiu, vykladachu: vVykladachu })[v](m);
      nagoru();
    }

    function vDen(m) {
      if (zaniattia) return vZaniattia(m);
      var d = sohodni();
      var st = Y.stanDnia(S, D, d);
      m.appendChild(el('h2', '', 'Справи дня · ' + datyLiudsku(d)));
      m.appendChild(el('p', 'tykho', 'П’ять справ, однакових для всіх сьогодні: від частої до рідкісної. Усі п’ять — день у серії.' +
        (o.bali ? ' Бали в скарбничку ігор — лише за справи дня.' : '')));
      var ryad = el('div', 'dni');
      var nastupna = -1;
      st.forEach(function (z, i) {
        if (z.zrobleno === undefined && nastupna < 0) nastupna = i;
        ryad.appendChild(el('div', 'den-krok' + (z.zrobleno === 1 ? ' tak' : z.zrobleno === 0 ? ' ni' : ''), '<b>' + (i + 1) + '</b>' + zirky(z.sprava.skladnist)));
      });
      if (nastupna >= 0) ryad.children[nastupna].classList.add('zaraz');
      m.appendChild(ryad);
      if (nastupna < 0) {
        var pr = st.filter(function (z) { return z.zrobleno === 1; }).length;
        var k = el('div', 'kartka kar-den-zakryto', '<h2>' + pr + ' з 5 — як суд</h2><p>Серія: <b>' + S.seriia + '</b> ' + dniv(S.seriia) +
          '. Нові справи дня — завтра. Помилки повернуться в тренуванні через 1, 3 і 7 днів.</p>');
        k.appendChild(knopka('klavisha klavisha--holovna klavisha--shyroka', 'До тренування', function () { pokazaty('trenuvannia'); }));
        m.appendChild(k);
        return;
      }
      sprava(m, st[nastupna].sprava, { rezhym: 'den', mitka: 'Справа ' + (nastupna + 1) + ' з 5',
        daliTekst: nastupna === 4 ? 'Завершити день' : 'Наступна справа',
        pislia: function () {
          var z = Y.stanDnia(S, D, d)[nastupna];
          ryad.children[nastupna].className = 'den-krok ' + (z.zrobleno === 1 ? 'tak' : 'ni');
          if (nastupna === 4) { shapka(); blysk(kar.querySelector('.plashka--seriia')); grai('den'); }
        },
        dali: function () { pokazaty('den'); } });
    }

    function vTrenuvannia(m) {
      var r = Y.riven(S);
      m.appendChild(el('h2', '', 'Тренування'));
      m.appendChild(el('p', 'tykho', 'Рівень «' + esc(r.nazva) + '»: справи складності до ' + r.maksSkladnist + ' з 5. Помилки повертаються першими.'));
      if (!potochna) { potochna = Y.nastupna(D, S, sohodni(), lichylnyk); lichylnyk += 1; }
      sprava(m, potochna.sprava, { rezhym: 'trenuvannia', povtor: potochna.povtor, mitka: potochna.povtor ? 'Повтор помилки' : 'Нова справа',
        dali: function () { potochna = null; pokazaty('trenuvannia'); } });
    }

    function vPlutaiu(m) {
      var st = Y.statystyka(S, D);
      m.appendChild(el('h2', '', 'Де плутаю'));
      m.appendChild(el('p', 'tykho', 'Лише на цьому пристрої. «Правильно → обрано»: які кваліфікації ви змішуєте найчастіше.'));
      m.appendChild(el('div', 'tsyfry', '<div class="tsyfra"><b>' + st.vidpovidi + '</b><small>справ розібрано</small></div>' +
        '<div class="tsyfra"><b>' + Math.round(st.tochnist * 100) + ' %</b><small>як суд, повністю</small></div>' +
        '<div class="tsyfra"><b>' + st.povtoriv + '</b><small>справ чекають повтору</small></div>'));
      m.appendChild(el('h3', '', 'Найчастіші плутанини'));
      if (!st.pary.length) m.appendChild(el('div', 'pusto', 'Поки без помилок. Розберіть кілька справ — тут з’являться пари, які ви плутаєте.'));
      else {
        var u = el('ul', 'spysok');
        st.pary.forEach(function (p) {
          var c = p.para.split(' → ');
          u.appendChild(el('li', '', '<span class="t">' + esc(c[0]) + '<small>а ви обрали: ' + esc(c[1]) + '</small></span><b class="n">' + p.raz + '×</b>'));
        });
        m.appendChild(u);
      }
      m.appendChild(el('h3', '', 'За статтями'));
      if (!st.slabki.length) m.appendChild(el('div', 'pusto', 'Ще немає відповідей.'));
      else {
        var u2 = el('ul', 'spysok');
        st.slabki.slice(0, 10).forEach(function (s) {
          u2.appendChild(el('li', '', '<span class="t">' + esc(statt(s.stattia)) + '<small>' + esc(s.nazva) + ' · ' + s.pravylno + ' з ' + s.vsogo + '</small></span><b class="n">' + Math.round(s.tochnist * 100) + ' %</b>'));
        });
        m.appendChild(u2);
      }
      var z = knopka('klavisha kar-vidstup', 'Змінити доріжку (' + esc(Y.N.treky[S.trek].nazva) + ')', vyborTreku);
      m.appendChild(z);
    }

    // ---------- викладачу: теми, свій набір, таблиця групи (без сервера) ----------
    function posylannia(kod, nazva) {
      if (o.posylannia) return o.posylannia(kod, nazva);
      return location.origin + location.pathname + '?nabir=' + kod + (nazva ? '&nazva=' + encodeURIComponent(nazva) : '');
    }
    function nabory() { var n = chytaty(KLIUCH_NABORY, []); return Array.isArray(n) ? n : []; }
    function zapamiataty(kod, nazva, n) {
      var l = nabory().filter(function (x) { return x.kod !== kod; });
      l.unshift({ kod: kod, nazva: nazva || '', n: n, data: sohodni() });
      pysaty(KLIUCH_NABORY, l.slice(0, 20));
    }
    function vVykladachu(m) {
      m.appendChild(el('h2', '', 'Викладачу'));
      m.appendChild(el('p', 'tykho', 'Набір справ на заняття — за темою чи своїми статтями. Посилання однакове для всієї групи; наприкінці кожен ' +
        'студент бачить код результату й надсилає його вам разом з іменем. Коди складаються в таблицю групи тут, на вашому пристрої: ' +
        'сервер і реєстрація не потрібні, відповіді нікуди не надсилаються.'));
      var pv = el('div', 'kar-pidvkladky', '');
      [['temy', 'Теми занять'], ['svii', 'Свій набір'], ['hrupa', 'Група']].forEach(function (x) {
        var b = knopka('', x[1], function () { pidvkladka = x[0]; pokazaty('vykladachu'); });
        b.setAttribute('aria-pressed', pidvkladka === x[0] ? 'true' : 'false');
        pv.appendChild(b);
      });
      m.appendChild(pv);
      ({ temy: vTemy, svii: vSvii, hrupa: vHrupa })[pidvkladka](m);
    }
    function pokazatyNabir(kont, nb, nazva) {
      var kod = Y.kodNaboru(nb), url = posylannia(kod, nazva);
      zapamiataty(kod, nazva, nb.length);
      kont.innerHTML = '';
      kont.appendChild(el('h3', '', 'Посилання для групи' + (nazva ? ' · ' + esc(nazva) : '')));
      kont.appendChild(el('div', 'posylannia', esc(url)));
      var r = el('div', 'ryad');
      r.appendChild(knopka('klavisha', 'Скопіювати посилання', function () {
        (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(function () { tost('Скопійовано'); }, function () { tost('Скопіюйте вручну'); });
      }));
      r.appendChild(knopka('klavisha', 'Таблиця групи ›', function () { pidvkladka = 'hrupa'; pokazaty('vykladachu'); }));
      kont.appendChild(r);
      var u = el('ul', 'spysok');
      nb.forEach(function (x, i) {
        u.appendChild(el('li', '', '<span class="t">' + (i + 1) + '. ' + esc(Y.povna(x.stattia, x.chastyna)) + '<small>' + esc(x.fabula.slice(0, 110)) + '…</small></span><a href="' + esc(x.url) + '" target="_blank" rel="noopener">рішення</a>'));
      });
      kont.appendChild(el('h3', '', 'Ключ для викладача'));
      kont.appendChild(u);
      kont.scrollIntoView && kont.scrollIntoView({ behavior: TYKHO ? 'auto' : 'smooth', block: 'start' });
    }
    function vTemy(m) {
      var ts = Y.temy(D);
      m.appendChild(el('p', 'tykho', 'Готові теми: статті, які на заняттях найчастіше плутають. Набір — 10 справ порівну між статтями теми.'));
      if (!ts.length) { m.appendChild(el('div', 'pusto', 'У цьому випуску замало справ для готових тем — складіть свій набір.')); return; }
      var sitka = el('div', 'kar-temy'), vykhid = el('div');
      ts.forEach(function (t) {
        var b = knopka('klavisha kar-tema', '<b>' + esc(t.nazva) + '</b><small>що розрізняє: ' + esc(t.rozriznyaie) + '</small>' +
          '<span class="kar-tema-st">' + t.statti.map(function (k) { return esc(statt(k)); }).join(' · ') + ' · ' + chyslo(t.spraw, SPRAV) + '</span>', function () {
            var nb = Y.nabir(D, { statti: t.statti, kilkist: 10, maksSkladnist: 5, zerno: sohodni() + t.id });
            pokazatyNabir(vykhid, nb, t.nazva);
          });
        sitka.appendChild(b);
      });
      m.appendChild(sitka); m.appendChild(vykhid);
    }
    function vSvii(m) {
      var spysok = el('div', 'statti-vybir');
      Object.keys(D.statti).forEach(function (k) {
        var st = D.statti[k];
        var n = D.spravy.filter(function (x) { return x.stattia === k; }).length;
        spysok.appendChild(el('label', '', '<input type="checkbox" value="' + esc(k) + '"><span>' + esc(statt(k)) + '<br><small>' + esc(st.korotko || st.nazva) + ' · ' + n + ' справ</small></span>'));
      });
      m.appendChild(spysok);
      var ryad = el('div', 'ryad', '<label>Справ: <select data-k="nabir-n"><option>5</option><option selected>10</option><option>15</option><option>20</option></select></label>' +
        '<label>Складність до: <select data-k="nabir-sk"><option>2</option><option>3</option><option>4</option><option selected>5</option></select></label>' +
        '<input type="text" data-k="nabir-nazva" placeholder="Назва заняття" maxlength="60">');
      m.appendChild(ryad);
      var vykhid = el('div');
      m.appendChild(knopka('klavisha klavisha--holovna', 'Скласти набір', function () {
        var statti = Array.prototype.map.call(spysok.querySelectorAll('input:checked'), function (i) { return i.value; });
        var nb = Y.nabir(D, { statti: statti, kilkist: Number($('nabir-n').value), maksSkladnist: Number($('nabir-sk').value), zerno: sohodni() });
        if (!nb.length) { tost('Для цих статей справ немає — оберіть інші.'); return; }
        pokazatyNabir(vykhid, nb, $('nabir-nazva').value.trim());
      }));
      m.appendChild(vykhid);
    }
    function vHrupa(m) {
      var l = nabory();
      m.appendChild(el('p', 'tykho', 'Оберіть заняття й вставте коди студентів — кожен з нового рядка, ім’я перед кодом: «Іваненко Олена 7/10-…». ' +
        'Таблиця й імена лишаються лише на цьому пристрої.'));
      var vybir = el('div', 'ryad');
      var sel = el('select', 'kar-nabir-vybir');
      sel.innerHTML = l.map(function (x, i) { return '<option value="' + i + '">' + esc((x.nazva || 'Без назви') + ' · ' + chyslo(x.n, SPRAV) + ' · ' + datyLiudsku(x.data)) + '</option>'; }).join('') +
        '<option value="-1">Інше заняття — вставити посилання</option>';
      vybir.appendChild(sel);
      var pos = el('input', 'kar-posylannia-pole'); pos.type = 'text'; pos.placeholder = 'Посилання на заняття'; pos.hidden = l.length > 0;
      vybir.appendChild(pos);
      m.appendChild(vybir);
      var ta = el('textarea', 'kar-kody'); ta.rows = 6; ta.placeholder = 'Іваненко Олена 7/10-0g1k-a3f\nПетренко Ігор 9/10-0040-k2z';
      m.appendChild(ta);
      var vykhid = el('div');
      function kod() {
        if (sel.value !== '-1' && l[Number(sel.value)]) return l[Number(sel.value)].kod;
        var mm = /[?&]nabir=([0-9a-z.]+)/i.exec(pos.value) || /^([0-9a-z]+(?:\.[0-9a-z]+)+)$/i.exec(pos.value.trim());
        return mm ? mm[1] : '';
      }
      function zavantazh() { var k = kod(); ta.value = k ? chytaty('mv-kariera-hrupa-' + k, '') : ''; if (ta.value) tablytsia(); else vykhid.innerHTML = ''; }
      function tablytsia() {
        var k = kod();
        vykhid.innerHTML = '';
        if (!k) { tost('Оберіть заняття чи вставте посилання'); return; }
        var sp = Y.rozibratyKod(D, k);
        if (!sp.length) { vykhid.appendChild(el('div', 'pusto', 'Справ цього заняття немає в поточних даних гри.')); return; }
        pysaty('mv-kariera-hrupa-' + k, ta.value);
        var t = Y.tablytsiaHrupy(D, k, ta.value);
        var dobri = t.studenty.filter(function (s) { return s.r; });
        var h = '<div class="kar-tabl-obgortka"><table class="kar-tabl"><thead><tr><th>Студент</th><th>як суд</th>' +
          sp.map(function (x, i) { return '<th title="' + esc(Y.povna(x.stattia, x.chastyna)) + '">' + (i + 1) + '</th>'; }).join('') + '</tr></thead><tbody>';
        t.studenty.forEach(function (s) {
          if (!s.r) { h += '<tr class="nevirnyi"><td>' + esc(s.imia || '—') + '</td><td colspan="' + (sp.length + 1) + '">код не з цього заняття чи з помилкою: ' + esc(s.kod) + '</td></tr>'; return; }
          h += '<tr><td>' + esc(s.imia) + '</td><td><b>' + s.r.pravylno + '</b>/' + s.r.n + '</td>' + s.r.kroky.map(function (v) {
            return v === 0 ? '<td class="tak" title="як суд">✓</td>' : '<td class="ni" title="розійшовся із судом: ' + KROK_NAZVA[v] + '">' + KROK_LITERA[v] + '</td>';
          }).join('') + '</tr>';
        });
        h += '</tbody><tfoot><tr><td>Група</td><td>' + chyslo(dobri.length, STUD) + '</td>' + t.spravy.map(function (p) {
          return '<td>' + (p.z ? Math.round(100 * p.pravylno / p.z) + '%' : '—') + '</td>';
        }).join('') + '</tr></tfoot></table></div>' +
          '<p class="tykho">✓ — як суд; К — інший кодекс; С — інша стаття; Ч — інша частина.' + (t.nevirni ? ' Рядків без дійсного коду: ' + t.nevirni + '.' : '') + '</p>';
        vykhid.innerHTML = h;
        if (!dobri.length) return;
        var vazhki = t.spravy.map(function (p, i) { return { p: p, i: i }; }).filter(function (x) { return x.p.pravylno < x.p.z; })
          .sort(function (a, b) { return a.p.pravylno / a.p.z - b.p.pravylno / b.p.z || a.i - b.i; }).slice(0, 5);
        vykhid.appendChild(el('h3', '', 'Де плутає група'));
        if (!vazhki.length) vykhid.appendChild(el('div', 'pusto', 'Усі справи група кваліфікувала, як суд.'));
        else {
          var u = el('ul', 'spysok');
          vazhki.forEach(function (x) {
            var kr = [1, 2, 3].filter(function (v) { return x.p.kroky[v]; }).map(function (v) { return KROK_NAZVA[v] + ' — ' + x.p.kroky[v]; }).join(', ');
            u.appendChild(el('li', '', '<span class="t">Справа ' + (x.i + 1) + ' · ' + esc(Y.povna(x.p.sprava.stattia, x.p.sprava.chastyna)) +
              '<small>розійшлися із судом: ' + esc(kr) + '</small></span><b class="n">' + x.p.pravylno + '/' + x.p.z + '</b>'));
          });
          vykhid.appendChild(u);
        }
        vykhid.appendChild(el('h3', '', 'За статтями'));
        var u2 = el('ul', 'spysok');
        t.statti.forEach(function (s) {
          u2.appendChild(el('li', '', '<span class="t">' + esc(statt(s.stattia)) + '<small>' + esc((D.statti[s.stattia] || {}).korotko || '') + '</small></span><b class="n">' +
            (s.z ? Math.round(100 * s.pravylno / s.z) : 0) + ' %</b>'));
        });
        vykhid.appendChild(u2);
      }
      sel.addEventListener('change', function () { pos.hidden = sel.value !== '-1'; zavantazh(); });
      pos.addEventListener('change', zavantazh);
      m.appendChild(knopka('klavisha klavisha--holovna', 'Показати таблицю', tablytsia));
      m.appendChild(vykhid);
      zavantazh();
    }

    function vZaniattia(m) {
      var z = zaniattia;
      var i = z.vidpovidi.length;
      m.appendChild(el('div', 'zaniattia', '<b>Заняття' + (z.nazva ? ': ' + esc(z.nazva) : '') + '</b> · справа ' + Math.min(i + 1, z.spravy.length) + ' з ' + z.spravy.length +
        ' · набір від викладача'));
      if (i >= z.spravy.length) {
        var kod = Y.kodRezultatu(z.kod, z.vidpovidi);
        var k = el('div', 'kartka', '<h2>Заняття завершено</h2><p>Як суд: <b>' + kod.split('-')[0] + '</b>.</p>' +
          '<p>Надішліть викладачу цей код разом зі своїм іменем — з нього видно, на якому кроці ви розійшлися із судом у кожній справі:</p>' +
          '<div class="posylannia posylannia--kod">' + esc(kod) + '</div>');
        var r = el('div', 'ryad');
        r.appendChild(knopka('klavisha', 'Скопіювати код', function () {
          (navigator.clipboard ? navigator.clipboard.writeText(kod) : Promise.reject()).then(function () { tost('Скопійовано'); }, function () { tost('Скопіюйте вручну'); });
        }));
        r.appendChild(knopka('klavisha', 'До своєї гри', function () {
          zaniattia = null; parametry.delete('nabir'); parametry.delete('nazva');
          var q = parametry.toString(); history.replaceState(null, '', location.pathname + (q ? '?' + q : '')); pokazaty('den');
        }));
        k.appendChild(r); m.appendChild(k);
        return;
      }
      sprava(m, z.spravy[i], { rezhym: 'zaniattia', mitka: 'Заняття', daliTekst: i === z.spravy.length - 1 ? 'Завершити' : 'Наступна справа',
        pislia: function (r) { z.vidpovidi.push(Y.krokPomylky(r.otsinka)); }, dali: function () { pokazaty('den'); } });
    }

    // ---------- доріжка (перший вхід) ----------
    function vyborTreku() {
      var hrupa = el('div', 'trek');
      Object.keys(Y.N.treky).forEach(function (t) {
        var tr = Y.N.treky[t];
        hrupa.appendChild(knopka('klavisha klavisha--shyroka', esc(tr.nazva) + '<small>' + esc(tr.rivni.join(' → ')) + '</small>', function () {
          if (S) S.trek = t; else S = Y.novyi(t);
          zberehty(); zakrytyVikno(); shapka(); pokazaty(vkladka);
        }));
      });
      vikno('<h2>Кваліфікуй: кар’єра</h2><p>Справжні справи судів Києва без статті. Ви визначаєте кодекс, статтю й частину — і бачите, як вирішив суд, його ж словами.</p>' +
        '<p class="tykho">Навчання, не юридична допомога. Прогрес — лише на цьому пристрої.</p><p><b>Оберіть доріжку</b> (лише назви рівнів):</p>', [hrupa]);
    }

    // ---------- старт ----------
    function pochaty(dani) {
      if (!zhyvyi) return;
      D = Y.pidhotuvaty(dani);
      S = zavantazhytyStan();
      if (parametry.get('nabir')) {
        var sp = Y.rozibratyKod(D, parametry.get('nabir'));
        if (sp.length) zaniattia = { kod: parametry.get('nabir'), nazva: (parametry.get('nazva') || '').slice(0, 60), spravy: sp, vidpovidi: [] };
      }
      Array.prototype.forEach.call(kar.querySelectorAll('.vkladky button'), function (b) {
        b.addEventListener('click', function () { if (S) { if (b.dataset.v === 'vykladachu' && vkladka !== 'vykladachu') pidvkladka = 'temy'; pokazaty(b.dataset.v); } });
      });
      $('riven').addEventListener('click', function () { if (S) pokazaty('plutaiu'); });
      if (!S) {
        if (zaniattia) { S = Y.novyi('pravo'); zberehty(); }
        else { vyborTreku(); return; }
      }
      shapka();
      var v = parametry.get('vkladka');
      pokazaty(v && /^(den|trenuvannia|plutaiu|vykladachu)$/.test(v) ? v : 'den');
      if (D.zrazok) tost('Даних випуску немає — показано зразок із ' + D.spravy.length + ' справ.');
    }
    var vzhe = function (u) { return fetch(u, { credentials: 'omit' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); };
    (typeof o.dani === 'object' && o.dani ? Promise.resolve(o.dani) : (o.dani ? vzhe(o.dani) : Promise.reject()))
      .catch(function () { return o.zapasni ? vzhe(o.zapasni) : Promise.reject(); })
      .then(pochaty)
      .catch(function () { if (zhyvyi) $('vmist').innerHTML = '<div class="pusto">Не вдалося завантажити справи.</div>'; });

    return {
      zupynyty: function () {
        zhyvyi = false;
        if (audio && audio.close) { try { audio.close(); } catch (e) { /* */ } }
        o.korin.innerHTML = '';
      }
    };
  }

  korin.MvKariera = { zapustyty: zapustyty };
})(typeof window !== 'undefined' ? window : this);
