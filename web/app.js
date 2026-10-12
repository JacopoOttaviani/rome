import * as THREE from './vendor/three.module.js';
import { MapControls } from './vendor/MapControls.js';

// Colours are authored in sRGB and drawn as they are.
THREE.ColorManagement.enabled = false;

const SKY = '#e4e8ea';
const LAND = '#f4f3ef';
const WATER = '#b5c7c6';
const MAQUETTE = '#efeee9';
const GROUP_COLORS = ['#ec0000', '#1f4e8c', '#d99a12', '#2e8b57', '#7b3fa0', '#00909a', '#8c5a2b', '#d6336c'];
const MAX_GROUPS = GROUP_COLORS.length;
const ATTR_W = 256;
const WORKERS = Math.min(4, navigator.hardwareConcurrency || 2);
const MODE = { period: 0, floors: 1, energy: 2, layers: 3, residents: 4 };
// Energy labels G … A+++++ (index 1–12; 0 = no label), from red through yellow to deep green.
const ENERGY_COLORS = ['#efeee9', '#c1272d', '#e4572e', '#f08a24', '#f6c445', '#c9d64a', '#8cc152', '#4caf50',
  '#2e9a49', '#1d8040', '#126b35', '#0b5a2c', '#064a24'];

const [config, layers, attrBuf] = await Promise.all([
  fetch('data/amsterdam.json').then(r => r.json()),
  fetch('data/layers.json').then(r => r.json()),
  fetch('data/attrs.bin').then(r => r.arrayBuffer()),
]);
const attrs = new DataView(attrBuf);
const periods = config.periods;

// ---------- Scene ----------
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setClearColor(SKY);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 5, 60000);
const controls = new MapControls(camera, canvas);
controls.enableDamping = true;
// Left drag turns and tilts the city; right drag, or Shift with the left, moves it.
controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
controls.rotateSpeed = 0.6;
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
const land = new THREE.Mesh(landGeo, new THREE.MeshBasicMaterial({ color: LAND }));
const water = new THREE.Mesh(waterGeo, new THREE.MeshBasicMaterial({ color: WATER }));
land.position.y = -0.05;
water.position.y = -0.4;
flat.add(land, water);

// ---------- Street and canal names ----------
// Flat on the ground, turned along the street (pipeline/s07_labels.py). Textures are drawn on first use.
const labelData = await fetch('data/labels.json').then(r => r.json());
const labelGroup = new THREE.Group();
scene.add(labelGroup);
const labelTex = new Map();
const LABEL_PX = 64;
function textureFor(L) {
  let t = labelTex.get(L.name + L.water);
  if (t) return t;
  const c = document.createElement('canvas'), ctx = c.getContext('2d');
  const font = `${L.water ? 'italic 500' : '500'} ${LABEL_PX * 0.62}px "Schibsted Grotesk", sans-serif`;
  ctx.font = font;
  c.width = Math.ceil(ctx.measureText(L.name).width + LABEL_PX * 0.4);
  c.height = LABEL_PX;
  ctx.font = font;
  ctx.textBaseline = 'middle';
  ctx.lineWidth = LABEL_PX * 0.12;
  ctx.strokeStyle = L.water ? 'rgba(181,199,198,0.85)' : 'rgba(244,243,239,0.85)';
  ctx.fillStyle = L.water ? '#3c6875' : '#50565b';
  ctx.strokeText(L.name, LABEL_PX * 0.2, LABEL_PX / 2);
  ctx.fillText(L.name, LABEL_PX * 0.2, LABEL_PX / 2);
  t = new THREE.CanvasTexture(c);
  t.anisotropy = 4;
  t.userData = { aspect: c.width / c.height };
  labelTex.set(L.name + L.water, t);
  return t;
}
const labelPlane = new THREE.PlaneGeometry(1, 1);
const labels = labelData.flatMap(L => L.pts.map(([x, z, ang, len, wid]) => ({ L, x, z, ang, len, wid: wid || 20, mesh: null })))
  .sort((a, b) => a.L.tier - b.L.tier || b.len - a.len);
