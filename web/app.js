import * as THREE from 'three';
import { MapControls } from './vendor/MapControls.js';

const BG = 0x0d0f14;
const ATTR_W = 256;
const WORKERS = Math.min(4, navigator.hardwareConcurrency || 2);

const config = await (await fetch('data/amsterdam.json')).json();
const attrs = new DataView(await (await fetch('data/attrs.bin')).arrayBuffer());
const periods = config.periods;

// ---------- Scene ----------
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setClearColor(BG);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 5, 60000);
const controls = new MapControls(camera, canvas);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.47;
controls.minDistance = 60;
controls.maxDistance = 30000;

function goHome() {
  const h = config.home, az = THREE.MathUtils.degToRad(h.azimuth), el = THREE.MathUtils.degToRad(h.elevation);
  const d = h.span * 0.9;
  controls.target.set(h.x, 0, h.z);
  camera.position.set(h.x + d * Math.cos(el) * Math.sin(az), d * Math.sin(el), h.z + d * Math.cos(el) * Math.cos(az));
  controls.update();
}
goHome();

// Land and water: flat polygons in the local frame (see pipeline/s04_water.py).
async function loadPolygons(url) {
  const buf = await (await fetch(url)).arrayBuffer();
  const [nPoly, nRing, nVert] = new Uint32Array(buf, 0, 3);
  const ringStart = new Uint32Array(buf, 12, nPoly + 1);
  const vertStart = new Uint32Array(buf, 12 + 4 * (nPoly + 1), nRing + 1);
  const xz = new Float32Array(buf, 12 + 4 * (nPoly + 1) + 4 * (nRing + 1), 2 * nVert);
  const ring = r => {
    const pts = [];
    for (let v = vertStart[r]; v < vertStart[r + 1]; v++) pts.push(new THREE.Vector2(xz[2 * v], -xz[2 * v + 1]));
    return pts;
  };
  const shapes = [];
  for (let p = 0; p < nPoly; p++) {
    const shape = new THREE.Shape(ring(ringStart[p]));
    for (let r = ringStart[p] + 1; r < ringStart[p + 1]; r++) shape.holes.push(new THREE.Path(ring(r)));
    shapes.push(shape);
  }
  const g = new THREE.ShapeGeometry(shapes);
  g.rotateX(-Math.PI / 2);
  return g;
}
const flat = new THREE.Group();
scene.add(flat);
const [landGeo, waterGeo] = await Promise.all([loadPolygons('data/land.bin'), loadPolygons('data/water.bin')]);
const land = new THREE.Mesh(landGeo, new THREE.MeshBasicMaterial({ color: 0x1d2028 }));
const water = new THREE.Mesh(waterGeo, new THREE.MeshBasicMaterial({ color: 0x0f2c45 }));
land.position.y = -0.05;
water.position.y = -0.4;
flat.add(land, water);

// ---------- Shared uniforms ----------
const hex = c => new THREE.Color(c);
const uniforms = {
  uYear: { value: config.yearMax },
  uYearFrom: { value: config.yearMin - 1 },
  uMode: { value: 0 },
  uPalette: { value: periods.map(p => hex(p.color)) },
  uMask: { value: periods.map(() => 1) },
  uHover: { value: -1 },
  uSelected: { value: -1 },
  uFogColor: { value: hex(BG) },
  uFog: { value: new THREE.Vector2(9000, 26000) },
};

const VERT = /* glsl */`
  in float bld;
  uniform sampler2D uAttr;
  uniform float uYear, uYearFrom, uMode, uHover, uSelected;
  uniform vec3 uPalette[${periods.length}];
  uniform float uMask[${periods.length}];
  out vec3 vColor;
  out vec3 vWorld;
  out float vGid;
  out float vRel;

  vec3 floorsRamp(float f) {
    float t = clamp(log(f) / log(40.0), 0.0, 1.0);
    vec3 a = vec3(0.16, 0.20, 0.42), b = vec3(0.17, 0.55, 0.62), c = vec3(0.55, 0.80, 0.42), d = vec3(0.99, 0.85, 0.30);
    return t < 0.33 ? mix(a, b, t / 0.33) : t < 0.66 ? mix(b, c, (t - 0.33) / 0.33) : mix(c, d, (t - 0.66) / 0.34);
  }

  void main() {
    int i = int(bld + 0.5);
    vec4 a = texelFetch(uAttr, ivec2(i % ${ATTR_W}, i / ${ATTR_W}), 0);
    float year = a.x;
    int pf = int(a.y + 0.5);
    int period = pf % 16;
    int flag = pf / 16;
    vGid = a.w;
    if (year > uYear || uMask[period] < 0.5) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }

    vec3 p = position;
    p.y *= clamp((uYear - year + 1.0) / 2.0, 0.0, 1.0);
    vec3 col = uMode < 0.5 ? uPalette[period] : floorsRamp(a.z);
    if (flag == 1 || flag == 2 || flag == 4) col = mix(col, vec3(0.55), 0.45);
    if (year <= uYearFrom) col *= 0.22;
    if (vGid == uHover || vGid == uSelected) col = mix(col, vec3(1.0), 0.6);
    vColor = col;
    vRel = position.y;
    vec4 w = modelMatrix * vec4(p, 1.0);
    vWorld = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }
`;

