// Знімки прототипу «Вулиця дня» (ZAVDANNYA-101): 390 px і 1280 px, світла й темна тема.
//
// Запуск:  python site/zahlushka/zibraty.py            (збирає _site/zahlushka з грою)
//          node tests/znimky_hry_vulytsia.js [тека]    (за замовчуванням — tmp/znimky/zavdannya-101/)
// Потрібен site/hra/vulytsia-dnia.json (site/hra/vulytsia_dnia.py з випуску й колоди; поза git).
// Сервер — простий локальний у цьому ж процесі, лише читає _site/zahlushka. Підкладка карти — з мережі
// (tiles.openfreemap.org), якщо вона є; без мережі видно лише межу Києва.
// Сценарій: загадка дня на 17.11.2026; спроби — далека вулиця, ближча, поруч у тому ж районі, потім відповідь.
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const KORIN = path.resolve(__dirname, '..');
const SAIT = path.join(KORIN, '_site', 'zahlushka');
const TEKA = path.resolve(process.argv[2] || path.join(KORIN, 'tmp', 'znimky', 'zavdannya-101'));
const DATA = '2026-11-17';
const TYPY = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.geojson': 'application/json', '.woff2': 'font/woff2', '.png': 'image/png', '.webmanifest': 'application/json' };

function server() {
  return new Promise((ok) => {
    const s = http.createServer((zap, vid) => {
      const shl = path.join(SAIT, decodeURIComponent(zap.url.split('?')[0]));
      if (!shl.startsWith(SAIT) || !fs.existsSync(shl) || fs.statSync(shl).isDirectory()) { vid.writeHead(404); vid.end(); return; }
      vid.writeHead(200, { 'Content-Type': TYPY[path.extname(shl)] || 'application/octet-stream' });
      fs.createReadStream(shl).pipe(vid);
    });
    s.listen(0, '127.0.0.1', () => ok(s));
  });
}

const km = (a, b) => Math.hypot((a.lat - b.lat) * 111, (a.lon - b.lon) * 71);

function plan(st) {
  const z = st.zahadana, vs = st.vulytsi.filter((v) => v.slug !== z.slug);
  const pershyi = (f, klyuch) => vs.filter(f).sort(klyuch || ((a, b) => (a.slug < b.slug ? -1 : 1)))[0];
  const daleko = pershyi((v) => v.rayon !== z.rayon && km(v, z) > 8 && km(v, z) < 12);
  const blyzhche = pershyi((v) => v.rayon !== z.rayon && km(v, z) > 3 && km(v, z) < 5);
  const poruch = pershyi((v) => v.rayon === z.rayon && km(v, z) > 0.5 && km(v, z) < 2, (a, b) => km(a, z) - km(b, z));
  return [daleko, blyzhche, poruch, z];
}

async function sproba(s, v) {
  await s.fill('#pole', v.nazva);
  await s.dispatchEvent('#pole', 'input');
  await s.waitForTimeout(100);
  await s.evaluate((nazva) => {
    const r = [...document.querySelectorAll('.vybir__ryadok')].find((l) => l.firstChild.textContent.startsWith(nazva));
    if (r) r.dispatchEvent(new MouseEvent('mousedown'));
  }, v.nazva);
  await s.click('#vidpravyty');
  await s.waitForTimeout(800);
}

(async () => {
  fs.mkdirSync(TEKA, { recursive: true });
  const srv = await server();
  const url = `http://127.0.0.1:${srv.address().port}`;
  const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  try {
    for (const [shyryna, tema] of [[1280, 'light'], [390, 'light'], [390, 'dark'], [1280, 'dark']]) {
      const telefon = shyryna < 600;
      const k = await b.newContext({ viewport: { width: shyryna, height: telefon ? 844 : 860 }, deviceScaleFactor: telefon ? 2 : 1,
        colorScheme: tema, hasTouch: telefon, isMobile: telefon });
      const s = await k.newPage();
      s.on('console', (m) => { if (m.type() === 'error') console.log('консоль:', m.text().slice(0, 160)); });
      const imya = (n) => path.join(TEKA, `${n}-${shyryna}${tema === 'dark' ? '-temna' : ''}.png`);
      await s.goto(`${url}/hra/vulytsia.html?data=${DATA}`);
      await s.waitForFunction(() => window.MvVulytsia && MvVulytsia.stan().zahadana);
      await s.waitForFunction(() => MvHraKarta.ostannia && MvHraKarta.ostannia.karta.loaded(), null, { timeout: 30000 })
        .catch(() => console.log('карта не дочекалась повного завантаження — знімаю як є'));
      await s.evaluate(() => document.fonts.ready);
      await s.waitForTimeout(2000);
      await s.screenshot({ path: imya('1-start'), fullPage: telefon });
      const p = plan(await s.evaluate(() => MvVulytsia.stan()));
      for (const v of p.slice(0, 3)) await sproba(s, v);
      await s.waitForTimeout(2000);
      await s.screenshot({ path: imya('2-try-sproby'), fullPage: telefon });
      await sproba(s, p[3]);
      await s.waitForTimeout(2500);
      await s.screenshot({ path: imya('3-kinets'), fullPage: telefon });
      console.log(shyryna, tema, p.map((v) => v.nazva).join(' → '));
      await k.close();
    }
  } finally {
    await b.close();
    srv.close();
  }
  console.log('Знімки:', TEKA);
})();
