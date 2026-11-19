// Сторінка гри «Кваліфікуй: кар'єра» (ZAVDANNYA-146, прототип). Обчислення — у kariera-yadro.js; тут лише показ і дотики.
// Прогрес — лише на пристрої (localStorage). Нічого не надсилає. Дата для знімків — ?den=РРРР-ММ-ДД.
(function () {
  'use strict';
  var Y = window.MvKarieraYadro;
  var KLIUCH = 'mv-kariera-1';
  var parametry = new URLSearchParams(location.search);
  var D = null, S = null;
  var vkladka = 'den';
  var lichylnyk = 0;            // скільки справ тренування показано за сесію (для сталого генератора)
  var potochna = null;          // { sprava, povtor } у тренуванні
  var zaniattia = null;         // { kod, nazva, spravy, vidpovidi[] } — режим заняття за посиланням викладача
  var $ = function (id) { return document.getElementById(id); };

  function sohodni() {
    var d = parametry.get('den');
    return /^\d{4}-\d{2}-\d{2}$/.test(d || '') ? d : Y.den(Date.now());
  }
  function zberehty() { try { localStorage.setItem(KLIUCH, JSON.stringify(S)); } catch (e) { /* приватний режим — без збереження */ } }
  function zavantazhyty() {
    try { var s = JSON.parse(localStorage.getItem(KLIUCH) || 'null'); if (s && s.v === Y.N.versiia) return s; } catch (e) { /* */ }
    return null;
  }
  function esc(t) {
    return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function el(teg, klas, html) { var e = document.createElement(teg); if (klas) e.className = klas; if (html != null) e.innerHTML = html; return e; }
  function datyLiudsku(d) {
    var m = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня'];
    var c = d.split('-');
    return Number(c[2]) + ' ' + m[Number(c[1]) - 1];
  }
  function tost(t) {
    var e = $('tost'); e.textContent = t; e.classList.add('vydno');
    clearTimeout(tost.t); tost.t = setTimeout(function () { e.classList.remove('vydno'); }, 2600);
  }

  // ---------- звук і дотик: тихо, без «казино» ----------
  var audio = null;
  function zvuk(tak) {
    if (navigator.vibrate) navigator.vibrate(tak ? 12 : [10, 40, 10]);
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      var t = audio.currentTime;
      (tak ? [660, 880] : [330]).forEach(function (f, i) {
        var o = audio.createOscillator(), g = audio.createGain();
        o.type = 'sine'; o.frequency.value = f;
        g.gain.setValueAtTime(0.0001, t + i * 0.09);
        g.gain.exponentialRampToValueAtTime(0.05, t + i * 0.09 + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, t + i * 0.09 + 0.18);
        o.connect(g); g.connect(audio.destination); o.start(t + i * 0.09); o.stop(t + i * 0.09 + 0.2);
      });
    } catch (e) { /* без звуку */ }
  }
  function balLetyt(vid, bal) {
    if (!bal) return;
    var r = vid.getBoundingClientRect();
    var b = el('div', 'bal-letyt', '+' + bal);
    b.style.left = (r.left + r.width / 2 - 16) + 'px'; b.style.top = (r.top - 8) + 'px';
    document.body.appendChild(b); setTimeout(function () { b.remove(); }, 1000);
  }

  // ---------- шапка ----------
  function shapka() {
    var r = Y.riven(S);
    $('riven-nazva').textContent = r.nazva;
    $('dosvid').textContent = S.dosvid + (r.do ? ' / ' + r.do : '');
    $('smuha').style.width = (r.do ? Math.round(100 * (S.dosvid - r.vid) / (r.do - r.vid)) : 100) + '%';
    $('seriia').textContent = S.seriia;
  }
  function blysk(id) { var e = $(id); e.classList.remove('blysk'); void e.offsetWidth; e.classList.add('blysk'); }

  // ---------- справа: кодекс → стаття → частина → як вирішив суд ----------
  function fabulaHtml(t) { return esc(t).replace(/\[стаття\]/g, '<mark>стаття прихована</mark>'); }
  function zirky(n) { var s = ''; for (var i = 1; i <= 5; i++) s += i <= n ? '●' : '○'; return s; }

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
        var b = el('button', 'klavisha', v.html); b.type = 'button';
        b.addEventListener('click', function () {
          var tak = v.id === prav;
          Array.prototype.forEach.call(hrupa.children, function (c) { c.disabled = true; if (c !== b && c.dataset.id !== prav) c.classList.add('tyho'); });
          b.classList.add(tak ? 'tak' : 'ni');
          if (!tak) Array.prototype.forEach.call(hrupa.children, function (c) { if (c.dataset.id === prav) c.classList.add('tak'); });
          zvuk(tak);
          setTimeout(function () { dali(v.id, tak); }, tak ? 450 : 1100);
        });
        b.dataset.id = v.id;
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
      var r = Y.vidpovisty(S, x, vybir, sohodni(), opts.rezhym, D);
      zberehty();
      shapka();
      var st = D.statti[x.stattia];
      var p = el('div', 'pidsumok');
      var bezChastyny = !x.chastyna && st.chastyny && st.chastyny.length;
      p.innerHTML = '<div class="vidpovid">' + (r.otsinka.vse ? 'Так, як суд: ' : 'Суд кваліфікував: ') + esc(Y.povna(x.stattia, x.chastyna)) +
        '<small>' + esc(st.nazva) + (bezChastyny ? ' · частину в рішенні не названо' : '') + '</small></div>' +
        (x.chomu ? '<div class="tsytata"><b>Як написав суд</b>' + esc(x.chomu) + '</div>' : '<p class="tykho">Чому саме так — суд пояснює в самому рішенні (посилання нижче).</p>') + chastkyHtml(st, x.chastyna) +
        '<p class="tykho"><a href="' + esc(x.url) + '" target="_blank" rel="noopener">Рішення повністю — у реєстрі суду</a> · +' + r.bal + ' досвіду</p>';
      var dali = el('button', 'klavisha klavisha--holovna klavisha--shyroka', opts.daliTekst || 'Далі'); dali.type = 'button';
      dali.addEventListener('click', function () { opts.dali(r); });
      p.appendChild(dali);
      zona.innerHTML = '';
      zona.appendChild(p);
      Array.prototype.forEach.call(p.querySelectorAll('[data-w]'), function (e) { e.style.width = e.dataset.w + '%'; });
      balLetyt($('plashka-riven'), r.bal);
      blysk('plashka-riven');
      if (opts.pislia) opts.pislia(r);
      if (r.novyiRiven) setTimeout(function () { vikno_riven(r.novyiRiven); }, 700);
    }
    krokKodeks();
  }

  function chastkyHtml(st, ch) {
    var ch_ = Object.keys(st.chastky || {});
    if (ch_.length < 2) return '';
    var vsogo = ch_.reduce(function (a, k) { return a + st.chastky[k]; }, 0);
    var h = '<div class="chastky" title="Серед рішень пробного випуску, з яких зібрано гру"><small class="tykho">Як суди Києва кваліфікували цю статтю (рішення, з яких зібрано гру):</small>';
    ch_.slice(0, 5).forEach(function (k) {
      var pct = Math.round(100 * st.chastky[k] / vsogo);
      h += '<div class="chastka' + ((k === ch || (k === '—' && !ch)) ? ' tsia' : '') + '"><span>' + (k === '—' ? 'без частини' : 'ч. ' + esc(k)) + '</span>' +
        '<span><span class="s" data-w="' + Math.max(pct, 2) + '"></span></span><span>' + pct + ' %</span></div>';
    });
    return h + '</div>';
  }

  function vikno(html, knopky_) {
    var v = $('vikno');
    v.innerHTML = '';
    var t = el('div', 'vikno-tilo', html);
    (knopky_ || []).forEach(function (k) { t.appendChild(k); });
    v.appendChild(t); v.hidden = false;
  }
  function zakrytyVikno() { $('vikno').hidden = true; }
  function vikno_riven(r) {
    var b = el('button', 'klavisha klavisha--holovna klavisha--shyroka', 'Далі'); b.type = 'button';
    b.addEventListener('click', zakrytyVikno);
    var novi = Object.keys(D.statti).filter(function (k) { return D.statti[k].riven === r.maksSkladnist; })
      .map(function (k) { return 'ст. ' + k.split(' ')[1] + ' ' + D.statti[k].kodeks; });
    vikno('<p class="tykho">Новий рівень</p><h2>' + esc(r.nazva) + '</h2><p>Тепер у тренуванні — справи складності до ' + r.maksSkladnist + ' з 5' +
      (novi.length ? ': рідші статті (' + esc(novi.slice(0, 6).join(', ')) + (novi.length > 6 ? '…' : '') + ') і рідші частини.' : '.') + '</p>', [b]);
    zvuk(true);
  }

  // ---------- вкладки ----------
  function pokazaty(v) {
    vkladka = v;
    Array.prototype.forEach.call(document.querySelectorAll('.vkladky button'), function (b) { b.setAttribute('aria-selected', b.dataset.v === v ? 'true' : 'false'); });
    var m = $('vmist'); m.innerHTML = '';
    ({ den: vDen, trenuvannia: vTrenuvannia, plutaiu: vPlutaiu, vykladachu: vVykladachu })[v](m);
    window.scrollTo(0, 0);
  }

  function vDen(m) {
    if (zaniattia) return vZaniattia(m);
    var d = sohodni();
    var st = Y.stanDnia(S, D, d);
    m.appendChild(el('h2', '', 'Справи дня · ' + datyLiudsku(d)));
    m.appendChild(el('p', 'tykho', 'П’ять справ, однакових для всіх сьогодні: від частої до рідкісної. Усі п’ять — день у серії.'));
    var ryad = el('div', 'dni');
    var nastupna = -1;
    st.forEach(function (z, i) {
      if (z.zrobleno === undefined && nastupna < 0) nastupna = i;
      var b = el('button', 'den-krok' + (z.zrobleno === 1 ? ' tak' : z.zrobleno === 0 ? ' ni' : ''), '<b>' + (i + 1) + '</b>' + zirky(z.sprava.skladnist));
      b.type = 'button';
      ryad.appendChild(b);
    });
    if (nastupna >= 0) ryad.children[nastupna].classList.add('zaraz');
    m.appendChild(ryad);
    if (nastupna < 0) {
      var pr = st.filter(function (z) { return z.zrobleno === 1; }).length;
      var k = el('div', 'kartka', '<h2>' + pr + ' з 5 — як суд</h2><p>Серія: <b>' + S.seriia + '</b> ' + dniv(S.seriia) +
        '. Нові справи дня — завтра. Помилки повернуться в тренуванні через 1, 3 і 7 днів.</p>');
      var b = el('button', 'klavisha klavisha--holovna klavisha--shyroka', 'До тренування'); b.type = 'button';
      b.addEventListener('click', function () { pokazaty('trenuvannia'); });
      k.appendChild(b); m.appendChild(k);
      return;
    }
    sprava(m, st[nastupna].sprava, { rezhym: 'den', mitka: 'Справа ' + (nastupna + 1) + ' з 5',
      daliTekst: nastupna === 4 ? 'Завершити день' : 'Наступна справа',
      pislia: function () {
        var z = Y.stanDnia(S, D, d)[nastupna];
        ryad.children[nastupna].className = 'den-krok ' + (z.zrobleno === 1 ? 'tak' : 'ni');
        if (nastupna === 4) { shapka(); blysk('plashka-seriia'); }
      },
      dali: function () { pokazaty('den'); } });
  }
  function dniv(n) { var a = n % 10, b = n % 100; return a === 1 && b !== 11 ? 'день' : a >= 2 && a <= 4 && (b < 12 || b > 14) ? 'дні' : 'днів'; }

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
        u2.appendChild(el('li', '', '<span class="t">ст. ' + esc(s.stattia.split(' ')[1]) + ' ' + esc(s.stattia.split(' ')[0]) + '<small>' + esc(s.nazva) + ' · ' + s.pravylno + ' з ' + s.vsogo + '</small></span><b class="n">' + Math.round(s.tochnist * 100) + ' %</b>'));
      });
      m.appendChild(u2);
    }
    var z = el('button', 'klavisha', 'Змінити доріжку (' + esc(Y.N.treky[S.trek].nazva) + ')'); z.type = 'button';
    z.style.marginTop = '20px';
    z.addEventListener('click', vyborTreku);
    m.appendChild(z);
  }

  // ---------- викладачу ----------
  function vVykladachu(m) {
    m.appendChild(el('h2', '', 'Набір справ на заняття'));
    m.appendChild(el('p', 'tykho', 'Оберіть статті й кількість — гра складе набір і дасть посилання для групи. Усі студенти отримають ті самі справи в тому самому порядку. ' +
      'Наприкінці кожен побачить код результату (наприклад, «7/10-k3f») — його можна попросити надіслати вам. Сервер і реєстрація не потрібні; відповіді нікуди не надсилаються.'));
    var spysok = el('div', 'statti-vybir');
    Object.keys(D.statti).forEach(function (k) {
      var st = D.statti[k];
      var n = D.spravy.filter(function (x) { return x.stattia === k; }).length;
      var l = el('label', '', '<input type="checkbox" value="' + esc(k) + '"><span>ст. ' + esc(k.split(' ')[1]) + ' ' + esc(st.kodeks) + '<br><small>' + esc(st.korotko || st.nazva) + ' · ' + n + ' справ</small></span>');
      spysok.appendChild(l);
    });
    m.appendChild(spysok);
    var ryad = el('div', 'ryad', '<label>Справ: <select id="nabir-n"><option>5</option><option selected>10</option><option>15</option><option>20</option></select></label>' +
      '<label>Складність до: <select id="nabir-sk"><option>2</option><option>3</option><option>4</option><option selected>5</option></select></label>' +
      '<input type="text" id="nabir-nazva" placeholder="Назва заняття" maxlength="60">');
    m.appendChild(ryad);
    var b = el('button', 'klavisha klavisha--holovna', 'Скласти набір'); b.type = 'button';
    m.appendChild(b);
    var vykhid = el('div');
    m.appendChild(vykhid);
    b.addEventListener('click', function () {
      var statti = Array.prototype.map.call(spysok.querySelectorAll('input:checked'), function (i) { return i.value; });
      var nb = Y.nabir(D, { statti: statti, kilkist: Number($('nabir-n').value), maksSkladnist: Number($('nabir-sk').value), zerno: sohodni() });
      if (!nb.length) { tost('Для цих статей справ немає — оберіть інші.'); return; }
      var url = location.origin + location.pathname + '?nabir=' + Y.kodNaboru(nb) + ($('nabir-nazva').value ? '&nazva=' + encodeURIComponent($('nabir-nazva').value) : '');
      vykhid.innerHTML = '<h3>Посилання для групи</h3><div class="posylannia">' + esc(url) + '</div>';
      var kop = el('button', 'klavisha', 'Скопіювати посилання'); kop.type = 'button'; kop.style.marginTop = '10px';
      kop.addEventListener('click', function () { (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(function () { tost('Скопійовано'); }, function () { tost('Скопіюйте вручну'); }); });
      vykhid.appendChild(kop);
      var u = el('ul', 'spysok'); u.style.marginTop = '12px';
      nb.forEach(function (x, i) {
        u.appendChild(el('li', '', '<span class="t">' + (i + 1) + '. ' + esc(Y.povna(x.stattia, x.chastyna)) + '<small>' + esc(x.fabula.slice(0, 110)) + '…</small></span><a href="' + esc(x.url) + '" target="_blank" rel="noopener">рішення</a>'));
      });
      vykhid.appendChild(el('h3', '', 'Ключ для викладача'));
      vykhid.appendChild(u);
    });
  }

  function vZaniattia(m) {
    var z = zaniattia;
    var i = z.vidpovidi.length;
    m.appendChild(el('div', 'zaniattia', '<b>Заняття' + (z.nazva ? ': ' + esc(z.nazva) : '') + '</b> · справа ' + Math.min(i + 1, z.spravy.length) + ' з ' + z.spravy.length +
      ' · набір від викладача'));
    if (i >= z.spravy.length) {
      var kod = Y.kodRezultatu(z.kod, z.vidpovidi);
      var k = el('div', 'kartka', '<h2>Заняття завершено</h2><p>Як суд: <b>' + kod.split('-')[0] + '</b>.</p><p>Код результату для викладача:</p><div class="posylannia posylannia--kod">' + esc(kod) + '</div>');
      var vyity = el('button', 'klavisha klavisha--shyroka', 'До своєї гри'); vyity.type = 'button'; vyity.style.marginTop = '14px';
      vyity.addEventListener('click', function () { zaniattia = null; history.replaceState(null, '', location.pathname); pokazaty('den'); });
      k.appendChild(vyity); m.appendChild(k);
      return;
    }
    sprava(m, z.spravy[i], { rezhym: 'zaniattia', mitka: 'Заняття', daliTekst: i === z.spravy.length - 1 ? 'Завершити' : 'Наступна справа',
      pislia: function (r) { z.vidpovidi.push(r.otsinka.vse); }, dali: function () { pokazaty('den'); } });
  }

  // ---------- доріжка (перший вхід) ----------
  function vyborTreku() {
    var knopky_ = Object.keys(Y.N.treky).map(function (t) {
      var tr = Y.N.treky[t];
      var b = el('button', 'klavisha klavisha--shyroka', esc(tr.nazva) + '<small>' + esc(tr.rivni.join(' → ')) + '</small>'); b.type = 'button';
      b.addEventListener('click', function () {
        if (S) S.trek = t; else S = Y.novyi(t);
        zberehty(); zakrytyVikno(); shapka(); pokazaty(vkladka);
      });
      return b;
    });
    var hrupa = el('div', 'trek'); knopky_.forEach(function (b) { hrupa.appendChild(b); });
    vikno('<h2>Кваліфікуй: кар’єра</h2><p>Справжні справи судів Києва без статті. Ви визначаєте кодекс, статтю й частину — і бачите, як вирішив суд, його ж словами.</p>' +
      '<p class="tykho">Навчання, не юридична допомога. Прогрес — лише на цьому пристрої.</p><p><b>Оберіть доріжку</b> (лише назви рівнів):</p>', [hrupa]);
  }

  // ---------- старт ----------
  function zapustyty(dani) {
    D = Y.pidhotuvaty(dani);
    S = zavantazhyty();
    if (parametry.get('nabir')) {
      var sp = Y.rozibratyKod(D, parametry.get('nabir'));
      if (sp.length) zaniattia = { kod: parametry.get('nabir'), nazva: (parametry.get('nazva') || '').slice(0, 60), spravy: sp, vidpovidi: [] };
    }
    Array.prototype.forEach.call(document.querySelectorAll('.vkladky button'), function (b) {
      b.addEventListener('click', function () { if (S) pokazaty(b.dataset.v); });
    });
    $('plashka-riven').addEventListener('click', function () { if (S) pokazaty('plutaiu'); });
    if (!S) {
      if (zaniattia) { S = Y.novyi('pravo'); zberehty(); }
      else { S = null; vyborTreku(); return; }
    }
    shapka();
    var v = parametry.get('vkladka');
    pokazaty(v && /^(den|trenuvannia|plutaiu|vykladachu)$/.test(v) ? v : 'den');
    if (D.zrazok) tost('Даних випуску немає — показано зразок із 7 справ.');
  }
  fetch('kariera.json').then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .catch(function () { return fetch('../kvalifikuy.json').then(function (r) { return r.json(); }); })
    .then(zapustyty)
    .catch(function () { $('vmist').innerHTML = '<div class="pusto">Не вдалося завантажити справи.</div>'; });
})();