const FRAG = /* glsl */`
  precision highp float;
  uniform vec3 uFogColor;
  uniform vec2 uFog;
  in vec3 vColor;
  in vec3 vWorld;
  in float vGid;
  in float vRel;
  out vec4 outColor;
  void main() {
    #ifdef PICK
      float id = vGid + 1.0;
      outColor = vec4(mod(id, 256.0), mod(floor(id / 256.0), 256.0), floor(id / 65536.0), 255.0) / 255.0;
    #else
      vec3 n = normalize(cross(dFdx(vWorld), dFdy(vWorld)));
      float light = 0.62 + 0.38 * max(dot(n, normalize(vec3(-0.4, 0.8, 0.45))), 0.0);
      if (n.y > 0.9) light = 1.02;
      float base = mix(0.7, 1.0, clamp(vWorld.y / 15.0, 0.0, 1.0));
      vec3 c = vColor * light * base;
      float d = length(vWorld - cameraPosition);
      c = mix(c, uFogColor, smoothstep(uFog.x, uFog.y, d));
      outColor = vec4(c, 1.0);
    #endif
  }
`;

function makeMaterial(tex, pick) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: { ...uniforms, uAttr: { value: tex } },
    vertexShader: VERT,
    fragmentShader: FRAG,
    defines: pick ? { PICK: 1 } : {},
    side: THREE.DoubleSide,
  });
}

// ---------- Tiles ----------
const meshes = [];
let loaded = 0;
const queue = [...config.tiles];
const pool = Array.from({ length: WORKERS }, () => new Worker('worker.js', { type: 'module' }));

function addTile(m) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(m.pos, 3));
  g.setAttribute('bld', new THREE.BufferAttribute(m.bld, 1));
  g.setIndex(new THREE.BufferAttribute(m.idx, 1));
  const rows = Math.ceil(m.nB / ATTR_W);
  const data = new Float32Array(ATTR_W * rows * 4);
  data.set(m.attr);
  const tex = new THREE.DataTexture(data, ATTR_W, rows, THREE.RGBAFormat, THREE.FloatType);
  tex.needsUpdate = true;
  const mesh = new THREE.Mesh(g, makeMaterial(tex, false));
  mesh.userData = { draw: mesh.material, pick: makeMaterial(tex, true) };
  mesh.scale.setScalar(0.1);
  mesh.position.set(m.origin[0], 0, m.origin[1]);
  scene.add(mesh);
  meshes.push(mesh);
}

for (const w of pool) {
  const next = () => {
    const t = queue.shift();
    if (t) w.postMessage({ url: `data/tiles/${t.file}`, id: t.file });
  };
  w.onmessage = ({ data }) => {
    addTile(data);
    loaded++;
    document.getElementById('progress').textContent = Math.round(100 * loaded / config.tiles.length);
    if (loaded === config.tiles.length) document.getElementById('loading').hidden = true;
    next();
  };
  next();
}

// ---------- Picking ----------
const pickTarget = new THREE.WebGLRenderTarget(1, 1);
const pickPixel = new Uint8Array(4);
function pick(x, y) {
  const w = renderer.domElement.clientWidth, h = renderer.domElement.clientHeight;
  camera.setViewOffset(w, h, x, y, 1, 1);
  for (const m of meshes) m.material = m.userData.pick;
  flat.visible = false;
  renderer.setRenderTarget(pickTarget);
  renderer.setClearColor(0x000000, 0);
  renderer.clear();
  renderer.render(scene, camera);
  renderer.readRenderTargetPixels(pickTarget, 0, 0, 1, 1, pickPixel);
  renderer.setRenderTarget(null);
  renderer.setClearColor(BG, 1);
  flat.visible = true;
  for (const m of meshes) m.material = m.userData.draw;
  camera.clearViewOffset();
  return pickPixel[0] + pickPixel[1] * 256 + pickPixel[2] * 65536 - 1;
}

