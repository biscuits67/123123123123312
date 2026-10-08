// Renders a preview of the animated emoji (lottie-web in Playwright).
//   node tools/emoji_preview.js [frame]   -> emoji_preview.gif (+ emoji_preview.png at the given frame)
// Needs Playwright, ffmpeg and lottie-web (npm i lottie-web; or set LOTTIE_JS=/path/to/lottie.min.js).
const path = require('path');
const fs = require('fs');
const zlib = require('zlib');
const { execFileSync } = require('child_process');
let pw; try { pw = require('playwright'); } catch { pw = require('/opt/node-tools/node_modules/playwright'); }

const DIR = path.resolve(__dirname, '..');
const TGS = path.join(DIR, 'bot', 'emerald_emoji', 'tgs');
const lottieJs = process.env.LOTTIE_JS || require.resolve('lottie-web/build/player/lottie.min.js');
const COLS = 6, CELL = 150, ICON = 110, STEP = 2;   // 60 fps source -> 30 fps gif

(async () => {
  const names = fs.readdirSync(TGS).filter(f => f.endsWith('.tgs')).map(f => f.slice(0, -4));
  const order = ['gem', 'check', 'cross', 'stop', 'wallet', 'star', 'payout', 'bolt', 'users', 'coin', 'chart', 'like',
    'plane', 'chat', 'link', 'book', 'info', 'medal', 'crown', 'calendar', 'globe', 'hourglass', 'bell', 'owner'];
  names.sort((a, b) => (order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99));
  const data = Object.fromEntries(names.map(n => [n, JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(TGS, n + '.tgs'))))]));
  const rows = Math.ceil(names.length / COLS);
  const W = COLS * CELL + 40, H = rows * CELL + 40;
  const browser = await pw.chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.setContent(`<html><body style="margin:0;background:radial-gradient(900px 500px at 50% 0%,#0a3a2a,#020c08 70%);
    width:${W}px;height:${H}px;font:500 12px Inter,sans-serif;color:#8fb8a7">
    <div id="g" style="display:grid;grid-template-columns:repeat(${COLS},${CELL}px);padding:20px"></div></body></html>`);
  await page.addScriptTag({ path: lottieJs });
  await page.evaluate(({ data, ICON, CELL }) => {
    window.anims = [];
    for (const [name, d] of Object.entries(data)) {
      const cell = document.createElement('div');
      cell.style.cssText = `height:${CELL}px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px`;
      const box = document.createElement('div');
      box.style.cssText = `width:${ICON}px;height:${ICON}px`;
      const label = document.createElement('div'); label.textContent = name;
      cell.append(box, label); document.getElementById('g').append(cell);
      anims.push(lottie.loadAnimation({ container: box, renderer: 'svg', loop: false, autoplay: false, animationData: d }));
    }
  }, { data, ICON, CELL });
  const tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'emoji-'));
  const still = +(process.argv[2] || 60);
  for (let f = 0, i = 0; f < 180; f += STEP, i++) {
    await page.evaluate(f => anims.forEach(a => a.goToAndStop(f, true)), f);
    await page.screenshot({ path: path.join(tmp, `f${String(i).padStart(3, '0')}.png`) });
    if (f === still) fs.copyFileSync(path.join(tmp, `f${String(i).padStart(3, '0')}.png`), path.join(DIR, 'emoji_preview.png'));
  }
  await browser.close();
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', '30', '-i', path.join(tmp, 'f%03d.png'),
    '-vf', 'split[a][b];[a]palettegen=max_colors=192[p];[b][p]paletteuse=dither=bayer:bayer_scale=4',
    path.join(DIR, 'emoji_preview.gif')]);
  fs.rmSync(tmp, { recursive: true });
  console.log('emoji_preview.gif', (fs.statSync(path.join(DIR, 'emoji_preview.gif')).size / 1024).toFixed(0), 'KB');
})();
