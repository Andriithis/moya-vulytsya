/* Візуал про публічне місце для медіа (MV-113, ZAVDANNYA-113; з прототипу ZAVDANNYA-91).
   Рендер: pokazaty(dani, {v: 'A'|'S', f: '1x1'|'16x9', n: 1..8}); dani — JSON з dani-edrsr/src/vizual_mistsia.py.
   Порівняння — два числа «тут · у типовому колі» і мітка шкали MV-98 (без «у N разів» і точних часток до повного Києва).
   Правила (docs/KOMPAS.md, AGENTS.md розд. 4): число — з порівнянням; колір = кількість подій у даних, не небезпека;
   без імен, без номерів житлових будинків, без «небезпечно», без прогнозів і причин. */
(function () {
  var SC = ['#9CA1E3', '#7E84CE', '#6066C1', '#464AA9', '#303482'];   // sc-1…5 (docs/STYL.md)
  function el(tag, cls, tekst) { var e = document.createElement(tag); if (cls) e.className = cls; if (tekst != null) e.textContent = tekst; return e; }
  function chyslo(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }
  function vids(x) { var v = x * 100; return (v > 0 && v < 1 || v > 99 && v < 100 ? koma(v.toFixed(1)) : Math.round(v)) + ' %'; }
  function koma(x) { return String(x).replace('.', ','); }
  function znak(r) {
    var ns = 'http://www.w3.org/2000/svg', s = document.createElementNS(ns, 'svg');
    s.setAttribute('width', r); s.setAttribute('height', r); s.setAttribute('viewBox', '0 0 24 24');
    s.innerHTML = '<path d="M12 1.5 21.1 6.75v10.5L12 22.5 2.9 17.25V6.75z" fill="#4447A6"/><path d="M12 7.6 15.8 9.8v4.4L12 16.4 8.2 14.2V9.8z" fill="#fff"/>';
    var z = el('span', 'znak'); z.appendChild(s); z.appendChild(el('b', null, 'Моя вулиця')); return z;
  }
  function podii(n) { var m10 = n % 10, m100 = n % 100;
    return m10 === 1 && m100 !== 11 ? 'подія' : (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? 'події' : 'подій'); }
  function typove(d) { return chyslo(Math.round(d.typove_kolo)); }
  function mitka(d) { return { 'більше': 'більше, ніж у типовому такому колі в Києві', 'як зазвичай': 'приблизно як у типовому такому колі в Києві' }[d.mitka]
    || 'чисел замало, щоб порівнювати з типовим колом'; }

  /* Шкала частками (MV-55): 20 / 20 / 20 / 28 / 12 % сот. */
  function porohy(soty) {
    var n = soty.map(function (s) { return s.n; }).sort(function (a, b) { return a - b; });
    return [.2, .4, .6, .88].map(function (q) { return n[Math.min(n.length - 1, Math.floor(q * n.length))]; });
  }
  function kolir(n, p) { var i = 0; while (i < 4 && n > p[i]) i++; return SC[i]; }

  function karta(d, w, h, opc) {
    opc = opc || {};
    var k = d.karta, R = k.radius_m, s = k.sota_m, masht = opc.masht || (Math.min(w, h) / (2.25 * R));
    var cx = w / 2 + (opc.zsuv || 0), cy = h / 2 + (opc.zsuvY || 0), p = porohy(k.soty);
    var ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('width', w); svg.setAttribute('height', h); svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
    var r = s * masht * 0.93, html = '';
    function hex(x, y) { var t = ''; for (var i = 0; i < 6; i++) { var a = Math.PI / 180 * (60 * i - 30);
      t += (i ? 'L' : 'M') + (x + r * Math.cos(a)).toFixed(1) + ' ' + (y + r * Math.sin(a)).toFixed(1); } return t + 'Z'; }
    /* Порожні соти — тонкий контур: карта читається як «соти», навіть де подій немає. */
    var zainyati = {}, sw = Math.sqrt(3) * s;
    k.soty.forEach(function (c) { zainyati[Math.round(c.x) + ':' + Math.round(c.y)] = 1; });
    var nr = Math.ceil(h / 2 / (1.5 * s * masht)) + 1, nq = Math.ceil(w / 2 / (sw * masht)) + nr;
    for (var rr = -nr; rr <= nr; rr++) for (var q = -nq; q <= nq; q++) {
      var mx = sw * (q + rr / 2), my = -1.5 * s * rr;
      if (zainyati[Math.round(mx) + ':' + Math.round(my)]) continue;
      var px = cx + mx * masht, py = cy + my * masht;
      if (px < -r || py < -r || px > w + r || py > h + r) continue;
      html += '<path d="' + hex(px, py) + '" fill="#EDEFFE" stroke="#DFE1E9" stroke-width="1"/>';
    }
    k.soty.forEach(function (c) {
      var x = cx + c.x * masht, y = cy + c.y * masht;
      if (x < -r || y < -r || x > w + r || y > h + r) return;
      html += '<path d="' + hex(x, y) + '" fill="' + kolir(c.n, p) + '" opacity="' + (c.v_koli ? 1 : 0.32) + '"/>';
    });
    html += '<circle cx="' + cx + '" cy="' + cy + '" r="' + (R * masht) + '" fill="none" stroke="#33357C" stroke-width="1.5" stroke-dasharray="5 4"/>';
    svg.innerHTML = html;
    var obg = el('div', 'karta'); obg.style.width = w + 'px'; obg.style.height = h + 'px'; obg.appendChild(svg);
    if (!opc.bez_mitky) {
      var m = el('span', 'mitka-mistsia', d.nazva); m.style.left = cx + 'px'; m.style.top = (cy - R * masht - 6) + 'px'; obg.appendChild(m);
    }
    var kp = el('span', 'kolo-pidpys', 'коло ' + R + ' м'); kp.style.left = Math.min(cx + R * masht * 0.72 + 4, w - 64) + 'px';
    kp.style.top = (cy + R * masht * 0.72) + 'px'; obg.appendChild(kp);
    return obg;
  }
  function shkala() {
    var l = el('span', 'lehenda'), sh = el('span', 'shkala');
    l.appendChild(document.createTextNode('менше'));
    SC.forEach(function (c) { var ns = 'http://www.w3.org/2000/svg', s = document.createElementNS(ns, 'svg');
      s.setAttribute('width', 12); s.setAttribute('height', 13); s.setAttribute('viewBox', '0 0 24 26');
      s.innerHTML = '<path d="M12 1 23 7.3v12.4L12 26 1 19.7V7.3z" fill="' + c + '"/>'; sh.appendChild(s); });
    l.appendChild(sh); l.appendChild(document.createTextNode('більше подій у даних')); return l;
  }
  function verkh(mitka) { var v = el('div', 'verkh'); v.appendChild(znak(24)); v.appendChild(el('span', 'micro', mitka || 'Місце в цифрах')); return v; }
  function niz(d, korotko) {
    var n = el('div', 'niz'), c = el('p', 'caption');
    c.appendChild(el('span', 'dzherelo', 'Джерело: Моя вулиця')); c.appendChild(el('br'));
    c.appendChild(document.createTextNode('Судові рішення ЄДРСР, ' + d.period + ', станом на ' + d.versiia.split('-').reverse().join('.') + '. '));
    if (!korotko) c.appendChild(document.createTextNode('Лише те, що дійшло до суду. Колір — кількість подій у даних, не небезпека.'));
    else c.appendChild(document.createTextNode('Лише те, що дійшло до суду.'));
    n.appendChild(c); n.appendChild(el('span', 'mitka posylannia', d.posylannia));
    return n;
  }
  function holovne(d) {
    var k = el('div', 'kartka holovne');
    k.appendChild(el('span', 'number', chyslo(d.podii)));
    k.appendChild(el('p', 'body-s', podii(d.podii) + ' у колі ' + d.radius + ' м — ' + mitka(d) + ': тут ' + chyslo(d.podii) +
      ' · у типовому ' + typove(d) + '.'));
    return k;
  }
  function hrupa(g, maxCh, shyr) {
    var b = el('div', 'hrupa');
    b.appendChild(el('b', null, g.nazva));
    var ch = el('span', 'chysla'); ch.appendChild(el('strong', null, vids(g.chastka_tut)));
    ch.appendChild(document.createTextNode(' тут · ' + vids(g.chastka_kyiv) + ' по Києву')); b.appendChild(ch);
    var sm = el('div', 'smuhy'), t = el('i', 'smuha'), ky = el('i', 'smuha kyiv');
    t.style.width = Math.max(3, shyr * g.chastka_tut / maxCh) + 'px'; ky.style.width = Math.max(3, shyr * g.chastka_kyiv / maxCh) + 'px';
    sm.appendChild(t); sm.appendChild(ky); b.appendChild(sm); return b;
  }
  function lehendaSmuh() {
    var l = el('div', 'lehenda'), a = el('span'), b = el('span'), i1 = el('i'), i2 = el('i');
    i1.style.background = 'var(--data-4)'; i2.style.background = 'var(--line-strong)';
    a.appendChild(i1); a.appendChild(document.createTextNode('частка тут')); b.appendChild(i2); b.appendChild(document.createTextNode('частка по Києву'));
    l.appendChild(a); l.appendChild(b); return l;
  }
  function maxCh(d, n) { return Math.max.apply(null, d.hrupy.slice(0, n).map(function (g) { return Math.max(g.chastka_tut, g.chastka_kyiv); })); }

  /* А — «Цифри + карта»: головне число з порівнянням, три групи, міні-карта сот. */
  function variantA(p, d, f) {
    p.appendChild(verkh());
    p.appendChild(el('h1', 'title-1 nazva', d.nazva)); p.appendChild(el('p', 'body-s pidpys', d.pidpys));
    var ryad = el('div', 'ryad'), st = el('div', 'stovp');
    st.style.flex = '1'; st.appendChild(holovne(d));
    var m = maxCh(d, 3); d.hrupy.slice(0, 3).forEach(function (g) { st.appendChild(hrupa(g, m, f === '1x1' ? 250 : 360)); });
    st.appendChild(lehendaSmuh()); ryad.appendChild(st);
    if (f === '16x9') { var kd = el('div', 'stovp'); kd.appendChild(karta(d, 330, 280)); kd.appendChild(shkala()); ryad.appendChild(kd); }
    else { var kd2 = el('div', 'stovp'); kd2.appendChild(karta(d, 170, 170, { bez_mitky: true })); ryad.appendChild(kd2); }
    p.appendChild(ryad); p.appendChild(niz(d, f === '1x1'));
  }
  /* Слайди 16:9 — 8 блоків. */
  function slaid(p, d, n) {
    p.classList.add('slaid');
    var nazvy = ['', 'Обкладинка', 'Головне число', 'Карта', 'Що саме', 'За роками', 'Коли', 'Найчастіші статті', 'Як читати'];
    var v = verkh(); v.lastChild.textContent = n + ' / 8 · ' + nazvy[n]; p.appendChild(v);
    if (n === 1) {
      var r = el('div', 'ryad'), s = el('div', 'stovp'); s.style.flex = '1'; s.style.justifyContent = 'center';
      s.appendChild(el('span', 'micro', 'Місце в цифрах')); s.appendChild(el('h1', 'display', d.nazva));
      s.appendChild(el('p', 'body-l', d.pidpys)); s.appendChild(el('p', 'body-s pidpys', 'Що тут відбувалося за рішеннями судів · ' + d.period));
      r.appendChild(s); r.appendChild(karta(d, 380, 380, { bez_mitky: true })); p.appendChild(r);
    } else if (n === 2) {
      p.appendChild(el('h2', 'title-2', 'Скільки подій у колі ' + d.radius + ' м'));
      p.appendChild(el('div', 'velyke', chyslo(d.podii)));
      var pr = el('div', 'porivniannia');
      var slovo = { 'більше': ['більше', 'тут більше, ніж у типовому колі, і різниця не схожа на випадкову'],
                    'як зазвичай': ['як зазвичай', 'тут приблизно стільки ж, як у типовому колі'] }[d.mitka] ||
                  ['мало даних', 'чисел замало, щоб порівнювати'];
      [[chyslo(d.podii), 'тут — у колі ' + d.radius + ' м'], [typove(d), 'у типовому колі ' + d.radius + ' м у Києві'], slovo].forEach(function (x) {
        var k = el('div', 'kartka'); k.appendChild(el('div', 'number', x[0])); k.appendChild(el('p', 'body-s', x[1])); pr.appendChild(k); });
      p.appendChild(pr);
      p.appendChild(el('p', 'body-s pidpys', 'Людне місце: де більше людей — там більше подій у даних. Число — не оцінка місця.'));
    } else if (n === 3) {
      var r3 = el('div', 'ryad'), s3 = el('div', 'stovp'); s3.style.width = '330px';
      s3.appendChild(el('h2', 'title-2', 'Де саме в колі'));
      s3.appendChild(el('p', 'body-s', 'Кожна сота — ділянка ≈ 100 м. Колір — скільки подій у даних, від світлого до темного. Адрес будинків не показуємо.'));
      s3.appendChild(shkala()); r3.appendChild(s3); r3.appendChild(karta(d, 500, 380)); p.appendChild(r3);
    } else if (n === 4) {
      p.appendChild(el('h2', 'title-2', 'Що саме: частка кожної групи тут і по Києву'));
      var h4 = el('div', 'stovp'); h4.style.marginTop = '12px'; var m = maxCh(d, 7);
      d.hrupy.forEach(function (g) { h4.appendChild(hrupa(g, m, 760)); }); h4.appendChild(lehendaSmuh()); p.appendChild(h4);
    } else if (n === 5) {
      p.appendChild(el('h2', 'title-2', 'За роками'));
      p.appendChild(el('p', 'body-s pidpys', 'Порівняння — частка місця в усіх подіях Києва того ж року'));
      var ro = el('div', 'roky'), mx = Math.max.apply(null, d.roky.map(function (y) { return y.tut; }));
      d.roky.forEach(function (y) { var c = el('div', 'st'); c.appendChild(el('span', null, chyslo(y.tut)));
        var i = el('i', y.nepovnyi ? 'nep' : ''); i.style.height = Math.round(170 * y.tut / mx) + 'px'; c.appendChild(i);
        c.appendChild(el('em', null, y.rik + (y.nepovnyi ? '*' : '') + ' · ' + koma((100 * y.tut / y.kyiv).toFixed(2)) + ' % Києва')); ro.appendChild(c); });
      var nep = d.roky.filter(function (y) { return y.nepovnyi; })[0];
      p.appendChild(ro); if (nep) p.appendChild(el('p', 'caption', '* ' + nep.rik + ' — рішення ще надходять: подія потрапляє в базу, коли суд оприлюднить рішення.'));
    } else if (n === 6) {
      p.appendChild(el('h2', 'title-2', 'О котрій годині'));
      p.appendChild(el('p', 'body-s pidpys', 'Година події з рішення — відома для ' + d.z_hodynoiu + ' з ' + d.podii));
      var ho = el('div', 'hodyny'), os = el('div', 'hodyny-os'), mh = Math.max.apply(null, d.hodyny);
      d.hodyny.forEach(function (x, h) { var i = el('i'); i.style.height = Math.max(2, Math.round(200 * x / mh)) + 'px'; ho.appendChild(i);
        os.appendChild(el('span', null, h % 3 === 0 ? String(h) : '')); });
      p.appendChild(ho); p.appendChild(os);
    } else if (n === 7) {
      p.appendChild(el('h2', 'title-2', 'Найчастіші статті'));
      var st7 = el('div', 'statti');
      d.statti.forEach(function (x) { var k = el('div', 'kartka'); k.appendChild(el('span', 'number', chyslo(x.n)));
        var pp = el('p', 'body'); pp.appendChild(el('b', null, x.nazva));
        pp.appendChild(document.createTextNode(' · ' + x.stattia)); k.appendChild(pp); st7.appendChild(k); });
      p.appendChild(st7);
    } else if (n === 8) {
      p.appendChild(el('h2', 'title-2', 'Як читати ці цифри'));
      var mt = el('div', 'metod body-s');
      ['Подія — один випадок з рішення суду. Не скарга й не виклик поліції: лише те, що дійшло до суду й суд оприлюднив.',
       'Подія ≠ небезпека. Число не каже, що тут з кимось щось станеться. Людні місця мають більше подій у даних.',
       'Типове коло — середнє з ' + chyslo(d.kil_u_porivnianni) + ' кіл по ' + d.radius + ' м у Києві, де є хоч одна подія (те, що посередині, коли кола вишикувати за числом подій).',
       'Без справ про статеві злочини й щодо дітей і без адрес будинків. Імен немає.',
       'Період — ' + d.period + ': роки, за які в даних уже достатньо рішень.',
       'Кожна подія має посилання на рішення в ЄДРСР — на сторінці місця.'].forEach(function (t) { mt.appendChild(el('p', null, t)); });
      p.appendChild(mt);
    }
    p.appendChild(niz(d, true));
  }

  window.pokazaty = function (d, o) {
    var p = document.getElementById('p'); p.innerHTML = ''; p.className = 'polotno';
    if (o.v === 'S') { p.classList.add('f16x9'); slaid(p, d, o.n); }
    else { p.classList.add('f' + o.f); variantA(p, d, o.f); }
    /* Самоперевірка тексту: заборонені слова (AGENTS.md, розд. 4; KOMPAS, розд. 6). */
    var t = p.textContent.toLowerCase(), pr = p.getBoundingClientRect(), perep = false;
    p.querySelectorAll('*').forEach(function (e) { if (e.closest('svg')) return; var r = e.getBoundingClientRect();
      if (r.width && (r.right > pr.right + 1 || r.bottom > pr.bottom + 1 || r.left < pr.left - 1)) perep = true; });
    /* наїзди: легенда чи текст на нижній смузі */
    var niz = p.querySelector('.niz'); if (niz) { var nr = niz.getBoundingClientRect();
      p.querySelectorAll('.ryad, .hrupy, .stovp, .roky, .hodyny-os, .statti, .metod, .porivniannia, .lehenda').forEach(function (e) { if (e.getBoundingClientRect().bottom > nr.top + 1) perep = true; }); }
    var zle = ['безпечн', 'рейтинг', 'найгірш', 'страшн', 'прогноз', 'особа', 'суддя'].filter(function (x) { return t.indexOf(x) >= 0; });
    return { zle: zle, perepovnennia: perep };
  };
})();
