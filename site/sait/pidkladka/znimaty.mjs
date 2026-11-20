// Підкладка першого екрана головної й /karta/ (ZAVDANNYA-164, MV-176): знімки справжньої карти сайту без сот —
// окремо «тло» (вода, парки, дороги, межі) і окремо «підписи» (прозоре тло), для телефона й комп'ютера, у світлій і
// темній темі. Збирач (site/zastavka.py) кладе між ними соти з даних випуску — і так виходить картинка першого екрана.
//
// Підкладка — це OpenStreetMap, вона не залежить від випуску: знімати заново треба, лише коли змінився вигляд карти
// (kolory.json, патч стилю в karta.js) або OpenFreeMap. Потрібні мережа (tiles.openfreemap.org) і Playwright:
//   python site/zibraty_sait.py <events.db> <тека>          # будь-який випуск
//   node site/worker/testy/mistsevyi.mjs 8799 <тека> &       # або будь-який інший сервер теки
//   node site/sait/pidkladka/znimaty.mjs http://127.0.0.1:8799
// Пише сюди ж: <варіант>-<тема>-tlo.webp, <варіант>-<тема>-pidpysy.webp і meta.json (центр, зум, розмір).
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const TEKA = path.dirname(fileURLToPath(import.meta.url));
const ADRESA = (process.argv[2] || 'http://127.0.0.1:8799').replace(/\/$/, '');

// Охоплення — з запасом під найпоширеніші екрани (розрахунок камери — kameraMista() у karta.js):
// телефон (до 700 px завширшки) — зум ≈ 9,0–9,3; комп'ютер і планшет — ≈ 9,85–10,4.
const VARIANTY = {
  telefon: { z: 9.2, dpr: 2, lon: [30.23, 30.83], lat: [50.03, 50.77] },
  komp: { z: 10.0, dpr: 1, lon: [29.83, 31.23], lat: [50.15, 50.65] },
};

function merc(lon, lat, z) {
  const s = 512 * 2 ** z;
  const y = Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360));
  return [(lon + 180) / 360 * s, (1 - y / Math.PI) / 2 * s];
}
function nazad(x, y, z) {
  const s = 512 * 2 ** z;
  const lon = x / s * 360 - 180;
  const lat = (2 * Math.atan(Math.exp((1 - 2 * y / s) * Math.PI)) - Math.PI / 2) * 180 / Math.PI;
  return [lon, lat];
}

const meta = { _pro: 'Підкладка першого екрана: центр [довгота, широта], зум карти (плитки 512), розмір у CSS-пікселях, щільність. ' +
  'Пише site/sait/pidkladka/znimaty.mjs; читає site/zastavka.py.', znyato: new Date().toISOString().slice(0, 10), varianty: {} };
