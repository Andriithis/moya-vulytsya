// Ядро ігор у карті (ZAVDANNYA-117; MV-129, MV-130, MV-26): лише розрахунки, без сторінки й карти.
// Працює в браузері (window.MvIhryYadro) і в Node для перевірок (tests/test_ihry.py). Нічого не надсилає.
// Спільне з першою грою (дата за Києвом, зерно, відстань) — з hra-yadro.js, щоб усі ігри рахували однаково.
(function (korin) {
  'use strict';

  var Y = korin.MvHraYadro || (typeof require === 'function' ? require('../hra/hra-yadro.js') : null);

  // ---------- Час за Києвом ----------
  // {data: 'РРРР-ММ-ДД', den: 1..7 (пн..нд), hodyna: 0..23}
  function chasKyiv(teper) {
    var d = teper || new Date();
    var z = {};
    try {
      new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Kyiv', year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', hour12: false, weekday: 'short' }).formatToParts(d).forEach(function (c) { z[c.type] = c.value; });
    } catch (e) { z = {}; }
    var data = z.year ? z.year + '-' + z.month + '-' + z.day : Y.dataKyiv(d);
    var dni = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7 };
    var den = dni[z.weekday] || ((denNomer(data) + 3) % 7 + 1);
    var hodyna = z.hour != null ? Number(z.hour) % 24 : d.getHours();
    return { data: data, den: den, hodyna: hodyna };
  }

  function denNomer(data) {               // дні від 1970-01-01 (UTC) — для зерна й тижнів
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(data));
    return m ? Math.floor(Date.UTC(+m[1], +m[2] - 1, +m[3]) / 86400000) : NaN;
  }
  function dataZDnia(n) {
    var d = new Date(n * 86400000);
    var mm = d.getUTCMonth() + 1, dd = d.getUTCDate();
    return d.getUTCFullYear() + '-' + (mm < 10 ? '0' : '') + mm + '-' + (dd < 10 ? '0' : '') + dd;
  }
  function ponedilok(data) { var n = denNomer(data); return dataZDnia(n - ((n + 3) % 7)); }   // 1970-01-01 — четвер
  function dodatyDni(data, k) { return dataZDnia(denNomer(data) + k); }

  // ---------- Детектив тижня ----------
  var POLIA = ['de', 'shcho', 'koly', 'pole'];
  var OCHKY = { de: 1000, shcho: 500, koly: 250, pole: 250 };
  var BONUS = 1.5;              // поле, виведене правильно ДО сліду, що його розкриває
  var ROZKRYTTIA_HODYNA = 20;   // неділя, 20:00 за Києвом

  // Справа тижня: та, чий тиждень — цей. Немає — зразки по колу за номером тижня (позначка demo).
  function spravaTyzhnia(spravy, data) {
    if (!spravy || !spravy.length) return null;
    var pn = ponedilok(data);
    for (var i = 0; i < spravy.length; i++) if (spravy[i].tyzhden === pn) return { sprava: spravy[i], demo: false };
    var tyzh = Math.floor((denNomer(pn) - 4) / 7);
    var por = spravy.slice().sort(function (a, b) { return a.tyzhden < b.tyzhden ? -1 : a.tyzhden > b.tyzhden ? 1 : 0; });
    return { sprava: por[((tyzh % por.length) + por.length) % por.length], demo: true };
  }

  // День справи: 1..7; сліди відкриваються по одному на день (пн — слід 1 … сб — слід 6); нд 20:00 — розкриття.
  function stanTyzhnia(chas) {
    return { den: chas.den, slidiv: Math.min(chas.den, 6), rozkryttia: chas.den === 7 && chas.hodyna >= ROZKRYTTIA_HODYNA };
  }

  function vidpovidaie(k, u) {
    var z = k.oznaky ? k.oznaky[u.oznaka] : undefined;
    var tak = z === u.znachennia;
    return u.ne ? !tak : tak;
  }

  // Та сама логіка, що в site/ihry/detektyv.py (тест звіряє): що лишається після слідів 1..k.
  function zvuzhennia(sprava, doSlidu) {
    var z = {};
    POLIA.forEach(function (p) { z[p] = sprava.polia[p].kandydaty.slice(); });
    var kroky = [kopiia(z)];
    sprava.slidy.forEach(function (s, i) {
      if (doSlidu != null && i >= doSlidu) return;
      s.rechennia.forEach(function (r) {
        (r.umovy || []).forEach(function (u) { z[u.pole] = z[u.pole].filter(function (k) { return vidpovidaie(k, u); }); });
      });
      kroky.push(kopiia(z));
    });
    return kroky;
    function kopiia(o) { var c = {}; POLIA.forEach(function (p) { c[p] = o[p].map(function (k) { return k.id; }); }); return c; }
  }

  function znaideno(slid, lat, lon) { return Y.vidstan(lat, lon, slid.tsil.lat, slid.tsil.lon) <= slid.tsil.radius_m; }

  // Відгук на версію — «N з M» лише про ті з полів «що / коли / поле справи», чий розкривальний слід уже відкрито
  // (den — скільки слідів відкрито); про «де» — нічого. Так перебором по одному полю на день відповіді не дізнатись
  // (гра на папері, ZAVDANNYA-117; IHRY-2, 3.2).
  function vidhuk(sprava, versiia, den) {
    var rozkr = sprava.rozkryto_pislia || {};
    var n = 0, z = 0;
    ['shcho', 'koly', 'pole'].forEach(function (p) {
      if (den != null && !(rozkr[p] <= den)) return;
      z++;
      if (versiia[p] === sprava.polia[p].vidpovid) n++;
    });
    return { tak: n, z: z };
  }

  // Очки за тиждень: остання версія; поле з бонусом ×1,5, якщо його правильно подали до дня сліду, що його розкриває,
  // і далі не міняли (оцінювач IHRY-2, розд. 9: винагороджувати міркування, а не ризик).
  function ochkyDetektyva(sprava, versii) {
    if (!versii || !versii.length) return { razom: 0, polia: {} };
    var ost = versii[versii.length - 1];
    var rozkr = sprava.rozkryto_pislia || {};
    var polia = {}, razom = 0;
    POLIA.forEach(function (p) {
      var tak = ost[p] === sprava.polia[p].vidpovid;
      var vid = null;   // перший день, з якого поле правильне й більше не змінювалось
      for (var i = versii.length - 1; i >= 0 && versii[i][p] === sprava.polia[p].vidpovid; i--) vid = versii[i].den;
      var bonus = tak && vid != null && rozkr[p] != null && vid < rozkr[p];
      var o = tak ? Math.round(OCHKY[p] * (bonus ? BONUS : 1)) : 0;
      polia[p] = { tak: tak, bonus: bonus, ochky: o };
      razom += o;
    });
    return { razom: razom, polia: polia };
  }

  // ---------- «Вгадай, де це було» в карті ----------
  // Спроба дня — однакова для всіх: події з колоди за зерном «дата + номер спроби» (MV-130: без «пощастило»).
  function sprobaVgadai(podii, data, nomer, skilky) {
    var vyp = Y.generator(Y.kheshRyadka('mv-vgadai-' + data + '-' + nomer));
    return Y.raund(podii, skilky || 5, vyp);
  }

  // ---------- «Кваліфікуй» ----------
  function spravyKvalifikuy(spravy, data) {
    return Y.peremishaty(spravy, Y.generator(Y.kheshRyadka('mv-kvalifikuy-' + data)));
  }
  // Стаття — 600, частина — 400; без частин стаття — 1 000. Лише за точність (MV-130).
  function ochkyKvalifikuy(sprava, statti, vybir) {
    var tak = vybir.stattia === sprava.vidpovid.stattia;
    var ch = sprava.vidpovid.chastyna;
    if (!ch) return { stattia: tak, chastyna: null, ochky: tak ? 1000 : 0 };
    var takCh = tak && String(vybir.chastyna) === String(ch);
    return { stattia: tak, chastyna: takCh, ochky: (tak ? 600 : 0) + (takCh ? 400 : 0) };
  }

  // ---------- Спроби й бали (MV-130) ----------
  // Стан на пристрої (поки немає кабінету, ZAVDANNYA-99): {data, vykorystano{gra:n}, kupleni, bali, baliSohodni, obminy[]}
  function novyiStan() { return { versiia: 1, data: '', vykorystano: {}, kupleni: 0, bali: 0, baliSohodni: 0, obminy: [] }; }
  function naDen(stan, data) {
    var s = stan && stan.versiia === 1 ? stan : novyiStan();
    if (s.data !== data) { s.data = data; s.vykorystano = {}; s.baliSohodni = 0; }
    return s;
  }
  function sproby(stan, gra, k, data) {
    var s = naDen(stan, data);
    var bez = (k.bezkoshtovno_na_den[gra] || 0) - (s.vykorystano[gra] || 0);
    var mozhnaKupleni = (k.kupleni_dlia || []).indexOf(gra) !== -1;
    return { bezkoshtovnykh: Math.max(0, bez), kuplenykh: mozhnaKupleni ? s.kupleni : 0,
      mozhna: bez > 0 || (mozhnaKupleni && s.kupleni > 0) };
  }
  // Спершу безкоштовна, потім куплена. Повертає 'bezkoshtovna' | 'kuplena' | null.
  function vytratyty(stan, gra, k, data) {
    var s = naDen(stan, data);
    var p = sproby(s, gra, k, data);
    if (p.bezkoshtovnykh > 0) { s.vykorystano[gra] = (s.vykorystano[gra] || 0) + 1; return 'bezkoshtovna'; }
    if (p.kuplenykh > 0) { s.kupleni -= 1; return 'kuplena'; }
    return null;
  }
  // Очки → бали; денна стеля. Бали з куплених спроб — так само (MV-130).
  function zarakhuvaty(stan, ochky, k, data) {
    var s = naDen(stan, data);
    var b = Math.floor(Math.max(0, ochky) / k.ochok_za_bal);
    b = Math.max(0, Math.min(b, k.stelia_baliv_na_den - s.baliSohodni));
    s.bali += b; s.baliSohodni += b;
    return b;
  }
  // Після підтвердження оплати сервером (ZAVDANNYA-99; зараз вимкнено) — лише так з'являються куплені спроби.
  function dodatyKupleni(stan, paket) { stan.kupleni = (stan.kupleni || 0) + paket.sprob; return stan.kupleni; }

  function obminMozhlyvyi(stan, tovar, k, data) {
    if (!k.obmin_uvimkneno) return { mozhna: false, chomu: k.obmin_chomu_ni };
    if (stan.bali < tovar.baliv) return { mozhna: false, chomu: 'Бракує ' + (tovar.baliv - stan.bali) + ' балів.' };
    var ost = (stan.obminy || []).slice(-1)[0];
    if (ost && denNomer(data) - denNomer(ost.data) < 30 / (k.obminiv_na_30_dniv || 1)) return { mozhna: false, chomu: 'Обмін — раз на 30 днів.' };
    return { mozhna: true };
  }

  // Найбільше балів за одну спробу (ідеальна гра) — для перевірки пакетів.
  function maksBalivZaSprobu(k) { return Math.max(k.vgadai_podii_v_sprobi * 1000, 1000) / k.ochok_za_bal; }
  // Запобіжник (порада, ZVIT-117): навіть ідеальна гра на куплених спробах не дає балів на суму, більшу за сплачену.
  // Повертає перелік порушень (порожній — гаразд).
  function perevirkaPaketiv(k) {
    var zh = [];
    var grnZaBal = Math.max.apply(null, k.obmin.map(function (t) { return t.tsina / t.baliv; }));
    k.pakety.forEach(function (p) {
      var vartist = p.sprob * maksBalivZaSprobu(k) * grnZaBal;
      if (vartist >= p.tsina) zh.push(p.id + ': ідеальна гра дає балів на ' + vartist.toFixed(0) + ' грн ≥ ціни ' + p.tsina);
    });
    return zh;
  }

  // ---------- Тихе запрошення (MV-26, IHRY-2, розд. 6) ----------
  // Одне за відвідування; через ≈ 40 с або після 3-го дотику; не поверх відкритого (картка, пошук, «ⓘ», панель ігор);
  // «×» — до кінця дня; тричі поспіль закрили — пауза 7 днів; «Не пропонувати ігри» — назавжди (налаштування).
  var CHEKATY_S = 40, DOTYKIV = 3, PAUZA_DNIV = 7, ZAKRYTTIV = 3;
  function chasZaproshuvaty(z, sesiia, kontekst) {
    if (!z) z = {};
    if (z.ne_proponuvaty || sesiia.pokazano || kontekst.vidkryto) return false;
    if (z.zakryto_den === kontekst.data) return false;
    if (z.pauza_do && kontekst.data < z.pauza_do) return false;
    return kontekst.sekund >= CHEKATY_S || kontekst.dotykiv >= DOTYKIV;
  }
  function zakrylyZaproshennia(z, data) {
    z.zakryto_den = data;
    z.zakryttiv = (z.zakryttiv || 0) + 1;
    if (z.zakryttiv >= ZAKRYTTIV) { z.pauza_do = dodatyDni(data, PAUZA_DNIV); z.zakryttiv = 0; }
    return z;
  }
  function pryinialyZaproshennia(z) { z.zakryttiv = 0; return z; }

  // Яка гра пропонує себе: справа «Кваліфікуй» поруч на карті → новий слід детектива → «Вулиця дня» → «Подія дня».
  function yakaGra(s) {
    if (s.kvalifikuyPoruch) return 'kvalifikuy-tut';
    if (s.detektyvNovyiSlid) return 'detektyv';
    if (s.vulytsiaYe && !s.vulytsiaZihrano) return 'vulytsia';
    if (s.podiiaYe && !s.podiiaZihrano) return 'vgadai';
    if (s.kvalifikuyZalyshylos) return 'kvalifikuy';
    return null;
  }

  var Yadro = {
    chasKyiv: chasKyiv, denNomer: denNomer, ponedilok: ponedilok, dodatyDni: dodatyDni,
    POLIA: POLIA, OCHKY: OCHKY, BONUS: BONUS, spravaTyzhnia: spravaTyzhnia, stanTyzhnia: stanTyzhnia,
    zvuzhennia: zvuzhennia, znaideno: znaideno, vidhuk: vidhuk, ochkyDetektyva: ochkyDetektyva,
    sprobaVgadai: sprobaVgadai, spravyKvalifikuy: spravyKvalifikuy, ochkyKvalifikuy: ochkyKvalifikuy,
    novyiStan: novyiStan, naDen: naDen, sproby: sproby, vytratyty: vytratyty, zarakhuvaty: zarakhuvaty,
    dodatyKupleni: dodatyKupleni, obminMozhlyvyi: obminMozhlyvyi, maksBalivZaSprobu: maksBalivZaSprobu,
    perevirkaPaketiv: perevirkaPaketiv,
    CHEKATY_S: CHEKATY_S, DOTYKIV: DOTYKIV, PAUZA_DNIV: PAUZA_DNIV,
    chasZaproshuvaty: chasZaproshuvaty, zakrylyZaproshennia: zakrylyZaproshennia,
    pryinialyZaproshennia: pryinialyZaproshennia, yakaGra: yakaGra
  };
  if (typeof module === 'object' && module.exports) module.exports = Yadro;
  korin.MvIhryYadro = Yadro;
})(typeof window !== 'undefined' ? window : this);
