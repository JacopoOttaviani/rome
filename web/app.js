import * as THREE from './vendor/three.module.js';
import { MapControls } from './vendor/MapControls.js';

// Colours are authored in sRGB and drawn as they are.
THREE.ColorManagement.enabled = false;

// Light and dark: the model, its ground and its labels. Building colours stay the same in both.
const THEMES = {
  light: { sky: '#e4e8ea', land: '#f4f3ef', water: '#b5c7c6', maquette: '#efeee9', minor: null, green: '#c9dab3', found: '#ec0000',
    street: ['#50565b', 'rgba(244,243,239,0.85)'], river: ['#3c6875', 'rgba(181,199,198,0.85)'],
    histText: '#5d6266', histMark: '#000000', histGrey: '#b9c0c4', contour: '#8c8270' },
  dark: { sky: '#121417', land: '#1a1d21', water: '#1d3439', maquette: '#2c3034', minor: '#4d5359', green: '#223528', found: '#ff4b3e',
    street: ['#b3b9bd', 'rgba(26,29,33,0.85)'], river: ['#8ab6bf', 'rgba(29,52,57,0.85)'],
    histText: '#9aa1a6', histMark: '#f2f2ef', histGrey: '#3a3f44', contour: '#59616a' },
};
// The reader's choice (data-theme, set before the first paint from localStorage), else the system's.
const darkQuery = matchMedia('(prefers-color-scheme: dark)');
const themeName = () => document.documentElement.dataset.theme || (darkQuery.matches ? 'dark' : 'light');
let TH = THEMES[themeName()];
const GROUP_COLORS = ['#ec0000', '#1f4e8c', '#d99a12', '#2e8b57', '#7b3fa0', '#00909a', '#8c5a2b', '#d6336c'];
const MAX_GROUPS = GROUP_COLORS.length;
const ATTR_W = 256;
const WORKERS = Math.min(4, navigator.hardwareConcurrency || 2);
const MODE = { period: 0, use: 2, layers: 3 }; // 1 was storeys, removed: height ÷ 3.2 m misread Rome's tall floors
// Date flags (pipeline/s02_attributes.py). Approximate ones are drawn paler.
const FLAG = { wikidata: 0, wikidataApprox: 1, census: 2, censusOld: 3, estimated: 4, undated: 5, construction: 6, ispra: 7, ispraNew: 8, byHand: 9 };

const [config, layers, attrBuf] = await Promise.all([
  fetch('data/rome.json').then(r => r.json()),
  fetch('data/layers.json').then(r => r.json()),
  fetch('data/attrs.bin').then(r => r.arrayBuffer()),
]);
const attrs = new DataView(attrBuf);

// ---------- Language ----------
// English and Italian. Data carries `<field>_it` next to each English text; the interface strings are below.
const IT_UI = {
  'About': 'Info', 'Photo': 'Foto', 'Source': 'Fonte', 'Close': 'Chiudi',
  'Period': 'Epoca', 'Context layers': 'Contesti', 'Use': 'Uso',
  'buildings': 'edifici', 'Building the city': 'Costruendo la città', 'All roads lead to Rome.': 'Tutte le strade portano a Roma.',
  'Drag to turn. Right-drag or Shift-drag to move. Scroll to zoom.': 'Trascina per ruotare. Trascina col tasto destro o con Shift per spostarti. Scorri per lo zoom.',
  'Show legend': 'Mostra legenda', 'Hide legend': 'Nascondi legenda',
  'Built in': 'Costruito', 'Click a period to see it alone. Faded buildings have an estimated date.': 'Clicca su un’epoca per vederla da sola. Gli edifici sbiaditi hanno una data stimata.',
  'Made with 💙 by': 'Fatto con 💙 da', 'North up': 'Nord in alto', 'Spin the city': 'Fai girare la città', 'Stop spinning': 'Ferma la rotazione', 'Buy me a coffee': 'Offrimi un caffè', 'Dark mode': 'Tema scuro', 'Light mode': 'Tema chiaro',
  'All context layers': 'Tutti i contesti', 'Buildings and their stories': 'Gli edifici e le loro storie',
  'Height': 'Altezza', 'Architect': 'Architetto', 'Architects': 'Architetti', 'Style': 'Stile',
  'In layers': 'Nei contesti', 'Dating': 'Datazione', 'Read more': 'Per saperne di più',
  'Wikipedia': 'Wikipedia', 'Italian Wikipedia': 'Wikipedia in italiano', 'Wikidata': 'Wikidata', 'On OpenStreetMap': 'Su OpenStreetMap',
  'Click for the story and sources': 'Clicca per la storia e le fonti', 'Click to keep this card open': 'Clicca per tenere aperta la scheda',
  'Play the city\'s growth': 'Guarda crescere la città', 'Pause': 'Pausa',
  'before 1919': 'prima del 1919', 'date unknown': 'data ignota', 'under construction in': 'in costruzione nel', 'BC': 'a.C.',
  'Height not surveyed; drawn at a default height.': 'Altezza non rilevata; disegnato a un’altezza convenzionale.',
  'Height from Wikidata; the survey drew the footprint only.': 'Altezza da Wikidata; il rilievo ne ha disegnato solo la pianta.',
  'Height from OpenStreetMap (its height or storeys): the building is newer than the survey.':
    'Altezza da OpenStreetMap (altezza o piani indicati): l’edificio è più recente del rilievo.',
  'Height not known: the building is newer than the survey, and is drawn at the median height of its neighbours.':
    'Altezza non nota: l’edificio è più recente del rilievo ed è disegnato all’altezza mediana dei vicini.',
  'What each building is used for, as the 2014 regional survey records it; for newer buildings, as OpenStreetMap does.':
    'L’uso di ogni edificio come lo registra il rilievo regionale del 2014; per gli edifici più recenti, come lo registra OpenStreetMap.',
  'Since 2001': 'Dal 2001',
  'Regione Lazio, geotopographic database 2014': 'Regione Lazio, database geotopografico 2014',
  // periods
  'Antiquity, before 500': 'Antichità, prima del 500', '500–1419 Middle Ages': '500–1419 Medioevo',
  '1420–1599 Renaissance': '1420–1599 Rinascimento', '1600–1750 Baroque': '1600–1750 Barocco',
  '1751–1870 Papal Rome': '1751–1870 Roma papale', 'Before 1919 or undated': 'Prima del 1919 o senza data',
  '1871–1918 Capital of Italy': '1871–1918 Roma capitale', '1919–1945 Between the wars': '1919–1945 Tra le due guerre',
  '1946–1960 Reconstruction': '1946–1960 Ricostruzione', '1961–1970 The boom': '1961–1970 Il boom',
  // uses
  'Not recorded': 'Non registrato', 'Homes': 'Abitazioni', 'Government and embassies': 'Amministrazione e ambasciate',
  'Schools and universities': 'Scuole e università', 'Hospitals and care': 'Ospedali e assistenza',
  'Other public services': 'Altri servizi pubblici', 'Military': 'Militare', 'Churches and convents': 'Chiese e conventi',
  'Stations and transport': 'Stazioni e trasporti', 'Shops and markets': 'Negozi e mercati',
  'Industry and utilities': 'Industria e impianti', 'Farms': 'Agricoltura', 'Culture and sport': 'Cultura e sport',
  'Hotels': 'Alberghi', 'Sheds and minor buildings': 'Edifici minori', 'Monuments and fountains': 'Monumenti e fontane',
  // how each date was found
  'Year from Wikidata, from the building’s own item. For a church this can be the founding of the first church on the site; for a building still being built at the 2014 survey, its opening.':
    'Anno da Wikidata, dall’elemento dell’edificio stesso. Per una chiesa può essere la fondazione della prima chiesa sul luogo; per un edificio ancora in costruzione al rilievo del 2014, la sua apertura.',
  'Wikidata dates the building to a decade or a century only; the map places it within that span.':
    'Wikidata data l’edificio solo a un decennio o a un secolo; la mappa lo colloca in quell’intervallo.',
  'Period from the 2011 census, which counts the residential buildings of each section by when they were built. This section’s buildings were given those periods in the same proportions; which building got which is an estimate.':
    'Epoca dal censimento 2011, che conta gli edifici residenziali di ogni sezione per epoca di costruzione. Agli edifici di questa sezione sono state assegnate quelle epoche nelle stesse proporzioni; quale edificio abbia avuto quale è una stima.',
  'Built before 1919, according to the 2011 census; no source gives a closer date. It could be Roman, medieval or of 1910. The map shows it from 1870.':
    'Costruito prima del 1919, secondo il censimento 2011; nessuna fonte dà una data più precisa. Potrebbe essere romano, medievale o del 1910. La mappa lo mostra dal 1870.',
  'No source dates this building on its own: the census counts only homes, section by section, and gives no period for this one. Estimated from the nearest dated buildings.':
    'Nessuna fonte data questo edificio: il censimento conta solo le abitazioni, sezione per sezione, e non gli assegna un’epoca. Stimato dagli edifici datati più vicini.',
  'A ruin, monument or fountain no source dates. The map shows it from 1870.':
    'Un rudere, un monumento o una fontana che nessuna fonte data. La mappa lo mostra dal 1870.',
  'Under construction when the region surveyed it in {year}. ISPRA’s land maps up to 2021 cannot say when it was finished: they show no finished building on this footprint, or one already stood here before the works.':
    'In costruzione quando la Regione lo ha rilevato nel {year}. Le mappe del suolo dell’ISPRA fino al 2021 non dicono quando sia stato finito: su questa pianta non mostrano un edificio finito, oppure ce n’era già uno prima dei lavori.',
  'Under construction when the region surveyed it. The years are the window in which ISPRA’s land maps first show a finished building here: from the survey, or the map before, to the first map that shows it. That is when the structure is visible from above, often a year or two before it opens.':
    'In costruzione quando la Regione lo ha rilevato. Gli anni sono l’intervallo in cui le mappe del suolo dell’ISPRA mostrano per la prima volta un edificio finito: dal rilievo, o dalla mappa precedente, alla prima mappa che lo mostra. È quando la struttura si vede dall’alto, spesso un anno o due prima dell’apertura.',
  'Newer than the region’s 2014 survey: the footprint is from OpenStreetMap. The year is when ISPRA’s land maps first show a building here, a window where the maps skip years (there are none for 2013–14). That is when the structure is visible from above, often a year or two before it opens.':
    'Più recente del rilievo regionale del 2014: la pianta è di OpenStreetMap. L’anno è quello in cui le mappe del suolo dell’ISPRA mostrano per la prima volta un edificio qui, un intervallo dove le mappe saltano degli anni (non ce ne sono per il 2013–14). È quando la struttura si vede dall’alto, spesso un anno o due prima dell’apertura.',
  'Dated by hand: no source the map reads dates this building rightly, so its years come from its history (Wikipedia): when its present building was begun and when it was finished. The map shows it from the year it was finished.':
    'Datato a mano: nessuna fonte letta dalla mappa data correttamente questo edificio, quindi gli anni vengono dalla sua storia (Wikipedia): quando l’edificio attuale fu iniziato e quando fu finito. La mappa lo mostra dall’anno in cui fu finito.',
  'Follow me on LinkedIn': 'Seguimi su LinkedIn',
  'Hills': 'Colli', 'Show the hills': 'Mostra i colli', 'Flatten the city': 'Torna in piano',
  'Street or CAP': 'Via o CAP', 'Find a street or a postcode (CAP)': 'Cerca una via o un CAP', 'Streets': 'Strade',
  'Not a postcode in Rome': 'Non è un CAP di Roma', 'No street by that name in Rome': 'Nessuna strada con questo nome a Roma',
  'Green': 'Verde', 'Show the green areas': 'Mostra le aree verdi', 'Hide the green areas': 'Nascondi le aree verdi',
};
let LANG = (() => {
  const q = new URLSearchParams(location.search).get('lang');
  if (q === 'it' || q === 'en') return q;
  try { const s = localStorage.getItem('lang'); if (s === 'it' || s === 'en') return s; } catch {}
  return navigator.language?.startsWith('it') ? 'it' : 'en';
})();
const t = s => (LANG === 'it' && IT_UI[s]) || s;
const tr = (o, k) => (LANG === 'it' && o?.[k + '_it']) || o?.[k];
const fmtLocale = () => LANG === 'it' ? 'it-IT' : 'en';
const fmtYear = y => y < 0 ? `${-y} ${t('BC')}` : String(y);
const periods = config.periods;

