// Variant B «Дневная трасса» = variant A markup in the day palette (tokens-day.json → [data-theme="day"] in shared/base.css).
// Keeping one markup guarantees that A and B differ only in colour, which is what the 5-second test compares.
const fs = require('fs');
const path = require('path');
const DIR = path.resolve(__dirname, '..');
for (const f of ['windshield.html', 'instruments.html']) {
  const src = path.join(DIR, 'a', f);
  if (!fs.existsSync(src)) continue;
  let html = fs.readFileSync(src, 'utf8');
  html = html.replace('<html lang="ru">', '<html lang="ru" data-theme="day">')
    .replace(/<title>A · Чистое лобовое/, '<title>B · Дневная трасса')
    .replace('<!doctype html>', '<!doctype html>\n<!-- GENERATED from ../a/' + f + ' by tools/build-b.js — edit A, then rebuild. -->');
  fs.writeFileSync(path.join(DIR, 'b', f), html);
  console.log('b/' + f);
}