function updateLabels(dist) {
  if (!document.fonts.check('500 16px "Schibsted Grotesk"')) return;
  // Label height in metres, roughly constant on screen; the canals and main streets read larger.
  const h1 = THREE.MathUtils.clamp(dist * 0.014, 4, 44), h2 = THREE.MathUtils.clamp(dist * 0.01, 3, 15);
  // Names appear only when the camera comes close: canals and main streets first, the rest closer still.
  const near = dist * 1.2, far = dist * 2;
  // Greedy collision: canals and main streets first, then the longest stretches; a label is dropped
  // when an accepted one already sits within a few label heights of it.
  const taken = new Map(), C = h1 * 5; // one grid, cells as wide as the largest separation
  const cellOf = (x, z) => `${Math.floor(x / C)},${Math.floor(z / C)}`;
  const clear = (l, sep) => {
    const cx = Math.floor(l.x / C), cz = Math.floor(l.z / C);
    for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) {
      for (const q of taken.get(`${cx + i},${cz + j}`) || []) if ((q.x - l.x) ** 2 + (q.z - l.z) ** 2 < sep * sep) return false;
    }
    return true;
  };
  for (const l of labels) {
    const d = Math.hypot(l.x - camera.position.x, l.z - camera.position.z);
    let show = d < (l.L.tier === 1 ? far : near) && dist < (l.L.tier === 1 ? 3200 : 1300);
    const sep = (l.L.tier === 1 ? h1 : h2) * 5;
    if (show && !clear(l, sep)) show = false;
    if (show) {
      const key = cellOf(l.x, l.z);
      if (!taken.has(key)) taken.set(key, []);
      taken.get(key).push(l);
    }
    if (show && !l.mesh) {
      const tex = textureFor(l.L);
      l.mesh = new THREE.Mesh(labelPlane, new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }));
      // Turn about the vertical first, then lay the plane flat.
      l.mesh.rotation.set(-Math.PI / 2, THREE.MathUtils.degToRad(-l.ang), 0, "YXZ"); // ang is measured towards +z, Y turns towards -z
      l.mesh.position.set(l.x, l.L.water ? 0.4 : 0.6, l.z);
      l.mesh.renderOrder = 2;
      labelGroup.add(l.mesh);
    }
    if (l.mesh) {
      // Never taller than the street or canal is wide, so a name stays off the buildings.
      const h = Math.min(l.L.tier === 1 ? h1 : h2, l.wid * 0.55);
      const w = h * l.mesh.material.map.userData.aspect;
      // A name much longer than its stretch of street would spill over the buildings.
      if (show && (w > l.len * 1.1 || h < 2.5)) show = false;
      l.mesh.visible = show;
      if (show) l.mesh.scale.set(w, h, 1);
    }
  }
}

// ---------- Shared uniforms ----------
const col = c => new THREE.Color(c);
const uniforms = {
  uYear: { value: config.yearMax },
  uYearFrom: { value: config.yearMin - 1 },
  uMode: { value: MODE.period },
  uPalette: { value: periods.map(p => col(p.color)) },
  uMask: { value: periods.map(() => 1) },
  uGroupBit: { value: Array(MAX_GROUPS).fill(-1) },
  uGroupColor: { value: GROUP_COLORS.map(col) },
  uMaquette: { value: col(MAQUETTE) },
  uEnergy: { value: ENERGY_COLORS.map(col) },
  uHover: { value: -1 },
  uSelected: { value: -1 },
  uFogColor: { value: col(SKY) },
  uFog: { value: new THREE.Vector2(9000, 26000) },
};