// ---------- Scene ----------
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setClearColor(TH.sky);
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

// Land, water and the green areas: flat polygons in the local frame (see pipeline/s04_water.py). Each is triangulated
// straight into one buffer, wound as ShapeGeometry would (outline clockwise, holes not, seen from above):
// ShapeGeometry itself takes seconds over the green areas' hundred thousand pieces.
async function loadPolygons(url) {
  const buf = await (await fetch(url)).arrayBuffer();
  const [nPoly, nRing, nVert] = new Uint32Array(buf, 0, 3);
  const ringStart = new Uint32Array(buf, 12, nPoly + 1);
  const vertStart = new Uint32Array(buf, 12 + 4 * (nPoly + 1), nRing + 1);
  const xz = new Float32Array(buf, 12 + 4 * (nPoly + 1) + 4 * (nRing + 1), 2 * nVert);
  const pos = new Float32Array(3 * nVert), index = [];
  for (let v = 0; v < nVert; v++) { pos[3 * v] = xz[2 * v]; pos[3 * v + 2] = xz[2 * v + 1]; }
  // A ring as the shape's points (x, -z) and the vertices they are, turned clockwise or not.
  const ring = (r, clockwise) => {
    const pts = [], ids = [];
    for (let v = vertStart[r]; v < vertStart[r + 1]; v++) { pts.push(new THREE.Vector2(xz[2 * v], -xz[2 * v + 1])); ids.push(v); }
    if (THREE.ShapeUtils.isClockWise(pts) !== clockwise) { pts.reverse(); ids.reverse(); }
    return [pts, ids];
  };
  for (let p = 0; p < nPoly; p++) {
    const [outer, ids] = ring(ringStart[p], true), holes = [];
    for (let r = ringStart[p] + 1; r < ringStart[p + 1]; r++) {
      const [pts, hids] = ring(r, false);
      holes.push(pts); ids.push(...hids);
    }
    for (const f of THREE.ShapeUtils.triangulateShape(outer, holes)) index.push(ids[f[0]], ids[f[1]], ids[f[2]]);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setIndex(new THREE.BufferAttribute(new Uint32Array(index), 1));
  return g;
}
const flat = new THREE.Group();
scene.add(flat);
const [landGeo, waterGeo] = await Promise.all([loadPolygons('data/land.bin'), loadPolygons('data/water.bin')]);
const land = new THREE.Mesh(landGeo, new THREE.MeshBasicMaterial({ color: TH.land }));
const water = new THREE.Mesh(waterGeo, new THREE.MeshBasicMaterial({ color: TH.water }));
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
  const [ink, halo] = L.water ? TH.river : TH.street;
  ctx.strokeStyle = halo;
  ctx.fillStyle = ink;
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
      l.mesh.position.set(l.x, labelY(l), l.z);
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
// Use colours, with the unrecorded and the minor buildings toned down to the model's own grey at night.
function useColors() {
  return config.uses.colors.map((c, i) => config.uses.keys[i] === 'none' ? TH.maquette
    : config.uses.keys[i] === 'minor' && TH.minor ? TH.minor : c);
}
const col = c => new THREE.Color(c);
const uniforms = {
  uYear: { value: config.yearMax },
  uYearFrom: { value: config.yearMin - 1 },
  uMode: { value: MODE.period },
  uPalette: { value: periods.map(p => col(p.color)) },
  uMask: { value: periods.map(() => 1) },
  uNow: { value: 0 },                              // seconds, for tiles dropping in as they load
  uPlaying: { value: 0 },                          // while the film plays buildings fly in rather than grow
  uRise: { value: 0.01 },
  uLayerAt: { value: -10 },                        // seconds; when a context layer opened, its buildings rise                          // years a building's entrance spans; only the film widens it
  uGroupBit: { value: Array(MAX_GROUPS).fill(-1) },
  uGroupColor: { value: GROUP_COLORS.map(col) },
  uMaquette: { value: col(TH.maquette) },
  uUse: { value: useColors().map(col) },
  uHover: { value: -1 },
  uSelected: { value: -1 },
  uFogColor: { value: col(TH.sky) },
  uFog: { value: new THREE.Vector2(9000, 26000) },
  uTerrain: { value: 0 },                          // 0 flat, 1 on the hills (see Hills)
  uGround: { value: new THREE.DataTexture(new Float32Array(1), 1, 1, THREE.RedFormat, THREE.FloatType) },
};

const VERT = /* glsl */`
  in float bld;
  uniform sampler2D uAttr;
  uniform float uYear, uYearFrom, uMode, uHover, uSelected, uNow, uBorn, uPlaying, uRise, uLayerAt, uTerrain;
  uniform sampler2D uGround;
  uniform vec3 uPalette[${periods.length}];
  uniform float uMask[${periods.length}];
  uniform int uGroupBit[${MAX_GROUPS}];
  uniform vec3 uGroupColor[${MAX_GROUPS}];
  uniform vec3 uMaquette;
  uniform vec3 uUse[${config.uses.colors.length}];
  out vec3 vColor;
  out vec3 vWorld;
  out float vGid;
  out float vLift;


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
    float vis = uMode < 0.5 ? uMask[period] : 1.0;
    float g = clamp((uYear - year + 1.0) / uRise, 0.0, 1.0);
    g = g * g * (3.0 - 2.0 * g);
    if (g <= 0.003 || vis <= 0.003) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }

    // Entrances, only while the film plays and while tiles load: a building drops in from its own side of the
    // sky, the same side every time (seeded by its id). Filters and scrubbing change the city at once.
    vec3 p = position;
    float seed = fract(sin(a.w * 12.9898) * 43758.5453);
    float arrive = clamp((uNow - uBorn) / 0.9 - seed * 0.35, 0.0, 1.0);
    float fly = 1.0 - arrive;
    if (uPlaying > 0.5) fly = max(fly, 1.0 - g);
    if (fly > 0.0) {
      float e = fly * fly * fly;
      float ang = seed * 6.2831853;
      // positions are in decimetres: a few hundred metres sideways and up
      p += vec3(cos(ang), 0.0, sin(ang)) * (1800.0 + 1600.0 * fract(seed * 7.13)) * e;
      p.y += (2600.0 + 2400.0 * fract(seed * 3.71)) * e;
    }
    vec3 c;
    if (uMode < 0.5) {
      c = uPalette[period];
      if (flag == 1 || flag == 4 || flag == 5) c = mix(c, uMaquette, 0.45); // approximate dates, paler
    } else if (uMode < 2.5) {
      c = uUse[int(a.z / 128.0)];
    } else {
      c = uMaquette;
      for (int g = 0; g < ${MAX_GROUPS}; g++) {
        if (uGroupBit[g] >= 0 && hasBit(lay, uGroupBit[g])) {
          c = uGroupColor[g];
          // Opening a layer: its buildings rise out of the ground in a quick wave, overshoot a little, settle.
          float k = clamp((uNow - uLayerAt) / 0.55 - seed * 0.6, 0.0, 1.0);
          float q = k - 1.0;
          p.y *= 1.0 + 2.70158 * q * q * q + 1.70158 * q * q;
          break;
        }
      }
    }
    if (year <= uYearFrom) c = mix(c, uMaquette, 0.8);
    if (vGid == uHover || vGid == uSelected) c = mix(c, vec3(0.0), 0.35);
    vColor = c;
    // The hills view: a building stands on the ground at its centre, with a 4 m footing so it meets a slope.
    // Positions are in decimetres; the ground texture holds metres, already exaggerated (see Hills).
    vLift = 0.0;
    if (uTerrain > 0.0) {
      int gi = int(a.w + 0.5);
      vLift = uTerrain * texelFetch(uGround, ivec2(gi % 1024, gi / 1024), 0).r;
      p.y += vLift * 10.0 - (position.y < 0.5 ? 40.0 * uTerrain : 0.0);
    }
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
  in float vLift;
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
      float foot = mix(0.82, 1.0, clamp((vWorld.y - vLift) / 12.0, 0.0, 1.0)); // darker at the foot, wherever the ground is
      vec3 c = vColor * light * foot;
      float d = length(vWorld - cameraPosition);
      c = mix(c, uFogColor, smoothstep(uFog.x, uFog.y, d));
      outColor = vec4(c, 1.0);
    #endif
  }
`;

function makeMaterial(tex, pick, born) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: { ...uniforms, uAttr: { value: tex }, uBorn: born },
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
  const born = { value: performance.now() / 1000 };
  const mesh = new THREE.Mesh(g, makeMaterial(tex, false, born));
  mesh.userData = { draw: mesh.material, pick: makeMaterial(tex, true, born) };
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
  renderer.setClearColor(TH.sky, 1);
  flat.visible = true;
  labelGroup.visible = true;
  for (const m of meshes) m.material = m.userData.draw;
  camera.clearViewOffset();
  return pickPixel[0] + pickPixel[1] * 256 + pickPixel[2] * 65536 - 1;
}