// ---------- Hover card ----------
const card = document.getElementById('card');
const FLAG_NOTE = [
  'Year from the BAG register.',
  'The register gives a round year here, more often than neighbouring years would predict. Read it as “around then”; the map spreads it across the rounding step.',
  'The register has no real year here (placeholder 1005, or one of the surplus 1905s of the old centre). Estimated from the nearest dated buildings.',
  'Year from the rijksmonument register (RCE), which dates the building earlier than BAG does.',
  'Dated by the rijksmonument register (RCE) to a century or part of one; the map spreads it across that span.',
];
function building(gid) {
  const o = gid * config.attrStride;
  return {
    bag: String(attrs.getFloat64(o, true)).padStart(16, '0'),
    height: attrs.getUint16(o + 8, true) / 10,
    fsrc: attrs.getUint8(o + 10),
    flag: attrs.getUint8(o + 11),
    year: attrs.getInt16(o + 12, true),
    orig: attrs.getInt16(o + 14, true),
    mon: attrs.getUint32(o + 16, true),
  };
}
function showCard(gid, x, y) {
  if (gid < 0) { card.hidden = true; return; }
  const b = building(gid);
  const p = periods.find(p => b.year >= p.from && b.year <= p.to) || periods[0];
  const floors = b.fsrc === 0 ? 'BAG 3D model' : 'height ÷ 3.2 m';
  card.innerHTML = `
    <b>${b.flag ? '≈ ' : ''}${b.year}</b>
    <div class="row"><span>Period</span><span>${p.label}</span></div>
    ${b.orig !== b.year ? `<div class="row"><span>BAG says</span><span>${b.orig}</span></div>` : ''}
    <div class="row"><span>Height</span><span>${b.height.toFixed(1)} m</span></div>
    <div class="row"><span>Floors from</span><span>${floors}</span></div>
    <div class="row"><span>BAG pand</span><span>${b.bag}</span></div>
    ${b.mon ? `<div class="row"><span>Rijksmonument</span><span>${b.mon}</span></div>` : ''}
    <div class="note">${FLAG_NOTE[b.flag]}</div>`;
  card.hidden = false;
  const r = card.getBoundingClientRect();
  card.style.left = Math.min(x + 16, innerWidth - r.width - 8) + 'px';
  card.style.top = Math.min(y + 16, innerHeight - r.height - 130) + 'px';
}

let pointer = null, dragging = false;
canvas.addEventListener('pointermove', e => { pointer = [e.clientX, e.clientY]; });
canvas.addEventListener('pointerdown', () => { dragging = true; card.hidden = true; });
canvas.addEventListener('pointerup', e => {
  dragging = false;
  const gid = pick(e.clientX, e.clientY);
  uniforms.uSelected.value = gid;
});
canvas.addEventListener('pointerleave', () => { pointer = null; card.hidden = true; uniforms.uHover.value = -1; });

// ---------- Legend & modes ----------
const legend = document.getElementById('legend');
const totals = periods.map(() => 0);
for (const v of Object.values(config.histogram)) v.forEach((n, i) => totals[i] += n);
periods.forEach((p, i) => {
  const b = document.createElement('button');
  b.innerHTML = `<i style="background:${p.color}"></i>${p.label}<span class="n">${totals[i].toLocaleString('en')}</span>`;
  b.onclick = () => {
    const solo = uniforms.uMask.value.every((m, j) => (j === i) === !!m);
    uniforms.uMask.value = periods.map((_, j) => (solo || j === i) ? 1 : 0);
    [...legend.children].forEach((el, j) => el.classList.toggle('off', !uniforms.uMask.value[j]));
    drawHist();
  };
  legend.append(b);
});
document.querySelectorAll('.modes button').forEach(b => b.onclick = () => {
  uniforms.uMode.value = +b.dataset.mode;
  document.querySelectorAll('.modes button').forEach(x => x.classList.toggle('on', x === b));
});

// ---------- Timeline ----------
const hist = document.getElementById('hist');
const hctx = hist.getContext('2d');
const T0 = Math.floor(config.yearMin / 50) * 50, T1 = config.yearMax + 1;
const years = Object.entries(config.histogram).map(([y, v]) => [+y, v]);
const yMax = Math.max(...years.map(([, v]) => v.reduce((a, b) => a + b, 0)));
const xOf = y => (y - T0) / (T1 - T0) * hist.clientWidth;
const yearOf = x => Math.round(T0 + x / hist.clientWidth * (T1 - T0));

