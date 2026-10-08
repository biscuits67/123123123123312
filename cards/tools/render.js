// Renders the Emerald cards from card.html.
//   node tools/render.js            -> all static PNGs + bot assets
//   node tools/render.js ok amount  -> only the listed variants
// Needs Playwright (npm i -g playwright).
const path = require('path');
const fs = require('fs');
let pw; try { pw = require('playwright'); } catch { pw = require('/opt/node-tools/node_modules/playwright'); }

const DIR = path.resolve(__dirname, '..');
const SCALE = 1.5;
const NAMES = {
  ok: 'application_accepted', no: 'application_rejected', wallet: 'wallet_trx', nick: 'nickname',
  address: 'wallet_address', payout: 'payout_choose', payout_ok: 'payout_done', payout_no: 'payout_rejected',
  no_wallet: 'payout_no_wallet', amount: 'payout_amount', branch: 'branch_info',
  forum: 'forum_link', sent: 'application_sent', failed: 'application_failed', nick_saved: 'nickname_saved',
  number: 'enter_number', promo: 'promo_name', promo_exists: 'promo_exists', domain_bad: 'domain_bad_format',
  domain_added: 'domain_added', domain_exists: 'domain_exists', domains: 'domains_list',
  materials: 'menu_materials', info: 'menu_info', domains_none: 'domains_not_found',
};
const THEME = { no: 'ruby', no_wallet: 'ruby', payout_no: 'ruby', failed: 'ruby', number: 'ruby',
  promo_exists: 'ruby', domain_bad: 'ruby', domain_exists: 'ruby', domains_none: 'ruby' };
const ASSETS = path.join(DIR, 'bot', 'emerald_cards', 'assets');

(async () => {
  const only = process.argv.slice(2);
  fs.mkdirSync(path.join(ASSETS, 'bases'), { recursive: true });
  fs.mkdirSync(path.join(ASSETS, 'static'), { recursive: true });
  const layoutFile = path.join(ASSETS, 'layout.json');
  const layout = fs.existsSync(layoutFile) ? JSON.parse(fs.readFileSync(layoutFile, 'utf8')) : {};
  const browser = await pw.chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 640 }, deviceScaleFactor: SCALE });
  for (const [v, name] of Object.entries(NAMES)) {
    if (only.length && !only.includes(v)) continue;
    const url = `file://${DIR}/card.html?v=${v}`;
    await page.goto(url); await page.waitForTimeout(250);
    await page.screenshot({ path: `${DIR}/${name}.png` });            // preview (sample values)
    const slots = await page.evaluate(() => window.__slots());
    if (slots.length) {                                              // dynamic card -> base + layout
      await page.goto(url + '&mode=base'); await page.waitForTimeout(250);
      await page.screenshot({ path: path.join(ASSETS, 'bases', `${name}.png`) });
      layout[name] = {  // replaced fully on each render
        theme: THEME[v] || 'emerald', scale: SCALE, slots: Object.fromEntries(slots.map(s => [s.name, s])) };
      for (const s of slots) delete layout[name].slots[s.name].name;
    } else {
      fs.copyFileSync(`${DIR}/${name}.png`, path.join(ASSETS, 'static', `${name}.png`));
    }
    console.log('rendered', name, slots.length ? '(dynamic)' : '');
  }
  fs.writeFileSync(layoutFile, JSON.stringify(layout, null, 2));
  await browser.close();
})();
