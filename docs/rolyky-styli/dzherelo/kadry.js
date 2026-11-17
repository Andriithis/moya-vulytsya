// Кадри-макети п'яти напрямів стилю (ZAVDANNYA-126). Кожен кадр: полотно (карта) + накладка HTML (текст).
// Факти на кадрах — справжні: випуск 08.11.2026 (соти, 71 698 подій), скарги 1551 (dani-edrsr/docs/1551-DLIA-ZVITU.md),
// події з еталона перевірки dani-edrsr (perevirka/etalon-500.jsonl) — лише публічні місця, без номерів житлових будинків.
(function () {
  const R = window.RUSHIY;
  const HR = { // кольори груп подій (brend/hrupy.json, MV-116)
    svitla: ['#7F82A7', '#838F25', '#10858A', '#AB366C', '#8660A7', '#8A6C13', '#186938'],
    temna: ['#B0B5D3', '#9AA841', '#52A8AD', '#CE6992', '#D19DFD', '#DEC26C', '#5C9C6E'],
  };
  const ST = {
    nich: { tlo: '#11142A', misto_tlo: '#161A33', mezha: '#3A3F63', sc: ['#444885', '#555A9A', '#6669AF', '#7879C6', '#8A8BDD'],
      pk: ['#33BB92', '#4DCB9E'], pk_bik1: '#2A9C7A', pk_bik2: '#1E765C', vyd: '#B37BFF', kontur: '#11142A' },
    papir: { tlo: '#F4F5FB', misto_tlo: '#FFFFFF', mezha: '#B5B7C4', sc: ['#9CA1E3', '#7E84CE', '#6066C1', '#464AA9', '#303482'],
      pk: ['#5DD0A9', '#31B88D'], pk_bik1: '#3FA884', pk_bik2: '#2B8A6B', vyd: '#3C3CA1', kontur: '#FFFFFF' },
    hra: { tlo: '#EDEFFE', misto_tlo: '#FFFFFF', mezha: '#76798C', mezha_tovsh: 5, sc: ['#C9CCF3', '#9CA1E3', '#7E84CE', '#6066C1', '#464AA9'],
      pk: ['#5DD0A9', '#31B88D'], pk_bik1: '#3FA884', pk_bik2: '#2B8A6B', vyd: '#3C3CA1', kontur: '#EDEFFE' },
    khron: { tlo: '#0C0E1F', misto_tlo: '#11142A', mezha: '#2A2E47', sc: ['#1B1F39', '#232849', '#2A2E57', '#323665', '#3A3E74'],
      pk: ['#33BB92', '#4DCB9E'], pk_bik1: '#2A9C7A', pk_bik2: '#1E765C', vyd: '#66E6BA', kontur: '#0C0E1F' },
  };
  const ZNAK = '<svg viewBox="0 0 48 48"><path fill="currentColor" d="M24 2 43 13v22L24 46 5 35V13z"/><path class="z2" d="M24 15 32 19.5v9L24 33l-8-4.5v-9z"/></svg>';
  const znak = (kl) => `<div class="znak ${kl || ''}">${ZNAK}<span>Моя вулиця</span></div>`;
  const NAZVY = ['ДТП', 'Порушення водіїв', 'Крадіжки й шкода майну', 'Насильство й грабежі', 'Наркотики', 'Хуліганство й порядок', 'Алкоголь, тютюн і торгівля'];

  // 15 помісячних чисел 1551 (08.2025–10.2026), dani-edrsr/docs/1551-DLIA-ZVITU.md, розд. 1.
  const S1551 = [51876, 51269, 69383, 103030, 73832, 211169, 195620, 85720, 57738, 57025, 59938, 55659, 53985, 58242, 84472];
  const MIS = ['сер', 'вер', 'жов', 'лис', 'гру', 'січ', 'лют', 'бер', 'кві', 'тра', 'чер', 'лип', 'сер', 'вер', 'жов'];

  window.KADRY = {
    // ---------- 1. «Ніч над містом» — кіношний проліт, темна тема сайту ----------
    'nich-1': { styl: 'nich', kam: { lon: 30.50, lat: 50.44, vidstan: 26000, nakhyl: 58, povorot: -18, fokus: 1700, tsentr_y: 1120 },
      html: `<div class="top nich"><div class="velyke m">71 698</div><div class="pid">подій з рішень судів.<br>Одне місто. Один проліт.</div></div>
      <div class="niz">${znak('nich')}<div class="sekunda">0:01 · камера падає з висоти, стовпчики виростають під удар басу</div></div>` },
    'nich-2': { styl: 'nich', kam: { lon: 30.521, lat: 50.4496, vidstan: 11000, nakhyl: 52, povorot: 25, fokus: 1700, tsentr_y: 1050 },
      opts: { prykhovaty: (it) => Math.hypot(it.cx - R.mx(30.5211), it.cy - R.my(50.4496)) < 300 },
      pislia: (ctx, P) => {
        const ps = R.krapky(ctx, P, 30.5211, 50.4496, 70, HR.temna, 0.9, 11);
        return ps;
      },
      html: `<div class="top nich"><div class="velyke">1 240</div><div class="pid">подій в одній соті. Центр Києва.<br><b class="m">Розкриваємо.</b></div></div>
      <div class="mitka nich" style="left:90px;top:1180px"><i style="background:#B0B5D3"></i>ДТП</div>
      <div class="mitka nich" style="left:560px;top:1290px"><i style="background:#52A8AD"></i>Крадіжки й шкода майну</div>
      <div class="mitka nich" style="left:170px;top:1430px"><i style="background:#DEC26C"></i>Хуліганство й порядок</div>
      <div class="niz"><div class="sekunda">0:03 · сота «лопається» — крапки вискакують клік-клік, кожна з підписом групи</div></div>` },
    'nich-3': { styl: 'nich', kam: { lon: 30.46, lat: 50.43, vidstan: 30000, nakhyl: 70, povorot: 60, fokus: 1700, tsentr_y: 1250 },
      html: `<div class="top nich"><div class="serednie">А що під <span class="m">вашим</span> вікном?</div></div>
      <div class="cta nich"><div class="klavisha m">Перевір свою вулицю</div><div class="pid2">Посилання — у профілі · сторінка вашої вулиці</div></div>
      <div class="niz">${znak('nich')}</div>` },

    // ---------- 2. «Редакційний» — світлий, як інфографіка в медіа ----------
    'papir-1': { styl: 'papir', bez_karty: true,
      html: `<div class="top papir"><div class="mitka-tekst">Скарги киян у 1551</div><div class="velyke i">211 169</div>
      <div class="pid t">скарг за січень 2026. У серпні 2025 — 51 876.</div></div>
      <div class="hrafik">${S1551.map((v, i) => `<div class="stovp ${i === 5 ? 'akt' : ''}"><div class="s" style="height:${Math.round(v / 211169 * 600)}px"></div><span>${MIS[i]}</span></div>`).join('')}</div>
      <div class="dzh papir">Дані: звернення до 1551, 08.2025–10.2026. Скарга — звернення, не перевірений факт.</div>
      <div class="niz">${znak('papir')}</div>` },
    'papir-2': { styl: 'papir', kam: { lon: 30.518, lat: 50.4452, vidstan: 34000, nakhyl: 0, povorot: 0, fokus: 1700, tsentr_y: 1060 },
      opts: { stovpchyky: false, vybrana: (it) => Math.hypot(it.cx - R.mx(30.518), it.cy - R.my(50.4452)) < 400 },
      html: `<div class="top papir panel"><div class="mitka-tekst">Одна подія</div><div class="serednie t">Станція «Театральна».<br>19 квітня 2024, 14:00</div></div>
      <div class="vynoska papir" style="left:120px;top:1170px"><b>Людина ходила по коліях.</b><br>Графік поїздів збився, метро зупинили.<div class="dzh-m">Рішення суду № 119586982 · ЄДРСР</div></div>
      <div class="liniia" style="left:540px;top:960px;height:210px"></div>
      <div class="niz">${znak('papir')}</div>` },
    'papir-3': { styl: 'papir', bez_karty: true,
      html: `<div class="top papir"><div class="mitka-tekst">Вулиця в цифрах · Солом'янський район</div><div class="serednie t">Кадетський Гай</div></div>
      <div class="fakty">
        <div class="fakt"><div class="ch i">405</div><div>подій у колі 1 км за 2023–2026 — лише те, що дійшло до суду</div></div>
        <div class="fakt"><div class="ch i">89 %</div><div>з них — про дороги: ДТП, нетверезі за кермом, без прав</div></div>
        <div class="fakt"><div class="ch i">2,2×</div><div>частіше, ніж у середньому по Києву, водії їдуть з місця ДТП</div></div>
      </div>
      <div class="roky">${[[2023, 34, 1], [2024, 146], [2025, 151], [2026, 73, 1]].map(([r, n, np]) => `<div class="rik"><div class="s ${np ? 'np' : ''}" style="height:${n * 2}px"></div><b>${n}</b><span>${r}${np ? '*' : ''}</span></div>`).join('')}</div>
      <div class="dzh papir">* 2023 — база неповна; 2026 — до листопада. Дані: рішення судів, ЄДРСР, станом на 08.11.2026.</div>
      <div class="niz">${znak('papir')}</div>` },

    // ---------- 3. «Гра-клавіші» — зовні гра: клавіші, таймер, рахунок ----------
    'hra-1': { styl: 'hra', kam: { lon: 30.50, lat: 50.46, vidstan: 30000, nakhyl: 0, povorot: 0, fokus: 1700, tsentr_y: 1240 },
      opts: { stovpchyky: false },
      html: `<div class="top hra"><div class="plashka">Вгадай, де це було · 1 / 3</div>
      <div class="kartka-hra">Неділя, 15:55. Продавали живу рибу без документів: <b>97 карасів</b> по 80 грн за кілограм.</div></div>
      <div class="taimer">3</div>
      <div class="varianty"><div class="kl">А · Оболонь</div><div class="kl">Б · Виноградар</div><div class="kl">В · Позняки</div></div>
      <div class="niz"><div class="sekunda temn">0:02 · пауза 3 с: «пиши в коментарях А, Б чи В»</div></div>` },
    'hra-2': { styl: 'hra', kam: { lon: 30.4497, lat: 50.5047, vidstan: 14000, nakhyl: 45, povorot: -10, fokus: 1700, tsentr_y: 1100 },
      opts: { vybrana: (it) => Math.hypot(it.cx - R.mx(30.4497), it.cy - R.my(50.5047)) < 400 },
      html: `<div class="top hra"><div class="plashka m-tlo">Б — так!</div>
      <div class="kartka-hra">просп. Європейського Союзу · Подільський район · листопад 2024</div></div>
      <div class="pin" style="left:516px;top:1060px"></div>
      <div class="varianty"><div class="kl tmn">А · Оболонь</div><div class="kl prav">Б · Виноградар  +1</div><div class="kl tmn">В · Позняки</div></div>` },
    'hra-3': { styl: 'hra', bez_karty: true,
      html: `<div class="top hra"><div class="plashka">Рахунок</div><div class="velyke i">2 / 3</div>
      <div class="pid t">Наступна гра — завтра о 19:00.</div></div>
      <div class="cta"><div class="klavisha">Грати на сайті</div><div class="pid2 t">А свою вулицю впізнаєте? Посилання — у профілі</div></div>
      <div class="niz">${znak('papir')}</div>` },

    // ---------- 4. «Хронометраж» — саспенс: час, тиша, одна точка ----------
    'khron-1': { styl: 'khron', kam: { lon: 30.518, lat: 50.4452, vidstan: 8000, nakhyl: 62, povorot: 140, fokus: 1700, tsentr_y: 1150 },
      opts: { stovpchyky: false, vybrana: (it) => Math.hypot(it.cx - R.mx(30.518), it.cy - R.my(50.4452)) < 400 },
      html: `<div class="top khron"><div class="chas">19.04.2024 · 14:00</div><div class="pid">Станція метро «Театральна»</div></div>
      <div class="tytr khron" style="top:1300px">Людина спускається<br>на колії.</div>
      <div class="niz"><div class="sekunda">0:00 · тиша, лише тихий гул; камера повільно наближається</div></div>` },
    'khron-2': { styl: 'khron', bez_karty: true, tlo: '#0C0E1F',
      html: `<div class="tytr khron velyke-tytr" style="top:760px">Метро<br><span class="m">зупинилось.</span></div>
      <div class="niz"><div class="sekunda">0:04 · різкий обрив звуку — і одне слово на чорному</div></div>` },
    'khron-3': { styl: 'khron', kam: { lon: 30.518, lat: 50.4452, vidstan: 24000, nakhyl: 50, povorot: 170, fokus: 1700, tsentr_y: 1000 },
      opts: { vybrana: (it) => Math.hypot(it.cx - R.mx(30.518), it.cy - R.my(50.4452)) < 400 },
      html: `<div class="top khron"><div class="serednie">Що вирішив суд —<br><span class="m">у частині 2.</span></div></div>
      <div class="cta"><div class="klavisha m">Ще 71 697 подій — на карті</div><div class="pid2">Посилання — у профілі</div></div>
      <div class="niz">${znak('nich')}</div>` },

    // ---------- 5. «Сота-кліп» — 7 секунд, удар у бит, величезні слова ----------
    'klip-1': { styl: 'papir', bez_karty: true, tlo: '#66E6BA',
      html: `<div class="klip-slovo i">СТОЛИК.</div><div class="klip-pid i">Його винесли з АЗС<br>о 00:36.</div>
      <div class="niz"><div class="sekunda temn">0:00–0:02 · слово падає з ударом</div></div>` },
    'klip-2': { styl: 'papir', bez_karty: true, tlo: '#303482',
      html: `<div class="klip-slovo b" style="font-size:180px">615 грн<br>65 коп.</div><div class="klip-pid b">вул. Бориспільська · грудень 2019<br>Рішення суду № 120658141</div>
      <div class="niz"><div class="sekunda">0:02–0:04 · різкий зсув вбік, лічильник «наганяє» суму</div></div>` },
    'klip-3': { styl: 'nich', kam: { lon: 30.62, lat: 50.40, vidstan: 22000, nakhyl: 55, povorot: -40, fokus: 1700, tsentr_y: 1200 },
      html: `<div class="top nich"><div class="serednie">Це одна з <span class="m">71 698</span><br>подій на карті.</div></div>
      <div class="cta nich"><div class="klavisha m">Що було на вашій вулиці?</div></div>
      <div class="niz">${znak('nich')}<div class="sekunda">0:05–0:07 · обрив на півслові — петля в початок</div></div>` },
  };

  window.namalyuvaty = function (id) {
    const k = window.KADRY[id];
    const c = document.getElementById('p'); const ctx = c.getContext('2d');
    const st = ST[k.styl];
    if (k.bez_karty) { ctx.fillStyle = k.tlo || st.tlo; ctx.fillRect(0, 0, R.W, R.H); }
    else {
      const { P } = R.misto(ctx, st, k.kam, k.opts);
      if (k.pislia) k.pislia(ctx, P);
    }
    document.getElementById('n').innerHTML = k.html;
    document.body.dataset.styl = k.styl;
  };
  window.NAZVY_HRUP = NAZVY;
})();