const VERT = /* glsl */`
  in float bld;
  uniform sampler2D uAttr;
  uniform float uYear, uYearFrom, uMode, uHover, uSelected;
  uniform vec3 uPalette[${periods.length}];
  uniform float uMask[${periods.length}];
  uniform int uGroupBit[${MAX_GROUPS}];
  uniform vec3 uGroupColor[${MAX_GROUPS}];
  uniform vec3 uMaquette;
  uniform vec3 uEnergy[13];
  out vec3 vColor;
  out vec3 vWorld;
  out float vGid;

  vec3 floorsRamp(float f) {
    float t = clamp(log(f) / log(40.0), 0.0, 1.0);
    vec3 a = vec3(0.86, 0.89, 0.90), b = vec3(0.49, 0.66, 0.75), c = vec3(0.17, 0.36, 0.55), d = vec3(0.05, 0.10, 0.25);
    return t < 0.33 ? mix(a, b, t / 0.33) : t < 0.66 ? mix(b, c, (t - 0.33) / 0.33) : mix(c, d, (t - 0.66) / 0.34);
  }

  bool hasBit(vec4 words, int bit) {
    int w = bit / 16;
    float v = w == 0 ? words.x : w == 1 ? words.y : w == 2 ? words.z : words.w;
    return ((int(v + 0.5) >> (bit - w * 16)) & 1) == 1;
  }

  void main() {
    int i = int(bld + 0.5);
    ivec2 tc = ivec2(2 * (i % ${ATTR_W}), i / ${ATTR_W});
    vec4 a = texelFetch(uAttr, tc, 0);
    vec4 lay = texelFetch(uAttr, tc + ivec2(1, 0), 0);
    float year = a.x;
    int pf = int(a.y + 0.5);
    int period = pf % 16;
    int flag = pf / 16;
    vGid = a.w;
    bool filtered = uMode < 1.5 && uMask[period] < 0.5;
    if (year > uYear || filtered) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }

    vec3 p = position;
    p.y *= clamp((uYear - year + 1.0) / 2.0, 0.0, 1.0);
    vec3 c;
    if (uMode < 0.5) {
      c = uPalette[period];
      if (flag == 1 || flag == 2 || flag == 4) c = mix(c, uMaquette, 0.45);
    } else if (uMode < 1.5) {
      c = floorsRamp(mod(a.z, 128.0));
    } else if (uMode < 2.5) {
      c = uEnergy[int(a.z / 128.0)];
    } else {
      c = uMaquette;
      for (int g = 0; g < ${MAX_GROUPS}; g++) {
        if (uGroupBit[g] >= 0 && hasBit(lay, uGroupBit[g])) { c = uGroupColor[g]; break; }
      }
    }
    if (year <= uYearFrom) c = mix(c, uMaquette, 0.8);
    if (vGid == uHover || vGid == uSelected) c = mix(c, vec3(0.0), 0.35);
    vColor = c;
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
  out vec4 outColor;
  void main() {
    #ifdef PICK
      float id = vGid + 1.0;
      outColor = vec4(mod(id, 256.0), mod(floor(id / 256.0), 256.0), floor(id / 65536.0), 255.0) / 255.0;
    #else
      vec3 n = normalize(cross(dFdx(vWorld), dFdy(vWorld)));
      // Low afternoon sun from the south-west, a soft sky from above.
      float sun = max(dot(n, normalize(vec3(-0.55, 0.55, 0.62))), 0.0);
      float light = n.y > 0.9 ? 1.04 : 0.66 + 0.34 * sun;
      float foot = mix(0.82, 1.0, clamp(vWorld.y / 12.0, 0.0, 1.0));
      vec3 c = vColor * light * foot;
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
  const data = new Float32Array(ATTR_W * 2 * rows * 4);
  data.set(m.attr);
  const tex = new THREE.DataTexture(data, ATTR_W * 2, rows, THREE.RGBAFormat, THREE.FloatType);
  tex.needsUpdate = true;
  const mesh = new THREE.Mesh(g, makeMaterial(tex, false));
  mesh.userData = { draw: mesh.material, pick: makeMaterial(tex, true) };
  mesh.scale.setScalar(0.1);
  mesh.position.set(m.origin[0], 0, m.origin[1]);
  scene.add(mesh);
  meshes.push(mesh);
}

// Tiles come in packs (see pipeline/s03_tiles.py); a tile is ready once its pack has arrived.
const packs = Object.fromEntries(config.packs.map(name => [name, fetch(`data/${name}`).then(r => r.arrayBuffer())]));
for (const w of pool) {
  const next = async () => {
    const t = queue.shift();
    if (!t) return;
    const buf = (await packs[t.pack]).slice(t.offset, t.offset + t.length);
    w.postMessage({ buf, id: t.file }, [buf]);
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
  labelGroup.visible = false;
  renderer.setRenderTarget(pickTarget);
  renderer.setClearColor(0x000000, 0);
  renderer.clear();
  renderer.render(scene, camera);
  renderer.readRenderTargetPixels(pickTarget, 0, 0, 1, 1, pickPixel);
  renderer.setRenderTarget(null);
  renderer.setClearColor(SKY, 1);
  flat.visible = true;
  labelGroup.visible = true;
  for (const m of meshes) m.material = m.userData.draw;
  camera.clearViewOffset();
  return pickPixel[0] + pickPixel[1] * 256 + pickPixel[2] * 65536 - 1;
}

// ---------- Building lookup ----------
const DATE_NOTE = [
  null,
  'The register gives a round year here, more often than neighbouring years predict. Read it as “around then”.',
  'The register has no real year (placeholder 1005, or one of the surplus 1905s of the old centre). Estimated from the nearest dated buildings.',
  'Year from the register of national monuments, which dates the building earlier than BAG does.',
  'Dated by the register of national monuments to a century or part of one; the map spreads it across that span.',
];
const residentsLayer = layers.find(L => L.id === 'residents');
const contextLayers = layers.filter(L => L !== residentsLayer);
const groupsByBit = contextLayers.flatMap(L => L.groups.map(g => ({ ...g, layer: L })));

function building(gid) {
  const o = gid * config.attrStride;
  const lay0 = attrs.getUint32(o + 20, true), lay1 = attrs.getUint32(o + 24, true);
  return {
    bag: String(attrs.getFloat64(o, true)).padStart(16, '0'),
    height: attrs.getUint16(o + 8, true) / 10,
    fsrc: attrs.getUint8(o + 10),
    flag: attrs.getUint8(o + 11),
    year: attrs.getInt16(o + 12, true),
    orig: attrs.getInt16(o + 14, true),
    mon: attrs.getUint32(o + 16, true),
    wk: attrs.getInt32(o + 28, true),
    energy: attrs.getUint8(o + 32),
    x: attrs.getFloat32(o + 36, true),
    z: attrs.getFloat32(o + 40, true),
    groups: groupsByBit.filter(g => g.bit < 32 ? (lay0 >>> g.bit) & 1 : (lay1 >>> (g.bit - 32)) & 1),
  };
}

const periodOf = y => periods.find(p => y >= p.from && y <= p.to) || periods[0];

// ---------- Building card ----------
// Hover shows a light card that follows the pointer; a click pins it, with the article extract and links.
let wiki = [];
fetch('data/wiki.json').then(r => r.json()).then(w => { wiki = w; });
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const link = (href, text) => `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(text)}</a>`;

// Local metres → RD New → WGS84 (Schreutelkamp and Strang van Hees approximation, ~1 m).
function toLatLon(x, z) {
  const dX = (x + config.origin[0] - 155000) * 1e-5, dY = (config.origin[1] - z - 463000) * 1e-5;
  const lat = 52.15517440 + (3235.65389 * dY - 32.58297 * dX ** 2 - 0.2475 * dY ** 2 - 0.84978 * dX ** 2 * dY
    - 0.0655 * dY ** 3 - 0.01709 * dX ** 2 * dY ** 2 - 0.00738 * dX + 0.0053 * dX ** 4 - 0.00039 * dX ** 2 * dY ** 3
    + 0.00033 * dX ** 4 * dY - 0.00012 * dX * dY) / 3600;
  const lon = 5.38720621 + (5260.52916 * dX + 105.94684 * dX * dY + 2.45656 * dX * dY ** 2 - 0.81885 * dX ** 3
    + 0.05594 * dX * dY ** 3 - 0.05607 * dX ** 3 * dY + 0.01199 * dY - 0.00256 * dX ** 3 * dY ** 2
    + 0.00128 * dX * dY ** 4 + 0.00022 * dY ** 2 - 0.00022 * dX ** 2 + 0.00026 * dX ** 5) / 3600;
  return [lat, lon];
}
// The city's street panoramas (CC BY 4.0), turned towards the building from the nearest point on the street.
function streetView(b) {
  const [lat, lon] = toLatLon(b.x, b.z);
  return `https://api.data.amsterdam.nl/panorama/thumbnail/?lat=${lat.toFixed(6)}&lon=${lon.toFixed(6)}&width=640&radius=80`;
}
const SV_CREDIT = `Street view: ${'<a href="https://data.amsterdam.nl" target="_blank" rel="noopener">Gemeente Amsterdam</a>'}, CC BY 4.0`;

