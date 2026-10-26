// Side-by-side comparison per screen: current build (CI run 126 screenshots on the ci-logs branch) vs A vs B vs C, at 390×844.
// Usage (repo root, after render.js):  node design/variants-ir/tools/compare.js
// Needs the ci-logs ref:  git fetch origin +ci-logs:refs/remotes/origin/ci-logs --depth=1
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const DIR = path.resolve(__dirname, '..');
const ROOT = path.resolve(DIR, '../..');
const RUN = 'runs/40242420125-1/screenshots';
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'verst-compare-'));

const SCREENS = { windshield: 'Главный экран', instruments: 'Приборы' };
const COLS = [
  ['now', 'Сейчас', 'сборка CI 126'],
  ['a', 'A · Чистое лобовое', 'та же ночь, меньше декораций'],
  ['b', 'B · Дневная трасса', 'A в светлой теме'],
  ['c', 'C · Простой контроль', 'метафора — только оформление'],
];

(async () => {
  const browser = await chromium.launch();
  for (const [screen, title] of Object.entries(SCREENS)) {
    const now = path.join(tmp, `${screen}.png`);
    fs.writeFileSync(now, execFileSync('git', ['-C', ROOT, 'show', `origin/ci-logs:${RUN}/${screen}/default@390x844.png`]));
    const src = { now, a: '', b: '', c: '' };
    for (const v of ['a', 'b', 'c']) src[v] = path.join(DIR, 'png', `${v}-${screen}-390x844.png`);
    const cols = COLS.map(([k, name, sub]) => `
      <figure><figcaption><b>${name}</b><span>${sub}</span></figcaption><img src="file://${src[k]}" width="390" height="844" alt=""></figure>`).join('');
    const html = `<!doctype html><html lang="ru"><meta charset="utf-8"><style>
      @font-face { font-family: "Verst Sans Narrow"; font-weight: 400; src: url("file://${ROOT}/android/core-ui/src/main/res/font/ibm_plex_sans_condensed_regular.ttf"); }
      @font-face { font-family: "Verst Sans Narrow"; font-weight: 700; src: url("file://${ROOT}/android/core-ui/src/main/res/font/ibm_plex_sans_condensed_bold.ttf"); }
      body { margin: 0; background: #232327; color: #F4F4F0; font-family: "Verst Sans Narrow", sans-serif; }
      .wrap { padding: 28px 32px 24px; width: max-content; }
      h1 { margin: 0 0 20px; font-size: 28px; line-height: 34px; }
      .row { display: flex; gap: 32px; }
      figure { margin: 0; }
      figcaption { display: flex; flex-direction: column; margin-bottom: 10px; }
      figcaption b { font-size: 22px; line-height: 28px; }
      figcaption span { font-size: 16px; line-height: 20px; color: #B9B9C0; }
      img { display: block; border-radius: 22px; box-shadow: 0 0 0 1px #55555E; }
      p { margin: 18px 0 0; font-size: 16px; line-height: 22px; color: #B9B9C0; max-width: 1650px; }
    </style><div class="wrap"><h1>«Верста» · ${title} · 390 × 844 dp</h1><div class="row">${cols}</div>
    <p>Суммы ≈ ₽ в вариантах — оценка демо-движка на экипаж из зеркала (2 взрослых, 1 ребёнок, собака; 300 км в день; «Спокойно»; бюджет 40 000 ₽). Команда — design/variants-ir/README.md §9.</p></div></html>`;
    const file = path.join(tmp, `${screen}.html`);
    fs.writeFileSync(file, html);
    const page = await browser.newPage({ viewport: { width: 1800, height: 1100 }, deviceScaleFactor: 1.5 });
    await page.goto('file://' + file);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(100);
    const box = await page.locator('.wrap').boundingBox();
    await page.screenshot({ path: path.join(DIR, `compare-${screen}.png`), clip: box });
    console.log(`compare-${screen}.png`);
    await page.close();
  }
  await browser.close();
  fs.rmSync(tmp, { recursive: true, force: true });
})();
