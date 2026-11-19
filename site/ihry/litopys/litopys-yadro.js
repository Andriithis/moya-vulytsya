// Ядро довгої гри «Літопис міста» (ZAVDANNYA-140, прототип). Лише обчислення — без сторінки й карти, щоб перевіряти
// тестами (tests/test_litopys.py запускає його в node). Числа гри — у NALASHTUVANNIA нижче: одне місце, щоб крутити баланс.
//
// Суть: гравець — літописець міста. Читає сторінки судових справ (дотик), наймає помічників, що читають самі (і поки
// гравця немає — до межі), за сторінки відкриває вулиці свого району, потім інші райони. Кожна вулиця — картка з
// безкоштовними числами й подіями з колоди гри (MV-12). Види подій — картки з рідкістю за справжньою частотою.
// Щодня — три короткі задачі й серія днів. «Нове видання» — перезапуск з постійним множником (престиж).
//
// Межі (ZAVDANNYA-140, розд. 3): нічого випадкового за гроші й узагалі нічого випадкового в нагородах — усе, що
// відкриє вулиця, видно наперед; гроші в прототипі не приймаються зовсім (MV-155 П8).
(function (korin, fabryka) {
  if (typeof module === 'object' && module.exports) module.exports = fabryka();
  else korin.MvLitopysYadro = fabryka();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var N = {
    versiia: 2,                     // 2 — ZAVDANNYA-141 (новий баланс; старий прогрес починається заново)
    dotyk: 1,                       // сторінок за дотик (+ частка від виробництва нижче)
    dotyk_vid_vyrobnytstva: 0.05,   // дотик дає ще 5 % від «сторінок за секунду»
    pomichnyky: [
      { id: 'chytach', nazva: 'Читач', opys: 'читає вголос по сторінці', tsina: 15, za_sek: 0.2 },
      { id: 'perepysuvach', nazva: 'Переписувач', opys: 'переносить справи в літопис', tsina: 120, za_sek: 1.5 },
      { id: 'arkhivarius', nazva: 'Архіваріус', opys: 'розбирає річні архіви', tsina: 1100, za_sek: 10 },
      { id: 'redaktsiia', nazva: 'Редакція району', opys: 'зводить вулиці в розділи', tsina: 12000, za_sek: 70 },
      { id: 'drukarnia', nazva: 'Друкарня', opys: 'видає літопис накладом', tsina: 130000, za_sek: 450 }
    ],
    rist_tsiny: 1.15,               // кожен наступний помічник того ж виду дорожчий на 15 %
    vulytsia_tsina: 20,             // перша вулиця (ZAVDANNYA-141: темп — симулятор symuliatsiia.js)
    vulytsia_stepin: 2.6,           // ціна вулиці k: 20 × k^2,6 × 1,12^k — бонус вулиць складний (×1,01 за кожну), тож
    vulytsia_rist: 1.12,            // ціна росте швидше за бонус: перший тиждень повільніший, далі темп тримає «Пошта архіву»
    bonus_vulytsi: 0.01,            // ×1,01 до читання за кожну відкриту вулицю (складний відсоток)
    bonus_karty: { zvychaina: 0.02, nechasta: 0.04, ridkisna: 0.08, duzhe: 0.15 },
    rayon_kozhni: 15,               // новий район — за кожні 15 відкритих вулиць
    offlain_hodyn: 8,               // поки гравця немає, помічники читають до 8 годин
    offlain_chastka: 0.15,          // …у 0,15 швидкості (ZVIT-140: ніч давала в 24 рази більше, ніж гра; тепер — ≈ 7)
    vydannia_vid_storinok: 20000,   // «нове видання» — коли за видання прочитано стільки сторінок
    vydannia_rist: 10,
    avtorytet_bonus: 0.05,          // кожен пункт авторитету — +5 % до читання назавжди
    natkhnennia_khv: 60,            // нагорода щоденної задачі — година подвійного читання
    natkhnennia_mnozhnyk: 2,
    seriia_bonus_den: 0.02, seriia_bonus_max: 0.3,   // серія днів: +2 % за день, не більше +30 %
    vykhidnykh_na_tyzhden: 1,       // один пропущений день на тиждень серію не рве
    poshta_vulyts: 3                // «Пошта архіву»: раз на день — сторінки рівно на 3 наступні вулиці (темп, ZAVDANNYA-141)
  };

  // ---------- час за Києвом ----------
  function denKyiv(ms) {
    var s = new Date(ms).toLocaleString('sv-SE', { timeZone: 'Europe/Kyiv' });
    return s.slice(0, 10);
  }
  function dniMizh(a, b) { return Math.round((Date.parse(b + 'T12:00:00Z') - Date.parse(a + 'T12:00:00Z')) / 864e5); }

  // ---------- стан ----------
  function novyi(ms, rayon) {
    return {
      v: N.versiia, pochatok: ms, chas: ms,
      storinky: 0, za_vydannia: 0, vsogo: 0, dotykiv: 0,
      pomichnyky: {}, vulytsi: [], rayony: rayon ? [rayon] : [], dim: rayon || null,
      karty: {}, vydannia: 0, avtorytet: 0,
      natkhnennia_do: 0,
      den: null, seriia: { dniv: 0, ostannii: null, vykhidni: [] }
    };
  }

  function kilkist(s, id) { return s.pomichnyky[id] || 0; }
  function tsinaPomichnyka(s, p) { return Math.ceil(p.tsina * Math.pow(N.rist_tsiny, kilkist(s, p.id))); }
  function tsinaVulytsi(s) { var k = s.vulytsi.length; return Math.ceil(N.vulytsia_tsina * Math.pow(k + 1, N.vulytsia_stepin) * Math.pow(N.vulytsia_rist, k)); }

  function bonusSerii(s) { return Math.min(N.seriia_bonus_max, N.seriia_bonus_den * (s.seriia.dniv || 0)); }
  // Рівень картки росте з кількістю подій цього виду у відкритих вулицях: 1, 2, 4, 8, 16 → рівні 1–5.
  function rivenKarty(n) { return n > 0 ? Math.min(5, 1 + Math.floor(Math.log2(n))) : 0; }
  function bonusKart(s, vydy) {
    var b = 0;
    // Картки видів з потерпілими бонусу не дають (MV-165: без балів «за шкоду»).
    Object.keys(s.karty).forEach(function (k) { var v = vydy && vydy[k]; if (v && !v.povazhna) b += (N.bonus_karty[v.ridkist] || 0) * rivenKarty(s.karty[k]); });
    return b;
  }
  // Множник читання: вулиці × картки × серія × авторитет (усе — від дій гравця, не від випадку).
  function mnozhnyk(s, vydy) {
    return Math.pow(1 + N.bonus_vulytsi, s.vulytsi.length) * (1 + bonusKart(s, vydy)) * (1 + bonusSerii(s)) *
      (1 + N.avtorytet_bonus * s.avtorytet);
  }
  function bazaZaSek(s) {
    return N.pomichnyky.reduce(function (a, p) { return a + kilkist(s, p.id) * p.za_sek; }, 0);
  }
  function zaSek(s, vydy, ms) {
    var m = mnozhnyk(s, vydy);
    if (ms != null && ms < s.natkhnennia_do) m *= N.natkhnennia_mnozhnyk;
    return bazaZaSek(s) * m;
  }
  function zaDotyk(s, vydy, ms) {
    return (N.dotyk * mnozhnyk(s, vydy) + N.dotyk_vid_vyrobnytstva * zaSek(s, vydy, ms));
  }

  function dodaty(s, n) { s.storinky += n; s.za_vydannia += n; s.vsogo += n; }

  // Час іде: помічники читають. Повертає, скільки прочитано, і чи впёрлися в межу «поки вас не було».
  function plyn(s, vydy, ms) {
    var vid = s.chas || ms;
    var sek = Math.max(0, (ms - vid) / 1000);
    var mezha = N.offlain_hodyn * 3600;
    var obrizano = sek > mezha;
    sek = Math.min(sek, mezha);
    // натхнення діє лише частину проміжку
    var z_natkh = Math.max(0, Math.min(vid + sek * 1000, s.natkhnennia_do) - vid) / 1000;
    var baza = bazaZaSek(s) * mnozhnyk(s, vydy) * (sek > 120 ? N.offlain_chastka : 1);
    var n = baza * (sek + z_natkh * (N.natkhnennia_mnozhnyk - 1));
    dodaty(s, n);
    s.chas = ms;
    return { storinok: n, sekund: sek, obrizano: obrizano };
  }

  function dotyk(s, vydy, ms) { var n = zaDotyk(s, vydy, ms); dodaty(s, n); s.dotykiv++; return n; }

  function naiaty(s, id) {
    var p = N.pomichnyky.filter(function (x) { return x.id === id; })[0];
    if (!p) return false;
    var t = tsinaPomichnyka(s, p);
    if (s.storinky < t) return false;
    s.storinky -= t; s.pomichnyky[id] = kilkist(s, id) + 1;
    return true;
  }

  // Помічник видно, коли гравець наблизився до його ціни (як у довгих іграх: нове з'являється поступово).
  function vydniPomichnyky(s) {
    return N.pomichnyky.filter(function (p, i) {
      return i === 0 || kilkist(s, p.id) > 0 || kilkist(s, N.pomichnyky[i - 1].id) > 0 || s.vsogo >= p.tsina * 0.5;
    });
  }

  function skilkyRayoniv(s, vsogo) { return Math.min(vsogo || 10, 1 + Math.floor(s.vulytsi.length / N.rayon_kozhni)); }

  // Відкрити вулицю: лише у відкритому районі, за сторінки. Події вулиці — наперед відомі (з колоди), картки видів
  // додаються всі, без жеребу.
  function vidkrytyVulytsiu(s, vul, podii) {
    if (!vul || s.vulytsi.indexOf(vul.slug) >= 0) return { ok: false, chomu: 'uzhe' };
    if (s.rayony.indexOf(vul.rayon) < 0) return { ok: false, chomu: 'rayon' };
    var t = tsinaVulytsi(s);
    if (s.storinky < t) return { ok: false, chomu: 'malo' };
    s.storinky -= t;
    s.vulytsi.push(vul.slug);
    var novi = [];
    (vul.podii || []).forEach(function (id) {
      var p = podii[id]; if (!p) return;
      var k = p[0];
      if (!s.karty[k]) novi.push(k);
      s.karty[k] = (s.karty[k] || 0) + 1;
    });
    if (s.den) s.den.vulyts = (s.den.vulyts || 0) + 1;
    return { ok: true, novi_karty: novi, novyi_rayon: s.rayony.length < skilkyRayoniv(s) };
  }

  function vidkrytyRayon(s, rayon) {
    if (s.rayony.indexOf(rayon) >= 0 || s.rayony.length >= skilkyRayoniv(s)) return false;
    s.rayony.push(rayon); return true;
  }

  // ---------- «Пошта архіву» (ZAVDANNYA-141, темп) ----------
  // Раз на день (за Києвом), коли гравець приходить, — сторінки на N наступних вулиць за їхньою поточною ціною. Так щодня є
  // що відкрити й тоді, коли ціни вже високі; однаково для всіх, без випадку. Перший день — без пошти (є навчання).
  function skilkyNaVulytsi(s, k) {
    var sum = 0, kopiia = { vulytsi: s.vulytsi.slice() };
    for (var i = 0; i < k; i++) { sum += tsinaVulytsi(kopiia); kopiia.vulytsi.push('~' + i); }
    return sum;
  }
  function poshta(s, ms) {
    var d = denKyiv(ms);
    if (!s.poshta) { s.poshta = d; return 0; }
    if (s.poshta === d) return 0;
    s.poshta = d;
    var n = skilkyNaVulytsi(s, N.poshta_vulyts);
    dodaty(s, n);
    return n;
  }

  // ---------- «Нове видання» (престиж) ----------
  // Авторитет — за порядок прочитаного (кожне «вдесятеро більше» — ще пункт), тож перезапуск вигідний, але не вибуховий.
  function avtorytetZa(s) {
    var porih = porihVydannia(s);
    return s.za_vydannia < porih ? 0 : 1 + Math.floor(Math.log10(s.za_vydannia / porih));
  }
  // Поріг кожного наступного видання — удесятеро вищий: перезапуск лишається цікавим, але не розганяє гру до кінця за тиждень.
  function porihVydannia(s) { return N.vydannia_vid_storinok * Math.pow(N.vydannia_rist, s.vydannia); }
  function mozhnaVydannia(s) { return avtorytetZa(s) >= 1; }
  // Скидаються сторінки й помічники; вулиці, райони, картки й серія лишаються (колекція — назавжди).
  function noveVydannia(s) {
    var a = avtorytetZa(s);
    if (a < 1) return 0;
    s.avtorytet += a; s.vydannia += 1;
    s.storinky = 0; s.za_vydannia = 0; s.pomichnyky = {};
    return a;
  }

  // ---------- щоденні задачі ----------
  // Детерміновано від дати: однакові для всіх у межах дня (MV-130: без випадкового «пощастило»).
  function zerno(t) { var h = 2166136261; for (var i = 0; i < t.length; i++) { h ^= t.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function vybir(spysok, kliuch) { return spysok.length ? spysok[zerno(kliuch) % spysok.length] : null; }

  // Справа дня: подія колоди (із уже не відкритих гравцем вулиць — щоб і вчила, і вела на карту), питання —
  // «який це вид?» (3 варіанти) і «у якому районі?» (3 варіанти). Варіанти — теж від дати.
  // Події з потерпілими в «Справу дня» не йдуть (MV-165): вгадування над чужою бідою — не гра.
  function dlyaSpravy(dani, id) { var p = dani.podii[id], v = dani.vydy[p[0]]; return !!p[2] && !(v && v.povazhna); }
  function spravaDnia(data, dani) {
    var ids = Object.keys(dani.podii).filter(function (id) { return dlyaSpravy(dani, id); }).sort();
    var id = vybir(ids, 'sprava:' + data);
    if (!id) return null;
    var p = dani.podii[id];
    var vul = null;
    for (var i = 0; i < dani.vulytsi.length; i++) if (dani.vulytsi[i].podii.indexOf(id) >= 0) { vul = dani.vulytsi[i]; break; }
    var vydy = Object.keys(dani.vydy).filter(function (k) { return k !== p[0] && !dani.vydy[k].povazhna; }).sort();
    var rayony = Object.keys(dani.rayony).filter(function (r) { return !vul || r !== vul.rayon; }).sort();
    function try3(pravylna, inshi, kl) {
      var a = vybir(inshi, kl + '1'); var b = vybir(inshi.filter(function (x) { return x !== a; }), kl + '2');
      var v = [pravylna, a, b].filter(Boolean);
      var zs = zerno(kl + 'p') % v.length; v.push(v.splice(0, 1)[0]); // зсув, щоб правильна не завжди перша
      for (var j = 0; j < zs; j++) v.push(v.shift());
      return v;
    }
    return { id: id, vyd: p[0], rayon: vul && vul.rayon, vulytsia: vul && vul.slug,
      varianty_vydu: try3(p[0], vydy, 'v:' + data), varianty_rayonu: vul ? try3(vul.rayon, rayony, 'r:' + data) : [] };
  }

  var ZADACHI = [
    { id: 'sprava', nazva: 'Справа дня: який це вид події?' },
    { id: 'rayon', nazva: 'Справа дня: у якому районі?' },
    { id: 'vulytsi', nazva: 'Відкрийте 3 вулиці', tsil: 3 }
  ];

  function den(s, ms) {
    var d = denKyiv(ms);
    if (!s.den || s.den.data !== d) s.den = { data: d, zrobleno: {}, vulyts: 0, vidpovidi: {} };
    return s.den;
  }

  // Відповідь на задачу справи дня: одна спроба на день; правильно — година натхнення. Неправильно — показуємо
  // правильну відповідь і все одно зараховуємо задачу як «прочитану» (вчить, а не карає), але без натхнення.
  function vidpovisty(s, ms, zadacha, vidpovid, pravylna) {
    var d = den(s, ms);
    if (d.vidpovidi[zadacha] != null) return null;
    var ok = vidpovid === pravylna;
    d.vidpovidi[zadacha] = vidpovid;
    d.zrobleno[zadacha] = true;
    if (ok) s.natkhnennia_do = Math.max(s.natkhnennia_do, ms) + N.natkhnennia_khv * 60000;
    onovytySeriiu(s, ms);
    return ok;
  }

  function perevirytyVulytsi(s, ms) {
    var d = den(s, ms);
    if (!d.zrobleno.vulytsi && d.vulyts >= 3) { d.zrobleno.vulytsi = true; s.natkhnennia_do = Math.max(s.natkhnennia_do, ms) + N.natkhnennia_khv * 60000; onovytySeriiu(s, ms); return true; }
    return false;
  }

  function vseZrobleno(s, ms) { var d = den(s, ms); return ZADACHI.every(function (z) { return d.zrobleno[z.id]; }); }

  // Серія днів: день зараховано, коли зроблено всі три задачі. Один пропуск на 7 днів серію не рве («вихідний»).
  function onovytySeriiu(s, ms) {
    if (!vseZrobleno(s, ms)) return;
    var d = denKyiv(ms), sr = s.seriia;
    if (sr.ostannii === d) return;
    var mizh = sr.ostannii ? dniMizh(sr.ostannii, d) : 1;
    sr.vykhidni = (sr.vykhidni || []).filter(function (x) { return dniMizh(x, d) < 7; });
    if (mizh === 1) sr.dniv += 1;
    else if (mizh === 2 && sr.vykhidni.length < N.vykhidnykh_na_tyzhden) { sr.vykhidni.push(d); sr.dniv += 1; }
    else sr.dniv = 1;
    sr.ostannii = d;
  }

  // Що чекає завтра (для екрана «завтрашня задача»): скільки прочитають помічники за ніч і чи серія живе.
  function zavtra(s, vydy, ms) {
    var d = denKyiv(ms);
    var pivnich = Date.parse(d + 'T00:00:00Z');
    // північ за Києвом: шукаємо найближчий момент, коли день змінюється (без бібліотек часових поясів)
    var t = ms; while (denKyiv(t) === d) t += 15 * 60000;
    var do_novoho = t - ms;
    var za_nich = bazaZaSek(s) * mnozhnyk(s, vydy) * N.offlain_chastka * N.offlain_hodyn * 3600;
    return { khv_do_novoho_dnia: Math.round(do_novoho / 60000), za_nich: za_nich, seriia: s.seriia.dniv, pivnich: pivnich };
  }

  // ---------- числа людською мовою ----------
  function chyslo(n) {
    n = Math.floor(n);
    if (n < 1e6) return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    var r = [[1e12, 'трлн'], [1e9, 'млрд'], [1e6, 'млн']];
    for (var i = 0; i < r.length; i++) if (n >= r[i][0]) return (n / r[i][0]).toFixed(n >= 10 * r[i][0] ? 1 : 2).replace('.', ',') + ' ' + r[i][1];
    return String(n);
  }

  // Перевірка стану з localStorage: зламаний чи чужої версії — новий (гра не падає).
  function pryniaty(s, ms) {
    if (!s || typeof s !== 'object' || s.v !== N.versiia || !Array.isArray(s.vulytsi)) return null;
    ['storinky', 'za_vydannia', 'vsogo'].forEach(function (k) { if (!(s[k] >= 0)) s[k] = 0; });
    if (!s.seriia) s.seriia = { dniv: 0, ostannii: null, vykhidni: [] };
    if (!s.chas || s.chas > ms) s.chas = ms;
    return s;
  }

  return {
    N: N, ZADACHI: ZADACHI, denKyiv: denKyiv, dniMizh: dniMizh, novyi: novyi, pryniaty: pryniaty,
    tsinaPomichnyka: tsinaPomichnyka, tsinaVulytsi: tsinaVulytsi, mnozhnyk: mnozhnyk, zaSek: zaSek, zaDotyk: zaDotyk,
    plyn: plyn, dotyk: dotyk, naiaty: naiaty, vydniPomichnyky: vydniPomichnyky, kilkist: kilkist,
    skilkyRayoniv: skilkyRayoniv, vidkrytyVulytsiu: vidkrytyVulytsiu, vidkrytyRayon: vidkrytyRayon,
    avtorytetZa: avtorytetZa, porihVydannia: porihVydannia, mozhnaVydannia: mozhnaVydannia, noveVydannia: noveVydannia,
    poshta: poshta, skilkyNaVulytsi: skilkyNaVulytsi, spravaDnia: spravaDnia, den: den, vidpovisty: vidpovisty, perevirytyVulytsi: perevirytyVulytsi,
    vseZrobleno: vseZrobleno, zavtra: zavtra, chyslo: chyslo, rivenKarty: rivenKarty, bonusSerii: bonusSerii, bonusKart: bonusKart
  };
});