function groupColor(g) {
  return GROUP_COLORS[g.layer.groups.findIndex(x => x.bit === g.bit)] || GROUP_COLORS[0];
}

function residentsHtml(b, pinned) {
  const n = residentsLayer?.notes?.[b.bag];
  if (!n) return '';
  const people = pinned ? n.people : n.people.slice(0, 3);
  return `<section><h4>Lived or worked here</h4><ul class="residents">${people.map(p => `<li>
    <b>${pinned ? link(p.url, p.person) : esc(p.person)}</b>${p.born ? ` <span>${esc(p.born)}${p.died ? '–' + esc(p.died) : ''}</span>` : ''}
    ${p.desc ? `<div class="desc">${esc(p.desc)}</div>` : ''}
    ${pinned ? `<blockquote lang="nl">${esc(p.quote)}</blockquote>` : ''}</li>`).join('')}</ul>
    ${!pinned && n.people.length > 3 ? `<p class="why">and ${n.people.length - 3} more</p>` : ''}</section>`;
}

// The card reads top to bottom: photo, name and year; what the building is; the layers it belongs to and why;
// the facts; how its date was found; where to read more.
function cardHtml(gid, pinned) {
  const b = building(gid);
  const w = b.wk >= 0 ? wiki[b.wk] : null;
  const im = w?.image?.thumb ? w.image : null;
  const period = periodOf(b.year);
  const facts = [
    ['Height', `${b.height.toFixed(1)} m`],
    ['Storeys', b.fsrc === 0 ? 'from the 3D BAG model' : 'height ÷ 3.2 m'],
    w?.architects?.length && [w.architects.length > 1 ? 'Architects' : 'Architect', w.architects.map(esc).join(', ')],
    w?.styles?.length && ['Style', w.styles.map(esc).join(', ')],
    b.mon && ['National monument', `no. ${b.mon}`],
    b.energy && ['Energy label', `<span class="elabel" style="background:${ENERGY_COLORS[b.energy]}">${config.energy.labels[b.energy - 1]}</span>`],
  ].filter(Boolean);
  const credit = im && (pinned
    ? `${link(im.page || im.thumb, im.artist || 'Wikimedia Commons')}${im.license ? `, ${im.licenseUrl ? link(im.licenseUrl, im.license) : esc(im.license)}` : ''}`
    : `${esc(im.artist || 'Wikimedia Commons')}${im.license ? `, ${esc(im.license)}` : ''}`);
  const sources = [
    w?.wiki?.url && link(w.wiki.url, w.wiki.lang === 'nl' ? 'Dutch Wikipedia' : 'Wikipedia'),
    b.mon && link(`https://monumentenregister.cultureelerfgoed.nl/monumenten/${b.mon}`, 'Monument register'),
    link(`https://bagviewer.kadaster.nl/lvbag/bag-viewer/?objectId=${b.bag}`, 'BAG register'),
  ].filter(Boolean);
  const inLayers = b.groups.map(g => {
    const note = g.layer.notes?.[b.bag];
    return `<li><i style="background:${groupColor(g)}"></i><div><b>${esc(g.layer.title)}</b> <span>${esc(g.label)}</span>
      ${pinned && note ? `<p>${esc(note.story)}${note.source ? ` ${link(note.source, 'Source')}` : ''}</p>` : ''}</div></li>`;
  }).join('');
  const dating = b.orig !== b.year ? `${DATE_NOTE[b.flag] || ''} BAG gives ${b.orig}.` : DATE_NOTE[b.flag];
  return `
    ${pinned ? '<button class="card-close" aria-label="Close">×</button>' : ''}
    ${im ? `<figure class="photo"><img src="${esc(im.thumb)}" alt="" onerror="this.parentElement.remove()"><figcaption>Photo: ${credit}</figcaption></figure>`
      : `<figure class="photo sv"><img data-sv="${esc(streetView(b))}" alt="" onerror="this.parentElement.remove()"><figcaption>${pinned ? SV_CREDIT : 'Street view: Gemeente Amsterdam, CC BY 4.0'}</figcaption></figure>`}
    <header class="card-head">
      ${w?.label ? `<h3>${esc(w.label)}</h3>` : ''}
      <div class="when"><span class="y">${b.flag && b.flag !== 3 ? 'c. ' : ''}${b.year}</span>
        <span class="period"><i style="background:${period.color}"></i>${esc(period.label)}</span></div>
    </header>
    ${pinned && w?.wiki?.extract ? `<section><p class="extract">${esc(w.wiki.extract)}</p></section>` : ''}
    ${residentsHtml(b, pinned)}
    ${pinned && im ? `<section><h4>From the street</h4><figure class="photo sv inline"><img data-sv="${esc(streetView(b))}" alt="" onerror="this.parentElement.parentElement.remove()"><figcaption>${SV_CREDIT}</figcaption></figure></section>` : ''}
    ${inLayers ? `<section><h4>In layers</h4><ul class="chips">${inLayers}</ul></section>` : ''}
    <section><dl>${facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl></section>
    ${dating ? `<section><h4>Dating</h4><p class="why">${dating}</p></section>` : ''}
    ${pinned ? `<section class="sources"><h4>Read more</h4><p>${sources.join(', ')}</p></section>`
      : `<p class="hint">${w?.wiki || b.groups.some(g => g.layer.notes?.[b.bag]) ? 'Click for the story and sources' : 'Click to keep this card open'}</p>`}`;
}

