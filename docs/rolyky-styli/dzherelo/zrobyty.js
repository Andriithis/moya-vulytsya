// Знімає кадри-макети стилів 1080×1920 у docs/rolyky-styli/ (ZAVDANNYA-126).
// Запуск із кореня moya-vulytsya: node docs/rolyky-styli/dzherelo/zrobyty.js
// Дані: video/dani/soty-kyiv.geojson (випуск 08.11.2026) і site/hra/mezha-kyieva.geojson; шрифт — site/sait/shryfty.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const KORIN = path.resolve(__dirname, '../../..');
const TUT = __dirname;
const VYKHID = path.resolve(TUT, '..');

function dani() {
  const s = JSON.parse(fs.readFileSync(path.join(KORIN, 'video/dani/soty-kyiv.geojson'), 'utf8'));
  const m = JSON.parse(fs.readFileSync(path.join(KORIN, 'site/hra/mezha-kyieva.geojson'), 'utf8'));
  const r = (v, n) => Math.round(v * 10 ** n) / 10 ** n;
  const soty = s.features.map((f) => ({ n: f.properties.n, k: f.properties.k,
    c: f.geometry.coordinates[0].map(([x, y]) => [r(x, 5), r(y, 5)]) }));
  const big = m.geometry.coordinates.reduce((a, p) => (p[0].length > a.length ? p[0] : a), []);
  const mezha = big.filter((_, i) => i % 3 === 0).map(([x, y]) => [r(x, 4), r(y, 4)]);
  return `window.SOTY=${JSON.stringify(soty)};window.MEZHA=${JSON.stringify(mezha)};`;
}

function shryfty() {
  const t = path.join(KORIN, 'site/sait/shryfty');
  return [400, 600, 700].map((w) => ['cyrillic', 'latin'].map((n) =>
    `@font-face{font-family:Plex;font-weight:${w};src:url("file://${t}/ibm-plex-sans-${n}-${w}-normal.woff2") format("woff2");}`).join('')).join('');
}

(async () => {
  const html = `<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8"><style>${shryfty()}${fs.readFileSync(path.join(TUT, 'kadr.css'), 'utf8')}</style></head>
<body><canvas id="p" width="1080" height="1920"></canvas><div id="n"></div>
<script>${dani()}</script><script>${fs.readFileSync(path.join(TUT, 'rushiy.js'), 'utf8')}</script>
<script>${fs.readFileSync(path.join(TUT, 'kadry.js'), 'utf8')}</script></body></html>`;
  const tmp = path.join(TUT, '_kadr.html');
  fs.writeFileSync(tmp, html);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  await p.goto('file://' + tmp);
  await p.evaluate(() => document.fonts.ready);
  const ids = process.argv[2] ? process.argv[2].split(',') : await p.evaluate(() => Object.keys(window.KADRY));
  for (const id of ids) {
    await p.evaluate((i) => window.namalyuvaty(i), id);
    await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: path.join(VYKHID, `${id}.png`) });
    console.log('кадр', id);
  }
  await b.close();
  fs.unlinkSync(tmp);
})();
