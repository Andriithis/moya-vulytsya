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
    zamorozka_kozhni: 7                       // один «вихідний» серії на 7 днів
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
    return ch.sort(function (a, b) { return a - b; });
  }

  // ---------- відповідь ----------
  function otsinyty(sprava, v) {
    var r = { kodeks: v.kodeks === sprava.stattia.split(' ')[0], stattia: v.stattia === sprava.stattia,
      chastyna: sprava.chastyna ? v.chastyna === sprava.chastyna : null };
    r.vse = r.kodeks && r.stattia && r.chastyna !== false;
    return r;
  }
  function vidpovisty(s, sprava, v, d, rezhym) {
    var o = otsinyty(sprava, v);
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
    if (!o.stattia) dodatyPomylku(s, sprava.stattia, v.kodeks === sprava.stattia.split(' ')[0] ? v.stattia : v.kodeks + ' (кодекс)');
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
  // Код результату студента: «7/10-k3f» — бал і коротка контрольна сума відповідей (викладач бачить, що код не вигаданий).
  function kodRezultatu(kodNab, vidpovidi) {
    var pr = vidpovidi.filter(function (x) { return x; }).length;
    return pr + '/' + vidpovidi.length + '-' + (khesh(kodNab + ':' + vidpovidi.map(function (x) { return x ? 1 : 0; }).join('')) % 46656).toString(36);
  }

  return { N: N, khesh: khesh, generator: generator, peremishaty: peremishaty, pidhotuvaty: pidhotuvaty, novyi: novyi,
    riven: riven, den: den, dodatyDni: dodatyDni, spravyDnia: spravyDnia, nastupna: nastupna, variantyStatti: variantyStatti,
    variantyChastyny: variantyChastyny, otsinyty: otsinyty, vidpovisty: vidpovisty, povna: povna, zakrytyDen: zakrytyDen,
    stanDnia: stanDnia, statystyka: statystyka, nabir: nabir, kodNaboru: kodNaboru, rozibratyKod: rozibratyKod,
    kodRezultatu: kodRezultatu };
});