const card = document.getElementById('card');
let pinnedGid = -1;
let svTimer = null;
function loadStreetViews(delay) {
  clearTimeout(svTimer);
  svTimer = setTimeout(() => card.querySelectorAll('img[data-sv]').forEach(img => {
    img.addEventListener('load', () => placeCard(...(pointer || lastPin)), { once: true });
    img.src = img.dataset.sv;
  }), delay);
}
let lastPin = [0, 0];
function placeCard(x, y) {
  const r = card.getBoundingClientRect();
  card.style.left = Math.max(12, Math.min(x + 18, innerWidth - r.width - 12)) + 'px';
  card.style.top = Math.max(12, Math.min(y + 18, innerHeight - r.height - 12)) + 'px';
}
let hoverGid = -1;
function showCard(gid, x, y) {
  if (pinnedGid >= 0 || phone.matches) return;
  if (gid < 0) { card.hidden = true; hoverGid = -1; return; }
  if (gid !== hoverGid || card.hidden) {
    // Re-render only when the building changes, so the photo is not reloaded every frame.
    hoverGid = gid;
    card.innerHTML = cardHtml(gid, false);
    card.classList.remove('pinned');
    card.hidden = false;
    loadStreetViews(350);
    card.querySelector('img')?.addEventListener('load', () => placeCard(...(pointer || [x, y])));
  }
  placeCard(x, y);
}
function pinCard(gid, x, y) {
  pinnedGid = gid;
  hoverGid = -1;
  uniforms.uSelected.value = gid;
  if (gid < 0) { card.hidden = true; card.classList.remove('pinned'); return; }
  card.innerHTML = cardHtml(gid, true);
  card.classList.add('pinned');
  lastPin = [x, y];
  collapsePanelOnPhone();
  loadStreetViews(0);
  card.hidden = false;
  card.querySelector('.card-close').onclick = () => pinCard(-1);
  card.querySelector('img')?.addEventListener('load', () => placeCard(x, y));
  placeCard(x, y);
}
addEventListener('keydown', e => { if (e.key === 'Escape') pinCard(-1); });

// A click (not a drag) pins the building under the pointer, or clears the pin on empty ground.
let pointer = null, dragging = false, downAt = null;
canvas.addEventListener('pointermove', e => { pointer = [e.clientX, e.clientY]; });
canvas.addEventListener('pointerdown', e => {
  dragging = true; downAt = [e.clientX, e.clientY];
  if (pinnedGid < 0) card.hidden = true;
});
canvas.addEventListener('pointerup', e => {
  dragging = false;
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 5) return;
  const gid = pick(e.clientX, e.clientY);
  pinCard(gid === pinnedGid ? -1 : gid, e.clientX, e.clientY);
});
canvas.addEventListener('pointerleave', () => { pointer = null; if (pinnedGid < 0) card.hidden = true; uniforms.uHover.value = -1; });