function visibleCount() {
  let n = 0;
  for (const [y, v] of years) if (y <= uniforms.uYear.value) v.forEach((c, i) => { if (uniforms.uMask.value[i]) n += c; });
  return n;
}

function drawHist() {
  const w = hist.clientWidth, h = hist.clientHeight, dpr = devicePixelRatio;
  hist.width = w * dpr; hist.height = h * dpr;
  hctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  hctx.clearRect(0, 0, w, h);
  const plotH = h - 18, bw = Math.max(1, w / (T1 - T0));
  for (const [y, v] of years) {
    let top = plotH;
    v.forEach((c, i) => {
      if (!c) return;
      const bh = Math.sqrt(c / yMax) * (plotH - 6);
      const on = uniforms.uMask.value[i] && y <= uniforms.uYear.value;
      hctx.fillStyle = periods[i].color;
      hctx.globalAlpha = on ? (y <= uniforms.uYearFrom.value ? 0.3 : 1) : 0.15;
      hctx.fillRect(xOf(y), top - bh, bw, bh);
      top -= bh;
    });
  }
  hctx.globalAlpha = 1;
  hctx.fillStyle = '#8a8d96';
  hctx.font = '10px ui-monospace, monospace';
  for (let y = Math.ceil(T0 / 100) * 100; y <= T1; y += 100) hctx.fillText(y, Math.max(0, xOf(y) - 12), h - 4);
  for (const [y, c] of [[uniforms.uYear.value, '#e8e6e1'], [uniforms.uYearFrom.value, '#8a8d96']]) {
    if (y < T0) continue;
    hctx.fillStyle = c;
    hctx.fillRect(xOf(y) - 0.5, 0, 1.5, plotH);
  }
  document.getElementById('year').textContent = uniforms.uYear.value;
  document.getElementById('count').textContent = visibleCount().toLocaleString('en');
}

let handle = null;
hist.addEventListener('pointerdown', e => {
  hist.setPointerCapture(e.pointerId);
  const x = e.offsetX;
  handle = Math.abs(x - xOf(uniforms.uYearFrom.value)) < Math.abs(x - xOf(uniforms.uYear.value)) ? 'uYearFrom' : 'uYear';
  moveHandle(x);
  stopPlay();
});
hist.addEventListener('pointermove', e => handle && moveHandle(e.offsetX));
hist.addEventListener('pointerup', () => handle = null);
function moveHandle(x) {
  const y = Math.max(T0, Math.min(config.yearMax, yearOf(x)));
  if (handle === 'uYear') uniforms.uYear.value = Math.max(y, uniforms.uYearFrom.value + 1);
  else uniforms.uYearFrom.value = Math.min(y, uniforms.uYear.value - 1);
  drawHist();
}

// Play: slow through the sparse centuries, then year by year through the dense ones.
let playing = false, playT0 = 0, playStart = 0;
const playBtn = document.getElementById('play');
const DURATION = 30000;
function playYear(t) {
  const k = 0.35; // share of time spent before 1850
  return t < k ? T0 + (1850 - T0) * (t / k) : 1850 + (config.yearMax - 1850) * ((t - k) / (1 - k));
}
function startPlay() {
  playing = true; playStart = performance.now();
  if (uniforms.uYear.value >= config.yearMax) uniforms.uYear.value = T0;
  playT0 = 0;
  while (playT0 < 1 && playYear(playT0) < uniforms.uYear.value) playT0 += 0.001;
  playBtn.textContent = '❚❚';
}
function stopPlay() { playing = false; playBtn.textContent = '▶'; }
playBtn.onclick = () => playing ? stopPlay() : startPlay();

// ---------- Loop ----------
function resize() {
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  drawHist();
}
addEventListener('resize', resize);
resize();

let frame = 0;
renderer.setAnimationLoop(now => {
  controls.update();
  const dist = camera.position.distanceTo(controls.target);
  uniforms.uFog.value.set(dist * 1.6, dist * 4);
  if (playing) {
    const t = Math.min(1, playT0 + (now - playStart) / DURATION);
    uniforms.uYear.value = Math.round(playYear(t));
    if (t >= 1) stopPlay();
    drawHist();
  }
  if (pointer && !dragging && ++frame % 3 === 0) {
    const gid = pick(pointer[0], pointer[1]);
    uniforms.uHover.value = gid;
    showCard(gid, pointer[0], pointer[1]);
  }
  renderer.render(scene, camera);
});

window.__dbg = { pick, uniforms, camera, controls };
