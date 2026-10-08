// Renders scene3d/index.html (three.js) to video, frame by frame:
//   node tools/render_scene3d.js [fps] [still-time]  -> emerald_scene3d.mp4 (H.264 1000x1500, 6 s loop) + emerald_scene3d.png
//   node tools/render_scene3d.js still 1.5           -> only emerald_scene3d.png at t = 1.5 s
// three.js is loaded from node_modules (npm i three@0.169.0) instead of the CDN in the importmap.
const path = require('path');
const fs = require('fs');
const os = require('os');
const { execFileSync } = require('child_process');
let pw; try { pw = require('playwright'); } catch { pw = require('/opt/node-tools/node_modules/playwright'); }

const DIR = path.resolve(__dirname, '..');
const THREE_DIR = process.env.THREE_DIR || path.dirname(path.dirname(require.resolve('three')));
const stillOnly = process.argv[2] === 'still';
const FPS = stillOnly ? 1 : +(process.argv[2] || 30), T = 6;
const stillT = +(process.argv[3] || 1.5);

(async () => {
  const browser = await pw.chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1000, height: 1500 } });
  page.on('pageerror', e => console.error('page error:', e.message));
  page.on('console', m => { if (m.type() === 'error') console.error('console:', m.text()); });
  await page.route('https://cdn.jsdelivr.net/npm/three@0.169.0/**', route => {
    const rel = route.request().url().split('three@0.169.0/')[1];
    route.fulfill({ path: path.join(THREE_DIR, rel), contentType: 'text/javascript' });
  });
  await page.goto(`file://${DIR}/scene3d/index.html`);
  await page.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
  const shot = async (t, file) => {
    await page.evaluate(t => window.render(t), t);
    await page.screenshot({ path: file });
  };
  await shot(stillT, path.join(DIR, 'emerald_scene3d.png'));
  if (stillOnly) { await browser.close(); return console.log('emerald_scene3d.png'); }
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'scene3d-'));
  const t0 = Date.now();
  for (let i = 0; i < FPS * T; i++) {
    await shot(i / FPS, path.join(tmp, `f${String(i).padStart(4, '0')}.png`));
    if (i % 30 === 0) console.log(`frame ${i}/${FPS * T}  ${((Date.now() - t0) / 1000).toFixed(0)} s`);
  }
  await browser.close();
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(tmp, 'f%04d.png'),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
    path.join(DIR, 'emerald_scene3d.mp4')]);
  fs.rmSync(tmp, { recursive: true });
  console.log('emerald_scene3d.mp4', (fs.statSync(path.join(DIR, 'emerald_scene3d.mp4')).size / 1e6).toFixed(1), 'MB');
})();
