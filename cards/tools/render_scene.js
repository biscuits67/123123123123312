// Renders scene/emerald_scene.html to video:
//   node tools/render_scene.js [fps] -> emerald_scene.mp4 (H.264, 1000x1500, 6 s loop) + emerald_scene.png (still)
// Needs Playwright and ffmpeg.
const path = require('path');
const fs = require('fs');
const os = require('os');
const { execFileSync } = require('child_process');
let pw; try { pw = require('playwright'); } catch { pw = require('/opt/node-tools/node_modules/playwright'); }

const DIR = path.resolve(__dirname, '..');
const FPS = +(process.argv[2] || 30), T = 6;

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'scene-'));
  const browser = await pw.chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1000, height: 1500 } });
  await page.goto(`file://${DIR}/scene/emerald_scene.html`);
  await page.evaluate(() => window.ready);
  const canvas = await page.$('canvas');
  for (let i = 0; i < FPS * T; i++) {
    await page.evaluate(t => window.render(t), i / FPS);
    await canvas.screenshot({ path: path.join(tmp, `f${String(i).padStart(4, '0')}.png`) });
  }
  fs.copyFileSync(path.join(tmp, 'f0000.png'), path.join(DIR, 'emerald_scene.png'));
  await browser.close();
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(tmp, 'f%04d.png'),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
    path.join(DIR, 'emerald_scene.mp4')]);
  fs.rmSync(tmp, { recursive: true });
  console.log('emerald_scene.mp4', (fs.statSync(path.join(DIR, 'emerald_scene.mp4')).size / 1e6).toFixed(1), 'MB');
})();
