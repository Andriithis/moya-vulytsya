// Єдиний модуль відправки даних заглушки (ZAVDANNYA-02, п. 5).
// Куди: таблиці сховища Supabase (MV-8) через його REST-адресу.
// Що: лише поля форми та назву події з каналом. Час ставить сховище саме.
// Чого НЕ робимо: не надсилаємо кукі, нічого не пишемо в пам'ять браузера, не створюємо
// ідентифікатор відвідувача, не передаємо адресу сторінки, з якої прийшли.
(function () {
  'use strict';

  var PODII = ['pryishly', 'adresa', 'peredzamovyty', 'kontakt'];
  var SHCHO = ['analiz', 'pidpyska', 'povidomyty', 'kompaniya'];

  function nalashtuvannya() {
    var c = window.MV_CONFIG || {};
    var adresa = String(c.adresaSkhovyshcha || '').replace(/\/+$/, '');
    var klyuch = String(c.publichnyiKlyuch || '');
    if (!adresa || !klyuch || adresa.indexOf('ZAMINITY') !== -1 || klyuch.indexOf('ZAMINITY') !== -1) {
      return null;
    }
    return { adresa: adresa, klyuch: klyuch };
  }

  // Канал — лише латинські малі літери, цифри й дефіс, до 40 знаків.
  function ochystytyKanal(dzherelo) {
    var k = String(dzherelo == null ? '' : dzherelo).trim().toLowerCase();
    if (!k) return 'priamo';
    return /^[a-z0-9-]{1,40}$/.test(k) ? k : 'inshe';
  }

  // Старий публічний ключ (JWT, починається з «eyJ») іде ще й у Authorization;
  // новий ключ «sb_publishable_…» — лише в apikey.
  function zaholovky(klyuch) {
    var z = {
      'apikey': klyuch,
      'Content-Type': 'application/json',
      // Лише додати рядок і нічого не читати назад: анонім читати не може.
      'Prefer': 'return=minimal'
    };
    if (klyuch.indexOf('eyJ') === 0) z['Authorization'] = 'Bearer ' + klyuch;
    return z;
  }

  function vidpravyty(tablytsya, ryadok, dovho) {
    var n = nalashtuvannya();
    if (!n) return Promise.reject(new Error('Сховище не налаштоване'));
    return fetch(n.adresa + '/rest/v1/' + tablytsya, {
      method: 'POST',
      headers: zaholovky(n.klyuch),
      body: JSON.stringify(ryadok),
      credentials: 'omit',
      referrerPolicy: 'no-referrer',
      cache: 'no-store',
      keepalive: !!dovho
    }).then(function (v) {
      if (!v.ok) throw new Error('Сховище відповіло ' + v.status);
      return true;
    });
  }

  // Подія для чотирьох чисел. Збій лічильника не повинен заважати людині,
  // тому помилку тихо ковтаємо і повертаємо false.
  function nadislatyPodiyu(nazva, dzherelo) {
    if (PODII.indexOf(nazva) === -1) return Promise.resolve(false);
    return vidpravyty('podiya', { nazva: nazva, kanal: ochystytyKanal(dzherelo) }, true)
      .catch(function () { return false; });
  }

  // Заявка з форми. Без згоди — не надсилаємо взагалі.
  function nadislatyZayavku(dani) {
    dani = dani || {};
    if (dani.zghoda !== true) return Promise.reject(new Error('Немає згоди'));
    var kontakt = String(dani.kontakt || '').trim();
    var misto = String(dani.misto || '').trim();
    if (!kontakt) return Promise.reject(new Error('Немає контакту'));
    if (!misto) return Promise.reject(new Error('Немає міста'));
    var adresa = String(dani.adresa || '').trim();
    var ryadok = {
      shcho: SHCHO.indexOf(dani.shcho) !== -1 ? dani.shcho : 'povidomyty',
      misto: misto.slice(0, 80),
      adresa: adresa ? adresa.slice(0, 200) : null,
      kontakt: kontakt.slice(0, 120),
      zghoda: true,
      kanal: ochystytyKanal(dani.dzherelo)
    };
    return vidpravyty('zayavka', ryadok, false);
  }

  // Звернення про виправлення або видалення (ZAVDANNYA-06, п. 2). Без згоди — не надсилаємо.
  var SHCHO_NE_TAK = ['mistse', 'opys', 'vydalyty', 'inshe'];
  function nadislatyZvernennya(dani) {
    dani = dani || {};
    if (dani.zghoda !== true) return Promise.reject(new Error('Немає згоди'));
    var posylannya = String(dani.posylannya || '').trim();
    var kontakt = String(dani.kontakt || '').trim();
    var poyasnennya = String(dani.poyasnennya || '').trim();
    if (!posylannya) return Promise.reject(new Error('Немає посилання чи номера рішення'));
    if (SHCHO_NE_TAK.indexOf(dani.shchoNeTak) === -1) return Promise.reject(new Error('Не вибрано, що не так'));
    if (!kontakt) return Promise.reject(new Error('Немає контакту'));
    return vidpravyty('zvernennya', {
      posylannya: posylannya.slice(0, 300),
      shcho_ne_tak: dani.shchoNeTak,
      poyasnennya: poyasnennya ? poyasnennya.slice(0, 2000) : null,
      kontakt: kontakt.slice(0, 120),
      zghoda: true
    }, false);
  }

  window.MvNadsylannya = {
    nadislatyPodiyu: nadislatyPodiyu,
    nadislatyZayavku: nadislatyZayavku,
    nadislatyZvernennya: nadislatyZvernennya,
    ochystytyKanal: ochystytyKanal
  };
})();
