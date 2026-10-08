// Renders the bot/channel avatars from avatar.html (1280x1280):
//   node tools/render_avatar.js  -> avatar.png, avatar_chat.png, avatar_deposits.png, avatar_news.png
const path = require('path');
let pw; try { pw = require('playwright'); } catch { pw = require('/opt/node-tools/node_modules/playwright'); }
const DIR = path.resolve(__dirname, '..');
const AVATARS = { avatar: '', avatar_chat: 'ЧАТ', avatar_deposits: 'ДЕПОЗИТЫ', avatar_news: 'NEWS' };
(async () => {
  const browser = await pw.chromium.launch();
  const page = await browser.newPage({ viewport: { width: 640, height: 640 }, deviceScaleFactor: 2 });
  for (const [name, sub] of Object.entries(AVATARS)) {
    await page.goto(`file://${DIR}/avatar.html` + (sub ? `?sub=${encodeURIComponent(sub)}` : '')); await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(DIR, `${name}.png`) });
    console.log(`${name}.png`);
  }
  await browser.close();
})();