const tymch = fs.mkdtempSync(path.join(os.tmpdir(), 'pidkladka-'));
const brauzer = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
try {
  for (const [nazva, v] of Object.entries(VARIANTY)) {
    const [x0, y1] = merc(v.lon[0], v.lat[0], v.z), [x1, y0] = merc(v.lon[1], v.lat[1], v.z);
    const W = Math.round(x1 - x0), H = Math.round(y1 - y0);
    const tsentr = nazad((x0 + x1) / 2, (y0 + y1) / 2, v.z).map((c) => +c.toFixed(6));
    meta.varianty[nazva] = { z: v.z, dpr: v.dpr, sirina: W, vysota: H, tsentr };
    for (const tema of ['svitla', 'temna']) {
      const st = await brauzer.newPage({ viewport: { width: W, height: H + 60 }, deviceScaleFactor: v.dpr });
      await st.addInitScript((t) => { try { localStorage.setItem('mv-tema', t); } catch (e) { /* без пам'яті */ } }, tema);
      // жива карта одразу (без першого екрана-картинки) і без «вау»
      await st.goto(`${ADRESA}/karta/?vau=0&zhyva=1#${v.z}/${tsentr[1]}/${tsentr[0]}/0/0`);
      await st.waitForFunction(() => window.MvKarta && window.MvKarta.gotovo, null, { timeout: 90000 });
      await st.evaluate(({ W, H, tsentr, z }) => {
        const ekran = document.querySelector('.ekran-karty');
        Array.from(ekran.children).forEach((e) => { if (e.id !== 'karta-mista') e.style.display = 'none'; });
        Array.from(document.body.children).forEach((e) => { if (e !== ekran && e.tagName !== 'SCRIPT') e.style.display = 'none'; });
        document.querySelectorAll('.chas, .vau-rayony, .vau-lich, .zastavka, .maplibregl-marker, .maplibregl-popup').forEach((e) => { e.style.display = 'none'; });
        Object.assign(ekran.style, { position: 'fixed', left: '0', top: '0', width: W + 'px', height: H + 'px', zIndex: 9999, border: '0' });
        const m = window.MvKarta.karta;
        m.resize();
        m.jumpTo({ center: tsentr, zoom: z, pitch: 0, bearing: 0 });
        m.getStyle().layers.forEach((l) => { if (/^k-/.test(l.id)) m.setLayoutProperty(l.id, 'visibility', 'none'); });
      }, { W, H, tsentr, z: v.z });
      const chekaty = () => st.evaluate(() => new Promise((r) => { const m = window.MvKarta.karta; if (m.loaded() && m.areTilesLoaded()) r(); else m.once('idle', r); }));
      await chekaty();
      await st.waitForTimeout(800);
      const ramka = { x: 0, y: 0, width: W, height: H };
      // 1) тло: усе, крім підписів
      await st.evaluate(() => {
        const m = window.MvKarta.karta;
        m.getStyle().layers.forEach((l) => { if (!/^k-/.test(l.id)) m.setLayoutProperty(l.id, 'visibility', l.type === 'symbol' ? 'none' : 'visible'); });
      });
      await chekaty(); await st.waitForTimeout(500);
      const tlo = path.join(tymch, `${nazva}-${tema}-tlo.png`);
      await st.screenshot({ path: tlo, clip: ramka });
      // 2) підписи на прозорому тлі
      await st.evaluate(() => {
        const m = window.MvKarta.karta;
        m.getStyle().layers.forEach((l) => { if (!/^k-/.test(l.id)) m.setLayoutProperty(l.id, 'visibility', l.type === 'symbol' ? 'visible' : 'none'); });
        document.getElementById('karta-mista').style.background = 'transparent';
        document.querySelector('.ekran-karty').style.background = 'transparent';
        document.documentElement.style.background = 'transparent'; document.body.style.background = 'transparent';
      });
      await chekaty(); await st.waitForTimeout(800);
      const pidpysy = path.join(tymch, `${nazva}-${tema}-pidpysy.png`);
      await st.screenshot({ path: pidpysy, clip: ramka, omitBackground: true });
      await st.close();
      // PNG → WebP (Pillow): тло — з втратами, підписи — з прозорістю
      execFileSync('python3', ['-c', `
import sys
from PIL import Image
Image.open(sys.argv[1]).convert('RGB').save(sys.argv[2], 'WEBP', quality=82, method=6)
Image.open(sys.argv[3]).convert('RGBA').save(sys.argv[4], 'WEBP', quality=90, method=6)
`, tlo, path.join(TEKA, `${nazva}-${tema}-tlo.webp`), pidpysy, path.join(TEKA, `${nazva}-${tema}-pidpysy.webp`)]);
      console.log(nazva, tema, W + '×' + H, 'зум', v.z);
    }
  }
  fs.writeFileSync(path.join(TEKA, 'meta.json'), JSON.stringify(meta, null, 2) + '\n');
} finally {
  await brauzer.close();
  fs.rmSync(tymch, { recursive: true, force: true });
}