// ---------- Building lookup ----------
// How each building's date was found, by date flag.
const DATE_NOTE = [
  'Year from Wikidata, from the building’s own item. For a church this can be the founding of the first church on the site; for a building still being built at the 2014 survey, its opening.',
  'Wikidata dates the building to a decade or a century only; the map places it within that span.',
  'Period from the 2011 census, which counts the residential buildings of each section by when they were built. This section’s buildings were given those periods in the same proportions; which building got which is an estimate.',
  'Built before 1919, according to the 2011 census; no source gives a closer date. It could be Roman, medieval or of 1910. The map shows it from 1870.',
  'No source dates this building on its own: the census counts only homes, section by section, and gives no period for this one. Estimated from the nearest dated buildings.',
  'A ruin, monument or fountain no source dates. The map shows it from 1870.',
  'Under construction when the region surveyed it in {year}. ISPRA’s land maps up to 2021 cannot say when it was finished: they show no finished building on this footprint, or one already stood here before the works.',
  'Under construction when the region surveyed it. The years are the window in which ISPRA’s land maps first show a finished building here: from the survey, or the map before, to the first map that shows it. That is when the structure is visible from above, often a year or two before it opens.',
  'Newer than the region’s 2014 survey: the footprint is from OpenStreetMap. The year is when ISPRA’s land maps first show a building here, a window where the maps skip years (there are none for 2013–14). That is when the structure is visible from above, often a year or two before it opens.',
  'Dated by hand: no source the map reads dates this building rightly, so its years come from its history (Wikipedia): when its present building was begun and when it was finished. The map shows it from the year it was finished.',
];
const contextLayers = layers;
const groupsByBit = layers.flatMap(L => L.groups.map(g => ({ ...g, layer: L })));

// attrs.bin, one record per building (pipeline/s03_tiles.py).
function building(gid) {
  const o = gid * config.attrStride;
  const lay0 = attrs.getUint32(o + 20, true), lay1 = attrs.getUint32(o + 24, true);
  return {
    gid,
    id: String(attrs.getFloat64(o, true)),
    height: attrs.getUint16(o + 8, true) / 10,
    flag: attrs.getUint8(o + 11),
    year: attrs.getInt16(o + 12, true),
    y0: attrs.getInt16(o + 14, true),
    y1: attrs.getInt16(o + 16, true),
    use: attrs.getUint8(o + 18),
    period: attrs.getUint8(o + 19),
    wk: attrs.getInt32(o + 28, true),
    x: attrs.getFloat32(o + 32, true),
    z: attrs.getFloat32(o + 36, true),
    hsrc: attrs.getUint8(o + 40),
    groups: groupsByBit.filter(g => g.bit < 32 ? (lay0 >>> g.bit) & 1 : (lay1 >>> (g.bit - 32)) & 1),
  };
}

// The date as the card shows it: a year, the span a source gives, or what is known when no year is.
const OLD = periods.findIndex(p => p.key === 'old');
function whenOf(b) {
  if (b.flag === FLAG.censusOld || (b.flag === FLAG.estimated && b.period === OLD)) return t('before 1919');
  if (b.flag === FLAG.undated) return t('date unknown');
  if (b.flag === FLAG.construction) return `${t('under construction in')} ${b.year}`;
  if (b.flag === FLAG.estimated) return `c. ${fmtYear(b.year)}`;
  if (b.y0 !== b.y1) return `${fmtYear(b.y0)}–${fmtYear(b.y1)}`;
  return fmtYear(b.year);
}

// ---------- Building card ----------
// Hover shows a light card that follows the pointer; a click pins it, with the article extract and links.
let wiki = [];
fetch('data/wiki.json').then(r => r.json()).then(w => { wiki = w; });
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const link = (href, text) => `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(text)}</a>`;

// Local metres → ETRS89 / UTM 33N → WGS84 (inverse transverse Mercator, GRS80; well under a metre here).
function toLatLon(x, z) {
  const E = x + config.origin[0] - 500000, N = config.origin[1] - z;
  const a = 6378137, f = 1 / 298.257222101, k0 = 0.9996, e2 = f * (2 - f), ep2 = e2 / (1 - e2);
  const mu = N / k0 / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256));
  const e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));
  const p = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * Math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * Math.sin(4 * mu)
    + (151 * e1 ** 3 / 96) * Math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * Math.sin(8 * mu);
  const s = Math.sin(p), c = Math.cos(p), T = Math.tan(p) ** 2, C = ep2 * c * c;
  const Nn = a / Math.sqrt(1 - e2 * s * s), R = a * (1 - e2) / (1 - e2 * s * s) ** 1.5, D = E / (Nn * k0);
  const lat = p - (Nn * Math.tan(p) / R) * (D ** 2 / 2 - (5 + 3 * T + 10 * C - 4 * C * C - 9 * ep2) * D ** 4 / 24
    + (61 + 90 * T + 298 * C + 45 * T * T - 252 * ep2 - 3 * C * C) * D ** 6 / 720);
  const lon = (D - (1 + 2 * T + C) * D ** 3 / 6 + (5 - 2 * C + 28 * T - 3 * C * C + 8 * ep2 + 24 * T * T) * D ** 5 / 120) / c;
  return [lat * 180 / Math.PI, 15 + lon * 180 / Math.PI]; // zone 33: central meridian 15° E
}

// The article in the reader's language when there is one.
const wikiOf = w => (LANG === 'it' && w?.wiki_it?.extract ? w.wiki_it : w?.wiki) || w?.wiki_it;

function groupColor(g) {
  return GROUP_COLORS[g.layer.groups.findIndex(x => x.bit === g.bit)] || GROUP_COLORS[0];
}

function photoHtml(im, credit) {
  if (!im?.thumb) return '';
  return `<figure class="photo"><div class="frame"><img src="${esc(im.thumb)}" alt=""></div>
    <figcaption>${t('Photo')}: ${credit}</figcaption></figure>`;
}
function wirePhoto(x, y) {
  const img = card.querySelector('.photo img');
  if (!img) return;
  img.addEventListener('error', () => img.closest('.photo').remove());
  img.addEventListener('load', () => placeCard(...(pointer || [x, y])));
}

// The card reads top to bottom: photo, name and date; what the building is; the layers it belongs to and why;
// the facts; how its date was found; where to read more.
function cardHtml(gid, pinned) {
  const b = building(gid);
  const w = b.wk >= 0 ? wiki[b.wk] : null;
  const im = w?.image?.thumb ? w.image : null;
  const period = periods[b.period] || periods[0];
  const heightNote = b.hsrc === 2 ? t('Height not surveyed; drawn at a default height.')
    : b.hsrc === 1 ? t('Height from Wikidata; the survey drew the footprint only.')
    : b.hsrc === 3 ? t('Height from OpenStreetMap (its height or storeys): the building is newer than the survey.')
    : b.hsrc === 4 ? t('Height not known: the building is newer than the survey, and is drawn at the median height of its neighbours.') : '';
  const facts = [
    [t('Height'), `${b.height.toFixed(1)} m${heightNote ? `<br><span class="why">${heightNote}</span>` : ''}`],
    b.use && [t('Use'), esc(t(config.uses.labels[b.use]))],
    w?.architects?.length && [t(w.architects.length > 1 ? 'Architects' : 'Architect'), w.architects.map(esc).join(', ')],
    w?.styles?.length && [t('Style'), w.styles.map(esc).join(', ')],
  ].filter(Boolean);
  const credit = im && (pinned
    ? `${link(im.page || im.thumb, im.artist || 'Wikimedia Commons')}${im.license ? `, ${im.licenseUrl ? link(im.licenseUrl, im.license) : esc(im.license)}` : ''}`
    : `${esc(im.artist || 'Wikimedia Commons')}${im.license ? `, ${esc(im.license)}` : ''}`);
  const [lat, lon] = toLatLon(b.x, b.z);
  const article = wikiOf(w);
  const sources = [
    article?.url && link(article.url, t(article.lang === 'it' ? 'Italian Wikipedia' : 'Wikipedia')),
    w?.qid && link(`https://www.wikidata.org/wiki/${w.qid}`, t('Wikidata')),
    link(`https://www.openstreetmap.org/?mlat=${lat.toFixed(6)}&mlon=${lon.toFixed(6)}#map=19/${lat.toFixed(6)}/${lon.toFixed(6)}`, t('On OpenStreetMap')),
  ].filter(Boolean);
  const inLayers = b.groups.map(g => {
    const note = g.layer.notes?.[b.id];
    const story = note && tr(note, 'story');
    return `<li><i style="background:${groupColor(g)}"></i><div><b>${esc(tr(g.layer, 'title'))}</b> <span>${esc(tr(g, 'label'))}</span>
      ${pinned && (story || note?.source) ? `<p>${esc(story || '')}${note.source ? ` ${link(note.source, t('Source'))}` : ''}</p>` : ''}</div></li>`;
  }).join('');
  const name = w && tr(w, 'label');
  return `
    ${pinned ? `<button class="card-close" aria-label="${t('Close')}">×</button>` : ''}
    ${photoHtml(im, credit)}
    <header class="card-head">
      ${name ? `<h3>${esc(name)}</h3>` : ''}
      <div class="when"><span class="y">${esc(whenOf(b))}</span>
        <span class="period"><i style="background:${period.color}"></i>${esc(t(period.label))}</span></div>
    </header>
    ${pinned && article?.extract ? `<section><p class="extract">${esc(article.extract)}</p></section>` : ''}
    ${inLayers ? `<section><h4>${t('In layers')}</h4><ul class="chips">${inLayers}</ul></section>` : ''}
    <section><dl>${facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl></section>
    <section><h4>${t('Dating')}</h4><p class="why">${t(DATE_NOTE[b.flag] || '').replace('{year}', b.year)}</p></section>
    ${pinned ? `<section class="sources"><h4>${t('Read more')}</h4><p>${sources.join(', ')}</p></section>`
      : `<p class="hint">${article || b.groups.some(g => g.layer.notes?.[b.id]) ? t('Click for the story and sources') : t('Click to keep this card open')}</p>`}`;
}

const card = document.getElementById('card');
let pinnedGid = -1;
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
    wirePhoto(x, y);
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
  card.hidden = false;
  card.querySelector('.card-close').onclick = () => pinCard(-1);
  wirePhoto(x, y);
  placeCard(x, y);
}
addEventListener('keydown', e => { if (e.key === 'Escape') pinCard(-1); });

