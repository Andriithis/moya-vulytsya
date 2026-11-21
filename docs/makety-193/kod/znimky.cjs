// Знімки макетів ZAVDANNYA-193: телефон 375 (×2), ПК 1366 (×1). Карта — один екран, сторінки — повністю.
(async () => {
const { chromium } = require('playwright');
const fs = require('node:fs');
const OUT = '/tmp/claude-0/-home-user/97326387-a0cb-5f2b-94fd-02e550169a0b/scratchpad/gen/out';
const [, , vykhid, ...tilky] = process.argv;
const styli = tilky.length ? tilky : fs.readdirSync(OUT);
const b = await chromium.launch();
for (const s of styli) {
  fs.mkdirSync(`${vykhid}/${s}`, { recursive: true });
  for (const f of fs.readdirSync(`${OUT}/${s}`)) {
    const tel = f.includes('-tel');
    const ctx = await b.newContext({ viewport: tel ? { width: 375, height: 812 } : { width: 1366, height: 820 }, deviceScaleFactor: tel ? 2 : 1 });
    const p = await ctx.newPage();
    p.on('pageerror', e => console.log('ПОМИЛКА', s, f, e.message));
    await p.goto(`http://127.0.0.1:8793/gen/out/${s}/${f}`, { waitUntil: 'networkidle' });
    await p.evaluate(() => document.fonts.ready);
    const karta = f.startsWith('karta');
    if (karta) {
      await p.waitForFunction(() => window.GOTOVO === true, null, { timeout: 60000 }).catch(() => console.log('не дочекались', s, f));
      await p.waitForTimeout(800);
    }
    await p.screenshot({ path: `${vykhid}/${s}/${f.replace('.html', '.png')}`, fullPage: !karta });
    await ctx.close();
  }
  console.log('готово', s);
}
await b.close();
})();
