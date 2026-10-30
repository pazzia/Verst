const { chromium } = require('playwright');
const fs = require('fs');
// Проверки лендинга: переполнение на 320 px, axe (WCAG 2.2 AA), фокус, ячейки Telegram, цели Метрики, форма, вес.
const path = require('path');
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const BASE = (process.env.BASE || 'http://127.0.0.1:8765') + '/index.html';
const SHOTS = process.argv[2] || path.join(__dirname, '..', 'screenshots');
function cfg(over) {
  return async route => {
    const r = await route.fetch(); let body = await r.text();
    for (const [k, v] of Object.entries(over)) {
      if (k === 'TELEGRAM_URLS') body = body.replace(/TELEGRAM_URLS: \{[^}]*\}/, 'TELEGRAM_URLS: ' + JSON.stringify(v));
      else body = body.replace(new RegExp('\\n  ' + k + ': [^,\\n]*'), `\n  ${k}: ${JSON.stringify(v)}`);
    }
    await route.fulfill({ response: r, body });
  };
}
const TG = { TELEGRAM_URL: 'https://t.me/verst_preview' };
(async () => {
  const b = await chromium.launch();
  let fail = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fail++; };

  // 1. Overflow + axe per variant and width
  for (const v of ['a', 'b', 'c']) for (const w of [320, 360, 1280]) {
    const p = await b.newPage({ viewport: { width: w, height: 800 } });
    await p.route('**/index.html*', cfg(TG));
    await p.goto(`${BASE}?v=${v}`, { waitUntil: 'networkidle' });
    await p.evaluate(() => document.fonts.ready);
    await p.evaluate(() => document.querySelectorAll('details').forEach(d => d.open = true));
    const o = await p.evaluate(() => {
      const W = document.documentElement.clientWidth; const bad = [];
      const clipped = e => { for (let a = e.parentElement; a && a !== document.body; a = a.parentElement) if (getComputedStyle(a).overflowX !== 'visible') return true; return false; };
      document.querySelectorAll('body *').forEach(e => { const r = e.getBoundingClientRect(); if (r.width && r.right > W + 0.5 && !clipped(e) && !e.closest('[hidden]')) bad.push(e.tagName + '.' + (e.getAttribute('class') || '')); });
      return { sw: document.documentElement.scrollWidth, W, bad: [...new Set(bad)].slice(0, 5) };
    });
    ok(o.sw <= o.W && o.bad.length === 0, `v=${v} ${w}px: scrollWidth ${o.sw} <= ${o.W}, overflowing elements: ${JSON.stringify(o.bad)}`);
    if (w !== 320) {
      await p.addScriptTag({ content: AXE });
      const res = await p.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] } })));
      const viol = res.violations.map(x => `${x.id}(${x.impact})x${x.nodes.length}`);
      ok(viol.length === 0, `axe v=${v} ${w}px: ${res.passes.length} rules pass, violations: ${JSON.stringify(viol)}`);
      if (viol.length) res.violations.forEach(x => x.nodes.slice(0, 3).forEach(n => console.log('   ', x.id, n.target.join(' '), n.failureSummary.split('\n')[1])));
    }
    await p.close();
  }

  // 2. Keyboard focus order and visibility
  {
    const p = await b.newPage({ viewport: { width: 360, height: 800 } });
    await p.route('**/index.html*', cfg(TG));
    await p.goto(`${BASE}?v=a`, { waitUntil: 'networkidle' });
    const seen = [];
    for (let i = 0; i < 12; i++) {
      await p.keyboard.press('Tab');
      const f = await p.evaluate(() => { const e = document.activeElement; if (e === document.body) return { t: 'BODY' }; const s = getComputedStyle(e); const r = e.getBoundingClientRect();
        return { t: (e.textContent || e.tagName).trim().replace(/\s+/g, ' ').slice(0, 40), outline: s.outlineStyle + ' ' + s.outlineWidth + ' ' + s.outlineColor, inView: r.top >= 0 && r.bottom <= innerHeight }; });
      if (f.t === 'BODY') break;
      seen.push(f);
      if (i === 0) await p.screenshot({ path: SHOTS + '/focus-cta-360.png', clip: { x: 0, y: 500, width: 360, height: 200 } });
      if (f.t.startsWith('Сколько')) await p.screenshot({ path: SHOTS + '/focus-faq-360.png', clip: { x: 0, y: 200, width: 360, height: 300 } });
    }
    seen.forEach(f => ok(/solid 3px rgb\(255, 210, 63\)/.test(f.outline) && f.inView, `focus "${f.t}": ${f.outline}, in view ${f.inView}`));
    await p.close();
  }

  // 3. Cells, events, PII
  const CELLS = { 'yandex-a': 'https://t.me/+cellYA', 'yandex-b': 'https://t.me/+cellYB', 'yandex-c': 'https://t.me/+cellYC', 'vk-a': 'https://t.me/+cellVA', 'vk-b': 'https://t.me/+cellVB', 'vk-c': '' };
  const DEF = 'https://t.me/+siteOrganic';
  const cases = [
    ['b', 'yandex', 'yandex', 'https://t.me/+cellYB'],
    ['a', 'vk', 'vk', 'https://t.me/+cellVA'],
    ['c', 'vk', 'vk', DEF],                                     // ячейка без ссылки -> запасная
    ['a', encodeURIComponent('Test User'), 'other', DEF],
    ['b', encodeURIComponent('ivan.petrov@mail.ru'), 'other', DEF],
    ['c', 'interview', 'interview', DEF],
    ['a', '', 'none', DEF],
    ['x', 'yandex', 'yandex', 'https://t.me/+cellYA'],           // неверный ?v= -> показан a -> ячейка yandex-a
  ];
  for (const [v, utm, expSrc, expUrl] of cases) {
    const p = await b.newPage({ viewport: { width: 360, height: 800 } });
    await p.route('**/index.html*', cfg({ TELEGRAM_URLS: CELLS, TELEGRAM_URL: DEF, METRIKA_ID: '12345678' }));
    await p.route('https://mc.yandex.ru/**', r => r.abort());
    let tgReq = null; await p.route('https://t.me/**', r => { tgReq = r.request().url(); r.fulfill({ body: 'tg' }); });
    await p.goto(`${BASE}?v=${v}${utm ? '&utm_source=' + utm : ''}&utm_campaign=val02-promise-2026-11&utm_content=Bad_Value`, { waitUntil: 'networkidle' });
    await p.click('summary >> text=Сколько это стоит?');
    const t0 = Date.now();
    await p.click('[data-tg="hero"]');
    await p.waitForTimeout(700);
    const q = await p.evaluate(() => JSON.stringify(window.ym.a)).catch(() => 'navigated');
    const shown = v === 'x' ? 'a' : v;
    ok(tgReq === expUrl, `v=${v} utm_source=${decodeURIComponent(utm) || '-'} -> Telegram link ${tgReq} (expected ${expUrl})`);
    await p.close();
    // повтор без перехода, чтобы прочитать очередь Метрики
    const p2 = await b.newPage();
    await p2.route('**/index.html*', cfg({ TELEGRAM_URLS: CELLS, TELEGRAM_URL: DEF, METRIKA_ID: '12345678' }));
    await p2.route('https://mc.yandex.ru/**', r => r.abort());
    await p2.goto(`${BASE}?v=${v}${utm ? '&utm_source=' + utm : ''}&utm_campaign=val02-promise-2026-11&utm_content=Bad_Value`, { waitUntil: 'networkidle' });
    await p2.click('summary >> text=Сколько это стоит?');
    await p2.waitForTimeout(100);
    await p2.evaluate(() => { const a = document.querySelector('[data-tg="final"]'); a.addEventListener('click', e => e.preventDefault()); });
    await p2.evaluate(() => { window.location.assign = () => {}; });
    const queue = await p2.evaluate(() => { const a = document.querySelector('[data-tg="final"]'); const ev = new MouseEvent('click', { bubbles: true, cancelable: true, ctrlKey: true }); a.dispatchEvent(ev); return JSON.stringify(window.ym.a.map(x => [x[1], x[2], x[3]])); });
    await p2.waitForTimeout(50);
    const okq = queue.includes(`["reachGoal","page_view",{"variant":"${shown}","utm_source":"${expSrc}","utm_campaign":"val02-promise-2026-11","utm_content":"other"}]`)
      && queue.includes(`["reachGoal","faq_open",{"variant":"${shown}","utm_source":"${expSrc}","faq_id":"q1"}]`)
      && queue.includes(`["reachGoal","tg_click",{"variant":"${shown}","utm_source":"${expSrc}","cta_location":"final"}]`)
      && queue.includes('"webvisor":false') && !/mail|@|Test/.test(queue);
    ok(okq, `Metrika queue: ${queue}`);
    await p2.close();
  }
  { // no METRIKA_ID -> no request to mc.yandex.ru
    const p = await b.newPage(); let mc = 0;
    p.on('request', r => { if (r.url().includes('mc.yandex')) mc++; });
    await p.route('**/index.html*', cfg(TG));
    await p.goto(`${BASE}?v=b&utm_source=yandex`, { waitUntil: 'networkidle' });
    const log = await p.evaluate(() => JSON.stringify(window.verstEvents));
    ok(mc === 0 && log.includes('"page_view"'), `no METRIKA_ID: ${mc} requests to Metrika; local log ${log}`);
    await p.close();
  }

  // 4. Config states: unset Telegram, form disabled, form enabled
  {
    const p = await b.newPage({ viewport: { width: 360, height: 800 } });
    await p.goto(`${BASE}`, { waitUntil: 'networkidle' });
    const st = await p.evaluate(() => ({ warn: !document.getElementById('config-warning').hidden, form: getComputedStyle(document.getElementById('email-form')).display, soon: !document.getElementById('email-soon').hidden, inputs: [...document.querySelectorAll('input')].filter(i => i.offsetParent).length }));
    ok(st.warn, 'unconfigured TELEGRAM_URL shows warning banner');
    ok(st.form === 'none' && st.soon && st.inputs === 0, `FORM_ENABLED=false: form display=${st.form}, «скоро» text shown=${st.soon}, visible inputs=${st.inputs}`);
    await p.close();
  }
  {
    const p = await b.newPage({ viewport: { width: 360, height: 800 } });
    await p.route('**/index.html*', cfg({ ...TG, FORM_ENABLED: false, FORM_ENDPOINT: 'https://api.example.test/waitlist', PRIVACY_URL: 'https://example.test/privacy', CONSENT_VERSION: 'test' }));
    await p.goto(`${BASE}`, { waitUntil: 'networkidle' });
    ok(await p.evaluate(() => document.getElementById('email-form').hidden), 'endpoint set but FORM_ENABLED=false: form stays hidden');
    await p.close();
  }
  {
    const p = await b.newPage({ viewport: { width: 360, height: 800 } });
    await p.route('**/index.html*', cfg({ ...TG, FORM_ENABLED: true, FORM_ENDPOINT: 'https://api.example.test/waitlist', PRIVACY_URL: 'https://example.test/privacy', CONSENT_VERSION: 'test-2026-10' }));
    let body = null;
    await p.route('https://api.example.test/**', r => { body = r.request().postData(); r.fulfill({ status: 200, contentType: 'application/json', body: '{}', headers: { 'access-control-allow-origin': '*' } }); });
    await p.goto(`${BASE}?v=b&utm_source=vk_ads`, { waitUntil: 'networkidle' });
    await p.click('#email-submit');
    const e1 = await p.evaluate(() => [document.getElementById('email-err').textContent, document.activeElement.id]);
    ok(e1[0].includes('Введите e-mail') && e1[1] === 'email-input', `empty submit -> "${e1[0]}", focus on ${e1[1]}`);
    await p.fill('#email-input', 'ivan@mail'); await p.click('#email-submit');
    await p.locator('#email').screenshot({ path: SHOTS + '/form-enabled-error-360.png' });
    await p.fill('#email-input', 'ivan@mail.ru'); await p.click('#email-submit');
    const e2 = await p.evaluate(() => [document.getElementById('consent-err').textContent, document.activeElement.id]);
    ok(e2[0].length > 0 && e2[1] === 'consent', `no consent -> "${e2[0]}", focus on ${e2[1]}`);
    await p.check('#consent');
    await p.addScriptTag({ content: AXE });
    const ax = await p.evaluate(async () => (await axe.run(document.getElementById('email'))).violations.map(v => v.id));
    ok(ax.length === 0, `axe on enabled form: ${JSON.stringify(ax)}`);
    await p.click('#email-submit');
    await p.waitForSelector('.form__done');
    const done = await p.evaluate(() => [document.querySelector('.form__done').textContent, document.activeElement.className, JSON.stringify(window.verstEvents)]);
    ok(body && JSON.parse(body).consent_version === 'test-2026-10' && done[1] === 'form__done', `POST body ${body}; success "${done[0]}"`);
    ok(!/mail\.ru/.test(done[2]), `form_submit goal carries no e-mail: ${done[2]}`);
    await p.locator('#email').screenshot({ path: SHOTS + '/form-enabled-success-360.png' });
    await p.close();
  }

  // 5. Reduced motion and weight
  {
    const p = await b.newPage(); await p.emulateMedia({ reducedMotion: 'reduce' });
    await p.route('**/index.html*', cfg(TG));
    await p.goto(BASE, { waitUntil: 'networkidle' });
    ok(await p.evaluate(() => getComputedStyle(document.querySelector('.lane')).animationName) === 'none', 'prefers-reduced-motion: lane animation off');
    await p.close();
    const p2 = await b.newPage(); let tot = 0, fonts = 0, n = 0;
    p2.on('response', async r => { try { const len = (await r.body()).length; n++; if (/\.woff2$/.test(r.url())) fonts += len; else tot += len; } catch (e) {} });
    await p2.goto(BASE + '?v=b', { waitUntil: 'networkidle' }); await p2.waitForTimeout(300);
    ok(tot < 300 * 1024, `page weight without fonts: ${(tot / 1024).toFixed(1)} KB; fonts: ${(fonts / 1024).toFixed(1)} KB; requests: ${n}`);
    await p2.close();
  }
  await b.close();
  console.log(fail ? `${fail} FAILED` : 'ALL PASS');
})();