// A click (not a drag) pins the building under the pointer, or clears the pin on empty ground.
let pointer = null, dragging = false, downAt = null;
canvas.addEventListener('pointermove', e => { pointer = [e.clientX, e.clientY]; });
canvas.addEventListener('pointerdown', e => {
  dragging = true; downAt = [e.clientX, e.clientY];
  spin = null; // a hand on the map stops the compass turning it
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
let idIndex = null;
function gidOf(id) {
  if (!idIndex) {
    idIndex = new Map();
    for (let g = 0; g < config.stats.buildings; g++) idIndex.set(String(attrs.getFloat64(g * config.attrStride, true)), g);
  }
  return idIndex.get(id) ?? -1;
}
let flight = null;
function flyTo(x, z, done, distance = 520) {
  turning = false;
  const dir = camera.position.clone().sub(controls.target).normalize();
  if (dir.y < 0.45) { dir.y = 0.45; dir.normalize(); }
  const target = new THREE.Vector3(x, 0, z);
  flight = { t0: performance.now(), dur: 1400, fromT: controls.target.clone(), toT: target,
    fromP: camera.position.clone(), toP: target.clone().add(dir.multiplyScalar(distance)), done };
}
// ---------- Compass ----------
// North on screen is the camera's azimuth (OrbitControls' theta: 0 with the camera due south, looking north).
// The card turns by it and tilts back with the camera, as if it lay on the ground.
const compassBtn = document.querySelector('.compass');
const compassSvg = compassBtn.querySelector('svg');
let compassKey = '', spin = null;
function updateCompass() {
  const north = THREE.MathUtils.radToDeg(controls.getAzimuthalAngle());
  const tilt = THREE.MathUtils.radToDeg(Math.min(controls.getPolarAngle(), 1.15)) * 0.8;
  const key = `${north.toFixed(1)} ${tilt.toFixed(1)}`;
  if (key === compassKey) return;
  compassKey = key;
  compassSvg.style.transform = `rotateX(${tilt.toFixed(1)}deg) rotate(${north.toFixed(1)}deg)`;
}
// A click turns the map back to north up, the short way round, keeping distance and tilt.
compassBtn.onclick = () => {
  turning = false;
  const from = controls.getAzimuthalAngle();
  if (Math.abs(from) > 0.002) spin = { t0: performance.now(), from, dur: 700 };
};
function stepSpin(now) {
  if (!spin) return;
  const k = Math.min(1, (now - spin.t0) / spin.dur), e = 1 - (1 - k) ** 3;
  const s = new THREE.Spherical().setFromVector3(camera.position.clone().sub(controls.target));
  s.theta = spin.from * (1 - e);
  camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(s));
  if (k >= 1) spin = null;
}

// ---------- Turning on its own ----------
// The city turns slowly, one turn every 90 s, while it loads and after, until the reader takes over:
// a drag, click or wheel on the map, a story in the panel or the compass. Colourings, the timeline and Play keep it turning.
// ?spin=0 keeps it still, and so does a reader who asks for reduced motion.
// Timed by the clock, not by frames, so it turns at the same speed at 60 Hz and 120 Hz.
const TURN = 2 * Math.PI / 90;
let turning = new URLSearchParams(location.search).get('spin') !== '0' && !matchMedia('(prefers-reduced-motion: reduce)').matches;
let turnT0 = -1, turnLast = 0;
controls.addEventListener('start', () => turning = false);
// The spin button, between About and the theme: it shows whether the city turns, and starts or stops it.
// Turning stops in several places (a drag, the compass, a story), so the button follows `turning` every frame.
const spinBtn = document.querySelector('.spin-toggle');
let spinShown = null;
function syncSpinBtn() {
  if (spinShown === turning) return;
  spinShown = turning;
  const label = t(turning ? 'Stop spinning' : 'Spin the city');
  spinBtn.setAttribute('aria-pressed', String(turning));
  spinBtn.setAttribute('aria-label', label); spinBtn.title = label;
}
spinBtn.onclick = () => {
  turning = !turning;
  if (turning) { turnT0 = -1; spin = null; } // starts again gently, and wins over a north-up turn under way
  syncSpinBtn();
};
function stepTurn(now) {
  syncSpinBtn();
  if (!turning) return;
  if (turnT0 < 0) turnT0 = turnLast = now;
  const dt = Math.min(0.1, (now - turnLast) / 1000), k = Math.min(1, (now - turnT0) / 3000); // full speed after 3 s
  turnLast = now;
  const a = TURN * k * k * (3 - 2 * k) * dt;
  const p = camera.position, o = controls.target, x = p.x - o.x, z = p.z - o.z, c = Math.cos(a), s = Math.sin(a);
  p.x = o.x + x * c - z * s;
  p.z = o.z + x * s + z * c;
}

// ---------- Hills ----------
// The relief of Rome (pipeline/s08_terrain.py), off by default. The button lifts the ground into its hills, heights
// doubled so the seven hills, the Gianicolo and Monte Mario read beside the buildings; every building rides up onto
// the ground at its centre, the Tiber follows its valley, street names lie on the slopes, and faint lines mark
// every 10 m of height. Loaded on first use.
const RELIEF = 2;
const terrainBtn = document.querySelector('.terrain-toggle');
let terrain = null, terrainOn = false, terrainAnim = null;

// What lies on the ground (the water, a street found) follows it onto the hills: each vertex takes the
// height of the ground beneath it. The height grid arrives with the hills; until then nothing reads it.
const groundU = {
  uTerrain: uniforms.uTerrain,
  uHeight: { value: new THREE.DataTexture(new Float32Array(4), 2, 2, THREE.RedFormat, THREE.FloatType) },
  uGrid: { value: new THREE.Vector3(0, 0, 1) },
};
const HEIGHT_AT = /* glsl */`
  uniform float uTerrain; uniform sampler2D uHeight; uniform vec3 uGrid;
  float heightAt(vec2 xz) {
    ivec2 s = textureSize(uHeight, 0);
    vec2 f = clamp((xz - uGrid.xy) / uGrid.z, vec2(0.0), vec2(s - 2));
    ivec2 i = ivec2(floor(f)); vec2 u = f - vec2(i);
    float a = texelFetch(uHeight, i, 0).r, b = texelFetch(uHeight, i + ivec2(1, 0), 0).r;
    float c = texelFetch(uHeight, i + ivec2(0, 1), 0).r, d = texelFetch(uHeight, i + ivec2(1, 1), 0).r;
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
  }`;
// A flat polygon mesh (rotated into the ground plane by loadPolygons) on the hills, `lift` metres above the ground.
function onGround(material, lift) {
  material.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, groundU, { uLift: { value: lift } });
    sh.vertexShader = sh.vertexShader.replace('void main() {', `${HEIGHT_AT}
      uniform float uLift;
      void main() {`).replace('#include <begin_vertex>', `#include <begin_vertex>
      if (uTerrain > 0.0) transformed.y += uTerrain * (heightAt(position.xz) + uLift);`);
  };
}
onGround(water.material, 0.8);
// The green areas on the hills: the ground itself turns green under a mask of them, drawn once from above (see Green
// areas). Polygons laid over the slopes would cut through the ground's 80 m mesh, whose cells twist by metres.
const greenU = {
  uGreenMask: { value: Object.assign(new THREE.DataTexture(new Uint8Array(4), 1, 1), { needsUpdate: true }) },
  uGreenBox: { value: new THREE.Vector4(0, 0, 1, 1) }, // the mask's extent: x and z from, x and z to
  uGreenOn: { value: 0 },
  uGreenColor: { value: col(TH.green) },
};

