// Ядро навчальної гри «Кваліфікуй: кар'єра» (ZAVDANNYA-146, прототип). Лише обчислення — без сторінки, щоб перевіряти
// тестами (tests/test_kariera.py запускає його в node). Числа гри — у N нижче: одне місце, щоб крутити баланс.
//
// Суть: людина читає справжню фабулу з рішення суду (знеособлену, без статті) і кваліфікує діяння: кодекс → стаття →
// частина. Після відповіді — як кваліфікував суд, його ж словами, і посилання на рішення. Рівні кар'єри відкривають рідші
// статті (складність — за частотою статті у випуску). Щодня — 5 справ, однакових для всіх; серія днів; помилки
// повертаються через 1, 3 і 7 днів; «де плутаєш» — пари «правильно → обрано».
//
// Межі: це навчання, не юридична допомога. Нічого випадкового за гроші й узагалі нічого не продається; випадковість —
// лише сталий генератор від дати чи коду (однаково для всіх, перевіряє тест).
(function (korin, fabryka) {
  if (typeof module === 'object' && module.exports) module.exports = fabryka();
  else korin.MvKarieraYadro = fabryka();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var N = {
    versiia: 1,
    // Дві доріжки — та сама гра, різні назви рівнів: студентам-правникам і курсантам.
    treky: {
      pravo: { nazva: 'Правник', rivni: ['Першокурсник', 'Стажист', 'Помічник юриста', 'Юрист', 'Старший юрист', 'Експерт з кваліфікації'] },
      kursant: { nazva: 'Курсант', rivni: ['Курсант', 'Патрульний', 'Дільничний', 'Слідчий', 'Старший слідчий', 'Наставник курсантів'] }
    },
    porohy: [0, 60, 180, 400, 800, 1500],   // досвід, з якого починається рівень
    bal: { kodeks: 2, stattia: 5, chastyna: 3 },  // за правильний крок; × множник складності нижче
    mnozhnyk: [1, 1, 1.2, 1.5, 1.8, 2.2],     // за складністю справи 1…5
    povtory_dni: [1, 3, 7],                   // помилка повертається через 1, потім 3, потім 7 днів
    spravy_dnia: [1, 1, 2, 3, 4],             // складність п'яти «Справ дня» (тяжча — остання)
    variantiv_statti: 4,
    zamorozka_kozhni: 7,                      // один «вихідний» серії на 7 днів
    // Готові теми занять для викладача (ZAVDANNYA-152): пари й трійки статей, які студенти плутають. «Що розрізняє» — лише
    // ознака, яку видно з самої фабули; суми, пороги й тлумачення — у статтях кодексу, не в грі. Тема показується, коли
    // для неї у випуску є справи щонайменше двох статей (на зачатку — хоч однієї).
    temy: [
      { id: 'kradizhka-hrabizh', nazva: 'Крадіжка, грабіж чи розбій', statti: ['КК 185', 'КК 186', 'КК 187'],
        rozriznyaie: 'таємно чи відкрито; чи було насильство або погроза ним' },
      { id: 'dribne-kradizhka', nazva: 'Дрібне викрадення чи крадіжка', statti: ['КУпАП 51', 'КК 185'],
        rozriznyaie: 'вартість викраденого — межа в примітці до ст. 51 КУпАП' },
      { id: 'dtp-spianinnia', nazva: '124 чи 130 КУпАП: ДТП чи сп’яніння', statti: ['КУпАП 124', 'КУпАП 130'],
        rozriznyaie: 'що саме порушив водій: правила руху з наслідком чи керування в стані сп’яніння' },
      { id: 'vodii', nazva: 'Водій: без прав, сп’яніння, правила руху', statti: ['КУпАП 126', 'КУпАП 130', 'КУпАП 122'],
        rozriznyaie: 'документи й право керування, стан водія чи сам маневр' },
      { id: 'dtp-naslidky', nazva: 'ДТП: адміністративне чи кримінальне', statti: ['КУпАП 124', 'КУпАП 122-4', 'КК 286', 'КК 286-1'],
        rozriznyaie: 'наслідки для людей, стан водія, чи поїхав з місця' },
      { id: 'narkotyky', nazva: 'Наркотики: 44 КУпАП, 309 чи 307 КК', statti: ['КУпАП 44', 'КК 309', 'КК 307', 'КК 311'],
        rozriznyaie: 'розмір і мета: для себе чи для збуту' },
      { id: 'khuliganstvo', nazva: 'Хуліганство: дрібне чи кримінальне', statti: ['КУпАП 173', 'КК 296'],
        rozriznyaie: 'наскільки грубо порушено порядок і чи були особливі обставини' },
      { id: 'poriadok', nazva: 'Громадський порядок і алкоголь', statti: ['КУпАП 173', 'КУпАП 178', 'КУпАП 185'],
        rozriznyaie: 'лайка й чіпляння, розпивання чи непокора поліцейському' },
      { id: 'politsiia', nazva: 'Непокора чи опір поліцейському', statti: ['КУпАП 185', 'КК 342', 'КК 345'],
        rozriznyaie: 'не виконав вимогу, чинив опір чи застосував насильство' },
      { id: 'tilesni', nazva: 'Тілесні ушкодження: легкі, середні, тяжкі', statti: ['КК 125', 'КК 122', 'КК 121'],
        rozriznyaie: 'ступінь тяжкості за висновком експерта, як його описує суд' },
      { id: 'shakhraistvo', nazva: 'Шахрайство чи крадіжка', statti: ['КК 190', 'КК 185'],
        rozriznyaie: 'обман або зловживання довірою чи таємне викрадення' }
    ]
  };

  // ---------- сталий генератор: та сама дата чи код → ті самі справи для всіх ----------
  function khesh(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function generator(zerno) {
    var a = zerno >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function peremishaty(m, g) {
    var a = m.slice();
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(g() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }

  // ---------- дані: kariera.json (поле `pole`) → об'єкти; запасний шлях — зачаток ../kvalifikuy.json ----------
  function pidhotuvaty(d) {
    if (d && d.pole && d.spravy) {
      var p = d.pole;
      var spravy = d.spravy.map(function (r) { var o = {}; p.forEach(function (k, i) { o[k] = r[i]; }); return o; });
      return { statti: d.statti, spravy: spravy, vypusk: d.vypusk || '', zrazok: false };
    }
    // зачаток «Кваліфікуй» (ZAVDANNYA-117): кілька справ з поясненням, написаним людиною
    var statti = {};
    Object.keys(d.statti || {}).forEach(function (k) {
      statti[k] = { nazva: d.statti[k].nazva, korotko: d.statti[k].nazva, kodeks: k.split(' ')[0], n: 1, riven: 1,
        chastyny: d.statti[k].chastyny || [], chastky: {} };
    });
    var sp = (d.spravy || []).map(function (s) {
      return { doc: s.rishennia.nomer, stattia: s.vidpovid.stattia, chastyna: s.vidpovid.chastyna || '', fabula: s.fabula,
        chomu: s.chomu, url: s.rishennia.url, data: s.rishennia.data, skladnist: 1, vyd: '' };
    });
    return { statti: statti, spravy: sp, vypusk: 'зразок', zrazok: true };
  }

  // ---------- стан гравця (лише на пристрої) ----------
  function novyi(trek) {
    return { v: N.versiia, trek: N.treky[trek] ? trek : 'pravo', dosvid: 0, vidpovidi: 0, pravylno: 0,
      zastattiamy: {}, pomylky: {}, povtory: {}, bachyv: {}, dni: {}, seriia: 0, ostanniiDen: '', zamorozkaDen: '' };
  }
  function riven(s) {
    var r = 0;
    for (var i = 0; i < N.porohy.length; i++) if (s.dosvid >= N.porohy[i]) r = i;
    var nastupnyi = N.porohy[r + 1];
    return { indeks: r, nazva: N.treky[s.trek].rivni[r], vid: N.porohy[r], do: nastupnyi === undefined ? null : nastupnyi,
      maksSkladnist: Math.min(5, r + 1) };
  }

  // ---------- дати ----------
  function den(t) { return new Date(t).toISOString().slice(0, 10); }
  function dodatyDni(d, n) { return den(Date.parse(d + 'T12:00:00Z') + n * 864e5); }
  function riznytsia(a, b) { return Math.round((Date.parse(b + 'T12:00:00Z') - Date.parse(a + 'T12:00:00Z')) / 864e5); }

  // ---------- «Справи дня»: 5 справ, однакові для всіх у цей день ----------
  function spravyDnia(D, d) {
    var g = generator(khesh('mv-kariera-den-' + d));
    var vzhe = {};
    return N.spravy_dnia.map(function (sk) {
      var pul = D.spravy.filter(function (s) { return s.skladnist === sk && !vzhe[s.doc]; });
      if (!pul.length) pul = D.spravy.filter(function (s) { return !vzhe[s.doc]; });
      var s = pul[Math.floor(g() * pul.length)];
      vzhe[s.doc] = 1;
      return s;
    });
  }

  // ---------- тренування: спершу повтори помилок, що настали; далі — нова справа свого рівня ----------
  function nastupna(D, s, d, lichylnyk) {
    var poDocu = {};
    D.spravy.forEach(function (x) { poDocu[x.doc] = x; });
    var nastaly = Object.keys(s.povtory).filter(function (doc) { return s.povtory[doc].koly <= d && poDocu[doc]; })
      .sort(function (a, b) { return s.povtory[a].koly < s.povtory[b].koly ? -1 : s.povtory[a].koly > s.povtory[b].koly ? 1 : 0; });
    if (nastaly.length) return { sprava: poDocu[nastaly[0]], povtor: true };
    var maks = riven(s).maksSkladnist;
    var pul = D.spravy.filter(function (x) { return x.skladnist <= maks && !s.bachyv[x.doc]; });
    if (!pul.length) pul = D.spravy.filter(function (x) { return x.skladnist <= maks; });
    // новіші рівні частіше: справа найвищої відкритої складності — удвічі частіше за інші
    var g = generator(khesh('mv-kariera-' + d + '-' + (lichylnyk || 0) + '-' + s.vidpovidi));
    var vahy = pul.map(function (x) { return x.skladnist === maks ? 2 : 1; });
    var sum = vahy.reduce(function (a, b) { return a + b; }, 0), r = g() * sum;
    for (var i = 0; i < pul.length; i++) { r -= vahy[i]; if (r < 0) return { sprava: pul[i], povtor: false }; }
    return { sprava: pul[pul.length - 1], povtor: false };
  }

  // ---------- варіанти відповіді ----------
  function variantyStatti(D, sprava) {
    // 3 «сусіди» правильної статті того самого кодексу: спершу та сама група подій, далі — найчастіші статті кодексу
    var prav = sprava.stattia, kod = D.statti[prav].kodeks;
    var g = generator(khesh('mv-kariera-var-' + sprava.doc));
    var tiiZh = Object.keys(D.statti).filter(function (k) { return k !== prav && D.statti[k].kodeks === kod; });
    var odnaHrupa = tiiZh.filter(function (k) {
      return D.spravy.some(function (x) { return x.stattia === k && x.vyd && x.vyd === sprava.vyd; });
    });
    var inshi = tiiZh.filter(function (k) { return odnaHrupa.indexOf(k) < 0; })
      .sort(function (a, b) { return D.statti[b].n - D.statti[a].n; }).slice(0, 8);
    var vybir = peremishaty(odnaHrupa, g).concat(peremishaty(inshi, g)).slice(0, N.variantiv_statti - 1);
    return peremishaty(vybir.concat([prav]), g);
  }
  function variantyChastyny(D, sprava) {
    if (!sprava.chastyna) return [];            // суд частину не назвав (або в статті частин немає) — кроку немає
    var ch = (D.statti[sprava.stattia].chastyny || []).slice();
    if (ch.indexOf(sprava.chastyna) < 0) ch.push(sprava.chastyna);
    // одна частина на вибір — не питання: крок пропускаємо (частину суду все одно показуємо у відповіді)
    return ch.length < 2 ? [] : ch.sort(function (a, b) { return a - b; });
  }

  // ---------- відповідь ----------
  function otsinyty(sprava, v, D) {
    var ye = D ? variantyChastyny(D, sprava).length > 0 : !!sprava.chastyna;
    var r = { kodeks: v.kodeks === sprava.stattia.split(' ')[0], stattia: v.stattia === sprava.stattia,
      chastyna: ye ? v.chastyna === sprava.chastyna : null };
    r.vse = r.kodeks && r.stattia && r.chastyna !== false;
    return r;
  }
  function vidpovisty(s, sprava, v, d, rezhym, D) {
    var o = otsinyty(sprava, v, D);
    var m = N.mnozhnyk[sprava.skladnist] || 1;
    var bal = (o.kodeks ? N.bal.kodeks : 0) + (o.stattia ? N.bal.stattia : 0) + (o.chastyna ? N.bal.chastyna : 0);
    bal = Math.round(bal * m);
    var buv = riven(s).indeks;
    s.dosvid += bal;
    s.vidpovidi += 1;
    if (o.vse) s.pravylno += 1;
    s.bachyv[sprava.doc] = d;
    var z = s.zastattiamy[sprava.stattia] || (s.zastattiamy[sprava.stattia] = [0, 0]);
    z[0] += 1; if (o.stattia && o.chastyna !== false) z[1] += 1;
    // «де плутаєш»: правильна кваліфікація → обрана (і кодекс, і стаття, і частина — окремими парами)
    var pravNazva = povna(sprava.stattia, sprava.chastyna);
    if (!o.stattia) dodatyPomylku(s, povna(sprava.stattia, ''), !o.kodeks ? 'інший кодекс (' + v.kodeks + ')' : povna(v.stattia, ''));
    else if (o.chastyna === false) dodatyPomylku(s, pravNazva, povna(v.stattia, v.chastyna));
    // повтори: помилка → через 1 день; правильний повтор → 3, потім 7 днів, далі справа знята
    var p = s.povtory[sprava.doc];
    if (!o.vse) s.povtory[sprava.doc] = { koly: dodatyDni(d, N.povtory_dni[0]), krok: 0 };
    else if (p) {
      if (p.krok + 1 >= N.povtory_dni.length) delete s.povtory[sprava.doc];
      else s.povtory[sprava.doc] = { koly: dodatyDni(d, N.povtory_dni[p.krok + 1]), krok: p.krok + 1 };
    }
    if (rezhym === 'den') zarakhuvatyDen(s, sprava, o, d);
    return { otsinka: o, bal: bal, novyiRiven: riven(s).indeks > buv ? riven(s) : null };
  }
  function dodatyPomylku(s, prav, obrano) {
    var k = prav + ' → ' + obrano;
    s.pomylky[k] = (s.pomylky[k] || 0) + 1;
  }
  function povna(st, ch) {
    var c = st.split(' ');
    return (ch ? 'ч. ' + ch + ' ' : '') + 'ст. ' + c[1] + ' ' + c[0];
  }

  // ---------- день і серія ----------
  function zarakhuvatyDen(s, sprava, o, d) {
    var dd = s.dni[d] || (s.dni[d] = { zrobleno: {}, pravylno: 0 });
    if (dd.zrobleno[sprava.doc] !== undefined) return;
    dd.zrobleno[sprava.doc] = o.vse ? 1 : 0;
    if (o.vse) dd.pravylno += 1;
    if (Object.keys(dd.zrobleno).length === N.spravy_dnia.length) zakrytyDen(s, d);
  }
  function zakrytyDen(s, d) {
    if (s.ostanniiDen === d) return;
    var r = s.ostanniiDen ? riznytsia(s.ostanniiDen, d) : 0;
    var mozhnaZamorozku = !s.zamorozkaDen || riznytsia(s.zamorozkaDen, d) >= N.zamorozka_kozhni;
    if (!s.ostanniiDen || r > 2 || (r === 2 && !mozhnaZamorozku)) s.seriia = 1;
    else if (r === 2) { s.seriia += 1; s.zamorozkaDen = dodatyDni(d, -1); }   // пропущений день — «вихідний»
    else s.seriia += 1;
    s.ostanniiDen = d;
  }
  function stanDnia(s, D, d) {
    var dd = s.dni[d] || { zrobleno: {}, pravylno: 0 };
    return spravyDnia(D, d).map(function (x) { return { sprava: x, zrobleno: dd.zrobleno[x.doc] }; });
  }

  // ---------- «де плутаєш» ----------
  function statystyka(s, D) {
    var pary = Object.keys(s.pomylky).map(function (k) { return { para: k, raz: s.pomylky[k] }; })
      .sort(function (a, b) { return b.raz - a.raz || (a.para < b.para ? -1 : 1); });
    var slabki = Object.keys(s.zastattiamy).map(function (k) {
      var z = s.zastattiamy[k];
      return { stattia: k, nazva: D.statti[k] ? D.statti[k].korotko : '', vsogo: z[0], pravylno: z[1], tochnist: z[1] / z[0] };
    }).sort(function (a, b) { return a.tochnist - b.tochnist || b.vsogo - a.vsogo; });
    return { vidpovidi: s.vidpovidi, tochnist: s.vidpovidi ? s.pravylno / s.vidpovidi : 0, pary: pary.slice(0, 8),
      slabki: slabki, povtoriv: Object.keys(s.povtory).length };
  }

  // ---------- викладачу: набір справ на заняття й посилання для групи (без сервера) ----------
  // Код набору — номери рішень у 36-ковій системі через крапку: посилання однакове для всієї групи, сервер не потрібен.
  function nabir(D, umovy) {
    var statti = umovy.statti && umovy.statti.length ? umovy.statti : Object.keys(D.statti);
    var pul = D.spravy.filter(function (x) {
      return statti.indexOf(x.stattia) >= 0 && x.skladnist <= (umovy.maksSkladnist || 5);
    });
    var g = generator(khesh('mv-kariera-nabir-' + (umovy.zerno || '') + statti.join(',')));
    // рівно розкласти між обраними статтями, щоб 124 КУпАП не з'їла все заняття
    var poStatti = {};
    peremishaty(pul, g).forEach(function (x) { (poStatti[x.stattia] = poStatti[x.stattia] || []).push(x); });
    var vybir = [], kola = 0, kilkist = Math.min(umovy.kilkist || 10, pul.length);
    while (vybir.length < kilkist && kola < 100) {
      statti.forEach(function (k) { var x = (poStatti[k] || [])[kola]; if (x && vybir.length < kilkist) vybir.push(x); });
      kola += 1;
    }
    return peremishaty(vybir, g);
  }
  function kodNaboru(spravy) {
    return spravy.map(function (x) { return Number(x.doc).toString(36); }).join('.');
  }
  function rozibratyKod(D, kod) {
    var poDocu = {};
    D.spravy.forEach(function (x) { poDocu[x.doc] = x; });
    return String(kod || '').split('.').map(function (c) { return poDocu[String(parseInt(c, 36))]; })
      .filter(function (x) { return x; });
  }
  // ---------- теми занять (ZAVDANNYA-152) ----------
  function temy(D) {
    var ye = {};
    D.spravy.forEach(function (x) { ye[x.stattia] = (ye[x.stattia] || 0) + 1; });
    var min = D.zrazok ? 1 : 2;
    return N.temy.map(function (t) {
      var st = t.statti.filter(function (k) { return ye[k]; });
      return { id: t.id, nazva: t.nazva, rozriznyaie: t.rozriznyaie, statti: st, vsi: t.statti,
        spraw: st.reduce(function (a, k) { return a + ye[k]; }, 0) };
    }).filter(function (t) { return t.statti.length >= min; });
  }

  // ---------- код результату студента ----------
  // Крок, на якому студент розійшовся із судом, по кожній справі: 0 — усе як суд, 1 — кодекс, 2 — стаття, 3 — частина.
  function krokPomylky(o) { return o.vse ? 0 : !o.kodeks ? 1 : !o.stattia ? 2 : 3; }
  // Код «7/10-3a0f2c-k3f»: бал; кроки по справах (по 5 справ у двох знаках 36-кової системи); контрольна сума, прив'язана
  // до набору (викладач бачить, що код не вигаданий і саме з цього заняття). Відповіді — числа 0–3 або true/false.
  function kodRezultatu(kodNab, vidpovidi) {
    var kroky = vidpovidi.map(function (x) { return x === true ? 0 : x === false ? 2 : Number(x) || 0; });
    var pr = kroky.filter(function (x) { return x === 0; }).length;
    var upak = '';
    for (var i = 0; i < kroky.length; i += 5) {
      var v = 0;
      for (var j = 0; j < 5; j++) v = v * 4 + (kroky[i + j] || 0);
      upak += ('0' + v.toString(36)).slice(-2);
    }
    var sum = (khesh(kodNab + ':' + kroky.join('')) % 46656).toString(36);
    return pr + '/' + kroky.length + '-' + upak + '-' + ('00' + sum).slice(-3);
  }
  // Розібрати код студента для таблиці групи. -> {pravylno, n, kroky[], dijsnyi} або null, якщо це не код.
  // dijsnyi=false — код з іншого набору, змінений вручну чи з помилкою при переписуванні.
  function rozibratyRezultat(kodNab, kod) {
    var m = /^(\d+)\/(\d+)-([0-9a-z]+)-([0-9a-z]{1,3})$/i.exec(String(kod || '').trim());
    if (!m) return null;
    var n = Number(m[2]), upak = m[3].toLowerCase(), kroky = [];
    if (upak.length !== Math.ceil(n / 5) * 2) return { pravylno: Number(m[1]), n: n, kroky: null, dijsnyi: false };
    for (var i = 0; i < upak.length; i += 2) {
      var v = parseInt(upak.slice(i, i + 2), 36), gr = [];
      for (var j = 0; j < 5; j++) { gr.unshift(v % 4); v = Math.floor(v / 4); }
      kroky = kroky.concat(gr);
    }
    kroky = kroky.slice(0, n);
    var dijsnyi = kodRezultatu(kodNab, kroky) === m[0].toLowerCase();
    return { pravylno: Number(m[1]), n: n, kroky: kroky, dijsnyi: dijsnyi };
  }
  // Таблиця групи: рядки «Ім'я Прізвище 7/10-…» (як студенти надіслали; ім'я — що стоїть перед кодом).
  // -> {studenty:[{imia, kod, r}], spravy:[{sprava, pravylno, z, kroky:{1,2,3}}], statti:[{stattia, pravylno, z}], nevirni}
  function tablytsiaHrupy(D, kodNab, tekst) {
    var spravy = rozibratyKod(D, kodNab);
    var studenty = [], nevirni = 0;
    String(tekst || '').split(/\n+/).forEach(function (r) {
      r = r.trim(); if (!r) return;
      var m = /(\d+\/\d+-[0-9a-z]+-[0-9a-z]{1,3})\s*$/i.exec(r);
      if (!m) { nevirni += 1; return; }
      var rr = rozibratyRezultat(kodNab, m[1]);
      if (!rr || !rr.dijsnyi || rr.n !== spravy.length) { nevirni += 1; studenty.push({ imia: r.slice(0, m.index).replace(/[\s:;,—–-]+$/, ''), kod: m[1], r: null }); return; }
      studenty.push({ imia: r.slice(0, m.index).replace(/[\s:;,—–-]+$/, '') || 'без імені', kod: m[1], r: rr });
    });
    var dobri = studenty.filter(function (s) { return s.r; });
    var poSpravakh = spravy.map(function (x, i) {
      var k = { 1: 0, 2: 0, 3: 0 }, pr = 0;
      dobri.forEach(function (s) { var v = s.r.kroky[i]; if (v === 0) pr += 1; else k[v] += 1; });
      return { sprava: x, pravylno: pr, z: dobri.length, kroky: k };
    });
    var poStattiakh = {};
    poSpravakh.forEach(function (p) {
      var z = poStattiakh[p.sprava.stattia] || (poStattiakh[p.sprava.stattia] = { stattia: p.sprava.stattia, pravylno: 0, z: 0 });
      z.pravylno += p.pravylno; z.z += p.z;
    });
    var statti = Object.keys(poStattiakh).map(function (k) { return poStattiakh[k]; })
      .sort(function (a, b) { return a.pravylno / (a.z || 1) - b.pravylno / (b.z || 1); });
    return { studenty: studenty, spravy: poSpravakh, statti: statti, nevirni: nevirni };
  }

  return { N: N, khesh: khesh, generator: generator, peremishaty: peremishaty, pidhotuvaty: pidhotuvaty, novyi: novyi,
    riven: riven, den: den, dodatyDni: dodatyDni, spravyDnia: spravyDnia, nastupna: nastupna, variantyStatti: variantyStatti,
    variantyChastyny: variantyChastyny, otsinyty: otsinyty, vidpovisty: vidpovisty, povna: povna, zakrytyDen: zakrytyDen,
    stanDnia: stanDnia, statystyka: statystyka, nabir: nabir, kodNaboru: kodNaboru, rozibratyKod: rozibratyKod,
    kodRezultatu: kodRezultatu, krokPomylky: krokPomylky, rozibratyRezultat: rozibratyRezultat, temy: temy,
    tablytsiaHrupy: tablytsiaHrupy };
});