// ---------- Flying to a building ----------
let bagIndex = null;
function gidOf(bag) {
  if (!bagIndex) {
    bagIndex = new Map();
    for (let g = 0; g < config.stats.buildings; g++) {
      bagIndex.set(String(attrs.getFloat64(g * config.attrStride, true)).padStart(16, '0'), g);
    }
  }
  return bagIndex.get(bag) ?? -1;
}
let flight = null;
function flyTo(x, z, done) {
  const dir = camera.position.clone().sub(controls.target).normalize();
  if (dir.y < 0.45) { dir.y = 0.45; dir.normalize(); }
  const target = new THREE.Vector3(x, 0, z);
  flight = { t0: performance.now(), dur: 1400, fromT: controls.target.clone(), toT: target,
    fromP: camera.position.clone(), toP: target.clone().add(dir.multiplyScalar(520)), done };
}
function stepFlight(now) {
  if (!flight) return;
  const k = Math.min(1, (now - flight.t0) / flight.dur), e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
  controls.target.lerpVectors(flight.fromT, flight.toT, e);
  camera.position.lerpVectors(flight.fromP, flight.toP, e);
  if (k >= 1) { const d = flight.done; flight = null; d?.(); }
}

// ---------- Panel ----------
const panelEl = document.getElementById('panel');
const panel = document.getElementById('panel-body');
const sheetHandle = panelEl.querySelector('.sheet-handle');
const phone = matchMedia('(max-width: 720px)');
// On a phone the panel is a sheet: folded to one line until opened, and folded again when the city is the point.
function setCollapsed(c) {
  panelEl.classList.toggle('collapsed', c);
  sheetHandle.setAttribute('aria-expanded', String(!c));
  sheetHandle.textContent = c ? 'Show legend' : 'Hide legend';
}
sheetHandle.onclick = () => setCollapsed(!panelEl.classList.contains('collapsed'));
function collapsePanelOnPhone() { if (phone.matches) setCollapsed(true); }
setCollapsed(phone.matches);
const totals = periods.map(() => 0);
for (const v of Object.values(config.histogram)) v.forEach((n, i) => totals[i] += n);
const fmt = n => n.toLocaleString('en');
let activeLayer = null;
const SECTION_ORDER = ['Architecture', 'Trade and empire', 'Faith and community', 'Countries and communities',
  'The modern city', 'War and occupation'];
const groupOn = {};

function renderPanel() {
  const mode = uniforms.uMode.value;
  if (mode === MODE.period) {
    panel.innerHTML = `<h2>Built in</h2><div class="swatches">${periods.map((p, i) => `
      <button class="swatch" data-i="${i}" aria-pressed="${!!uniforms.uMask.value[i]}">
        <i style="background:${p.color}"></i><span>${p.label}</span><span class="n">${fmt(totals[i])}</span>
      </button>`).join('')}</div>
      <p class="note">Click a period to see it alone. Paler buildings have an approximate year.</p>`;
    panel.querySelectorAll('.swatch').forEach(b => b.onclick = () => {
      const i = +b.dataset.i, m = uniforms.uMask.value;
      const solo = m.every((v, j) => (j === i) === !!v);
      uniforms.uMask.value = periods.map((_, j) => (solo || j === i) ? 1 : 0);
      renderPanel(); drawHist();
    });
  } else if (mode === MODE.floors) {
    panel.innerHTML = `<h2>Storeys</h2>
      <div class="ramp" style="background:linear-gradient(90deg,#dbe3e6,#7da8bf,#2b5c8c,#0d1a40)"></div>
      <div class="ramp-scale"><span>1</span><span>3</span><span>8</span><span>20</span><span>40+</span></div>
      <p class="note">${fmt(config.stats.floorsBag3d)} buildings take their storeys from the 3D BAG model; the rest, ${fmt(config.stats.floorsHeight)}, from their height divided by 3.2 m.</p>`;
  } else if (mode === MODE.energy) {
    const e = config.energy;
    panel.innerHTML = `<h2>Energy label</h2><div class="energy-scale">${e.labels.map((l, i) => `
      <div><i style="background:${ENERGY_COLORS[i + 1]}"></i><span>${l}</span><span class="n">${fmt(e.counts[i + 1])}</span></div>`).reverse().join('')}</div>
      <p class="note">The label most homes in a building carry. ${fmt(e.counts[0])} buildings, white on the map, have no registered label.</p>
      <a class="src" href="https://www.atlasleefomgeving.nl/energielabels-van-gebouwen" target="_blank" rel="noopener">RVO energy labels, via Atlas Leefomgeving</a>`;
  } else if (mode === MODE.residents) {
    const notes = Object.entries(residentsLayer?.notes || {});
    const people = notes.flatMap(([bag, n]) => n.people.map(p => ({ ...p, bag, at: n.at })))
      .sort((a, b) => b.links - a.links);
    panel.innerHTML = `<h2 class="layer-title">Who lived here</h2>
      <p class="layer-intro">${esc(residentsLayer?.text || '')}</p>
      <input class="filter" type="search" placeholder="Find a person" aria-label="Find a person">
      <ul class="stories people">${people.map(p => `<li data-q="${esc((p.person + ' ' + (p.desc || '')).toLowerCase())}">
        <button class="story" data-bag="${p.bag}"><b>${esc(p.person)}</b>
        <span>${[p.born && p.died ? `${p.born}–${p.died}` : p.born, p.desc].filter(Boolean).map(esc).join(', ')}</span>
        <span class="addr">${esc(p.address)}</span></button></li>`).join('')}</ul>
      ${residentsLayer?.caveat ? `<p class="caveat">${esc(residentsLayer.caveat)}</p>` : ''}`;
    panel.querySelector('.filter').oninput = e => {
      const q = e.target.value.toLowerCase();
      panel.querySelectorAll('.people li').forEach(li => { li.hidden = q && !li.dataset.q.includes(q); });
    };
    panel.querySelectorAll('.story').forEach(b => b.onclick = () => {
      const n = residentsLayer.notes[b.dataset.bag];
      collapsePanelOnPhone();
      flyTo(n.at[0], n.at[1], () => { const gid = gidOf(b.dataset.bag); if (gid >= 0) pinCard(gid, innerWidth * 0.62, innerHeight * 0.18); });
    });
  } else if (!activeLayer) {
    const sections = [...new Set(contextLayers.map(L => L.section))].sort((a, b) => SECTION_ORDER.indexOf(a) - SECTION_ORDER.indexOf(b));
    panel.innerHTML = sections.map(sec => `<h2 class="section">${esc(sec)}</h2><div class="layers">${contextLayers.filter(L => L.section === sec).map(L => `
      <button class="layer" data-id="${L.id}">
        <b>${esc(L.title)}</b><span class="n">${fmt(L.count)}</span><span class="era">${esc(L.era)}</span>
      </button>`).join('')}</div>`).join('');
    panel.querySelectorAll('.layer').forEach(b => b.onclick = () => setLayer(contextLayers.find(l => l.id === b.dataset.id)));
  } else {
    panel.innerHTML = `<button class="back">All layers</button>
      <h2 class="layer-title">${activeLayer.title}</h2><p class="layer-era">${activeLayer.era}</p>${layerDetail(activeLayer)}`;
    panel.querySelector('.back').onclick = () => setLayer(null);
    panel.querySelectorAll('.story').forEach(b => b.onclick = () => {
      const n = activeLayer.notes[b.dataset.bag];
      collapsePanelOnPhone();
      flyTo(n.at[0], n.at[1], () => {
        const gid = gidOf(b.dataset.bag);
        if (gid >= 0) pinCard(gid, innerWidth * 0.62, innerHeight * 0.18);
      });
    });
    panel.querySelectorAll('.swatch').forEach(b => b.onclick = () => {
      groupOn[b.dataset.bit] = groupOn[b.dataset.bit] === false;
      setLayer(activeLayer);
    });
  }
}

