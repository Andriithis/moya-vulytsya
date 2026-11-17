// Записи екрана й знімки прототипу «вау» і смуги «роки · місяці» (ZAVDANNYA-105).
//
//   python tests/shtuchne_misto.py <tmp>/events.db
//   python site/zibraty_sait.py <tmp>/events.db <tmp>/sait
//   python -m http.server 8105 -d <tmp>/sait &
//   node tests/znimky_vau.js http://127.0.0.1:8105 <тека-для-записів> [сцена…]
//
// Комп'ютер 1440 × 900 і телефон (iPhone 13): ?vau=1, ?vau=2, ?vau=3 (з натиском району), програвання місяців;
// «вау» ще й з «менше руху» в системі. Відео — .webm (запис Playwright), знімки — .png.
const { chromium, devices } = require('playwright');
const fs = require('fs'), path = require('path');
const [adresa, teka, ...lyshe] = process.argv.slice(2);
const K = +(process.env.TEMPO || 1);
const ARG = ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'];
(async () => {
  fs.mkdirSync(teka, { recursive: true });
  const br = await chromium.launch({ args: ARG });
  const tel = devices['iPhone 13'];
  const prystroi = { pk: { viewport: { width: 1440, height: 900 } }, tel };
  for (const [nazva, nal] of Object.entries(prystroi)) {
    for (const tykho of [false, true]) {
      for (const stsena of ['vau1', 'vau2', 'vau3', 'misiatsi']) {
        if (tykho && stsena === 'misiatsi') continue;
        if (lyshe.length && !lyshe.includes(stsena)) continue;
        const imia = `${stsena}-${nazva}${tykho ? '-tykho' : ''}`, tmp = path.join(teka, '_' + imia);
        const ctx = await br.newContext({ ...nal, reducedMotion: tykho ? 'reduce' : 'no-preference',
          recordVideo: { dir: tmp, size: nal.viewport } });
        const s = await ctx.newPage();
        s.on('pageerror', e => console.log('ПОМИЛКА', imia, String(e)));
        const T = process.env.TEMPO ? '&tempo=' + process.env.TEMPO : '';
        const q = { vau1: '?vau=1' + T, vau2: '?vau=2' + T, vau3: '?vau=3' + T, misiatsi: '' }[stsena];
        await s.goto(adresa + '/karta/' + q);
        await s.waitForFunction(() => window.MvKarta && window.MvKarta.gotovo, null, { timeout: 90000, polling: 250 });
        const zn = n => s.screenshot({ path: path.join(teka, `${imia}-${n}.png`) });
        if (stsena === 'vau1') { await s.waitForTimeout(K * 500); await zn('pochatok'); await s.waitForTimeout(K * 4500); }
        else if (stsena === 'vau2') { await s.waitForTimeout(K * 1800); await zn('seredyna'); await s.waitForTimeout(K * 5000); }
        else if (stsena === 'vau3') {
          await s.waitForTimeout(2200); await zn('rayony');
          await s.click('[data-rayon="Оболонський"]'); await s.waitForTimeout(K * 3800);
        } else {
          await s.click('.chas [data-krok="rik"]'); await s.waitForTimeout(800); await zn('rik');
          await s.click('.chas .ch-gra'); await s.waitForTimeout(5200); await zn('misiats');
        }
        await zn('kinets');
        const v = s.video();
        await ctx.close();
        fs.renameSync(await v.path(), path.join(teka, imia + '.webm'));
        fs.rmSync(tmp, { recursive: true, force: true });
        console.log(imia);
      }
    }
  }
  await br.close();
})();