async function loadTerrain() {
  const buf = await (await fetch('data/terrain.bin')).arrayBuffer();
  const dv = new DataView(buf);
  const nx = dv.getUint32(4, true), nz = dv.getUint32(8, true);
  const [x0, z0, cell, zmin, zstep] = [12, 16, 20, 24, 28].map(o => dv.getFloat32(o, true));
  const q = new Uint16Array(buf, 32, nx * nz), kind = new Uint8Array(buf, 32 + 2 * nx * nz, nx * nz);
  const h = new Float32Array(nx * nz);
  for (let k = 0; k < h.length; k++) h[k] = Math.max(0, zmin + zstep * q[k]) * RELIEF;
  // Bilinear height (exaggerated metres) at a local position.
  const at = (x, z) => {
    const fx = THREE.MathUtils.clamp((x - x0) / cell, 0, nx - 1.001), fz = THREE.MathUtils.clamp((z - z0) / cell, 0, nz - 1.001);
    const i = Math.floor(fx), j = Math.floor(fz), u = fx - i, v = fz - j, k = j * nx + i;
    return (h[k] * (1 - u) + h[k + 1] * u) * (1 - v) + (h[k + nx] * (1 - u) + h[k + nx + 1] * u) * v;
  };
  // The ground under every building, by its id: the building shader reads it.
  const n = config.stats.buildings, W = 1024, g = new Float32Array(W * Math.ceil(n / W));
  for (let i = 0; i < n; i++) g[i] = at(attrs.getFloat32(i * config.attrStride + 32, true), attrs.getFloat32(i * config.attrStride + 36, true));
  const groundTex = new THREE.DataTexture(g, W, g.length / W, THREE.RedFormat, THREE.FloatType);
  groundTex.needsUpdate = true;
  uniforms.uGround.value = groundTex;
  const heightTex = new THREE.DataTexture(h, nx, nz, THREE.RedFormat, THREE.FloatType);
  heightTex.needsUpdate = true;

  // The ground itself: a mesh on every other cell (80 m), with slopes from the full 40 m grid.
  const S = 2, mx = Math.floor((nx - 1) / S) + 1, mz = Math.floor((nz - 1) / S) + 1;
  const pos = new Float32Array(mx * mz * 3), grad = new Float32Array(mx * mz * 3), kd = new Float32Array(mx * mz);
  for (let b = 0; b < mz; b++) for (let a = 0; a < mx; a++) {
    const i = Math.min(a * S, nx - 1), j = Math.min(b * S, nz - 1), k = j * nx + i, v = b * mx + a;
    pos.set([x0 + i * cell, h[k], z0 + j * cell], v * 3);
    const hx = (h[j * nx + Math.min(i + 1, nx - 1)] - h[j * nx + Math.max(i - 1, 0)]) / (2 * cell);
    const hz = (h[Math.min(j + 1, nz - 1) * nx + i] - h[Math.max(j - 1, 0) * nx + i]) / (2 * cell);
    grad.set([hx, 0, hz], v * 3);
    kd[v] = kind[k];
  }
  const idx = [];
  for (let b = 0; b < mz - 1; b++) for (let a = 0; a < mx - 1; a++) {
    const v = b * mx + a;
    if (kd[v] || kd[v + 1] || kd[v + mx] || kd[v + mx + 1]) idx.push(v, v + mx, v + 1, v + 1, v + mx, v + mx + 1);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('grad', new THREE.BufferAttribute(grad, 3));
  geo.setAttribute('kind', new THREE.BufferAttribute(kd, 1));
  geo.setIndex(new THREE.BufferAttribute(new Uint32Array(idx), 1));
  const groundMat = new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: { uTerrain: uniforms.uTerrain, uFogColor: uniforms.uFogColor, uFog: uniforms.uFog, uRelief: { value: RELIEF },
      uLand: { value: col(TH.land) }, uWater: { value: col(TH.water) }, uLine: { value: col(TH.contour) }, ...greenU },
    vertexShader: /* glsl */`
      in vec3 grad;
      in float kind;
      uniform float uTerrain;
      out vec3 vN; out vec3 vW; out float vKind; out float vH;
      void main() {
        vec3 p = vec3(position.x, position.y * uTerrain - 0.6, position.z); // flat, it lies just under the water
        vN = vec3(-grad.x * uTerrain, 1.0, -grad.z * uTerrain);
        vKind = kind; vH = position.y;
        vec4 w = modelMatrix * vec4(p, 1.0);
        vW = w.xyz;
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: /* glsl */`
      precision highp float;
      uniform float uTerrain, uRelief;
      uniform vec3 uLand, uWater, uLine, uFogColor;
      uniform sampler2D uGreenMask; uniform vec4 uGreenBox; uniform float uGreenOn; uniform vec3 uGreenColor;
      uniform vec2 uFog;
      in vec3 vN; in vec3 vW; in float vKind; in float vH;
      out vec4 outColor;
      void main() {
        if (vKind < 0.5) discard;
        vec3 n = normalize(vN);
        // The same low sun from the south-west as the buildings: sunny slopes lighter, the lee darker.
        float sun = dot(n, normalize(vec3(-0.55, 0.55, 0.62)));
        vec3 c = vKind > 1.5 ? uWater : uLand;
        if (uGreenOn > 0.0 && vKind < 1.5) { // the green areas, from their mask (north is up in it)
          vec2 uv = vec2(vW.x - uGreenBox.x, uGreenBox.w - vW.z) / (uGreenBox.zw - uGreenBox.xy);
          c = mix(c, uGreenColor, smoothstep(0.25, 0.75, texture(uGreenMask, uv).r) * uGreenOn);
        }
        c *= max(0.45, 1.0 + 1.6 * (sun - 0.552) * uTerrain);
        // A thin line every 10 m of real height, a stronger one every 50 m.
        float m = vH / uRelief, t = m / 10.0, T = m / 50.0;
        float line = 1.0 - smoothstep(0.4, 1.4, abs(fract(t - 0.5) - 0.5) / fwidth(t));
        float major = 1.0 - smoothstep(0.6, 1.8, abs(fract(T - 0.5) - 0.5) / fwidth(T));
        if (vKind < 1.5) c = mix(c, uLine, max(line * 0.5, major * 0.85) * uTerrain);
        c = mix(c, uFogColor, smoothstep(uFog.x, uFog.y, length(vW - cameraPosition)));
        outColor = vec4(c, 1.0);
      }`,
  });
  const ground = new THREE.Mesh(geo, groundMat);
  ground.visible = false;
  ground.frustumCulled = false;
  flat.add(ground); // in the flat group, so picking leaves it out like the land

  // The water follows the valley, and the green areas and a street found their slopes (see onGround).
  groundU.uHeight.value = heightTex;
  groundU.uGrid.value.set(x0, z0, cell);
  water.material.polygonOffset = true; water.material.polygonOffsetFactor = -2; water.material.polygonOffsetUnits = -2;
  water.material.needsUpdate = true;
  return { at, ground, groundMat };
}

// A label lies on the ground; on the hills, on the ground at its own place, the Tiber's names a little higher.
function labelY(l) {
  const base = l.L.water ? 0.4 : 0.6, k = uniforms.uTerrain.value;
  if (!k || !terrain) return base;
  l.h ??= terrain.at(l.x, l.z);
  return base + k * (l.h + (l.L.water ? 3 : 1.5));
}

function syncTerrainBtn() {
  const label = t(terrainOn ? 'Flatten the city' : 'Show the hills');
  terrainBtn.setAttribute('aria-pressed', String(terrainOn));
  terrainBtn.setAttribute('aria-label', label); terrainBtn.title = label;
  terrainBtn.querySelector('span').textContent = t('Hills');
}
async function setTerrain(on) {
  if (on && !terrain) {
    terrainBtn.classList.add('loading');
    try { terrain = await loadTerrain(); } finally { terrainBtn.classList.remove('loading'); }
  }
  terrainOn = on;
  if (on) { terrain.ground.visible = true; land.visible = false; syncGreen(); }
  terrainAnim = { t0: performance.now(), from: uniforms.uTerrain.value, to: on ? 1 : 0 };
  syncTerrainBtn();
}
terrainBtn.onclick = () => setTerrain(!terrainOn);
// The ground rises (or settles) over a second and a half; buildings and names ride with it.
function stepTerrain(now) {
  if (!terrainAnim) return;
  const k = Math.min(1, (now - terrainAnim.t0) / 1500), e = k < 0.5 ? 4 * k ** 3 : 1 - (-2 * k + 2) ** 3 / 2;
  uniforms.uTerrain.value = terrainAnim.from + (terrainAnim.to - terrainAnim.from) * e;
  for (const l of labels) if (l.mesh) l.mesh.position.y = labelY(l);
  if (k < 1) return;
  terrainAnim = null;
  if (!terrainOn) { terrain.ground.visible = false; land.visible = true; syncGreen(); }
}

function stepFlight(now) {
  if (!flight) return;
  const k = Math.min(1, (now - flight.t0) / flight.dur), e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
  controls.target.lerpVectors(flight.fromT, flight.toT, e);
  camera.position.lerpVectors(flight.fromP, flight.toP, e);
  if (k >= 1) { const d = flight.done; flight = null; d?.(); }
}

// ---------- Search ----------
// One box under "Roma", for postcodes and streets. Five digits fly to a CAP: the middle of the addresses OpenStreetMap
// files under it (pipeline/s09_postcodes.py), where a pin stands; Rome has no open map of its postcode areas, so the
// pin marks a middle, not a boundary. Words look up a street, square or path of the comune (pipeline/s10_streets.py),
// loaded when the box is first used: the camera flies there, the street is drawn in red along its length, the pin
// stands on it.
const searchForm = document.querySelector('.search'), searchInput = searchForm.querySelector('input');
const searchList = document.getElementById('search-list');
const searchMsg = document.querySelector('.search-msg'), pinEl = document.querySelector('.pin');
let postcodes = {}, pinAt = null, msgKey = null;
fetch('data/postcodes.json').then(r => r.json()).then(p => { postcodes = p; }).catch(() => {});
function setMsg(key) {
  msgKey = key;
  searchMsg.hidden = !key;
  if (key) searchMsg.textContent = t(key);
}
// The keyboard down and the sheet folded on a phone, so the place is in view.
function leaveForMap() {
  collapsePanelOnPhone();
  if (phone.matches) searchInput.blur();
}

function findCap(cap) {
  setMsg(null);
  clearStreet();
  if (cap === '00100') { // Rome's general CAP: the whole city
    pinAt = null;
    flyTo(config.home.x, config.home.z, null, config.home.span * 0.9);
    return;
  }
  const p = postcodes[cap];
  if (!p) { pinAt = null; setMsg('Not a postcode in Rome'); return; }
  const [x, z, spread] = p;
  pinAt = { x, z };
  pinEl.querySelector('b').textContent = cap;
  leaveForMap();
  flyTo(x, z, null, THREE.MathUtils.clamp(spread * 2.8, 900, 9000));
}

// Names compared without case, accents or apostrophes ("campo de fiori" finds Campo de' Fiori), and also by what a
// street is called after its kind and article: "Via dei Fori Imperiali" is "fori imperiali", "Via del Corso" "corso".
const fold = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
const KIND = /^(via|viale|vicolo|vicoletto|piazza|piazzale|piazzetta|largo|corso|lungotevere|lungomare|circonvallazione|clivo|salita|scalinata|scesa|discesa|strada|stradone|borgo|galleria|ponte|rampa|passeggiata|passaggio|traversa|viadotto|vialetto|arco|cortile|gradinata|sottopassaggio|belvedere) /;
const ARTICLE = /^(di|del|della|dello|dei|degli|delle|de|d|dell|da|dal|dalla|al|alla|ai|agli|alle) /;
// OpenStreetMap mostly spells a closing ordinal out: "giovanni xxiii" finds Viale Giovanni Ventitreesimo, and back.
const ORDINAL = { primo: 'i', secondo: 'ii', terzo: 'iii', quarto: 'iv', quinto: 'v', sesto: 'vi', settimo: 'vii', ottavo: 'viii',
  nono: 'ix', decimo: 'x', undicesimo: 'xi', dodicesimo: 'xii', tredicesimo: 'xiii', quattordicesimo: 'xiv', quindicesimo: 'xv',
  sedicesimo: 'xvi', ventitreesimo: 'xxiii' };
const NUMERAL = Object.fromEntries(Object.entries(ORDINAL).map(([w, n]) => [n, w]));
function otherOrdinal(key) {
  const i = key.lastIndexOf(' '), last = key.slice(i + 1), other = ORDINAL[last] || NUMERAL[last];
  return i > 0 && other ? `${key.slice(0, i)} ${other}` : '';
}
let streets = null, streetsLoading = null;
function loadStreets() {
  return streetsLoading ??= fetch('data/streets.json').then(r => r.json()).then(list => {
    streets = list.map(([name, cap, rank, x, z, r, parts]) => {
      const key = fold(name);
      return { name, cap, rank, x, z, r, parts, key, alt: otherOrdinal(key), base: key.replace(KIND, '').replace(ARTICLE, '') };
    });
  }).catch(() => { streetsLoading = null; });
}
// Best first: the whole name, or what the street is called; then names that start so; then names with a word starting
// with each word typed; then names that hold it anywhere. Among equals the main roads, then the longest (the file's order).
const hasWord = (key, w) => key.startsWith(w) || key.includes(' ' + w);
function matchStreets(q) {
  const f = fold(q), words = f.split(' ');
  if (f.length < 2) return [];
  const hits = [];
  streets.forEach((s, i) => {
    const score = s.key === f || s.base === f || s.alt === f ? 0
      : s.key.startsWith(f) || s.base.startsWith(f) || (s.alt && s.alt.startsWith(f)) ? 1
      : words.every(w => hasWord(s.key, w)) || (s.alt && words.every(w => hasWord(s.alt, w))) ? 2
      : s.key.includes(f) || (s.alt && s.alt.includes(f)) ? 3 : -1;
    if (score >= 0) hits.push([score, i]);
  });
  hits.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return hits.slice(0, 8).map(([, i]) => streets[i]);
}

// The suggestions under the box: arrows move through them, Enter or a click picks one, Escape closes them.
let options = [], active = -1;
function showOptions(list) {
  options = list;
  searchList.innerHTML = list.map((o, i) => `<li role="option" id="search-opt-${i}" aria-selected="false">
    <span class="nm">${esc(o.label)}</span>${o.note ? `<span class="cap">${esc(o.note)}</span>` : ''}</li>`).join('');
  searchList.hidden = !list.length;
  searchInput.setAttribute('aria-expanded', String(!!list.length));
  setActive(list.length ? 0 : -1);
}
function setActive(i) {
  active = i;
  [...searchList.children].forEach((li, j) => li.setAttribute('aria-selected', String(j === i)));
  if (i < 0) { searchInput.removeAttribute('aria-activedescendant'); return; }
  searchInput.setAttribute('aria-activedescendant', `search-opt-${i}`);
  searchList.children[i].scrollIntoView({ block: 'nearest' });
}
const closeList = () => { if (options.length) showOptions([]); };
function choose(o) {
  searchInput.value = o.label;
  closeList();
  o.go();
}
function onSearch() {
  const v = searchInput.value.trim();
  setMsg(null);
  if (!v) { closeList(); pinAt = null; clearStreet(); return; }
  if (/^\d+$/.test(v)) { // a postcode: the fifth digit flies
    if (v.length >= 5) { closeList(); findCap(v); return; }
    showOptions(Object.keys(postcodes).filter(c => c.startsWith(v)).sort().slice(0, 8).map(c => ({ label: c, note: 'CAP', go: () => findCap(c) })));
    return;
  }
  if (!streets) { loadStreets().then(() => { if (streets && searchInput.value.trim() === v) onSearch(); }); return; }
  const hits = matchStreets(v);
  showOptions(hits.map(s => ({ label: s.name, note: s.cap, go: () => findStreet(s) })));
  if (!hits.length && fold(v).length >= 3) setMsg('No street by that name in Rome');
}
searchInput.addEventListener('focus', loadStreets);
searchInput.addEventListener('input', onSearch);
searchInput.addEventListener('keydown', e => {
  if (!options.length) return;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    setActive((active + (e.key === 'ArrowDown' ? 1 : options.length - 1)) % options.length);
  } else if (e.key === 'Escape') {
    e.preventDefault(); e.stopPropagation(); // closes the list, leaves the text and any card as they are
    closeList();
  }
});
searchInput.addEventListener('blur', () => setTimeout(closeList, 150));
searchForm.addEventListener('submit', e => {
  e.preventDefault();
  if (options[active]) choose(options[active]);
});
searchList.addEventListener('mousedown', e => e.preventDefault()); // the box keeps the focus
searchList.addEventListener('click', e => {
  const li = e.target.closest('li');
  if (li) choose(options[[...searchList.children].indexOf(li)]);
});

// The street found: a red band on the ground along its whole length, under the names and some 6 px wide on screen
// (uWidth, set every frame), solid where the street is in view and faint where buildings stand in front of it.
const foundU = { uWidth: { value: 4 }, uColor: { value: col(TH.found) } };
function foundMaterial(opacity, depthTest) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: { ...groundU, ...foundU, uOpacity: { value: opacity } },
    vertexShader: /* glsl */`
      in vec2 side;
      uniform float uWidth;
      ${HEIGHT_AT}
      void main() {
        vec3 p = position + vec3(side.x, 0.0, side.y) * uWidth;
        p.y = 0.3 + (uTerrain > 0.0 ? uTerrain * (heightAt(position.xz) + 2.5) : 0.0);
        gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(p, 1.0);
      }`,
    fragmentShader: /* glsl */`
      precision highp float;
      uniform vec3 uColor;
      uniform float uOpacity;
      out vec4 outColor;
      void main() { outColor = vec4(uColor, uOpacity); }`,
    transparent: opacity < 1, depthTest, depthWrite: false, side: THREE.DoubleSide,
  });
}
// A band two vertices wide along each line; at a bend the two sides meet on the bisector, lengthened so the band keeps
// its width (up to twice, at a hairpin).
function streetGeometry(s) {
  const pos = [], side = [], idx = [];
  const normal = (p, q) => { const dx = q[0] - p[0], dz = q[1] - p[1], l = Math.hypot(dx, dz) || 1; return [-dz / l, dx / l]; };
  for (const part of s.parts) {
    const pts = [];
    for (let k = 0, x = s.x, z = s.z; k < part.length; k += 2) pts.push([x += part[k], z += part[k + 1]]);
    if (pts.length < 2) continue;
    const first = pos.length / 3;
    pts.forEach((p, k) => {
      const n0 = k > 0 && normal(pts[k - 1], p), n1 = k < pts.length - 1 && normal(p, pts[k + 1]);
      let [nx, nz] = n0 && n1 ? [n0[0] + n1[0], n0[1] + n1[1]] : n0 || n1;
      if (n0 && n1) {
        const l = Math.hypot(nx, nz);
        if (l < 1e-3) [nx, nz] = n1;
        else { const f = Math.min(2 / (l * l), 2 / l); nx *= f; nz *= f; }
      }
      pos.push(p[0], 0, p[1], p[0], 0, p[1]);
      side.push(nx, nz, -nx, -nz);
      if (k) { const v = first + 2 * k; idx.push(v - 2, v - 1, v, v - 1, v + 1, v); }
    });
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pos), 3));
  g.setAttribute('side', new THREE.BufferAttribute(new Float32Array(side), 2));
  g.setIndex(idx);
  return g;
}
let found = null;
function clearStreet() {
  if (!found) return;
  flat.remove(found);
  found.children[0].geometry.dispose();
  for (const m of found.children) m.material.dispose();
  found = null;
}
function findStreet(s) {
  setMsg(null);
  clearStreet();
  const g = streetGeometry(s);
  found = new THREE.Group();
  for (const [opacity, depthTest] of [[1, true], [0.25, false]]) {
    const m = new THREE.Mesh(g, foundMaterial(opacity, depthTest));
    m.renderOrder = 1;          // under the street names
    m.frustumCulled = false;    // the band is widened, and lifted onto the hills, in the shader
    found.add(m);
  }
  flat.add(found);              // in the flat group, so picking leaves it out like the land
  pinAt = { x: s.x, z: s.z };
  pinEl.querySelector('b').textContent = s.name;
  leaveForMap();
  flyTo(s.x, s.z, null, THREE.MathUtils.clamp(s.r * 2.8, 450, 9000));
}

// The pin stands on the ground, on the hills when they are up, drawn over the canvas where the camera sees it.
const pinV = new THREE.Vector3();
function stepPin() {
  if (!pinAt) { pinEl.hidden = true; return; }
  const k = uniforms.uTerrain.value;
  pinV.set(pinAt.x, k && terrain ? k * terrain.at(pinAt.x, pinAt.z) : 0, pinAt.z).project(camera);
  const on = pinV.z < 1 && Math.abs(pinV.x) < 1.1 && Math.abs(pinV.y) < 1.1;
  pinEl.hidden = !on;
  if (on) pinEl.style.transform = `translate(${((pinV.x + 1) / 2 * innerWidth).toFixed(1)}px, ${((1 - pinV.y) / 2 * innerHeight).toFixed(1)}px)`;
}

// ---------- Green areas ----------
// Parks, gardens, woods and meadows from OpenStreetMap (pipeline/s11_green.py), off by default. The button lays them on
// the land in a soft green, under the buildings and the street names; farmland is left out. On the hills the mesh steps
// aside and the ground turns green under a mask of it (greenU). Loaded on first use.
const greenBtn = document.querySelector('.green-toggle');
let green = null, greenOn = false, greenMasked = false;
function syncGreenBtn() {
  const label = t(greenOn ? 'Hide the green areas' : 'Show the green areas');
  greenBtn.setAttribute('aria-pressed', String(greenOn));
  greenBtn.setAttribute('aria-label', label); greenBtn.title = label;
  greenBtn.querySelector('span').textContent = t('Green');
}
// The mask: the green areas drawn white on black, from straight above, north up, some 13 m to the pixel.
function drawGreenMask() {
  const g = green.geometry;
  g.computeBoundingBox();
  const b = g.boundingBox, w = b.max.x - b.min.x, d = b.max.z - b.min.z;
  const k = Math.min(4096, renderer.capabilities.maxTextureSize) / Math.max(w, d);
  const target = new THREE.WebGLRenderTarget(Math.round(w * k), Math.round(d * k),
    { format: THREE.RedFormat, type: THREE.UnsignedByteType, depthBuffer: false });
  const eye = new THREE.OrthographicCamera(b.min.x, b.max.x, -b.min.z, -b.max.z, -10, 10);
  eye.up.set(0, 0, -1); eye.position.set(0, 5, 0); eye.lookAt(0, 0, 0);
  const white = new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide });
  const stage = new THREE.Scene().add(new THREE.Mesh(g, white));
  renderer.setRenderTarget(target);
  renderer.setClearColor(0x000000, 1);
  renderer.render(stage, eye);
  renderer.setRenderTarget(null);
  renderer.setClearColor(TH.sky, 1);
  white.dispose();
  greenU.uGreenMask.value = target.texture;
  greenU.uGreenBox.value.set(b.min.x, b.min.z, b.max.x, b.max.z);
}
// The mesh lies on the flat land; while the hills' ground is up (rising, standing or settling) the ground is green instead.
function syncGreen() {
  if (!green) return;
  const hills = !!terrain?.ground.visible;
  green.visible = greenOn && !hills;
  if (greenOn && hills && !greenMasked) { drawGreenMask(); greenMasked = true; }
  greenU.uGreenOn.value = greenOn ? 1 : 0;
}
async function setGreen(on) {
  if (on && !green) {
    greenBtn.classList.add('loading');
    try {
      // Drawn just in front of the land it lies on (polygon offset), so the two never flicker.
      const mat = new THREE.MeshBasicMaterial({ color: TH.green, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });
      green = new THREE.Mesh(await loadPolygons('data/green.bin'), mat);
      green.position.y = -0.05;
      flat.add(green);
    } catch { return; } finally { greenBtn.classList.remove('loading'); }
  }
  greenOn = on;
  syncGreen();
  syncGreenBtn();
}
greenBtn.onclick = () => { if (!greenBtn.classList.contains('loading')) setGreen(!greenOn); };

// ---------- Panel ----------
const panelEl = document.getElementById('panel');
const panel = document.getElementById('panel-body');
const sheetHandle = panelEl.querySelector('.sheet-handle');
const phone = matchMedia('(max-width: 720px)');
// On a phone the panel is a sheet: folded to one line until opened, and folded again when the city is the point.
// On a computer it opens, and a small arrow in its corner folds it to one line for whoever wants the whole city.
function setCollapsed(c) {
  panelEl.classList.toggle('collapsed', c);
  sheetHandle.setAttribute('aria-expanded', String(!c));
  sheetHandle.textContent = sheetHandle.title = t(c ? 'Show legend' : 'Hide legend');
}
sheetHandle.onclick = () => setCollapsed(!panelEl.classList.contains('collapsed'));
function collapsePanelOnPhone() { if (phone.matches) setCollapsed(true); }
setCollapsed(phone.matches);
const totals = periods.map(() => 0);
for (const v of Object.values(config.histogram)) v.forEach((n, i) => totals[i] += n);
const fmt = n => n.toLocaleString(fmtLocale());
let activeLayer = null;
const SECTION_ORDER = ['Ancient Rome', 'Architecture', 'Faith and power', 'The city'];
const groupOn = {};
let maskTarget = periods.map(() => 1);

const ICON = {
  'Ancient Rome': '<path d="M2.5 14.5h11M3.5 4.5h9M3 2.5h10l-.5 2h-9z"/><path d="M5 4.5v10M8 4.5v10M11 4.5v10"/>',
  'Faith and power': '<path d="M8 1.5v4M6.2 3.3h3.6"/><path d="M4 14.5V8.5L8 5.5l4 3v6z"/><path d="M7 14.5v-3h2v3"/>',
  'The city': '<rect x="2.5" y="5" width="5" height="9.5"/><rect x="8.5" y="2" width="5" height="12.5"/><path d="M4.5 7.5h1M4.5 10h1M10.5 4.5h1M10.5 7h1M10.5 9.5h1"/>',
  'Discover': '<circle cx="8" cy="8" r="6.2"/><path d="M10.6 5.4 9 9 5.4 10.6 7 7z"/>',
  'Architecture': '<path d="M3 14.5V7l5-4.5L13 7v7.5z"/><path d="M6.5 14.5v-4h3v4"/>',
  'Trade and empire': '<path d="M2 11h12l-1.8 3H3.8z"/><path d="M8 2v9M8 3l4.5 6H8"/>',
  'Faith and community': '<path d="M8 1.5v4M6.2 3.3h3.6"/><path d="M4 14.5V8.5L8 5.5l4 3v6z"/><path d="M7 14.5v-3h2v3"/>',
  'The modern city': '<rect x="2.5" y="5" width="5" height="9.5"/><rect x="8.5" y="2" width="5" height="12.5"/><path d="M4.5 7.5h1M4.5 10h1M10.5 4.5h1M10.5 7h1M10.5 9.5h1"/>',
  'War and occupation': '<path d="M8 1.8 13 4v4c0 3.2-2.2 5.3-5 6.3-2.8-1-5-3.1-5-6.3V4z"/>',
};
const sectionIcon = sec => `<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round">${ICON[sec] || ''}</svg>`;

function renderPanel() {
  const mode = uniforms.uMode.value;
  if (mode === MODE.period) {
    panel.innerHTML = `<h2>${t('Built in')}</h2><div class="swatches">${periods.map((p, i) => `
      <button class="swatch" data-i="${i}" aria-pressed="${!!maskTarget[i]}">
        <i style="background:${p.color}"></i><span>${t(p.label)}</span><span class="n">${fmt(totals[i])}</span>
      </button>`).join('')}</div>
      <p class="note">${t('Click a period to see it alone. Faded buildings have an estimated date.')}</p>`;
    panel.querySelectorAll('.swatch').forEach(b => b.onclick = () => {
      const i = +b.dataset.i, m = maskTarget;
      const solo = m.every((v, j) => (j === i) === !!v);
      maskTarget = periods.map((_, j) => (solo || j === i) ? 1 : 0);
      renderPanel(); drawHist();
    });
  } else if (mode === MODE.use) {
    const u = config.uses;
    panel.innerHTML = `<h2>${t('Use')}</h2><div class="energy-scale">${u.labels.map((l, i) => i === 0 ? '' : `
      <div><i style="background:${useColors()[i]}"></i><span>${esc(t(l))}</span><span class="n">${fmt(u.counts[i])}</span></div>`).join('')}</div>
      <p class="note">${t('What each building is used for, as the 2014 regional survey records it; for newer buildings, as OpenStreetMap does.')}</p>
      <a class="src" href="https://dati.lazio.it/dataset/2014-carta-tecnica-regionale-numerica-scala-1-5-000-provincia-di-roma" target="_blank" rel="noopener">${t('Regione Lazio, geotopographic database 2014')}</a>`;
  } else if (!activeLayer) {
    const sections = [...new Set(contextLayers.map(L => L.section))].sort((a, b) => SECTION_ORDER.indexOf(a) - SECTION_ORDER.indexOf(b));
    const secTitle = sec => tr(contextLayers.find(L => L.section === sec), 'section');
    panel.innerHTML = `<nav class="jump" aria-label="${t('Context layers')}">${sections.map(sec => `
      <button data-sec="${esc(sec)}" title="${esc(secTitle(sec))}" aria-label="${esc(secTitle(sec))}">${sectionIcon(sec)}</button>`).join('')}</nav>` +
      sections.map(sec => `<h2 class="section" id="sec-${sec.replace(/\W+/g, '-')}">${sectionIcon(sec)}${esc(secTitle(sec))}</h2><div class="layers">${contextLayers.filter(L => L.section === sec).map(L => `
      <button class="layer" data-id="${L.id}">
        <b>${esc(tr(L, 'title'))}</b><span class="n">${fmt(L.count)}</span><span class="era">${esc(tr(L, 'era'))}</span>
      </button>`).join('')}</div>`).join('');
    panel.querySelectorAll('.jump button').forEach(b => b.onclick = () =>
      panel.querySelector(`#sec-${b.dataset.sec.replace(/\W+/g, '-')}`).scrollIntoView({ behavior: 'smooth', block: 'start' }));
    panel.querySelectorAll('.layer').forEach(b => b.onclick = () => setLayer(contextLayers.find(l => l.id === b.dataset.id)));
  } else {
    panel.innerHTML = `<button class="back">${t('All context layers')}</button>
      <h2 class="layer-title">${sectionIcon(activeLayer.section)}${esc(tr(activeLayer, 'title'))}</h2><p class="layer-era">${esc(tr(activeLayer, 'era'))}</p>${layerDetail(activeLayer)}`;
    panel.querySelector('.back').onclick = () => setLayer(null);
    panel.querySelectorAll('.story').forEach(b => b.onclick = () => {
      const n = activeLayer.notes[b.dataset.id];
      collapsePanelOnPhone();
      flyTo(n.at[0], n.at[1], () => {
        const gid = gidOf(b.dataset.id);
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
      <i style="background:${GROUP_COLORS[i]}"></i><span>${esc(tr(g, 'label'))}</span><span class="n">${fmt(g.count)}</span>
    </button>`).join('')}</div>` : '';
  // One line per story: a complex the survey splits into several buildings carries the same note on each.
  const seenName = new Set();
  const named = Object.entries(L.notes || {}).filter(([, n]) => n.name && n.at && !seenName.has(n.name) && seenName.add(n.name));
  const stories = named.length ? `<h2 class="section">${t('Buildings and their stories')}</h2><ul class="stories">${named.map(([id, n]) => `
    <li><button class="story" data-id="${id}"><b>${esc(tr(n, 'name'))}</b><span>${esc(tr(n, 'story'))}</span></button></li>`).join('')}</ul>` : '';
  return `<div class="layer-detail"><p>${esc(tr(L, 'text'))}</p>${groups}${stories}
    ${L.caveat ? `<p class="caveat">${esc(tr(L, 'caveat'))}</p>` : ''}
    <a href="${L.source.url}" target="_blank" rel="noopener">${esc(tr(L.source, 'label'))}</a></div>`;
}

function setLayer(L) {
  if (L) uniforms.uLayerAt.value = performance.now() / 1000;
  activeLayer = L;
  const bits = Array(MAX_GROUPS).fill(-1);
  if (L) L.groups.forEach((g, i) => { if (i < MAX_GROUPS && groupOn[g.bit] !== false) bits[i] = g.bit; });
  uniforms.uGroupBit.value = bits;
  renderPanel(); drawHist();
}

document.querySelectorAll('.modes button[data-mode]').forEach(b => b.onclick = () => {
  uniforms.uMode.value = +b.dataset.mode;
  document.querySelectorAll('.modes button[data-mode]').forEach(x => x.setAttribute('aria-pressed', x === b));
  const bits = Array(MAX_GROUPS).fill(-1);
  if (activeLayer) activeLayer.groups.forEach((g, i) => { if (groupOn[g.bit] !== false) bits[i] = g.bit; });
  uniforms.uGroupBit.value = bits;
  if (uniforms.uMode.value === MODE.layers && activeLayer) uniforms.uLayerAt.value = performance.now() / 1000;
  // On a phone the sheet opens only when there is a choice to make: a layer to pick.
  if (!phone.matches || (uniforms.uMode.value === MODE.layers && !activeLayer)) setCollapsed(false);
  renderPanel(); drawHist();
});

// ---------- Timeline ----------
const hist = document.getElementById('hist');
const hctx = hist.getContext('2d');
const T0 = Math.floor(config.yearMin / 50) * 50, T1 = config.yearMax + 1;
const years = Object.entries(config.histogram).map(([y, v]) => [+y, v]);
const yMax = Math.max(...years.map(([, v]) => v.reduce((a, b) => a + b, 0)));
// The timeline runs from antiquity, but most of Rome is from the last 150 years: the centuries before 1400 get
// an eighth of the axis, 1400–1870 a sixth, the modern city the rest.
const AXIS = [[T0, 0], [Math.max(T0 + 1, 1400), 0.12], [1870, 0.3], [T1, 1]];
function along(v, from, to) {
  for (let i = 1; i < AXIS.length; i++) {
    const a = AXIS[i - 1], b = AXIS[i];
    if (v <= b[from] || i === AXIS.length - 1) return a[to] + (Math.max(v, a[from]) - a[from]) / (b[from] - a[from]) * (b[to] - a[to]);
  }
}
const xOf = y => along(y, 0, 1) * hist.clientWidth;
const yearOf = x => Math.round(along(x / hist.clientWidth, 1, 0));

function layerGroupsShown() {
  if (uniforms.uMode.value !== MODE.layers || !activeLayer) return [];
  return activeLayer.groups.map((g, i) => ({ ...g, color: GROUP_COLORS[i] })).filter(g => groupOn[g.bit] !== false);
}

function visibleCount() {
  const Y = uniforms.uYear.value;
  const shown = layerGroupsShown();
  if (shown.length) return shown.reduce((n, g) => n + Object.entries(g.years).reduce((m, [y, c]) => m + (+y <= Y ? c : 0), 0), 0);
  let n = 0;
  for (const [y, v] of years) if (y <= Y) v.forEach((c, i) => { if (uniforms.uMode.value !== MODE.period || maskTarget[i]) n += c; });
  return n;
}

function drawHist() {
  const w = hist.clientWidth, h = hist.clientHeight, dpr = devicePixelRatio;
  hist.width = w * dpr; hist.height = h * dpr;
  hctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  hctx.clearRect(0, 0, w, h);
  const plotH = h - 20;
  const Y = uniforms.uYear.value, Yf = uniforms.uYearFrom.value;
  const shown = layerGroupsShown();
  const bar = (y, bh, top, color, on) => {
    hctx.fillStyle = color;
    hctx.globalAlpha = on ? (y <= Yf ? 0.3 : 1) : 0.18;
    hctx.fillRect(xOf(y), top - bh, Math.max(1, xOf(y + 1) - xOf(y)), bh);
  };
  if (shown.length) {
    // Layer mode: the city in grey behind, the layer's own buildings in its colours.
    for (const [y, v] of years) {
      const bh = Math.sqrt(v.reduce((a, b) => a + b, 0) / yMax) * (plotH - 6);
      bar(y, bh, plotH, TH.histGrey, false);
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
        const masked = uniforms.uMode.value === MODE.period && !maskTarget[i];
        bar(y, bh, top, periods[i].color, !masked && y <= Y);
        top -= bh;
      });
    }
  }
  hctx.globalAlpha = 1;
  hctx.fillStyle = TH.histText;
  hctx.font = '500 11px "Schibsted Grotesk", sans-serif';
  let lastX = -Infinity;
  for (const y of [0, 500, 1000, 1400, 1600, 1870, 1900, 1925, 1950, 1975, 2000]) {
    const x = Math.min(w - 28, Math.max(0, xOf(y) - 13));
    if (y < T0 || y > T1 || x - lastX < 36) continue;
    hctx.fillText(y, x, h - 4);
    lastX = x;
  }
  hctx.fillStyle = TH.histMark;
  hctx.fillRect(xOf(Y) - 1, 0, 2, plotH);
  if (Yf >= T0) { hctx.fillStyle = TH.histText; hctx.fillRect(xOf(Yf) - 0.5, 0, 1, plotH); }
  // at the end of the timeline the map shows the city as it stands, not a year that reads like a date
  document.getElementById('year').textContent = fmtYear(Math.round(Math.min(Y, config.yearMax)));
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

// Play: at the axis's own pace, quickly through the sparse centuries, slowly through the dense ones.
let playing = false, playT0 = 0, playStart = 0;
const playBtn = document.getElementById('play');
const playIcon = document.getElementById('play-icon');
const DURATION = (+new URLSearchParams(location.search).get('film') || 30) * 1000; // ?film=6 for a short film
function playYear(t) {
  return Math.min(config.yearMax, along(t, 1, 0));
}
function startPlay() {
  playing = true; playStart = performance.now();
  if (uniforms.uYear.value >= config.yearMax) uniforms.uYear.value = T0;
  playT0 = 0;
  while (playT0 < 1 && playYear(playT0) < uniforms.uYear.value) playT0 += 0.001;
  playIcon.setAttribute('d', 'M4 2.5h3v11H4zM9 2.5h3v11H9z');
  uniforms.uPlaying.value = 1;
  playBtn.setAttribute('aria-label', t('Pause'));
  playBtn.setAttribute('aria-pressed', 'true');
}
function stopPlay() {
  playing = false;
  uniforms.uPlaying.value = 0;
  uniforms.uRise.value = 0.01;
  uniforms.uYear.value = Math.round(uniforms.uYear.value);
  playIcon.setAttribute('d', 'M4 2.5v11l9-5.5z');
  playBtn.setAttribute('aria-label', t("Play the city's growth"));
  playBtn.setAttribute('aria-pressed', 'false');
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
function applyStaticText() {
  document.documentElement.lang = LANG;
  document.querySelector('.dek').textContent = t('All roads lead to Rome.');
  document.querySelector('.about-open').textContent = t('About');
  document.querySelector('.byline-top .by').textContent = t('Made with 💙 by');
  document.querySelector('.masthead-note .cta-coffee span').textContent = t('Buy me a coffee');
  document.querySelector('.masthead-note .cta-in').title = t('Follow me on LinkedIn');
  compassBtn.setAttribute('aria-label', t('North up')); compassBtn.title = t('North up');
  spinShown = null; syncSpinBtn(); // relabels the spin button in the new language
  syncTerrainBtn();
  searchInput.placeholder = t('Street or CAP');
  searchInput.setAttribute('aria-label', t('Find a street or a postcode (CAP)'));
  searchList.setAttribute('aria-label', t('Streets'));
  if (msgKey) searchMsg.textContent = t(msgKey);
  syncGreenBtn();
  const themeLabel = t(themeName() === 'dark' ? 'Light mode' : 'Dark mode');
  document.querySelector('.theme-toggle').setAttribute('aria-label', themeLabel);
  document.querySelector('.theme-toggle').title = themeLabel;
  const stats = { ...config.stats, wikidataAll: config.stats.wikidata + config.stats.wikidataApprox,
    ispraAll: config.stats.ispra + config.stats.ispraNew };
  document.querySelectorAll('[data-stat]').forEach(el => { el.textContent = fmt(stats[el.dataset.stat] ?? 0); });
  document.querySelectorAll('[data-lang-block]').forEach(a => { a.hidden = a.dataset.langBlock !== LANG; });
  document.querySelectorAll('.modes button[data-mode]').forEach(b => { b.textContent = t(b.dataset.label); });
  document.querySelector('.tally-count').childNodes[1].textContent = ' ' + t('buildings');
  document.querySelector('.howto').textContent = t('Drag to turn. Right-drag or Shift-drag to move. Scroll to zoom.');
  document.querySelector('#loading .motto').textContent = t('All roads lead to Rome.');
  document.querySelector('#loading .building-text').textContent = t('Building the city');
  playBtn.setAttribute('aria-label', t(playing ? 'Pause' : "Play the city's growth"));
  document.querySelectorAll('.lang [data-lang]').forEach(b => b.setAttribute('aria-pressed', b.dataset.lang === LANG));
  sheetHandle.textContent = sheetHandle.title = t(panelEl.classList.contains('collapsed') ? 'Show legend' : 'Hide legend');
}
document.querySelectorAll('.modes button[data-mode]').forEach(b => { b.dataset.label = b.textContent.trim(); });
const about = document.getElementById('about');
document.querySelector('.about-open').onclick = () => about.showModal();
about.querySelector('.about-close').onclick = () => about.close();
about.addEventListener('click', e => { if (e.target === about) about.close(); });

function setLang(l) {
  LANG = l;
  try { localStorage.setItem('lang', l); } catch {}
  const u = new URL(location.href); u.searchParams.set('lang', l); history.replaceState(null, '', u);
  applyStaticText(); renderPanel(); drawHist();
  if (pinnedGid >= 0) pinCard(pinnedGid, ...lastPin);
}
document.querySelectorAll('.lang [data-lang]').forEach(b => b.onclick = () => setLang(b.dataset.lang));

// ---------- Theme ----------
const themeBtn = document.querySelector('.theme-toggle');
function applyTheme() {
  TH = THEMES[themeName()];
  renderer.setClearColor(TH.sky);
  land.material.color.set(TH.land);
  water.material.color.set(TH.water);
  if (terrain) {
    terrain.groundMat.uniforms.uLand.value.set(TH.land);
    terrain.groundMat.uniforms.uWater.value.set(TH.water);
    terrain.groundMat.uniforms.uLine.value.set(TH.contour);
  }
  uniforms.uMaquette.value.set(TH.maquette);
  uniforms.uFogColor.value.set(TH.sky);
  uniforms.uUse.value = useColors().map(col);
  if (green) green.material.color.set(TH.green);
  greenU.uGreenColor.value.set(TH.green);
  foundU.uColor.value.set(TH.found);
  // Street names are drawn into textures: drop them, and they are redrawn in the new colours on next use.
  for (const l of labels) if (l.mesh) { labelGroup.remove(l.mesh); l.mesh.material.dispose(); l.mesh = null; }
  for (const tex of labelTex.values()) tex.dispose();
  labelTex.clear();
  const next = themeName() === 'dark' ? 'Light mode' : 'Dark mode';
  themeBtn.setAttribute('aria-label', t(next)); themeBtn.title = t(next);
  renderPanel(); drawHist();
}
themeBtn.onclick = () => {
  const next = themeName() === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('theme', next); } catch {}
  applyTheme();
};
darkQuery.addEventListener('change', () => { if (!document.documentElement.dataset.theme) applyTheme(); });
applyStaticText();
renderPanel();
resize();
document.fonts?.ready.then(drawHist);

let frame = 0;
renderer.setAnimationLoop(now => {
  frame++;
  stepFlight(now);
  stepSpin(now);
  stepTurn(now);
  stepTerrain(now);
  uniforms.uNow.value = now / 1000;
  uniforms.uMask.value = maskTarget;
  controls.update();
  updateCompass();
  stepPin();
  const dist = camera.position.distanceTo(controls.target);
  uniforms.uFog.value.set(dist * 1.6, dist * 4);
  foundU.uWidth.value = Math.max(1.2, 2 * dist / innerHeight); // half the band: about 3 px on screen, at least 1.2 m
  if (frame % 6 === 0) updateLabels(dist);
  if (playing) {
    const t = Math.min(1, playT0 + (now - playStart) / DURATION);
    uniforms.uYear.value = playYear(t);
    // A flight lasts about 0.8 s on screen whatever the film's pace: as many years as the film covers in that time.
    uniforms.uRise.value = Math.max(2, (playYear(Math.min(1, t + 800 / DURATION)) - playYear(t)));
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


window.__dbg = { pick, uniforms, camera, controls, setLayer, layers, pinCard, showCard, building, labelGroup, labels, flyTo, startPlay, gidOf,
  setGreen, setTerrain, loadStreets, matchStreets, findStreet };
