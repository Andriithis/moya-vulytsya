// Знімки й банер для сторінки застосунку в Google Play (ZAVDANNYA-144).
//
//   node android/znimky_play.js <зібраний-сайт> [тека-виходу]       (за замовчуванням tmp/android-play/)
//
// Сайт збирає site/zibraty_sait.py (для Play — зі СПРАВЖНЬОГО випуску: на штучному місті знімки лише для перевірки
// вигляду, у Play їх не вантажимо). Тут він лише віддається локальним сервером; підкладку карти (tiles.openfreemap.org)
// можна вимкнути ZNIMKY_BEZ_PIDKLADKY=1 — тоді видно лише соти й межу міста.
//
// Що виходить:
//   telefon-1..6.png — 1080×1920 (9:16; Google Play: від 320 до 3840 px, щонайменше 1080 по короткій стороні, щоб
//                      застосунок могли показувати в добірках), сайт у режимі застосунку (?dzherelo=dodatok — без цін, MV-126);
//   telefon-temna-*.png — те саме в темній темі (2 знімки, за бажанням);
//   baner-1024x500.png — «графіка для рекомендацій» (обов'язкова в Play Console), без тексту біля країв;
//   ikona-512.png       — іконка для Play Console (512×512, PNG) — копія site/zahlushka/ikony/ikona-maskable-512.png
//                         (суцільний фон: Play сам заокруглює кути, прозорість там не годиться).
// Знімки не в git: їх завжди можна зробити заново цією командою.
'use strict';
const fs = require('fs');
const path = require('path');
const http = require('http');
const { chromium } = require('playwright');

const KORIN = path.resolve(__dirname, '..');
const [SAIT, VYKHID = path.join(KORIN, 'tmp', 'android-play')] = process.argv.slice(2);
if (!SAIT) { console.error('node android/znimky_play.js <зібраний-сайт> [тека-виходу]'); process.exit(2); }

// Порядок — як людина знайомиться із застосунком: головна → свій будинок → вулиця → карта → гра → район.
const ZNIMKY = [
  ['telefon-1', '/'],
  ['telefon-2', process.env.ZNIMKY_BUDYNOK || null],     // сторінка будинку; без змінної — перший будинок із sitemap
  ['telefon-3', process.env.ZNIMKY_VULYTSIA || null],    // сторінка вулиці; без змінної — перша вулиця з sitemap
  ['telefon-4', '/karta/'],
  ['telefon-5', '/karta/?hra=vgadai'],
  ['telefon-6', '/miy-budynok/'],
];
const TYPY = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json',
  '.png': 'image/png', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json', '.geojson': 'application/json',
  '.svg': 'image/svg+xml', '.bin': 'application/octet-stream', '.pbf': 'application/x-protobuf' };

function server(teka) {
  return new Promise((ok) => {
    const s = http.createServer((zap, vid) => {
      let f = path.join(teka, decodeURIComponent(zap.url.split('?')[0]));
      if (!f.startsWith(path.resolve(teka))) { vid.writeHead(403); vid.end(); return; }
      if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
      if (!fs.existsSync(f)) { vid.writeHead(404); vid.end(); return; }
      vid.writeHead(200, { 'Content-Type': TYPY[path.extname(f)] || 'application/octet-stream' });
      fs.createReadStream(f).pipe(vid);
    });
    s.listen(0, '127.0.0.1', () => ok(s));
  });
}

function pershaAdresa(teka, pochatok) {
  const sm = path.join(teka, 'sitemap.xml');
  if (!fs.existsSync(sm)) return null;
  let tekst = fs.readFileSync(sm, 'utf8');
  const chastyna = tekst.match(/<loc>[^<]*\/(sitemap-1\.xml)<\/loc>/);
  if (chastyna) tekst = fs.readFileSync(path.join(teka, chastyna[1]), 'utf8');
  const m = [...tekst.matchAll(/<loc>https?:\/\/[^/<]+(\/[^<]*)<\/loc>/g)].map((x) => x[1]).find((a) => a.startsWith(pochatok));
  return m || null;
}