function layerDetail(L) {
  const groups = L.groups.length > 1 ? `<div class="swatches">${L.groups.map((g, i) => `
    <button class="swatch" data-bit="${g.bit}" aria-pressed="${groupOn[g.bit] !== false}">
      <i style="background:${GROUP_COLORS[i]}"></i><span>${g.label}</span><span class="n">${fmt(g.count)}</span>
    </button>`).join('')}</div>` : '';
  const named = Object.entries(L.notes || {}).filter(([, n]) => n.name && n.at);
  const stories = named.length ? `<h2 class="section">Buildings and their stories</h2><ul class="stories">${named.map(([bag, n]) => `
    <li><button class="story" data-bag="${bag}"><b>${esc(n.name)}</b><span>${esc(n.story)}</span></button></li>`).join('')}</ul>` : '';
  return `<div class="layer-detail"><p>${L.text}</p>${groups}${stories}
    ${L.caveat ? `<p class="caveat">${L.caveat}</p>` : ''}
    <a href="${L.source.url}" target="_blank" rel="noopener">${L.source.label}</a></div>`;
}

function setLayer(L) {
  activeLayer = L;
  const bits = Array(MAX_GROUPS).fill(-1);
  if (L) L.groups.forEach((g, i) => { if (i < MAX_GROUPS && groupOn[g.bit] !== false) bits[i] = g.bit; });
  uniforms.uGroupBit.value = bits;
  renderPanel(); drawHist();
}

document.querySelectorAll('.modes button').forEach(b => b.onclick = () => {
  uniforms.uMode.value = +b.dataset.mode;
  document.querySelectorAll('.modes button').forEach(x => x.setAttribute('aria-pressed', x === b));
  const bits = Array(MAX_GROUPS).fill(-1);
  if (uniforms.uMode.value === MODE.residents && residentsLayer) bits[0] = residentsLayer.groups[0].bit;
  else if (activeLayer) activeLayer.groups.forEach((g, i) => { if (groupOn[g.bit] !== false) bits[i] = g.bit; });
  uniforms.uGroupBit.value = bits;
  if (!phone.matches) setCollapsed(false);
  renderPanel(); drawHist();
});

// ---------- Timeline ----------
const hist = document.getElementById('hist');
const hctx = hist.getContext('2d');
const T0 = Math.floor(config.yearMin / 50) * 50, T1 = config.yearMax + 1;
const years = Object.entries(config.histogram).map(([y, v]) => [+y, v]);
const yMax = Math.max(...years.map(([, v]) => v.reduce((a, b) => a + b, 0)));
const xOf = y => (y - T0) / (T1 - T0) * hist.clientWidth;
const yearOf = x => Math.round(T0 + x / hist.clientWidth * (T1 - T0));

function layerGroupsShown() {
  if (uniforms.uMode.value === MODE.residents && residentsLayer) return [{ ...residentsLayer.groups[0], color: GROUP_COLORS[0] }];
  if (uniforms.uMode.value !== MODE.layers || !activeLayer) return [];
  return activeLayer.groups.map((g, i) => ({ ...g, color: GROUP_COLORS[i] })).filter(g => groupOn[g.bit] !== false);
}

