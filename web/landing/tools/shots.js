// Скриншоты 3 вариантов × 360/1280 px. Запуск: см. README.md, раздел «Проверки».
const path = require('path');
const { chromium } = require('playwright');
const OUT = process.argv[2] || path.join(__dirname, '..', 'screenshots');
const BASE = (process.env.BASE || 'http://127.0.0.1:8765') + '/index.html';
const TEST_TG = 'https://t.me/verst_preview'; // только для скриншотов
(async () => {
  const b = await chromium.launch();
  for (const v of ['a', 'b', 'c']) {
    for (const [w, h] of [[360, 800], [1280, 800]]) {
      const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
      const p = await ctx.newPage();
      await p.route('**/index.html*', async route => {
        const r = await route.fetch(); let body = await r.text();
        body = body.replace('TELEGRAM_URL: ""', `TELEGRAM_URL: "${TEST_TG}"`);
        await route.fulfill({ response: r, body });
      });
      await p.emulateMedia({ reducedMotion: 'reduce' });
      await p.goto(`${BASE}?v=${v}`, { waitUntil: 'networkidle' });
      await p.evaluate(() => document.fonts.ready);
      await p.screenshot({ path: `${OUT}/${v}-${w}-fold.png` });
      await p.screenshot({ path: `${OUT}/${v}-${w}-full.png`, fullPage: true });
      await ctx.close();
    }
  }
  await b.close();
  console.log('ok');
})();
