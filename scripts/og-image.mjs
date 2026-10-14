// The link-preview image for WhatsApp, Slack and the rest (og:image): the city at 1200×630, captioned, as a JPEG under
// 300 KB, rendered by the Chrome installed on this Mac through its DevTools protocol (Node 22+, no packages).
//   node scripts/og-image.mjs [url] [out]   defaults: the live site, web/og-image.jpg
// Then publish (scripts/publish.sh) so the image matches the data. Previews are cached by WhatsApp and Slack for days.
import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const [url = 'https://jacopoottaviani.com/rome-over-time/?spin=0&lang=en', out = 'web/og-image.jpg'] = process.argv.slice(2);
// dolly < 1 moves the camera in from the opening view; azimuthDeg, polarDeg and target: [x, z] can turn and aim it.
const view = {
  dolly: 0.82,
  quality: 80,
  caption: '<div style="font-size:56px;font-weight:800;letter-spacing:-0.035em;line-height:.95">Every building<br>in Rome, by age<br>and history</div>' +
    '<div style="margin-top:16px;font-size:22px;font-weight:500;color:#3e4448">250,000 buildings · 25 centuries · open data</div>',
  captionStyle: "position:fixed;left:40px;bottom:40px;font-family:'Schibsted Grotesk',sans-serif;color:#000;" +
    'background:rgba(244,243,240,.9);padding:24px 30px 26px;border-radius:12px;box-shadow:0 1px 0 rgba(0,0,0,.06)',
};
const W = 1200, H = 630, PORT = 9333;
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), 'og-'))}`,
  `--window-size=${W},${H}`, '--hide-scrollbars', '--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist',
  '--no-first-run', '--no-default-browser-check', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));

let targets;
for (let i = 0; i < 50 && !targets; i++) {
  await sleep(200);
  try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); } catch {}
}
const ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r, { once: true }));
let id = 0; const pending = new Map();
ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async expression => {
  const m = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (m.result?.exceptionDetails) throw new Error(JSON.stringify(m.result.exceptionDetails));
  return m.result?.result?.value;
};

try {
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
  await send('Page.enable');
  await send('Page.navigate', { url });
  await evaluate(`new Promise((ok, fail) => { const t0 = Date.now(); (function wait() {
    const l = document.getElementById('loading');
    if (window.__dbg && l && l.hidden) return ok(true);
    if (Date.now() - t0 > 90000) return fail('timed out loading the city');
    setTimeout(wait, 250); })(); })`);
  const info = await evaluate(`(async () => {
    await document.fonts.ready;
    const v = ${JSON.stringify(view)}, d = window.__dbg, THREE_ = d.camera.position.constructor;
    if (v.target) d.controls.target.set(v.target[0], 0, v.target[1]);
    const off = d.camera.position.clone().sub(d.controls.target);
    let r = off.length() * (v.dolly || 1);
    const polar = v.polarDeg != null ? v.polarDeg * Math.PI / 180 : Math.acos(off.y / off.length());
    const az = v.azimuthDeg != null ? v.azimuthDeg * Math.PI / 180 : Math.atan2(off.x, off.z);
    d.camera.position.set(d.controls.target.x + r * Math.sin(polar) * Math.sin(az), r * Math.cos(polar),
                          d.controls.target.z + r * Math.sin(polar) * Math.cos(az));
    d.controls.update();
    for (const s of ['.masthead', '.modes', '.lang', '.tally', '.compass', '#panel', '#card', '.howto', '.timeline', '.veil'])
      document.querySelectorAll(s).forEach(e => e.style.display = 'none');
    if (v.caption) {
      const cap = document.createElement('div');
      cap.innerHTML = v.caption;
      cap.style.cssText = v.captionStyle || '';
      document.body.appendChild(cap);
    }
    return { target: d.controls.target.toArray().map(Math.round), dist: Math.round(d.camera.position.distanceTo(d.controls.target)),
             az: Math.round(d.controls.getAzimuthalAngle() * 180 / Math.PI), polar: Math.round(d.controls.getPolarAngle() * 180 / Math.PI) };
  })()`);
  await sleep(3000);
  const shot = await send('Page.captureScreenshot', { format: 'jpeg', quality: view.quality || 86 });
  writeFileSync(out, Buffer.from(shot.result.data, 'base64'));
  console.log(out, JSON.stringify(info));
} finally {
  ws.close();
  chrome.kill();
}