function visibleCount() {
  const Y = uniforms.uYear.value;
  const shown = layerGroupsShown();
  if (shown.length) return shown.reduce((n, g) => n + Object.entries(g.years).reduce((m, [y, c]) => m + (+y <= Y ? c : 0), 0), 0);
  let n = 0;
  for (const [y, v] of years) if (y <= Y) v.forEach((c, i) => { if (uniforms.uMode.value !== MODE.period || uniforms.uMask.value[i]) n += c; });
  return n;
}

function drawHist() {
  const w = hist.clientWidth, h = hist.clientHeight, dpr = devicePixelRatio;
  hist.width = w * dpr; hist.height = h * dpr;
  hctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  hctx.clearRect(0, 0, w, h);
  const plotH = h - 20, bw = Math.max(1, w / (T1 - T0));
  const Y = uniforms.uYear.value, Yf = uniforms.uYearFrom.value;
  const shown = layerGroupsShown();
  const bar = (y, bh, top, color, on) => {
    hctx.fillStyle = color;
    hctx.globalAlpha = on ? (y <= Yf ? 0.3 : 1) : 0.18;
    hctx.fillRect(xOf(y), top - bh, bw, bh);
  };
  if (shown.length) {
    // Layer mode: the city in grey behind, the layer's own buildings in its colours.
    for (const [y, v] of years) {
      const bh = Math.sqrt(v.reduce((a, b) => a + b, 0) / yMax) * (plotH - 6);
      bar(y, bh, plotH, '#b9c0c4', false);
    }
    // Stack the groups per year; the stack's total height follows sqrt(total), split in proportion.
    const total = {};
    for (const g of shown) for (const [y, c] of Object.entries(g.years)) total[y] = (total[y] || 0) + c;
    const lMax = Math.max(1, ...Object.values(total));
    const stack = {};
    for (const g of shown) for (const [ys, c] of Object.entries(g.years)) {
      const y = +ys, full = Math.sqrt(total[ys] / lMax) * (plotH - 6) * 0.9, bh = full * c / total[ys];
      bar(y, bh, plotH - (stack[y] || 0), g.color, y <= Y);
      stack[y] = (stack[y] || 0) + bh;
    }
  } else {
    for (const [y, v] of years) {
      let top = plotH;
      v.forEach((c, i) => {
        if (!c) return;
        const bh = Math.sqrt(c / yMax) * (plotH - 6);
        const masked = uniforms.uMode.value === MODE.period && !uniforms.uMask.value[i];
        bar(y, bh, top, periods[i].color, !masked && y <= Y);
        top -= bh;
      });
    }
  }
  hctx.globalAlpha = 1;
  hctx.fillStyle = '#5d6266';
  hctx.font = '500 11px "Schibsted Grotesk", sans-serif';
  const step = w < 500 ? 200 : 100;
  for (let y = Math.ceil(T0 / step) * step; y <= T1; y += step) hctx.fillText(y, Math.min(w - 28, Math.max(0, xOf(y) - 13)), h - 4);
  hctx.fillStyle = '#000';
  hctx.fillRect(xOf(Y) - 1, 0, 2, plotH);
  if (Yf >= T0) { hctx.fillStyle = '#5d6266'; hctx.fillRect(xOf(Yf) - 0.5, 0, 1, plotH); }
  document.getElementById('year').textContent = Y;
  document.getElementById('count').textContent = fmt(visibleCount());
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

// Play: quickly through the sparse centuries, then slowly through the dense ones.
let playing = false, playT0 = 0, playStart = 0;
const playBtn = document.getElementById('play');
const playIcon = document.getElementById('play-icon');
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
  playIcon.setAttribute('d', 'M4 2.5h3v11H4zM9 2.5h3v11H9z');
  playBtn.setAttribute('aria-label', 'Pause');
}
function stopPlay() {
  playing = false;
  playIcon.setAttribute('d', 'M4 2.5v11l9-5.5z');
  playBtn.setAttribute('aria-label', "Play the city's growth");
}
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
renderPanel();
resize();
document.fonts?.ready.then(drawHist);

let frame = 0;
renderer.setAnimationLoop(now => {
  frame++;
  stepFlight(now);
  controls.update();
  const dist = camera.position.distanceTo(controls.target);
  uniforms.uFog.value.set(dist * 1.6, dist * 4);
  if (frame % 6 === 0) updateLabels(dist);
  if (playing) {
    const t = Math.min(1, playT0 + (now - playStart) / DURATION);
    uniforms.uYear.value = Math.round(playYear(t));
    if (t >= 1) stopPlay();
    drawHist();
  }
  if (pointer && !dragging && frame % 3 === 0) {
    const gid = pick(pointer[0], pointer[1]);
    uniforms.uHover.value = gid;
    showCard(gid, pointer[0], pointer[1]);
  }
  renderer.render(scene, camera);
});

window.__dbg = { pick, uniforms, camera, controls, setLayer, layers, pinCard, showCard, building, labelGroup, labels };
