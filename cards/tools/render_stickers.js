// Renders the Emerald sticker pack from stickers.html:
//   node tools/render_stickers.js [id ...] -> bot/emerald_stickers/webp/<id>.webp (512x512, transparent)
//                                            + bot/emerald_stickers/manifest.json + stickers_preview.png
// Needs Playwright and ffmpeg (PNG -> WEBP).
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');
let pw; try { pw = require('playwright'); } catch { pw = require('/opt/node-tools/node_modules/playwright'); }

const DIR = path.resolve(__dirname, '..');
const OUT = path.join(DIR, 'bot', 'emerald_stickers');

(async () => {
  fs.mkdirSync(path.join(OUT, 'webp'), { recursive: true });
  const tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'stk-'));
  const browser = await pw.chromium.launch();
  const page = await browser.newPage({ viewport: { width: 512, height: 512 } });
  await page.goto(`file://${DIR}/stickers.html`);
  const all = await page.evaluate(() => window.__stickers);
  const only = process.argv.slice(2);
  for (const id of Object.keys(all)) {
    if (only.length && !only.includes(id)) continue;
    await page.goto(`file://${DIR}/stickers.html?s=${id}`); await page.waitForTimeout(150);
    const png = path.join(tmp, `${id}.png`);
    await page.screenshot({ path: png, omitBackground: true });
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', png, '-c:v', 'libwebp', '-lossless', '0', '-quality', '92',
      path.join(OUT, 'webp', `${id}.webp`)]);
    console.log(id, all[id], (fs.statSync(path.join(OUT, 'webp', `${id}.webp`)).size / 1024).toFixed(0), 'KB');
  }
  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(all, null, 1));
  // contact sheet on a Telegram-like chat background
  const ids = Object.keys(all), cols = 5, cell = 256, rows = Math.ceil(ids.length / cols);
  const sheet = await browser.newPage({ viewport: { width: cols * cell, height: rows * cell } });
  const imgs = ids.map(id => `<img src="data:image/webp;base64,${fs.readFileSync(path.join(OUT, 'webp', id + '.webp')).toString('base64')}"
    style="width:${cell}px;height:${cell}px">`).join('');
  await sheet.setContent(`<body style="margin:0;background:#0e1621;display:flex;flex-wrap:wrap;width:${cols * cell}px">${imgs}</body>`);
  await sheet.waitForTimeout(400);
  await sheet.screenshot({ path: path.join(DIR, 'stickers_preview.png') });
  await browser.close();
  fs.rmSync(tmp, { recursive: true });
})();
