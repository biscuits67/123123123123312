// Renders the bot avatar from avatar.html:  node tools/render_avatar.js  -> avatar.png (1280x1280)
const path = require('path');
let pw; try { pw = require('playwright'); } catch { pw = require('/opt/node-tools/node_modules/playwright'); }
const DIR = path.resolve(__dirname, '..');
(async () => {
  const browser = await pw.chromium.launch();
  const page = await browser.newPage({ viewport: { width: 640, height: 640 }, deviceScaleFactor: 2 });
  await page.goto(`file://${DIR}/avatar.html`); await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(DIR, 'avatar.png') });
  await browser.close();
  console.log('avatar.png');
})();
