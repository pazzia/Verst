// Verst · design/variants-ir — render the mockups to PNG with Playwright.
// Usage (from the repo root):
//   node design/variants-ir/tools/build-b.js      # B = A markup with data-theme="day"
//   node design/variants-ir/tools/render.js       # all variants × screens × sizes → png/
//   node design/variants-ir/tools/render.js a/windshield.html   # one file (both sizes)
// Output: png/<variant>-<screen>-<w>x<h>.png at 2× (1 CSS px = 1 dp).
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const DIR = path.resolve(__dirname, '..');
const SIZES = [[390, 844], [360, 640]];
const ALL = ['a', 'b', 'c'].flatMap(v => ['windshield', 'instruments'].map(s => `${v}/${s}.html`));

(async () => {
  const only = process.argv.slice(2);
  const files = only.length ? only : ALL;
  const browser = await chromium.launch();
  const report = [];
  for (const rel of files) {
    for (const [w, h] of SIZES) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2, locale: 'ru-RU' });
      const page = await ctx.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(String(e)));
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
      await page.goto('file://' + path.join(DIR, rel));
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(150);
      // Self-checks: no horizontal overflow, no clipped text, touch targets, minimum text size.
      const check = await page.evaluate(() => {
        const out = { overflowX: document.documentElement.scrollWidth > innerWidth, clipped: [], small: [], tiny: [], fonts: [] };
        document.fonts.forEach(f => { if (f.status === 'error') out.fonts.push(f.family + ' ' + f.weight + ' ' + f.status); });
        const scroll = document.querySelector('.scroll');
        const limit = scroll ? scroll.getBoundingClientRect().bottom : innerHeight;
        for (const el of document.querySelectorAll('button, a, [role=radio]')) {
          const r = el.getBoundingClientRect();
          if (r.width === 0) continue;
          if (r.top >= limit) continue; // below the fold of the scroll region
          if (r.height < 47.5 || r.width < 47.5) out.small.push((el.getAttribute('aria-label') || el.textContent.trim()).slice(0, 40) + ` ${Math.round(r.width)}×${Math.round(r.height)}`);
        }
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
          const n = walker.currentNode;
          if (!n.textContent.trim()) continue;
          const el = n.parentElement;
          if (el.closest('.sr,[aria-hidden=true]')) continue;
          const cs = getComputedStyle(el);
          const fs = parseFloat(cs.fontSize);
          if (fs < 14) out.tiny.push(n.textContent.trim().slice(0, 30) + ' ' + fs);
          if (el.scrollWidth > el.clientWidth + 1 && cs.textOverflow !== 'ellipsis' && cs.overflow !== 'visible') out.clipped.push(n.textContent.trim().slice(0, 30));
          if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1) out.clipped.push('ELLIPSIS: ' + n.textContent.trim().slice(0, 40));
        }
        return out;
      });
      const [variant, file] = rel.split('/');
      const name = `${variant}-${file.replace('.html', '')}-${w}x${h}.png`;
      await page.screenshot({ path: path.join(DIR, 'png', name) });
      report.push({ name, errors, ...check });
      await ctx.close();
    }
  }
  await browser.close();
  for (const r of report) {
    const issues = [];
    if (r.errors.length) issues.push('errors: ' + r.errors.join('; '));
    if (r.fonts.length) issues.push('fonts: ' + r.fonts.join(', '));
    if (r.overflowX) issues.push('horizontal overflow');
    if (r.small.length) issues.push('targets < 48: ' + r.small.join(' | '));
    if (r.tiny.length) issues.push('text < 14 sp: ' + r.tiny.join(' | '));
    if (r.clipped.length) issues.push('clipped: ' + r.clipped.join(' | '));
    console.log((issues.length ? 'CHECK ' : 'ok    ') + r.name + (issues.length ? '\n      ' + issues.join('\n      ') : ''));
  }
})();