function banerHtml() {
  const shryft = (vaha) => `url(data:font/woff2;base64,${fs.readFileSync(path.join(KORIN, 'site', 'sait', 'shryfty',
    `ibm-plex-sans-cyrillic-${vaha}-normal.woff2`)).toString('base64')}) format('woff2')`;
  // Соти на тлі — лише візерунок (колір = дані, не небезпека; без червоного — MV-58).
  const soty = [];
  for (let r = 0; r < 7; r++) for (let k = 0; k < 9; k++) {
    const x = 560 + k * 56 + (r % 2) * 28, y = -20 + r * 48, a = [0.10, 0.18, 0.28, 0.42, 0.62][(r * r * 3 + k * 7 + r * k) % 5];
    soty.push(`<path transform="translate(${x} ${y}) scale(2)" d="M13 1 L25 8 L25 20 L13 27 L1 20 L1 8 Z" fill="#4447A6" fill-opacity="${a}"/>`);
  }
  return `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:Plex;font-weight:400;src:${shryft(400)}}
@font-face{font-family:Plex;font-weight:700;src:${shryft(700)}}
html,body{margin:0;width:1024px;height:500px;overflow:hidden;background:#F4F5FB;font-family:Plex,sans-serif}
.soty{position:absolute;left:0;top:0}
.tekst{position:absolute;left:72px;top:150px;width:470px}
.znak{display:flex;align-items:center;gap:16px;margin-bottom:22px}
.znak b{font-size:44px;color:#11142A;letter-spacing:-.5px}
h1{margin:0;font-size:34px;line-height:1.2;color:#11142A;font-weight:700}
p{margin:14px 0 0;font-size:21px;line-height:1.35;color:#4A4E66}
</style></head><body>
<svg class="soty" width="1024" height="500" viewBox="0 0 1024 500">${soty.join('')}</svg>
<div class="tekst"><div class="znak"><svg width="52" height="56" viewBox="0 0 26 28"><path d="M13 1 L25 8 L25 20 L13 27 L1 20 L1 8 Z" fill="#4447A6"/><path d="M13 9 L18 12 L18 17 L13 20 L8 17 L8 12 Z" fill="#fff"/></svg><b>Моя вулиця</b></div>
<h1>Що відбувається під боком</h1><p>Скарги мешканців і події з рішень судів — по кожному будинку</p></div>
</body></html>`;
}

(async () => {
  fs.mkdirSync(VYKHID, { recursive: true });
  ZNIMKY[1][1] = ZNIMKY[1][1] || pershaAdresa(SAIT, '/budynok/');
  ZNIMKY[2][1] = ZNIMKY[2][1] || pershaAdresa(SAIT, '/vulytsia/');
  const srv = await server(SAIT);
  const U = `http://127.0.0.1:${srv.address().port}`;
  const b = await chromium.launch({ args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  try {
    for (const tema of ['svitla', 'temna']) {
      // 360×640 при щільності 3 = 1080×1920 — як звичайний телефон Android.
      const ctx = await b.newContext({ viewport: { width: 360, height: 640 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true,
        colorScheme: tema === 'temna' ? 'dark' : 'light', locale: 'uk-UA' });
      if (process.env.ZNIMKY_BEZ_PIDKLADKY === '1') await ctx.route('https://tiles.openfreemap.org/**', (r) => r.abort());
      const pg = await ctx.newPage();
      await pg.goto(`${U}/?dzherelo=dodatok`, { waitUntil: 'load' });          // як запуск застосунку
      for (const [imia, adresa] of tema === 'svitla' ? ZNIMKY : ZNIMKY.slice(0, 2)) {
        if (!adresa) { console.log(`${imia}: немає сторінки — пропущено`); continue; }
        await pg.goto(U + adresa, { waitUntil: 'load' });
        await pg.waitForTimeout(adresa === '/' || adresa.startsWith('/karta/') ? 6000 : 600);   // карта домальовує соти (на телефоні головна — теж карта)
        const f = path.join(VYKHID, `${tema === 'temna' ? imia.replace('telefon', 'telefon-temna') : imia}.png`);
        await pg.screenshot({ path: f });
        console.log(`${path.basename(f)} — ${adresa}`);
      }
      await ctx.close();
    }
    const ctx = await b.newContext({ viewport: { width: 1024, height: 500 }, deviceScaleFactor: 1 });
    const pg = await ctx.newPage();
    await pg.setContent(banerHtml(), { waitUntil: 'load' });
    await pg.evaluate(() => document.fonts.ready);
    await pg.screenshot({ path: path.join(VYKHID, 'baner-1024x500.png') });
    console.log('baner-1024x500.png');
    await ctx.close();
    fs.copyFileSync(path.join(KORIN, 'site', 'zahlushka', 'ikony', 'ikona-maskable-512.png'), path.join(VYKHID, 'ikona-512.png'));
    console.log('ikona-512.png');
  } finally {
    await b.close();
    srv.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });
