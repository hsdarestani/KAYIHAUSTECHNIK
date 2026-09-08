import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const KAYI_ROOM_PLANNER_PRO = '2026.08.10.7';
const root = document.querySelector('[data-room-planner]');
if (!root) throw new Error('Raumplaner konnte nicht gestartet werden.');

const $ = (sel, scope = document) => scope.querySelector(sel);
const $$ = (sel, scope = document) => [...scope.querySelectorAll(sel)];
const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
const round = (v, p = 3) => Number(Number(v || 0).toFixed(p));
const metric = (v) => `${Number(v || 0).toFixed(2)} m`;
const deepClone = (v) => JSON.parse(JSON.stringify(v));
const csrf = () => document.querySelector('input[name=csrfmiddlewaretoken]')?.value || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
const uid = (prefix = 'obj') => `${prefix}-${crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;

const canvas = $('[data-rp-canvas]', root);
const loading = $('[data-rp-loading]', root);
const engineError = $('[data-rp-engine-error]', root);
const dragHud = $('[data-rp-drag-metrics]', root);
const inspector = $('[data-rp-inspector-form]', root);
const inspectorEmpty = $('[data-rp-inspector-empty]', root);
const stats = null;
const saveButtons = $$('[data-rp-save]', root);
const saveStatus = $('[data-rp-save-state]', root);
const visionDialog = $('[data-rp-vision-dialog]', root);
const visionForm = $('.rp-dialog-shell', root);
const visionStatus = $('[data-rp-vision-feedback]', root);
const cameraInput = $('[data-rp-camera-files]', root);
const galleryInput = $('[data-rp-gallery-files]', root);
const filePreview = $('[data-rp-photo-previews]', root);
const photoCount = $('[data-rp-photo-count]', root);
const clearPhotosButton = $('[data-rp-clear-files]', root);
const readonly = root.dataset.readonly === '1';
let selectedVisionFiles = [];
let previewObjectUrls = [];

let state = JSON.parse($('#room-planner-state')?.textContent || '{}');
state = normalizeState(state);
let selected = null;
let selectedKind = null;
let hover = null;
let dragging = null;
let pointerDown = null;
let dirty = false;
let renderQueued = false;
let collisionIds = new Set();
let sceneObjectMap = new Map();
let wallMeshes = [];
let openingMeshes = [];
let ceilingMesh = null;
let gridHelper = null;
let guidesGroup = null;
let history = [deepClone(state)];
let historyIndex = 0;

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf6f7f9);
scene.fog = new THREE.Fog(0xf6f7f9, 10, 28);

const camera = new THREE.PerspectiveCamera(48, 1, 0.05, 100);
camera.position.set(5.8, 4.5, 6.8);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.screenSpacePanning = true;
controls.minDistance = 1.2;
controls.maxDistance = 22;
controls.maxPolarAngle = Math.PI * 0.495;
controls.target.set(0, 1.2, 0);

const ambient = new THREE.HemisphereLight(0xffffff, 0xb8bdc8, 2.1);
scene.add(ambient);
const sun = new THREE.DirectionalLight(0xffffff, 3.1);
sun.position.set(5, 8, 4);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.near = 0.5;
sun.shadow.camera.far = 25;
sun.shadow.camera.left = -8;
sun.shadow.camera.right = 8;
sun.shadow.camera.top = 8;
sun.shadow.camera.bottom = -8;
scene.add(sun);

const world = new THREE.Group();
scene.add(world);
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const floorDragPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const dragIntersection = new THREE.Vector3();

function normalizeState(raw) {
  const s = deepClone(raw || {});
  s.schema_version = 3;
  s.room ||= {};
  s.room.length_m = Number(s.room.length_m || 4.2);
  s.room.width_m = Number(s.room.width_m || 3.4);
  s.room.height_m = Number(s.room.height_m || 2.6);
  s.room.wall_thickness_m = Number(s.room.wall_thickness_m || 0.12);
  s.openings = Array.isArray(s.openings) ? s.openings : [];
  s.objects = Array.isArray(s.objects) ? s.objects : [];
  s.materials ||= { floor: 'warm_concrete', walls: 'soft_white' };
  s.lighting ||= { temperature: 'neutral', intensity: 1 };
  s.view ||= {};
  s.view.mode ||= 'perspective';
  if (s.view.mode === '3d') s.view.mode = 'perspective';
  s.view.show_ceiling = Boolean(s.view.show_ceiling);
  s.view.transparent_near_walls = s.view.transparent_near_walls !== false;
  s.view.grid = s.view.grid !== false;
  s.view.snap = s.view.snap !== false;
  s.calibration ||= { scale_verified: false, method: 'unknown', confidence: null, warnings: [] };
  s.openings.forEach((o) => {
    o.id ||= uid('opening');
    o.kind ||= 'door';
    o.wall ||= 'back';
    o.offset_m = Number(o.offset_m || 0.5);
    o.width_m = Number(o.width_m || (o.kind === 'door' ? 0.9 : 1.1));
    o.height_m = Number(o.height_m || (o.kind === 'door' ? 2.05 : 1.1));
    o.sill_height_m = Number(o.sill_height_m || (o.kind === 'window' ? 0.9 : 0));
    o.enabled = o.enabled !== false;
    o.locked = Boolean(o.locked);
  });
  s.objects.forEach((o) => {
    o.id ||= uid('obj');
    o.kind ||= 'fixture';
    o.label ||= labelForKind(o.kind);
    o.anchor ||= wallOnlyKinds.has(o.kind) ? 'wall' : 'floor';
    o.wall ||= o.anchor === 'wall' ? 'back' : null;
    o.x_m = Number(o.x_m ?? o.x ?? 1);
    o.z_m = Number(o.z_m ?? o.z ?? 1);
    o.elevation_m = Number(o.elevation_m || 0);
    o.width_m = Number(o.width_m || defaultSize(o.kind)[0]);
    o.depth_m = Number(o.depth_m || defaultSize(o.kind)[1]);
    o.height_m = Number(o.height_m || defaultSize(o.kind)[2]);
    o.rotation_deg = Number(o.rotation_deg || 0);
    o.enabled = o.enabled !== false;
    o.locked = Boolean(o.locked);
    o.color ||= defaultColor(o.kind);
  });
  return s;
}

const kindLabels = {
  shower: 'Dusche', vanity: 'Waschtisch', sink: 'Spüle', toilet: 'WC', bathtub: 'Badewanne',
  radiator: 'Heizkörper', boiler: 'Kessel', water_heater: 'Warmwasserspeicher', heat_pump: 'Wärmepumpe',
  cabinet: 'Schrank', wardrobe: 'Kleiderschrank', shelf: 'Regal', table: 'Tisch', chair: 'Stuhl', sofa: 'Sofa', bed: 'Bett',
  kitchen_base: 'Küchenunterschrank', kitchen_wall: 'Küchenoberschrank', fridge: 'Kühlschrank', oven: 'Backofen', stove: 'Kochfeld', dishwasher: 'Spülmaschine', washing_machine: 'Waschmaschine', dryer: 'Trockner',
  socket: 'Steckdose', switch: 'Schalter', pipe: 'Rohr', drain: 'Ablauf', column: 'Säule', fixture: 'Objekt'
};
const defaultSizes = {
  shower: [0.9, 0.9, 2.05], vanity: [0.8, 0.48, 0.85], sink: [0.75, 0.55, 0.9], toilet: [0.38, 0.68, 0.78], bathtub: [1.7, 0.75, 0.58],
  radiator: [0.9, 0.11, 0.65], boiler: [0.6, 0.55, 1.25], water_heater: [0.55, 0.55, 1.25], heat_pump: [0.95, 0.55, 1.25],
  cabinet: [0.9, 0.45, 1.9], wardrobe: [1.4, 0.6, 2.1], shelf: [0.9, 0.35, 1.8], table: [1.2, 0.75, 0.76], chair: [0.48, 0.48, 0.9], sofa: [1.9, 0.85, 0.82], bed: [2.0, 1.6, 0.55],
  kitchen_base: [0.6, 0.62, 0.9], kitchen_wall: [0.6, 0.36, 0.72], fridge: [0.65, 0.67, 1.85], oven: [0.6, 0.62, 0.9], stove: [0.6, 0.52, 0.06], dishwasher: [0.6, 0.62, 0.85], washing_machine: [0.6, 0.62, 0.85], dryer: [0.6, 0.62, 0.85],
  socket: [0.1, 0.025, 0.1], switch: [0.09, 0.025, 0.09], pipe: [0.08, 0.08, 1.4], drain: [0.14, 0.14, 0.025], column: [0.35, 0.35, 2.6], fixture: [0.6, 0.6, 0.9]
};
const kindColors = {
  shower: '#cfe8f4', vanity: '#c9b39b', sink: '#e9ecef', toilet: '#f3f4f6', bathtub: '#e6edf2', radiator: '#e7e7e7', boiler: '#d6dde2', water_heater: '#d6dde2', heat_pump: '#cbd5db',
  cabinet: '#c8aa86', wardrobe: '#b99772', shelf: '#bc9874', table: '#b88c62', chair: '#a77c58', sofa: '#a9adb8', bed: '#b9c5d8', kitchen_base: '#d3c8ba', kitchen_wall: '#ded5ca', fridge: '#dfe4e8', oven: '#34373d', stove: '#24262a', dishwasher: '#d9dfe3', washing_machine: '#e2e5e8', dryer: '#e2e5e8', socket: '#f2f2f2', switch: '#f2f2f2', pipe: '#a9adb2', drain: '#969a9f', column: '#d1d5db', fixture: '#c7ccd3'
};
const wallOnlyKinds = new Set(['radiator', 'kitchen_wall', 'socket', 'switch', 'boiler', 'water_heater']);
function labelForKind(kind) { return kindLabels[kind] || kindLabels.fixture; }
function defaultSize(kind) { return defaultSizes[kind] || defaultSizes.fixture; }
function defaultColor(kind) { return kindColors[kind] || kindColors.fixture; }

function pushHistory() {
  if (readonly) return;
  const snap = JSON.stringify(state);
  if (JSON.stringify(history[historyIndex]) === snap) return;
  history = history.slice(0, historyIndex + 1);
  history.push(deepClone(state));
  historyIndex = history.length - 1;
  if (history.length > 80) { history.shift(); historyIndex--; }
  updateUndoRedo();
}
function restoreHistory(index) {
  if (index < 0 || index >= history.length) return;
  historyIndex = index;
  state = normalizeState(history[index]);
  selected = null;
  selectedKind = null;
  dirty = true;
  rebuildScene();
  renderInspector();
  syncControlsFromState();
  updateUndoRedo();
}
function updateUndoRedo() {
  $('[data-rp-undo]', root)?.toggleAttribute('disabled', historyIndex <= 0);
  $('[data-rp-redo]', root)?.toggleAttribute('disabled', historyIndex >= history.length - 1);
}
function markDirty() {
  dirty = true;
  saveStatus.textContent = 'Nicht gespeichert';
  saveStatus.dataset.state = 'dirty';
}

function clearWorld() {
  while (world.children.length) {
    const child = world.children.pop();
    child.traverse?.((node) => {
      if (node.geometry) node.geometry.dispose?.();
      if (node.material) {
        const mats = Array.isArray(node.material) ? node.material : [node.material];
        mats.forEach((m) => m.dispose?.());
      }
    });
  }
  sceneObjectMap.clear();
  wallMeshes = [];
  openingMeshes = [];
  ceilingMesh = null;
  guidesGroup = null;
}

function material(color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: opts.roughness ?? 0.72, metalness: opts.metalness ?? 0.03, transparent: Boolean(opts.transparent), opacity: opts.opacity ?? 1, side: opts.side ?? THREE.FrontSide });
}
function box(w, h, d, mat) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(Math.max(w, 0.005), Math.max(h, 0.005), Math.max(d, 0.005)), mat);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}
function cylinder(radius, height, mat, segments = 32) {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, height, segments), mat);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}
function addPart(group, mesh, x, y, z, rotX = 0, rotY = 0, rotZ = 0) {
  mesh.position.set(x, y, z); mesh.rotation.set(rotX, rotY, rotZ); group.add(mesh); return mesh;
}

function buildRoom() {
  const { width_m: w, length_m: l, height_m: h, wall_thickness_m: t } = state.room;
  const floorMat = material(0xd9d7d2, { roughness: 0.88 });
  const floor = box(w, 0.06, l, floorMat);
  floor.position.set(w / 2, -0.03, l / 2);
  floor.receiveShadow = true;
  floor.userData.role = 'floor';
  world.add(floor);

  const baseWallMat = () => material(0xf0efec, { roughness: 0.9, transparent: true, opacity: 1, side: THREE.DoubleSide });
  const wallDefs = [
    { name: 'back', axis: 'x', length: w, constPos: 0, thickness: t, rotation: 0 },
    { name: 'front', axis: 'x', length: w, constPos: l, thickness: t, rotation: 0 },
    { name: 'left', axis: 'z', length: l, constPos: 0, thickness: t, rotation: 0 },
    { name: 'right', axis: 'z', length: l, constPos: w, thickness: t, rotation: 0 }
  ];
  wallDefs.forEach((def) => buildWallWithOpenings(def, h, baseWallMat));

  if (state.view.show_ceiling) {
    ceilingMesh = box(w, 0.045, l, material(0xf7f7f5, { roughness: 0.95, transparent: true, opacity: 0.42, side: THREE.DoubleSide }));
    ceilingMesh.position.set(w / 2, h + 0.022, l / 2);
    ceilingMesh.receiveShadow = true;
    world.add(ceilingMesh);
  }

  gridHelper = new THREE.GridHelper(Math.max(w, l) * 2.2, Math.max(8, Math.round(Math.max(w, l) * 20)), 0x8b94a3, 0xd9dde4);
  gridHelper.position.set(w / 2, 0.004, l / 2);
  gridHelper.visible = Boolean(state.view.grid);
  gridHelper.material.opacity = 0.24;
  gridHelper.material.transparent = true;
  world.add(gridHelper);
}

function wallOpenings(name) {
  return state.openings.filter((o) => o.enabled !== false && o.wall === name).sort((a, b) => a.offset_m - b.offset_m);
}
function buildWallWithOpenings(def, roomHeight, makeMaterial) {
  const t = state.room.wall_thickness_m;
  const spans = [{ a: 0, b: def.length, y0: 0, y1: roomHeight }];
  const openings = wallOpenings(def.name).map((o) => ({
    ...o,
    a: clamp(Number(o.offset_m || 0), 0, def.length),
    b: clamp(Number(o.offset_m || 0) + Number(o.width_m || 0.8), 0, def.length),
    y0: clamp(Number(o.sill_height_m || 0), 0, roomHeight),
    y1: clamp(Number(o.sill_height_m || 0) + Number(o.height_m || 2), 0, roomHeight)
  })).filter((o) => o.b > o.a && o.y1 > o.y0);

  // Segment the wall into vertical strips at every opening edge, then fill non-opening vertical intervals.
  const xs = [...new Set([0, def.length, ...openings.flatMap((o) => [o.a, o.b])])].sort((a, b) => a - b);
  for (let i = 0; i < xs.length - 1; i++) {
    const a = xs[i], b = xs[i + 1];
    if (b - a < 0.005) continue;
    const mid = (a + b) / 2;
    const cuts = openings.filter((o) => mid >= o.a - 1e-5 && mid <= o.b + 1e-5).map((o) => [o.y0, o.y1]).sort((x, y) => x[0] - y[0]);
    const ys = [0];
    cuts.forEach(([c0, c1]) => { ys.push(c0, c1); });
    ys.push(roomHeight);
    const sortedY = [...new Set(ys.map((v) => clamp(v, 0, roomHeight)))].sort((x, y) => x - y);
    for (let j = 0; j < sortedY.length - 1; j++) {
      const y0 = sortedY[j], y1 = sortedY[j + 1];
      const ym = (y0 + y1) / 2;
      if (cuts.some(([c0, c1]) => ym > c0 + 1e-5 && ym < c1 - 1e-5)) continue;
      if (y1 - y0 < 0.005) continue;
      const seg = def.axis === 'x' ? box(b - a, y1 - y0, t, makeMaterial()) : box(t, y1 - y0, b - a, makeMaterial());
      if (def.name === 'back') seg.position.set((a + b) / 2, (y0 + y1) / 2, -t / 2);
      if (def.name === 'front') seg.position.set((a + b) / 2, (y0 + y1) / 2, state.room.length_m + t / 2);
      if (def.name === 'left') seg.position.set(-t / 2, (y0 + y1) / 2, (a + b) / 2);
      if (def.name === 'right') seg.position.set(state.room.width_m + t / 2, (y0 + y1) / 2, (a + b) / 2);
      seg.userData = { role: 'wall', wall: def.name };
      wallMeshes.push(seg); world.add(seg);
    }
  }
  openings.forEach((opening) => buildOpeningVisual(opening, def));
}

function buildOpeningVisual(o, def) {
  const group = new THREE.Group();
  group.userData = { role: 'opening', id: o.id, source: o };
  const frameMat = material(o.kind === 'window' ? 0xbfc7ce : 0x9b7d61, { roughness: 0.58 });
  const glassMat = material(0x92c3db, { roughness: 0.12, transparent: true, opacity: 0.28, side: THREE.DoubleSide });
  const ww = Math.max(0.2, o.width_m); const hh = Math.max(0.2, o.height_m); const sill = o.sill_height_m || 0;
  const frame = 0.035; const depth = Math.max(0.05, state.room.wall_thickness_m * 1.35);
  const along = o.offset_m + ww / 2;
  const y = sill + hh / 2;
  if (def.axis === 'x') {
    addPart(group, box(frame, hh, depth, frameMat), -ww / 2, 0, 0);
    addPart(group, box(frame, hh, depth, frameMat), ww / 2, 0, 0);
    addPart(group, box(ww + frame, frame, depth, frameMat), 0, hh / 2, 0);
    if (sill > 0.02 || o.kind === 'window') addPart(group, box(ww + frame, frame, depth, frameMat), 0, -hh / 2, 0);
    if (o.kind === 'window') addPart(group, box(ww - frame * 1.8, hh - frame * 1.8, 0.012, glassMat), 0, 0, 0);
    group.position.set(along, y, def.name === 'back' ? -state.room.wall_thickness_m * 0.12 : state.room.length_m + state.room.wall_thickness_m * 0.12);
  } else {
    addPart(group, box(depth, hh, frame, frameMat), 0, 0, -ww / 2);
    addPart(group, box(depth, hh, frame, frameMat), 0, 0, ww / 2);
    addPart(group, box(depth, frame, ww + frame, frameMat), 0, hh / 2, 0);
    if (sill > 0.02 || o.kind === 'window') addPart(group, box(depth, frame, ww + frame, frameMat), 0, -hh / 2, 0);
    if (o.kind === 'window') addPart(group, box(0.012, hh - frame * 1.8, ww - frame * 1.8, glassMat), 0, 0, 0);
    group.position.set(def.name === 'left' ? -state.room.wall_thickness_m * 0.12 : state.room.width_m + state.room.wall_thickness_m * 0.12, y, along);
  }
  group.traverse((m) => { if (m.isMesh) m.userData = group.userData; });
  openingMeshes.push(group); sceneObjectMap.set(o.id, group); world.add(group);
}

function buildObjects() {
  state.objects.filter((o) => o.enabled !== false).forEach((o) => {
    const group = createObjectMesh(o);
    placeObjectGroup(group, o);
    group.userData = { role: 'object', id: o.id, source: o };
    group.traverse((m) => { if (m.isMesh) m.userData = group.userData; });
    sceneObjectMap.set(o.id, group);
    world.add(group);
  });
}

function createObjectMesh(o) {
  const g = new THREE.Group();
  const w = o.width_m, d = o.depth_m, h = o.height_m;
  const base = material(o.color || defaultColor(o.kind));
  const dark = material(0x4b5058, { roughness: 0.48, metalness: 0.2 });
  const white = material(0xf1f3f5, { roughness: 0.55 });
  const chrome = material(0xaab1b7, { roughness: 0.25, metalness: 0.65 });
  const glass = material(0xa8d5e6, { roughness: 0.12, transparent: true, opacity: 0.24, side: THREE.DoubleSide });

  switch (o.kind) {
    case 'radiator': {
      const bars = Math.max(5, Math.round(w / 0.08));
      for (let i = 0; i < bars; i++) addPart(g, box(w / bars * 0.62, h, d * 0.7, white), -w / 2 + (i + 0.5) * w / bars, 0, 0);
      addPart(g, box(w, 0.035, d, chrome), 0, h / 2 - 0.03, 0); break;
    }
    case 'toilet': {
      addPart(g, box(w * 0.72, h * 0.45, d * 0.78, white), 0, -h * 0.22, d * 0.06);
      const bowl = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.37, w * 0.29, h * 0.28, 28), white); bowl.scale.z = 1.25; addPart(g, bowl, 0, 0, d * 0.05, Math.PI / 2, 0, 0);
      addPart(g, box(w * 0.86, h * 0.52, d * 0.25, white), 0, h * 0.2, -d * 0.34); break;
    }
    case 'bathtub':
    case 'shower': {
      const lowH = o.kind === 'bathtub' ? h : Math.min(0.12, h * 0.1);
      addPart(g, box(w, lowH, d, white), 0, -h / 2 + lowH / 2, 0);
      const rimH = o.kind === 'bathtub' ? h * 0.8 : h;
      const rimT = Math.min(0.055, Math.min(w, d) * 0.08);
      if (o.kind === 'bathtub') {
        addPart(g, box(rimT, rimH, d, white), -w / 2 + rimT / 2, -h / 2 + rimH / 2, 0);
        addPart(g, box(rimT, rimH, d, white), w / 2 - rimT / 2, -h / 2 + rimH / 2, 0);
        addPart(g, box(w - rimT * 2, rimH, rimT, white), 0, -h / 2 + rimH / 2, -d / 2 + rimT / 2);
        addPart(g, box(w - rimT * 2, rimH, rimT, white), 0, -h / 2 + rimH / 2, d / 2 - rimT / 2);
      } else {
        addPart(g, box(0.018, h, d, glass), -w / 2, 0, 0);
        addPart(g, box(w, h, 0.018, glass), 0, 0, -d / 2);
      }
      break;
    }
    case 'vanity':
    case 'sink': {
      addPart(g, box(w, h * 0.62, d, base), 0, -h * 0.19, 0);
      const basin = new THREE.Mesh(new THREE.CylinderGeometry(Math.min(w, d) * 0.27, Math.min(w, d) * 0.34, h * 0.12, 28), white); basin.scale.z = 1.25; addPart(g, basin, 0, h * 0.22, 0, 0, 0, 0);
      addPart(g, cylinder(0.018, h * 0.28, chrome, 18), 0, h * 0.36, -d * 0.18); break;
    }
    case 'table': {
      addPart(g, box(w, 0.06, d, base), 0, h / 2 - 0.03, 0);
      [[-1,-1],[1,-1],[-1,1],[1,1]].forEach(([sx, sz]) => addPart(g, box(0.06, h - 0.06, 0.06, dark), sx*(w/2-0.07), -0.03, sz*(d/2-0.07))); break;
    }
    case 'chair': {
      addPart(g, box(w, 0.06, d, base), 0, -h * 0.12, 0);
      addPart(g, box(w, h * 0.46, 0.06, base), 0, h * 0.23, -d / 2 + 0.03);
      [[-1,-1],[1,-1],[-1,1],[1,1]].forEach(([sx, sz]) => addPart(g, box(0.045, h * 0.45, 0.045, dark), sx*(w/2-0.06), -h * 0.34, sz*(d/2-0.06))); break;
    }
    case 'sofa': {
      addPart(g, box(w, h * 0.46, d, base), 0, -h * 0.27, 0);
      addPart(g, box(w, h * 0.55, d * 0.22, base), 0, h * 0.19, -d / 2 + d * 0.11);
      addPart(g, box(w * 0.05, h * 0.55, d, base), -w/2+w*.025, 0, 0); addPart(g, box(w*.05,h*.55,d,base),w/2-w*.025,0,0); break;
    }
    case 'bed': {
      addPart(g, box(w, h * 0.36, d, material(0xd6dbe3)), 0, -h * 0.2, 0);
      addPart(g, box(w, h * 0.7, 0.09, base), 0, h * 0.12, -d / 2 + 0.045); break;
    }
    case 'washing_machine':
    case 'dryer':
    case 'dishwasher': {
      addPart(g, box(w, h, d, base), 0, 0, 0);
      if (o.kind !== 'dishwasher') {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(Math.min(w,h)*.23, .025, 12, 40), dark); addPart(g, ring, 0, 0.02, d/2+.006, Math.PI/2,0,0);
        const glassDoor = cylinder(Math.min(w,h)*.2, .025, glass, 36); addPart(g, glassDoor,0,.02,d/2+.01,Math.PI/2,0,0);
      } else addPart(g, box(w*.82,.025,d*.02,dark),0,h*.36,d/2+.012);
      break;
    }
    case 'fridge': {
      addPart(g, box(w, h, d, base), 0, 0, 0); addPart(g, box(.02,h*.78,.025,dark),w*.34,.04,d/2+.015); addPart(g, box(w*.9,.012,d*.02,dark),0,h*.08,d/2+.015); break;
    }
    case 'oven': {
      addPart(g, box(w, h, d, material(0x52565c,{metalness:.2})),0,0,0); addPart(g, box(w*.82,h*.55,.025,material(0x181a1d,{roughness:.2})),0,-h*.08,d/2+.015); break;
    }
    case 'stove': {
      addPart(g, box(w,h,d,material(0x202226,{roughness:.18})),0,0,0); [[-.24,-.2],[.24,-.2],[-.24,.2],[.24,.2]].forEach(([px,pz])=>{ const ring=new THREE.Mesh(new THREE.TorusGeometry(Math.min(w,d)*.13,.01,8,30),chrome); addPart(g,ring,px*w,.02,pz*d,Math.PI/2,0,0); }); break;
    }
    case 'kitchen_base':
    case 'kitchen_wall':
    case 'cabinet':
    case 'wardrobe':
    case 'shelf': {
      addPart(g, box(w,h,d,base),0,0,0);
      if (o.kind === 'shelf') for(let i=1;i<5;i++) addPart(g,box(w*.9,.025,d*.88,material(0xb38d67)),0,-h/2+i*h/5,0);
      else { addPart(g, box(.018,h*.9,.018,dark),-.04,0,d/2+.012); addPart(g, box(.018,h*.9,.018,dark),.04,0,d/2+.012); }
      break;
    }
    case 'boiler':
    case 'water_heater':
    case 'heat_pump': {
      if (o.kind === 'water_heater') { const cyl=cylinder(w*.46,h,base,36); addPart(g,cyl,0,0,0); }
      else addPart(g, box(w,h,d,base),0,0,0);
      addPart(g,box(w*.28,h*.12,.022,dark),0,h*.24,d/2+.012); break;
    }
    case 'socket':
    case 'switch': {
      addPart(g, box(w,h,d,base),0,0,0); if(o.kind==='socket'){ addPart(g,cylinder(w*.08,.012,dark,20),-w*.18,0,d/2+.008,Math.PI/2,0,0); addPart(g,cylinder(w*.08,.012,dark,20),w*.18,0,d/2+.008,Math.PI/2,0,0); } else addPart(g,box(w*.55,h*.55,.01,material(0xdedede)),0,0,d/2+.008); break;
    }
    case 'pipe': { const c=cylinder(Math.min(w,d)/2,h,material(0xaeb5bb,{metalness:.45,roughness:.25}),24); addPart(g,c,0,0,0); break; }
    case 'drain': { const c=cylinder(Math.min(w,d)/2,h,chrome,30); addPart(g,c,0,0,0); const grate=new THREE.Mesh(new THREE.TorusGeometry(Math.min(w,d)*.35,.006,8,24),dark); addPart(g,grate,0,h/2+.008,0,Math.PI/2,0,0); break; }
    case 'column': addPart(g,box(w,h,d,base),0,0,0); break;
    default: addPart(g,box(w,h,d,base),0,0,0);
  }
  return g;
}

function placeObjectGroup(g, o) {
  const w = state.room.width_m, l = state.room.length_m;
  if (o.anchor === 'wall') {
    const wall = o.wall || 'back';
    if (wall === 'back') { g.position.set(o.x_m, o.elevation_m + o.height_m / 2, Math.max(o.depth_m / 2, 0.001)); g.rotation.y = THREE.MathUtils.degToRad(o.rotation_deg || 0); }
    if (wall === 'front') { g.position.set(o.x_m, o.elevation_m + o.height_m / 2, l - Math.max(o.depth_m / 2, .001)); g.rotation.y = Math.PI + THREE.MathUtils.degToRad(o.rotation_deg || 0); }
    if (wall === 'left') { g.position.set(Math.max(o.depth_m / 2, .001), o.elevation_m + o.height_m / 2, o.z_m); g.rotation.y = Math.PI / 2 + THREE.MathUtils.degToRad(o.rotation_deg || 0); }
    if (wall === 'right') { g.position.set(w - Math.max(o.depth_m / 2, .001), o.elevation_m + o.height_m / 2, o.z_m); g.rotation.y = -Math.PI / 2 + THREE.MathUtils.degToRad(o.rotation_deg || 0); }
  } else {
    g.position.set(o.x_m, o.elevation_m + o.height_m / 2, o.z_m);
    g.rotation.y = THREE.MathUtils.degToRad(o.rotation_deg || 0);
  }
}

function applySelectionVisuals() {
  sceneObjectMap.forEach((group, id) => {
    group.traverse((m) => {
      if (!m.isMesh || !m.material) return;
      const mats = Array.isArray(m.material) ? m.material : [m.material];
      mats.forEach((mat) => {
        if (!mat.emissive) return;
        if (collisionIds.has(id)) { mat.emissive.set(0x7d1818); mat.emissiveIntensity = 0.45; }
        else if (selected === id) { mat.emissive.set(0x1e5eff); mat.emissiveIntensity = 0.16; }
        else if (hover === id) { mat.emissive.set(0x4e6d9d); mat.emissiveIntensity = 0.08; }
        else { mat.emissive.set(0x000000); mat.emissiveIntensity = 0; }
      });
    });
  });
}

function rebuildScene({ keepCamera = true } = {}) {
  clearWorld();
  buildRoom(); buildObjects();
  updateWallTransparency();
  applySelectionVisuals();
  updateStats();
  if (!keepCamera) fitCamera();
  queueRender();
}

function updateWallTransparency() {
  const transparent = Boolean(state.view.transparent_near_walls);
  wallMeshes.forEach((wall) => {
    const name = wall.userData.wall;
    let opacity = 1;
    if (transparent && state.view.mode === 'perspective') {
      if (name === 'front') opacity = 0.18;
      else if (name === 'right') opacity = 0.62;
    }
    wall.material.transparent = opacity < 1;
    wall.material.opacity = opacity;
    wall.material.depthWrite = opacity > 0.6;
  });
}

function objectRecord(id) { return state.objects.find((o) => o.id === id); }
function openingRecord(id) { return state.openings.find((o) => o.id === id); }
function selectedRecord() { return selectedKind === 'opening' ? openingRecord(selected) : objectRecord(selected); }

function roomBoundsForObject(o) {
  const angle = THREE.MathUtils.degToRad(effectiveRotationDeg(o));
  const c = Math.abs(Math.cos(angle)), s = Math.abs(Math.sin(angle));
  const halfX = (o.width_m * c + o.depth_m * s) / 2;
  const halfZ = (o.width_m * s + o.depth_m * c) / 2;
  return { minX: o.x_m-halfX, maxX:o.x_m+halfX, minZ:o.z_m-halfZ, maxZ:o.z_m+halfZ, halfX, halfZ };
}
function effectiveRotationDeg(o) {
  const base = Number(o.rotation_deg || 0);
  if (o.anchor !== 'wall') return base;
  if (o.wall === 'left') return base + 90;
  if (o.wall === 'right') return base - 90;
  if (o.wall === 'front') return base + 180;
  return base;
}
function distancesFor(o) {
  const b = roomBoundsForObject(o); const w=state.room.width_m,l=state.room.length_m;
  let nearest = Infinity, nearestLabel = '—';
  for (const other of state.objects) {
    if (other.id === o.id || other.enabled === false) continue;
    const ob=roomBoundsForObject(other);
    const dx=Math.max(0,Math.max(ob.minX-b.maxX,b.minX-ob.maxX));
    const dz=Math.max(0,Math.max(ob.minZ-b.maxZ,b.minZ-ob.maxZ));
    const dist=Math.hypot(dx,dz);
    if(dist<nearest){nearest=dist;nearestLabel=other.label||labelForKind(other.kind);}
  }
  return { left: Math.max(0,b.minX), right: Math.max(0,w-b.maxX), back: Math.max(0,b.minZ), front: Math.max(0,l-b.maxZ), nearest: Number.isFinite(nearest)?nearest:null, nearestLabel };
}
function collisionSet() {
  const ids = new Set(); const active=state.objects.filter((o)=>o.enabled!==false);
  for(let i=0;i<active.length;i++) for(let j=i+1;j<active.length;j++){
    const a=roomBoundsForObject(active[i]), b=roomBoundsForObject(active[j]);
    const overlapX=Math.min(a.maxX,b.maxX)-Math.max(a.minX,b.minX);
    const overlapZ=Math.min(a.maxZ,b.maxZ)-Math.max(a.minZ,b.minZ);
    const y1a=active[i].elevation_m||0,y2a=y1a+active[i].height_m,y1b=active[j].elevation_m||0,y2b=y1b+active[j].height_m;
    if(overlapX>0.015&&overlapZ>0.015&&Math.min(y2a,y2b)-Math.max(y1a,y1b)>0.02){ ids.add(active[i].id); ids.add(active[j].id); }
  }
  return ids;
}

function constrainObject(o) {
  const w=state.room.width_m,l=state.room.length_m;
  if(o.anchor==='wall'){
    const wall=o.wall||'back';
    if(wall==='back'||wall==='front') o.x_m=clamp(o.x_m,o.width_m/2,w-o.width_m/2);
    else o.z_m=clamp(o.z_m,o.width_m/2,l-o.width_m/2);
    if (wall === 'back') o.z_m = o.depth_m / 2;
    if (wall === 'front') o.z_m = l - o.depth_m / 2;
    if (wall === 'left') o.x_m = o.depth_m / 2;
    if (wall === 'right') o.x_m = w - o.depth_m / 2;
    o.elevation_m=clamp(o.elevation_m,0,Math.max(0,state.room.height_m-o.height_m));
    return;
  }
  const b=roomBoundsForObject(o);
  if(b.minX<0)o.x_m-=b.minX;if(b.maxX>w)o.x_m-=b.maxX-w;if(b.minZ<0)o.z_m-=b.minZ;if(b.maxZ>l)o.z_m-=b.maxZ-l;
  o.elevation_m=clamp(o.elevation_m,0,Math.max(0,state.room.height_m-o.height_m));
}
function snapObject(o) {
  if(!state.view.snap)return;
  const grid=.05; const threshold=.065;
  o.x_m=Math.round(o.x_m/grid)*grid;o.z_m=Math.round(o.z_m/grid)*grid;
  const b=roomBoundsForObject(o), w=state.room.width_m,l=state.room.length_m;
  if(Math.abs(b.minX)<.09)o.x_m-=b.minX;if(Math.abs(w-b.maxX)<.09)o.x_m+=w-b.maxX;if(Math.abs(b.minZ)<.09)o.z_m-=b.minZ;if(Math.abs(l-b.maxZ)<.09)o.z_m+=l-b.maxZ;
  for(const other of state.objects){ if(other.id===o.id||other.enabled===false)continue; const ob=roomBoundsForObject(other); const b2=roomBoundsForObject(o);
    const candidates=[['x',ob.minX-b2.maxX],['x',ob.maxX-b2.minX],['x',(ob.minX+ob.maxX)/2-(b2.minX+b2.maxX)/2],['z',ob.minZ-b2.maxZ],['z',ob.maxZ-b2.minZ],['z',(ob.minZ+ob.maxZ)/2-(b2.minZ+b2.maxZ)/2]];
    for(const [axis,delta] of candidates){if(Math.abs(delta)<threshold){ if(axis==='x')o.x_m+=delta;else o.z_m+=delta; }}
  }
}

function setPointer(ev) {
  const r=canvas.getBoundingClientRect(); pointer.x=((ev.clientX-r.left)/r.width)*2-1; pointer.y=-((ev.clientY-r.top)/r.height)*2+1; raycaster.setFromCamera(pointer,camera);
}
function pick(ev) {
  setPointer(ev);
  const meshes=[];sceneObjectMap.forEach((g)=>g.traverse((m)=>{if(m.isMesh)meshes.push(m);}));
  const hit=raycaster.intersectObjects(meshes,false)[0];
  return hit?.object?.userData?.id ? {id:hit.object.userData.id, role:hit.object.userData.role, hit} : null;
}

function pointerDownHandler(ev) {
  if(ev.button!==0)return;
  const p=pick(ev); pointerDown={x:ev.clientX,y:ev.clientY,p};
  if(!p){ select(null,null); return; }
  select(p.id,p.role==='opening'?'opening':'object');
  if(readonly)return;
  const rec=selectedRecord();if(!rec||rec.locked)return;
  dragging={id:p.id,kind:selectedKind,start:deepClone(rec),moved:false,offset:new THREE.Vector3()};
  if(selectedKind==='object'&&rec.anchor!=='wall'){
    raycaster.ray.intersectPlane(floorDragPlane,dragIntersection);
    dragging.offset.set(rec.x_m-dragIntersection.x,0,rec.z_m-dragIntersection.z);
  }
  controls.enabled=false;canvas.setPointerCapture?.(ev.pointerId);
}
function pointerMoveHandler(ev) {
  if(!dragging){ const p=pick(ev); const next=p?.id||null;if(next!==hover){hover=next;applySelectionVisuals();queueRender();} canvas.style.cursor=p&&!readonly?'grab':'default';return; }
  setPointer(ev); const rec=selectedRecord(); if(!rec)return;
  dragging.moved=dragging.moved||Math.hypot(ev.clientX-pointerDown.x,ev.clientY-pointerDown.y)>3;
  if(selectedKind==='opening') dragOpening(rec,ev);
  else if(rec.anchor==='wall') dragWallObject(rec,ev);
  else if(raycaster.ray.intersectPlane(floorDragPlane,dragIntersection)) { rec.x_m=dragIntersection.x+dragging.offset.x;rec.z_m=dragIntersection.z+dragging.offset.z;snapObject(rec);constrainObject(rec); }
  collisionIds=collisionSet(); updateDraggedMesh(rec); showDragMetrics(rec); markDirty();renderInspector({quiet:true});applySelectionVisuals();queueRender();
}
function pointerUpHandler(ev) {
  if(!dragging)return; controls.enabled=true;canvas.releasePointerCapture?.(ev.pointerId);hideGuides(); if(dragging.moved)pushHistory(); dragging=null; collisionIds=collisionSet();applySelectionVisuals();queueRender();
}
function dragOpening(o,ev){
  const wall=o.wall||'back'; const r=canvas.getBoundingClientRect(); const normalizedX=clamp((ev.clientX-r.left)/r.width,0,1); const normalizedY=clamp(1-(ev.clientY-r.top)/r.height,0,1);
  // Raycast against wall-aligned vertical plane for exact world coordinate.
  const plane=wall==='back'?new THREE.Plane(new THREE.Vector3(0,0,1),0):wall==='front'?new THREE.Plane(new THREE.Vector3(0,0,-1),state.room.length_m):wall==='left'?new THREE.Plane(new THREE.Vector3(1,0,0),0):new THREE.Plane(new THREE.Vector3(-1,0,0),state.room.width_m);
  if(raycaster.ray.intersectPlane(plane,dragIntersection)){
    const max=(wall==='back'||wall==='front')?state.room.width_m:state.room.length_m;let coord=(wall==='back'||wall==='front')?dragIntersection.x:dragIntersection.z;coord-=o.width_m/2; if(state.view.snap)coord=Math.round(coord/.05)*.05;o.offset_m=clamp(coord,0,Math.max(0,max-o.width_m));
  }
  rebuildScene(); select(o.id,'opening',{skipScene:true});
}
function dragWallObject(o,ev){
  const wall=o.wall||'back'; const plane=wall==='back'?new THREE.Plane(new THREE.Vector3(0,0,1),0):wall==='front'?new THREE.Plane(new THREE.Vector3(0,0,-1),state.room.length_m):wall==='left'?new THREE.Plane(new THREE.Vector3(1,0,0),0):new THREE.Plane(new THREE.Vector3(-1,0,0),state.room.width_m);
  if(raycaster.ray.intersectPlane(plane,dragIntersection)){
    if(wall==='back'||wall==='front')o.x_m=dragIntersection.x;else o.z_m=dragIntersection.z;
    o.elevation_m=dragIntersection.y-o.height_m/2;if(state.view.snap){ if(wall==='back'||wall==='front')o.x_m=Math.round(o.x_m/.05)*.05;else o.z_m=Math.round(o.z_m/.05)*.05;o.elevation_m=Math.round(o.elevation_m/.05)*.05;} constrainObject(o);
  }
}
function updateDraggedMesh(o){const g=sceneObjectMap.get(o.id);if(g)placeObjectGroup(g,o);}

function positionDragHud(id) {
  const group = sceneObjectMap.get(id);
  if (!group || !dragHud) return;
  const rect = canvas.getBoundingClientRect();
  const point = group.getWorldPosition(new THREE.Vector3()).project(camera);
  const x = (point.x * 0.5 + 0.5) * rect.width;
  const y = (-point.y * 0.5 + 0.5) * rect.height;
  dragHud.style.left = `${clamp(x, 90, Math.max(90, rect.width - 90))}px`;
  dragHud.style.top = `${clamp(y, 85, Math.max(85, rect.height - 25))}px`;
}
function nearestObjectToPoint(x, z, excludeId = null) {
  let nearest = Infinity, label = '—';
  for (const other of state.objects) {
    if (other.id === excludeId || other.enabled === false) continue;
    const dist = Math.hypot(Number(other.x_m || 0) - x, Number(other.z_m || 0) - z);
    if (dist < nearest) { nearest = dist; label = other.label || labelForKind(other.kind); }
  }
  return { distance: Number.isFinite(nearest) ? nearest : null, label };
}
function showDragMetrics(rec){
  if (!rec || !dragHud) { if (dragHud) dragHud.hidden = true; return; }
  dragHud.hidden=false;
  if (selectedKind === 'opening') {
    const wallLen = wallLength(rec.wall);
    const left = Math.max(0, Number(rec.offset_m || 0));
    const right = Math.max(0, wallLen - left - Number(rec.width_m || 0));
    const sill = Number(rec.sill_height_m || 0);
    const top = Math.max(0, state.room.height_m - sill - Number(rec.height_m || 0));
    let cx = state.room.width_m / 2, cz = state.room.length_m / 2;
    const along = left + Number(rec.width_m || 0) / 2;
    if (rec.wall === 'back') { cx = along; cz = 0; }
    if (rec.wall === 'front') { cx = along; cz = state.room.length_m; }
    if (rec.wall === 'left') { cx = 0; cz = along; }
    if (rec.wall === 'right') { cx = state.room.width_m; cz = along; }
    const nearest = nearestObjectToPoint(cx, cz);
    dragHud.innerHTML=`<div><b>${escapeHtml(rec.label || (rec.kind === 'window' ? 'Fenster' : 'Tür'))}</b></div><div class="rp-hud-grid"><span>Wandanfang ${metric(left)}</span><span>Wandende ${metric(right)}</span><span>Unterkante ${metric(sill)}</span><span>Decke ${metric(top)}</span></div><div>Nächstes Objekt: ${nearest.distance===null?'—':`${metric(nearest.distance)} · ${escapeHtml(nearest.label)}`}</div>`;
    positionDragHud(rec.id);
    return;
  }
  const d=distancesFor(rec);
  dragHud.innerHTML=`<div><b>${escapeHtml(rec.label||labelForKind(rec.kind))}</b>${collisionIds.has(rec.id)?'<span class="rp-collision"> Kollision</span>':''}</div><div class="rp-hud-grid"><span>← ${metric(d.left)}</span><span>→ ${metric(d.right)}</span><span>↑ ${metric(d.back)}</span><span>↓ ${metric(d.front)}</span></div><div>Nächstes: ${d.nearest===null?'—':`${metric(d.nearest)} · ${escapeHtml(d.nearestLabel)}`}</div>`;
  positionDragHud(rec.id);
  renderDimensionGuides(rec,d);
}
function hideGuides(){dragHud.hidden=true;if(guidesGroup){world.remove(guidesGroup);guidesGroup=null;}queueRender();}
function renderDimensionGuides(o,d){ if(guidesGroup)world.remove(guidesGroup);guidesGroup=new THREE.Group(); const y=Math.max(.02,o.elevation_m+.03); const c=0x2d66e5;
  const addLine=(a,b)=>{const geo=new THREE.BufferGeometry().setFromPoints([a,b]);guidesGroup.add(new THREE.Line(geo,new THREE.LineBasicMaterial({color:c,transparent:true,opacity:.82})));};
  addLine(new THREE.Vector3(0,y,o.z_m),new THREE.Vector3(Math.max(0,o.x_m-o.width_m/2),y,o.z_m));addLine(new THREE.Vector3(Math.min(state.room.width_m,o.x_m+o.width_m/2),y,o.z_m),new THREE.Vector3(state.room.width_m,y,o.z_m));
  addLine(new THREE.Vector3(o.x_m,y,0),new THREE.Vector3(o.x_m,y,Math.max(0,o.z_m-o.depth_m/2)));addLine(new THREE.Vector3(o.x_m,y,Math.min(state.room.length_m,o.z_m+o.depth_m/2)),new THREE.Vector3(o.x_m,y,state.room.length_m));world.add(guidesGroup);
}

function select(id,kind,{skipScene=false}={}){selected=id;selectedKind=kind;if(!skipScene)applySelectionVisuals();renderInspector();queueRender();}
function renderInspector({quiet=false}={}){
  if(!inspector)return; const rec=selectedRecord();
  if(!rec){ inspector.hidden = true; if (inspectorEmpty) inspectorEmpty.hidden = false; return;}
  inspector.hidden = false; if (inspectorEmpty) inspectorEmpty.hidden = true;
  if(selectedKind==='opening')return renderOpeningInspector(rec);
  const d=distancesFor(rec); const wallOpts=['back','front','left','right'].map((w)=>`<option value="${w}" ${rec.wall===w?'selected':''}>${wallLabel(w)}</option>`).join('');
  inspector.innerHTML=`<div class="rp-inspector-head"><div><span>${escapeHtml(labelForKind(rec.kind))}</span><strong>${escapeHtml(rec.label||labelForKind(rec.kind))}</strong></div><div class="rp-inspector-actions">${readonly?'':`<button type="button" data-rp-duplicate title="Duplizieren">⧉</button><button type="button" data-rp-delete title="Löschen">⌫</button>`}</div></div>
  <label>Name<input data-field="label" value="${escapeAttr(rec.label||'')}" ${readonly?'disabled':''}></label>
  <div class="rp-form-grid"><label>Breite (m)<input type="number" min="0.02" step="0.01" data-field="width_m" value="${rec.width_m}" ${readonly?'disabled':''}></label><label>Tiefe (m)<input type="number" min="0.02" step="0.01" data-field="depth_m" value="${rec.depth_m}" ${readonly?'disabled':''}></label><label>Höhe (m)<input type="number" min="0.02" step="0.01" data-field="height_m" value="${rec.height_m}" ${readonly?'disabled':''}></label><label>Drehung °<input type="number" step="1" data-field="rotation_deg" value="${rec.rotation_deg||0}" ${readonly?'disabled':''}></label></div>
  <div class="rp-form-grid"><label>X (m)<input type="number" step="0.01" data-field="x_m" value="${rec.x_m}" ${readonly||rec.anchor==='wall'&&['left','right'].includes(rec.wall)?'disabled':''}></label><label>Z (m)<input type="number" step="0.01" data-field="z_m" value="${rec.z_m}" ${readonly||rec.anchor==='wall'&&['back','front'].includes(rec.wall)?'disabled':''}></label><label>Höhe über Boden<input type="number" step="0.01" min="0" data-field="elevation_m" value="${rec.elevation_m||0}" ${readonly?'disabled':''}></label><label>Farbe<input type="color" data-field="color" value="${safeColor(rec.color)}" ${readonly?'disabled':''}></label></div>
  <div class="rp-form-grid"><label>Verankerung<select data-field="anchor" ${readonly?'disabled':''}><option value="floor" ${rec.anchor==='floor'?'selected':''}>Boden</option><option value="wall" ${rec.anchor==='wall'?'selected':''}>Wand</option></select></label>${rec.anchor==='wall'?`<label>Wand<select data-field="wall" ${readonly?'disabled':''}>${wallOpts}</select></label>`:''}<label class="rp-check"><input type="checkbox" data-field="locked" ${rec.locked?'checked':''} ${readonly?'disabled':''}> Position sperren</label></div>
  <div class="rp-distance-card"><strong>Live-Abstände</strong><div><span>Links<b>${metric(d.left)}</b></span><span>Rechts<b>${metric(d.right)}</b></span><span>Hinten<b>${metric(d.back)}</b></span><span>Vorne<b>${metric(d.front)}</b></span></div><p>Nächstes Objekt: <b>${d.nearest===null?'—':`${metric(d.nearest)} · ${escapeHtml(d.nearestLabel)}`}</b></p></div>
  ${rec.source==='ai_photo'?`<div class="rp-ai-evidence"><strong>KI-Erkennung ${rec.confidence?`· ${Math.round(rec.confidence*100)} %`:''}</strong><p>${escapeHtml(rec.evidence||'Aus Fotos erkannt. Position und Maße bitte prüfen.')}</p></div>`:''}`;
  bindInspectorInputs(rec);
}
function renderOpeningInspector(rec){
  const max=wallLength(rec.wall); inspector.innerHTML=`<div class="rp-inspector-head"><div><span>${rec.kind==='window'?'Fenster':'Tür / Öffnung'}</span><strong>${escapeHtml(rec.label|| (rec.kind==='window'?'Fenster':'Tür'))}</strong></div>${readonly?'':`<button type="button" data-rp-delete>⌫</button>`}</div>
  <label>Wand<select data-field="wall" ${readonly?'disabled':''}>${['back','front','left','right'].map(w=>`<option value="${w}" ${rec.wall===w?'selected':''}>${wallLabel(w)}</option>`).join('')}</select></label>
  <div class="rp-form-grid"><label>Abstand vom Wandanfang<input type="number" min="0" max="${max}" step="0.01" data-field="offset_m" value="${rec.offset_m}" ${readonly?'disabled':''}></label><label>Breite<input type="number" min="0.2" step="0.01" data-field="width_m" value="${rec.width_m}" ${readonly?'disabled':''}></label><label>Höhe<input type="number" min="0.2" step="0.01" data-field="height_m" value="${rec.height_m}" ${readonly?'disabled':''}></label><label>Brüstungshöhe<input type="number" min="0" step="0.01" data-field="sill_height_m" value="${rec.sill_height_m||0}" ${readonly||rec.kind==='door'?'disabled':''}></label></div>
  <div class="rp-distance-card"><strong>Wandposition</strong><p>Links / Anfang: <b>${metric(rec.offset_m)}</b> · Rechts / Ende: <b>${metric(Math.max(0,max-rec.offset_m-rec.width_m))}</b></p></div>
  ${rec.source==='ai_photo'?`<div class="rp-ai-evidence"><strong>KI-Erkennung ${rec.confidence?`· ${Math.round(rec.confidence*100)} %`:''}</strong><p>${escapeHtml(rec.evidence||'Aus Fotos erkannt.')}</p></div>`:''}`;bindInspectorInputs(rec);
}
function bindInspectorInputs(rec){
  $$('[data-field]',inspector).forEach((el)=>el.addEventListener('change',()=>{let value=el.type==='checkbox'?el.checked:el.type==='number'?Number(el.value):el.value;rec[el.dataset.field]=value;if(rec.anchor==='wall'&&!rec.wall)rec.wall='back';if(selectedKind==='opening'){rec.offset_m=clamp(rec.offset_m,0,Math.max(0,wallLength(rec.wall)-rec.width_m));rec.sill_height_m=clamp(rec.sill_height_m||0,0,state.room.height_m);rec.height_m=clamp(rec.height_m,.2,Math.max(.2,state.room.height_m-rec.sill_height_m));} else constrainObject(rec);markDirty();pushHistory();rebuildScene();select(rec.id,selectedKind,{skipScene:true});}));
  $('[data-rp-delete]',inspector)?.addEventListener('click',()=>{if(readonly)return;if(selectedKind==='opening')state.openings=state.openings.filter(o=>o.id!==rec.id);else state.objects=state.objects.filter(o=>o.id!==rec.id);select(null,null);markDirty();pushHistory();rebuildScene();});
  $('[data-rp-duplicate]',inspector)?.addEventListener('click',()=>{if(readonly||selectedKind!=='object')return;const clone=deepClone(rec);clone.id=uid('obj');clone.label=`${clone.label||labelForKind(clone.kind)} Kopie`;clone.x_m+=.15;clone.z_m+=.15;clone.source='manual';clone.confidence=null;clone.evidence='';constrainObject(clone);state.objects.push(clone);markDirty();pushHistory();rebuildScene();select(clone.id,'object',{skipScene:true});});
}

function addObject(kind){if(readonly)return;const [w,d,h]=defaultSize(kind);const wall=wallOnlyKinds.has(kind);const o={id:uid('obj'),kind,label:labelForKind(kind),anchor:wall?'wall':'floor',wall:wall?'back':null,x_m:state.room.width_m/2,z_m:state.room.length_m/2,elevation_m:wall?0.8:0,width_m:w,depth_m:d,height_m:h,rotation_deg:0,color:defaultColor(kind),enabled:true,locked:false,source:'manual',confidence:null,evidence:''}; if(wall)o.elevation_m=Math.min(.9,Math.max(0,state.room.height_m-h));constrainObject(o);state.objects.push(o);markDirty();pushHistory();rebuildScene();select(o.id,'object',{skipScene:true});}
function addOpening(kind){if(readonly)return;const width=kind==='window'?1.2:.9,height=kind==='window'?1.1:2.05;const o={id:uid('opening'),kind,label:kind==='window'?'Fenster':'Tür',wall:'back',offset_m:Math.max(0,(state.room.width_m-width)/2),width_m:width,height_m:Math.min(height,state.room.height_m),sill_height_m:kind==='window'?Math.min(.9,Math.max(0,state.room.height_m-height)):0,enabled:true,locked:false,source:'manual'};state.openings.push(o);markDirty();pushHistory();rebuildScene();select(o.id,'opening',{skipScene:true});}

function syncControlsFromState(){
  const r=state.room;
  ['length_m','width_m','height_m','wall_thickness_m'].forEach((field)=>{const el=$(`[data-rp-room-field="${field}"]`,root);if(el)el.value=r[field];});
  $('[data-rp-toggle="grid"]',root)?.classList.toggle('is-active',Boolean(state.view.grid));
  $('[data-rp-toggle="snap"]',root)?.classList.toggle('is-active',Boolean(state.view.snap));
  $('[data-rp-toggle="transparent_near_walls"]',root)?.classList.toggle('is-active',Boolean(state.view.transparent_near_walls));
  $('[data-rp-toggle="show_ceiling"]',root)?.classList.toggle('is-active',Boolean(state.view.show_ceiling));
  $$('[data-rp-view]',root).forEach((b)=>b.classList.toggle('is-active',b.dataset.rpView===state.view.mode));
}
function bindUi(){
  $$('[data-rp-add-object]',root).forEach(b=>b.addEventListener('click',()=>addObject(b.dataset.rpAddObject)));
  $$('[data-rp-add-opening]',root).forEach(b=>b.addEventListener('click',()=>addOpening(b.dataset.rpAddOpening)));
  $$('[data-rp-room-field]',root).forEach(el=>el.addEventListener('change',()=>{const field=el.dataset.rpRoomField;state.room[field]=Number(el.value);state.room.width_m=clamp(state.room.width_m,1,30);state.room.length_m=clamp(state.room.length_m,1,30);state.room.height_m=clamp(state.room.height_m,1.8,8);state.room.wall_thickness_m=clamp(state.room.wall_thickness_m,.05,.8);state.objects.forEach(constrainObject);state.openings.forEach(o=>{o.offset_m=clamp(o.offset_m,0,Math.max(0,wallLength(o.wall)-o.width_m));o.height_m=clamp(o.height_m,.2,Math.max(.2,state.room.height_m-(o.sill_height_m||0)));});markDirty();pushHistory();rebuildScene({keepCamera:false});renderInspector();}));
  $$('[data-rp-view]',root).forEach(b=>b.addEventListener('click',()=>setView(b.dataset.rpView)));
  $('[data-rp-toggle="grid"]',root)?.addEventListener('click',()=>{state.view.grid=!state.view.grid;markDirty();syncControlsFromState();if(gridHelper)gridHelper.visible=state.view.grid;queueRender();});
  $('[data-rp-toggle="snap"]',root)?.addEventListener('click',()=>{state.view.snap=!state.view.snap;markDirty();syncControlsFromState();});
  $('[data-rp-toggle="transparent_near_walls"]',root)?.addEventListener('click',()=>{state.view.transparent_near_walls=!state.view.transparent_near_walls;markDirty();syncControlsFromState();updateWallTransparency();queueRender();});
  $('[data-rp-toggle="show_ceiling"]',root)?.addEventListener('click',()=>{state.view.show_ceiling=!state.view.show_ceiling;markDirty();syncControlsFromState();rebuildScene();});
  $('[data-rp-fit]',root)?.addEventListener('click',fitCamera);
  $('[data-rp-fullscreen]',root)?.addEventListener('click',()=>root.requestFullscreen?.());
  $('[data-rp-undo]',root)?.addEventListener('click',()=>restoreHistory(historyIndex-1));$('[data-rp-redo]',root)?.addEventListener('click',()=>restoreHistory(historyIndex+1));
  saveButtons.forEach((b)=>b.addEventListener('click',saveState));
  $$('[data-rp-open-vision]',root).forEach((b)=>b.addEventListener('click',()=>visionDialog?.showModal()));$$('[data-rp-close-vision]',root).forEach(b=>b.addEventListener('click',()=>visionDialog?.close()));
  cameraInput?.addEventListener('change',()=>{addVisionFiles(cameraInput.files);cameraInput.value='';}); galleryInput?.addEventListener('change',()=>{addVisionFiles(galleryInput.files);galleryInput.value='';}); clearPhotosButton?.addEventListener('click',clearVisionFiles); $('[data-rp-run-vision]',root)?.addEventListener('click',runVision);
  canvas.addEventListener('pointerdown',pointerDownHandler);canvas.addEventListener('pointermove',pointerMoveHandler);canvas.addEventListener('pointerup',pointerUpHandler);canvas.addEventListener('pointercancel',pointerUpHandler);
  window.addEventListener('keydown',(ev)=>{if(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName))return;if((ev.ctrlKey||ev.metaKey)&&ev.key.toLowerCase()==='z'){ev.preventDefault();restoreHistory(historyIndex+(ev.shiftKey?1:-1));return;}if(readonly)return;const rec=selectedRecord();if(!rec)return;if((ev.key==='Delete'||ev.key==='Backspace')){$('[data-rp-delete]',inspector)?.click();}if(selectedKind==='object'&&(ev.key.toLowerCase()==='q'||ev.key.toLowerCase()==='e')){rec.rotation_deg=(rec.rotation_deg||0)+(ev.key.toLowerCase()==='q'?-5:5);constrainObject(rec);markDirty();pushHistory();rebuildScene();select(rec.id,'object',{skipScene:true});}});
  window.addEventListener('resize',resize);
  window.addEventListener('beforeunload',(e)=>{if(dirty){e.preventDefault();e.returnValue='';}});
}

function setView(mode){state.view.mode=mode;syncControlsFromState();const w=state.room.width_m,l=state.room.length_m,h=state.room.height_m;if(mode==='top'){camera.up.set(0,0,-1);camera.position.set(w/2,Math.max(w,l)*1.55+2,l/2);controls.target.set(w/2,0,l/2);controls.enableRotate=false;} else if(mode==='front'){camera.up.set(0,1,0);camera.position.set(w/2,h*.52,l+Math.max(w,l)*1.35+1);controls.target.set(w/2,h*.5,l/2);controls.enableRotate=false;} else {camera.up.set(0,1,0);controls.enableRotate=true;camera.position.set(w+2.5,h+1.4,l+2.8);controls.target.set(w/2,h*.42,l/2);}controls.update();updateWallTransparency();markDirty();queueRender();}
function fitCamera(){const w=state.room.width_m,l=state.room.length_m,h=state.room.height_m;if(state.view.mode==='top')setView('top');else if(state.view.mode==='front')setView('front');else{camera.up.set(0,1,0);controls.enableRotate=true;const s=Math.max(w,l,h);camera.position.set(w/2+s*.85,h*.58+s*.58,l/2+s*.95);controls.target.set(w/2,h*.42,l/2);controls.update();queueRender();}}
function wallLength(wall){return (wall==='back'||wall==='front')?state.room.width_m:state.room.length_m;}
function wallLabel(w){return ({back:'Rückwand',front:'Vorderwand',left:'Linke Wand',right:'Rechte Wand'})[w]||w;}

async function saveState(){if(readonly)return;saveButtons.forEach(b=>b.disabled=true);saveStatus.textContent='Speichert…';try{const notes=$('[data-rp-version-label]',root)?.value||'';const res=await fetch(root.dataset.saveUrl,{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest','Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({measurement_id:root.dataset.measurementId||null,state,label:notes})});const data=await readJson(res,'Speichern fehlgeschlagen. Bitte Seite neu laden.');root.dataset.measurementId=String(data.measurement_id);dirty=false;saveStatus.textContent=`Gespeichert · Version ${data.revision}`;saveStatus.dataset.state='saved';if(history.length===0)history=[deepClone(state)];toast('Raumplanung gespeichert.','success');}catch(err){saveStatus.textContent='Speichern fehlgeschlagen';toast(err.message,'error');}finally{saveButtons.forEach(b=>b.disabled=false);}}

function fileKey(f){return `${f.name}:${f.size}:${f.lastModified}`;}
function addVisionFiles(list){const ok=new Set(['image/jpeg','image/png','image/webp']);let rejected=false;[...(list||[])].forEach(f=>{if(!ok.has(f.type)){rejected=true;return;}if(f.size>12*1024*1024){toast(`${f.name}: Das Foto ist größer als 12 MB.`,'error');return;}if(selectedVisionFiles.some(x=>fileKey(x)===fileKey(f)))return;if(selectedVisionFiles.length>=12){rejected=true;return;}selectedVisionFiles.push(f);});if(rejected)toast(selectedVisionFiles.length>=12?'Es können maximal 12 Fotos ausgewählt werden.':'Ein Dateiformat wird nicht unterstützt.','error');renderFilePreviews();}
function clearVisionFiles(){selectedVisionFiles=[];previewObjectUrls.forEach(URL.revokeObjectURL);previewObjectUrls=[];if(filePreview)filePreview.innerHTML='';if(photoCount)photoCount.textContent='0 / 12 Fotos ausgewählt';if(clearPhotosButton)clearPhotosButton.disabled=true;}
function renderFilePreviews(){if(!filePreview)return;previewObjectUrls.forEach(URL.revokeObjectURL);previewObjectUrls=[];filePreview.innerHTML='';selectedVisionFiles.forEach((f,i)=>{const card=document.createElement('div');card.className='rp-photo-preview';const img=document.createElement('img');const url=URL.createObjectURL(f);previewObjectUrls.push(url);img.src=url;img.alt=`Vorschau Foto ${i+1}`;const meta=document.createElement('span');meta.textContent=`Foto ${i+1}`;const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label',`Foto ${i+1} entfernen`);remove.onclick=()=>{selectedVisionFiles.splice(i,1);renderFilePreviews();};card.append(img,meta,remove);filePreview.appendChild(card);});if(photoCount)photoCount.textContent=`${selectedVisionFiles.length} / 12 Fotos ausgewählt`;if(clearPhotosButton)clearPhotosButton.disabled=!selectedVisionFiles.length;}
function germanRequestError(err,fallback){const raw=String(err?.message||'');if(/Failed to fetch|NetworkError|Load failed|fetch failed/i.test(raw))return 'Netzwerkfehler. Bitte Internetverbindung prüfen und erneut versuchen.';if(/Unexpected token|not valid JSON|JSON/i.test(raw))return fallback;return raw||fallback;}
async function readJson(res,fallback){if(res.redirected&&new URL(res.url,location.href).pathname.includes('/login'))throw new Error('Deine Sitzung ist abgelaufen. Bitte neu anmelden.');const type=(res.headers.get('content-type')||'').toLowerCase();const raw=await res.text();if(!type.includes('application/json')){if(res.status===413)throw new Error('Die ausgewählten Fotos sind zusammen zu groß. Bitte weniger oder kleinere Fotos verwenden.');if(res.status===403)throw new Error('Die Anfrage wurde aus Sicherheitsgründen abgelehnt. Bitte Seite neu laden.');if(res.status>=500)throw new Error('Die Raumerkennung ist momentan nicht erreichbar. Bitte später erneut versuchen.');throw new Error(fallback);}let data;try{data=raw?JSON.parse(raw):{};}catch(_){throw new Error(fallback);}if(!res.ok)throw new Error(data.error||fallback);return data;}
async function runVision(ev){ev.preventDefault();if(visionStatus)visionStatus.hidden=false;const files=selectedVisionFiles.slice(0,12);if(!files.length){visionStatus.textContent='Bitte mindestens ein Foto aufnehmen oder aus der Galerie auswählen.';return;}if(files.reduce((sum,f)=>sum+f.size,0)>50*1024*1024){visionStatus.textContent='Die ausgewählten Fotos sind zusammen größer als 50 MB.';return;}const submit=$('[data-rp-run-vision]',visionForm);submit.disabled=true;visionStatus.textContent='KI analysiert Raum, Wände und Objekte…';const fd=new FormData();files.slice(0,12).forEach(f=>fd.append('images',f));fd.append('measurement_id',root.dataset.measurementId||'');const kl=Number($('[data-rp-known-length]',visionForm)?.value||0),kw=Number($('[data-rp-known-width]',visionForm)?.value||0),kh=Number($('[data-rp-known-height]',visionForm)?.value||0),known=[kl,kw,kh],anyKnown=known.some(v=>v>0),allKnown=known.every(v=>Number.isFinite(v)&&v>0);if(anyKnown&&!allKnown){visionStatus.textContent='Wenn Raummaße bekannt sind, bitte Länge/Tiefe, Breite und Höhe vollständig eintragen.';submit.disabled=false;return;}const visionState=deepClone(state);if(allKnown){visionState.room.length_m=clamp(kl,1,30);visionState.room.width_m=clamp(kw,1,30);visionState.room.height_m=clamp(kh,1.8,8);fd.append('known_room_dimensions','1');}fd.append('state',JSON.stringify(visionState));const refType=$('[data-rp-reference-type]',visionForm)?.value||'';fd.append('reference_type',refType);fd.append('reference_width_cm',$('[data-rp-reference-width]',visionForm)?.value||'');fd.append('reference_height_cm',$('[data-rp-reference-height]',visionForm)?.value||'');fd.append('capture_sequence','entrance,opposite,left,right');try{const res=await fetch(root.dataset.visionUrl,{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf()},body:fd});const data=await readJson(res,'Die Raumerkennung hat eine unerwartete Serverantwort erhalten. Bitte Seite neu laden und erneut versuchen.');state=normalizeState(data.state);root.dataset.measurementId=String(data.measurement_id);history=[deepClone(state)];historyIndex=0;dirty=false;saveStatus.textContent='KI-Entwurf gespeichert';saveStatus.dataset.state='saved';syncControlsFromState();rebuildScene({keepCamera:false});renderInspector();visionStatus.innerHTML=`<strong>${escapeHtml(data.summary||'Analyse abgeschlossen.')}</strong>${(data.warnings||[]).length?`<ul>${data.warnings.map(w=>`<li>${escapeHtml(w)}</li>`).join('')}</ul>`:''}<p>${data.scale_verified?'Maßstab verifiziert.':'Positionen wurden relativ rekonstruiert. Für exakte Maße bitte Referenzmaß oder Scan verwenden.'}</p>`;toast(`${data.recognized_objects||0} Objekte und ${data.recognized_openings||0} Öffnungen erkannt.`,'success');clearVisionFiles();setTimeout(()=>visionDialog?.close(),1600);}catch(err){const message=germanRequestError(err,'Die Raumerkennung konnte nicht abgeschlossen werden. Bitte Seite neu laden und erneut versuchen.');visionStatus.textContent=message;toast(message,'error');}finally{submit.disabled=false;}}

function updateStats(){
  const area=state.room.width_m*state.room.length_m;
  const wallArea=2*(state.room.width_m+state.room.length_m)*state.room.height_m;
  const openings=state.openings.filter(o=>o.enabled!==false); const objects=state.objects.filter(o=>o.enabled!==false);
  const set=(sel,text)=>{const el=$(sel,root);if(el)el.textContent=text;};
  set('[data-rp-room-size]',`${state.room.length_m.toFixed(2)} × ${state.room.width_m.toFixed(2)} × ${state.room.height_m.toFixed(2)} m`);
  set('[data-rp-object-count]',`${objects.length} Objekte`);
  set('[data-rp-scale-state]',state.calibration.scale_verified?'Maßstab verifiziert':'Maßstab prüfen');
  set('[data-rp-calc="floor"]',`${area.toFixed(2)} m²`);set('[data-rp-calc="wall"]',`${wallArea.toFixed(2)} m²`);set('[data-rp-calc="openings"]',String(openings.length));set('[data-rp-calc="objects"]',String(objects.length));
  set('[data-rp-selection-summary]',selected?(selectedRecord()?.label||labelForKind(selectedRecord()?.kind)):'Nichts ausgewählt');
}
function resize(){const r=canvas.parentElement.getBoundingClientRect();const w=Math.max(320,r.width),h=Math.max(360,r.height);renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();queueRender();}
function queueRender(){renderQueued=true;}
function animate(){requestAnimationFrame(animate);controls.update();if(renderQueued||controls.enabled){renderer.render(scene,camera);renderQueued=false;}}
function toast(message,type='info'){let el=$('.rp-toast');if(!el){el=document.createElement('div');el.className='rp-toast';document.body.appendChild(el);}el.textContent=message;el.dataset.type=type;el.classList.add('show');clearTimeout(el._t);el._t=setTimeout(()=>el.classList.remove('show'),3000);}
function escapeHtml(v){return String(v??'').replace(/[&<>'"]/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
function escapeAttr(v){return escapeHtml(v);}
function safeColor(v){return /^#[0-9a-f]{6}$/i.test(v||'')?v:'#c7ccd3';}

try {
  bindUi();syncControlsFromState();rebuildScene({keepCamera:false});renderInspector();resize();updateUndoRedo();loading.hidden=true;engineError.hidden=true;canvas.dataset.ready='1';root.dataset.engine=KAYI_ROOM_PLANNER_PRO;animate();
} catch (err) {
  console.error('A+Bau Room Planner Pro failed', err);loading.hidden=true;engineError.hidden=false;const msg=engineError.querySelector('span');if(msg)msg.textContent=err.message||'3D-Engine konnte nicht initialisiert werden.';
}

// A+Bau 3D KI assistant polish 20260810
(() => {
  // The 3D room must stay readable from every camera angle. Keep every wall
  // translucent in every view and remove the old on/off control so saved
  // state, KI drafts and photo reconstructions cannot make walls opaque again.
  const forceAlwaysTransparentWalls = () => {
    state.view ||= {};
    state.view.transparent_near_walls = true;
    wallMeshes.forEach((wall) => {
      if (!wall?.material) return;
      wall.material.transparent = true;
      wall.material.opacity = 0.22;
      wall.material.depthWrite = false;
      wall.material.needsUpdate = true;
    });
  };
  updateWallTransparency = forceAlwaysTransparentWalls;
  $('[data-rp-toggle="transparent_near_walls"]', root)?.remove();
  forceAlwaysTransparentWalls();
  queueRender();

  const commandInput = $('[data-rp-ai-command]', root);
  const runButton = $('[data-rp-run-ai]', root);
  const feedback = $('[data-rp-ai-feedback]', root);
  if (!commandInput || !runButton || !root.dataset.aiUrl) return;

  const safeMessage = (error, fallback) => {
    const raw = String(error?.message || '');
    if (/Failed to fetch|NetworkError|Load failed|fetch failed/i.test(raw)) {
      return 'Netzwerkfehler. Bitte Internetverbindung prüfen und erneut versuchen.';
    }
    return raw || fallback;
  };

  const requestJson = async (url, options, fallback) => {
    const response = await fetch(url, {
      credentials: 'same-origin',
      ...options,
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        ...(options?.headers || {}),
      },
    });
    const contentType = (response.headers.get('content-type') || '').toLowerCase();
    const raw = await response.text();
    if (!contentType.includes('application/json')) {
      if (response.status === 403) throw new Error('Sicherheitsprüfung fehlgeschlagen. Bitte Seite einmal neu laden und erneut versuchen.');
      if (response.status === 429) throw new Error('Zu viele KI-Anfragen. Bitte kurz warten und erneut versuchen.');
      if (response.status >= 500) throw new Error('Der KI-Raumassistent ist momentan nicht erreichbar. Bitte später erneut versuchen.');
      throw new Error(fallback);
    }
    let data = {};
    try { data = raw ? JSON.parse(raw) : {}; } catch (_) { throw new Error(fallback); }
    if (!response.ok) {
      const error = new Error(data.error || fallback);
      error.consentRequired = response.status === 428 && Boolean(data.consent_required);
      error.settingsUrl = data.settings_url || '/settings/next/';
      throw error;
    }
    return data;
  };

  const setFeedback = (message, stateName = '') => {
    if (!feedback) return;
    feedback.hidden = false;
    feedback.dataset.state = stateName;
    feedback.innerHTML = message;
  };

  $$('[data-rp-ai-example]', root).forEach((button) => {
    button.addEventListener('click', () => {
      commandInput.value = button.dataset.rpAiExample || button.textContent.trim();
      commandInput.focus();
    });
  });

  runButton.addEventListener('click', async () => {
    const command = commandInput.value.trim();
    if (!command) {
      setFeedback('<strong>Anweisung fehlt.</strong>Beschreibe kurz, was die KI im Raum ändern soll.', 'error');
      commandInput.focus();
      return;
    }
    runButton.disabled = true;
    setFeedback('<strong>KI arbeitet am Raum …</strong>Bestehende Objekte werden berücksichtigt und nicht erwähnte Elemente bleiben erhalten.', 'loading');
    try {
      const data = await requestJson(root.dataset.aiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf(),
        },
        body: JSON.stringify({
          measurement_id: root.dataset.measurementId || null,
          command,
          state,
        }),
      }, 'Der KI-Vorschlag konnte nicht verarbeitet werden.');

      state = normalizeState(data.state || state);
      history = history.slice(0, historyIndex + 1);
      history.push(deepClone(state));
      historyIndex = history.length - 1;
      dirty = true;
      syncControlsFromState();
      rebuildScene({ keepCamera: true });
      renderInspector();
      updateUndoRedo();
      if (saveStatus) {
        saveStatus.textContent = 'KI-Vorschlag noch nicht gespeichert';
        saveStatus.dataset.state = 'dirty';
      }
      const warnings = Array.isArray(data.warnings) && data.warnings.length
        ? `<ul>${data.warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
        : '';
      setFeedback(`<strong>${escapeHtml(data.summary || 'KI-Vorschlag angewendet.')}</strong>${warnings}<small>Prüfe den Vorschlag im 3D-Raum und speichere anschließend bewusst eine neue Version.</small>`, 'success');
      toast('KI-Vorschlag im 3D-Raum angewendet.','success');
    } catch (error) {
      const message = safeMessage(error, 'Der KI-Raumassistent konnte die Änderung nicht ausführen.');
      if (error?.consentRequired) {
        const settingsUrl = String(error.settingsUrl || '/settings/next/').replace(/"/g, '&quot;');
        setFeedback(`<strong>Einwilligung erforderlich.</strong>${escapeHtml(message)}<br><a class="nx-btn" style="margin-top:8px" href="${settingsUrl}">KI-Einwilligung in den Einstellungen öffnen →</a>`, 'error');
      } else {
        setFeedback(`<strong>KI konnte die Änderung nicht anwenden.</strong>${escapeHtml(message)}`, 'error');
      }
      toast(message, 'error');
    } finally {
      runButton.disabled = false;
    }
  });
})();

// A+Bau always-transparent walls runtime hotfix 20260815
(() => {
  const forceAlwaysTransparentWalls = () => {
    state.view ||= {};
    state.view.transparent_near_walls = true;
    wallMeshes.forEach((wall) => {
      const mat = wall?.material;
      if (!mat) return;
      mat.transparent = true;
      mat.opacity = 0.08;
      mat.depthWrite = false;
      mat.side = THREE.DoubleSide;
      if (mat.color?.setHex) mat.color.setHex(0xf5f6f7);
      mat.needsUpdate = true;
    });
  };

  // Override every older camera-dependent wall visibility rule.
  updateWallTransparency = forceAlwaysTransparentWalls;
  forceAlwaysTransparentWalls();
  document.querySelector('[data-rp-toggle="transparent_near_walls"]')?.remove();
  queueRender();
})();

// A+Bau premium room object visuals 20260815
(() => {
  const legacyCreateObjectMesh = createObjectMesh;

  const physical = (color, opts = {}) => new THREE.MeshPhysicalMaterial({
    color,
    roughness: opts.roughness ?? 0.38,
    metalness: opts.metalness ?? 0.02,
    clearcoat: opts.clearcoat ?? 0.18,
    clearcoatRoughness: opts.clearcoatRoughness ?? 0.3,
    transparent: Boolean(opts.transparent),
    opacity: opts.opacity ?? 1,
    transmission: opts.transmission ?? 0,
    thickness: opts.thickness ?? 0,
    ior: opts.ior ?? 1.45,
    side: opts.side ?? THREE.FrontSide,
  });

  const ceramic = physical(0xf8fafb, { roughness: 0.19, clearcoat: 0.72, clearcoatRoughness: 0.16 });
  const porcelainShadow = physical(0xd8dde0, { roughness: 0.28, clearcoat: 0.4 });
  const chromePremium = physical(0xbfc7cd, { roughness: 0.12, metalness: 0.92, clearcoat: 0.85, clearcoatRoughness: 0.08 });
  const brushedMetal = physical(0x9ea8af, { roughness: 0.3, metalness: 0.82, clearcoat: 0.26 });
  const darkPremium = physical(0x323940, { roughness: 0.31, metalness: 0.22, clearcoat: 0.28 });
  const glassPremium = physical(0xd8f0f6, {
    roughness: 0.06,
    metalness: 0,
    transparent: true,
    opacity: 0.28,
    transmission: 0.62,
    thickness: 0.012,
    clearcoat: 0.9,
    clearcoatRoughness: 0.05,
    side: THREE.DoubleSide,
  });
  const waterShadow = physical(0xb9d7df, { roughness: 0.18, transparent: true, opacity: 0.62, clearcoat: 0.5 });

  function finish(mesh) {
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  }

  function roundedPrism(w, h, d, radius, mat, bevel = 0.012) {
    w = Math.max(0.01, Number(w));
    h = Math.max(0.01, Number(h));
    d = Math.max(0.01, Number(d));
    const r = Math.max(0.002, Math.min(Number(radius || 0), w * 0.48, h * 0.48));
    if (r <= 0.003) return finish(new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat));
    const x = -w / 2, y = -h / 2;
    const shape = new THREE.Shape();
    shape.moveTo(x + r, y);
    shape.lineTo(x + w - r, y);
    shape.quadraticCurveTo(x + w, y, x + w, y + r);
    shape.lineTo(x + w, y + h - r);
    shape.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    shape.lineTo(x + r, y + h);
    shape.quadraticCurveTo(x, y + h, x, y + h - r);
    shape.lineTo(x, y + r);
    shape.quadraticCurveTo(x, y, x + r, y);
    const b = Math.min(Math.max(0, bevel), d * 0.18, r * 0.45);
    const geometry = new THREE.ExtrudeGeometry(shape, {
      depth: Math.max(0.006, d - b * 2),
      bevelEnabled: b > 0.001,
      bevelSegments: 2,
      steps: 1,
      bevelSize: b,
      bevelThickness: b,
      curveSegments: 8,
    });
    geometry.translate(0, 0, -d / 2 + b);
    geometry.computeVertexNormals();
    return finish(new THREE.Mesh(geometry, mat));
  }

  function sphere(w, h, d, mat, seg = 32) {
    const m = finish(new THREE.Mesh(new THREE.SphereGeometry(0.5, seg, Math.max(16, Math.round(seg * 0.6))), mat));
    m.scale.set(w, h, d);
    return m;
  }

  function torus(major, tube, mat, scaleZ = 1) {
    const m = finish(new THREE.Mesh(new THREE.TorusGeometry(Math.max(0.006, major), Math.max(0.003, tube), 12, 48), mat));
    m.rotation.x = Math.PI / 2;
    m.scale.z = scaleZ;
    return m;
  }

  function premiumCylinder(radius, height, mat, segments = 36) {
    return finish(new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, height, segments), mat));
  }

  function add(g, mesh, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0) {
    mesh.position.set(x, y, z);
    mesh.rotation.x += rx;
    mesh.rotation.y += ry;
    mesh.rotation.z += rz;
    g.add(mesh);
    return mesh;
  }

  function faucet(g, w, d, h, x = 0, z = 0) {
    const stemH = Math.max(0.1, Math.min(0.28, h * 0.36));
    const stemR = Math.max(0.008, Math.min(0.018, w * 0.025));
    add(g, premiumCylinder(stemR, stemH, chromePremium, 24), x, h / 2 - stemH * 0.55, z);
    const spout = premiumCylinder(stemR * 0.86, Math.max(0.08, d * 0.22), chromePremium, 24);
    add(g, spout, x, h / 2 - stemH * 0.1, z + Math.max(0.035, d * 0.08), Math.PI / 2, 0, 0);
    add(g, sphere(stemR * 3.2, stemR * 1.7, stemR * 3.2, chromePremium, 20), x, h / 2 - stemH * 0.05, z - stemR * 1.6);
  }

  function buildToilet(o) {
    const g = new THREE.Group();
    const w = o.width_m, d = o.depth_m, h = o.height_m;
    const baseH = h * 0.25;
    add(g, roundedPrism(w * 0.48, baseH, d * 0.55, Math.min(w, d) * 0.12, porcelainShadow), 0, -h / 2 + baseH / 2, d * 0.06);
    add(g, sphere(w * 0.82, h * 0.24, d * 0.72, ceramic), 0, -h * 0.17, d * 0.09);
    add(g, sphere(w * 0.63, h * 0.12, d * 0.54, physical(0xe7ecef, { roughness: 0.24, clearcoat: 0.42 })), 0, -h * 0.08, d * 0.12);
    const seat = torus(w * 0.27, Math.max(0.015, w * 0.038), ceramic, 1.3);
    seat.scale.x = 1.05;
    add(g, seat, 0, h * 0.01, d * 0.13);
    add(g, roundedPrism(w * 0.86, h * 0.46, d * 0.22, Math.min(w, h) * 0.08, ceramic), 0, h * 0.18, -d * 0.34);
    add(g, roundedPrism(w * 0.68, h * 0.035, d * 0.2, 0.018, ceramic, 0.005), 0, h * 0.43, -d * 0.34);
    add(g, premiumCylinder(Math.max(0.011, w * 0.035), 0.012, chromePremium, 24), w * 0.17, h * 0.44, -d * 0.34, Math.PI / 2, 0, 0);
    return g;
  }

  function buildBathtub(o) {
    const g = new THREE.Group();
    const w = o.width_m, d = o.depth_m, h = o.height_m;
    const bodyH = h * 0.76;
    add(g, roundedPrism(w, bodyH, d, Math.min(w, d) * 0.13, ceramic, 0.018), 0, -h / 2 + bodyH / 2, 0);
    add(g, roundedPrism(w * 0.86, h * 0.12, d * 0.72, Math.min(w, d) * 0.16, porcelainShadow, 0.01), 0, h * 0.24, 0);
    add(g, roundedPrism(w * 0.8, h * 0.055, d * 0.64, Math.min(w, d) * 0.14, waterShadow, 0.006), 0, h * 0.285, 0);
    const rimH = Math.max(0.035, h * 0.075);
    const rimT = Math.max(0.035, Math.min(0.065, d * 0.08));
    add(g, roundedPrism(w, rimH, rimT, rimH * 0.45, ceramic, 0.006), 0, h * 0.36, -d / 2 + rimT / 2);
    add(g, roundedPrism(w, rimH, rimT, rimH * 0.45, ceramic, 0.006), 0, h * 0.36, d / 2 - rimT / 2);
    add(g, roundedPrism(rimT, rimH, d - rimT * 2, rimH * 0.45, ceramic, 0.006), -w / 2 + rimT / 2, h * 0.36, 0);
    add(g, roundedPrism(rimT, rimH, d - rimT * 2, rimH * 0.45, ceramic, 0.006), w / 2 - rimT / 2, h * 0.36, 0);
    add(g, premiumCylinder(Math.max(0.012, w * 0.011), Math.max(0.12, h * 0.28), chromePremium, 24), w * 0.34, h * 0.37, -d * 0.37);
    const spout = premiumCylinder(Math.max(0.01, w * 0.009), Math.max(0.08, d * 0.18), chromePremium, 24);
    add(g, spout, w * 0.34, h * 0.47, -d * 0.3, Math.PI / 2, 0, 0);
    add(g, premiumCylinder(Math.max(0.018, d * 0.04), 0.012, chromePremium, 28), 0, h * 0.318, d * 0.12, Math.PI / 2, 0, 0);
    return g;
  }

  function buildShower(o) {
    const g = new THREE.Group();
    const w = o.width_m, d = o.depth_m, h = o.height_m;
    const trayH = Math.min(0.11, h * 0.08);
    add(g, roundedPrism(w, trayH, d, Math.min(w, d) * 0.06, ceramic, 0.01), 0, -h / 2 + trayH / 2, 0);
    add(g, roundedPrism(w * 0.9, 0.018, d * 0.9, Math.min(w, d) * 0.05, porcelainShadow, 0.002), 0, -h / 2 + trayH + 0.006, 0);
    const glassH = h * 0.88;
    const glassY = -h / 2 + trayH + glassH / 2;
    add(g, roundedPrism(0.012, glassH, d * 0.98, 0.004, glassPremium, 0), -w / 2 + 0.006, glassY, 0);
    add(g, roundedPrism(w * 0.98, glassH, 0.012, 0.004, glassPremium, 0), 0, glassY, -d / 2 + 0.006);
    add(g, roundedPrism(0.018, glassH, 0.018, 0.005, chromePremium, 0.003), -w / 2 + 0.012, glassY, -d / 2 + 0.012);
    add(g, premiumCylinder(0.012, h * 0.58, chromePremium, 20), w * 0.31, -h * 0.02, -d * 0.42);
    const arm = premiumCylinder(0.011, d * 0.16, chromePremium, 20);
    add(g, arm, w * 0.31, h * 0.28, -d * 0.34, Math.PI / 2, 0, 0);
    const head = premiumCylinder(Math.max(0.055, Math.min(w, d) * 0.09), 0.018, chromePremium, 36);
    add(g, head, w * 0.31, h * 0.28, -d * 0.25, Math.PI / 2, 0, 0);
    return g;
  }

  function buildVanity(o) {
    const g = new THREE.Group();
    const w = o.width_m, d = o.depth_m, h = o.height_m;
    const baseColor = /^#[0-9a-f]{6}$/i.test(o.color || '') ? Number.parseInt(o.color.slice(1), 16) : 0xc9b39b;
    const cabinet = physical(baseColor, { roughness: 0.46, clearcoat: 0.18 });
    const counterH = Math.max(0.035, h * 0.055);
    add(g, roundedPrism(w, h * 0.67, d * 0.96, Math.min(w, h) * 0.045, cabinet), 0, -h * 0.15, 0);
    add(g, roundedPrism(w * 1.02, counterH, d, Math.min(w, d) * 0.035, ceramic, 0.007), 0, h * 0.21, 0);
    add(g, sphere(w * 0.54, h * 0.11, d * 0.54, ceramic), 0, h * 0.27, d * 0.02);
    add(g, sphere(w * 0.42, h * 0.065, d * 0.4, physical(0xd5e4e8, { roughness: 0.2, clearcoat: 0.5 })), 0, h * 0.3, d * 0.02);
    add(g, roundedPrism(w * 0.012, h * 0.52, 0.018, 0.004, brushedMetal, 0.002), -w * 0.015, -h * 0.12, d / 2 + 0.012);
    faucet(g, w, d, h, w * 0.2, -d * 0.17);
    return g;
  }

  function buildSink(o) {
    const g = new THREE.Group();
    const w = o.width_m, d = o.depth_m, h = o.height_m;
    add(g, roundedPrism(w, h * 0.52, d, Math.min(w, d) * 0.12, ceramic, 0.012), 0, 0, 0);
    add(g, sphere(w * 0.7, h * 0.18, d * 0.62, physical(0xdbe7ea, { roughness: 0.21, clearcoat: 0.5 })), 0, h * 0.13, d * 0.02);
    add(g, premiumCylinder(Math.max(0.018, w * 0.035), h * 0.52, ceramic, 28), 0, -h * 0.42, -d * 0.08);
    faucet(g, w, d, h, w * 0.22, -d * 0.18);
    return g;
  }

  function buildRadiator(o) {
    const g = new THREE.Group();
    const w = o.width_m, d = o.depth_m, h = o.height_m;
    const columns = Math.max(6, Math.round(w / 0.065));
    const gap = w / columns;
    for (let i = 0; i < columns; i++) {
      add(g, roundedPrism(gap * 0.64, h * 0.9, d * 0.72, gap * 0.16, ceramic, 0.005), -w / 2 + gap * (i + 0.5), 0, 0);
    }
    add(g, roundedPrism(w * 0.96, h * 0.045, d * 0.78, 0.012, ceramic, 0.004), 0, h * 0.43, 0);
    add(g, roundedPrism(w * 0.96, h * 0.045, d * 0.78, 0.012, ceramic, 0.004), 0, -h * 0.43, 0);
    add(g, premiumCylinder(Math.max(0.008, d * 0.12), Math.max(0.07, w * 0.08), chromePremium, 20), w * 0.44, -h * 0.34, d * 0.3, 0, 0, Math.PI / 2);
    return g;
  }

  function buildCabinet(o) {
    const g = new THREE.Group();
    const w = o.width_m, d = o.depth_m, h = o.height_m;
    const baseColor = /^#[0-9a-f]{6}$/i.test(o.color || '') ? Number.parseInt(o.color.slice(1), 16) : 0xb08b68;
    const wood = physical(baseColor, { roughness: 0.48, clearcoat: 0.12 });
    add(g, roundedPrism(w, h, d, Math.min(w, d) * 0.035, wood, 0.009), 0, 0, 0);
    const faceZ = d / 2 + 0.007;
    add(g, roundedPrism(w * 0.008, h * 0.9, 0.012, 0.002, darkPremium, 0.001), 0, 0, faceZ);
    const handleY = h * 0.06;
    [-1, 1].forEach((side) => {
      const handle = premiumCylinder(Math.max(0.006, w * 0.008), Math.max(0.09, h * 0.15), brushedMetal, 20);
      add(g, handle, side * w * 0.08, handleY, faceZ + 0.015);
    });
    return g;
  }

  function buildAppliance(o) {
    const g = legacyCreateObjectMesh(o);
    g.traverse((m) => {
      if (!m.isMesh || !m.material) return;
      const mats = Array.isArray(m.material) ? m.material : [m.material];
      mats.forEach((mat) => {
        if ('roughness' in mat) mat.roughness = Math.min(0.5, Math.max(0.18, mat.roughness ?? 0.4));
        if ('metalness' in mat && ['oven','stove','fridge'].includes(o.kind)) mat.metalness = Math.max(mat.metalness ?? 0, 0.18);
        mat.needsUpdate = true;
      });
    });
    return g;
  }

  function createPremiumObjectMesh(o) {
    try {
      switch (o.kind) {
        case 'toilet': return buildToilet(o);
        case 'bathtub': return buildBathtub(o);
        case 'shower': return buildShower(o);
        case 'vanity': return buildVanity(o);
        case 'sink': return buildSink(o);
        case 'radiator': return buildRadiator(o);
        case 'cabinet':
        case 'wardrobe':
        case 'kitchen_base':
        case 'kitchen_wall': return buildCabinet(o);
        case 'washing_machine':
        case 'dryer':
        case 'dishwasher':
        case 'fridge':
        case 'oven':
        case 'stove': return buildAppliance(o);
        default: return legacyCreateObjectMesh(o);
      }
    } catch (error) {
      console.warn('Premium object renderer fallback', o?.kind, error);
      return legacyCreateObjectMesh(o);
    }
  }

  createObjectMesh = createPremiumObjectMesh;

  // Improve depth without changing room geometry: a soft camera-side fill and a
  // gentle overhead light make sanitary ceramics/glass/metal read naturally.
  if (!scene.getObjectByName('kayi-premium-fill')) {
    const fill = new THREE.DirectionalLight(0xeaf2ff, 0.72);
    fill.name = 'kayi-premium-fill';
    fill.position.set(-4.5, 5.5, 6.5);
    fill.castShadow = false;
    scene.add(fill);
  }
  if (!scene.getObjectByName('kayi-premium-softbox')) {
    const soft = new THREE.PointLight(0xfffbf5, 0.52, 18, 2);
    soft.name = 'kayi-premium-softbox';
    soft.position.set(0, Math.max(2.2, Number(state.room?.height_m || 2.6) + 0.8), 0);
    scene.add(soft);
  }
  renderer.toneMappingExposure = 1.0;

  // Rebuild immediately so an already-open planner uses the premium meshes too.
  rebuildScene({ keepCamera: true });
  queueRender();
})();

// A+Bau renovation surface renderer 20260815
(() => {
  const legacyNormalizeStateForRenovation = normalizeState;
  const legacyRebuildSceneForRenovation = rebuildScene;

  const copyRenovation = (raw, normalized) => {
    if (raw?.renovation && typeof raw.renovation === 'object') {
      normalized.renovation = deepClone(raw.renovation);
    } else {
      normalized.renovation ||= { intent: {}, surface_plan: {}, work_scope: {}, source_command: '' };
    }
    return normalized;
  };

  normalizeState = function normalizeStateWithRenovation(raw) {
    return copyRenovation(raw, legacyNormalizeStateForRenovation(raw));
  };

  // The original normalizeState predates renovation metadata and already ran once
  // before this final runtime layer. Recover the server JSON for the first render.
  try {
    const rawInitial = JSON.parse($('#room-planner-state')?.textContent || '{}');
    copyRenovation(rawInitial, state);
  } catch (_) {
    state.renovation ||= { intent: {}, surface_plan: {}, work_scope: {}, source_command: '' };
  }

  const colorMap = {
    'weiß': '#f5f5f2', 'weiss': '#f5f5f2', 'white': '#f5f5f2',
    'hellgrau': '#d7d9da', 'hell grau': '#d7d9da', 'light grey': '#d7d9da', 'light gray': '#d7d9da',
    'grau': '#afb3b5', 'grey': '#afb3b5', 'gray': '#afb3b5',
    'dunkelgrau': '#686d70', 'anthrazit': '#4d5356', 'schwarz': '#303336',
    'beige': '#d9d0c0', 'sand': '#d8cbb6', 'creme': '#eee8da',
  };
  const resolveColor = (value, fallback) => {
    const text = String(value || '').trim().toLowerCase();
    if (/^#[0-9a-f]{6}$/i.test(text)) return text;
    return colorMap[text] || fallback;
  };
  const finite = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const positive = (value, fallback) => Math.max(0.01, finite(value, fallback));

  function makeTileTexture(baseColor, groutColor = '#aeb2b4') {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = baseColor;
    ctx.fillRect(0, 0, 128, 128);
    const shade = ctx.createLinearGradient(0, 0, 128, 128);
    shade.addColorStop(0, 'rgba(255,255,255,.16)');
    shade.addColorStop(.55, 'rgba(255,255,255,0)');
    shade.addColorStop(1, 'rgba(20,28,32,.045)');
    ctx.fillStyle = shade;
    ctx.fillRect(0, 0, 128, 128);
    ctx.strokeStyle = groutColor;
    ctx.lineWidth = 3;
    ctx.strokeRect(1.5, 1.5, 125, 125);
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy?.() || 1);
    texture.needsUpdate = true;
    return texture;
  }

  function tiledMaterial({ color, grout, tileW, tileH, width, height, offsetX = 0, offsetY = 0, opacity = 0.32 }) {
    const texture = makeTileTexture(color, grout);
    texture.repeat.set(Math.max(0.01, width / tileW), Math.max(0.01, height / tileH));
    texture.offset.set((offsetX / tileW) % 1, (offsetY / tileH) % 1);
    return new THREE.MeshStandardMaterial({
      map: texture,
      color: 0xffffff,
      roughness: 0.68,
      metalness: 0.01,
      transparent: opacity < 1,
      opacity,
      depthWrite: opacity >= 0.95,
      side: THREE.DoubleSide,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
    });
  }

  function paintedMaterial(opacity = 0.12) {
    return new THREE.MeshStandardMaterial({
      color: 0xf5f4ef,
      roughness: 0.94,
      metalness: 0,
      transparent: true,
      opacity,
      depthWrite: false,
      side: THREE.DoubleSide,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
    });
  }

  function addWallPlane(group, wall, a, b, y0, y1, mat) {
    if (b - a < 0.008 || y1 - y0 < 0.008) return;
    const width = b - a;
    const height = y1 - y0;
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, height), mat);
    mesh.receiveShadow = true;
    mesh.castShadow = false;
    mesh.renderOrder = 3;
    if (wall === 'back') mesh.position.set((a + b) / 2, (y0 + y1) / 2, 0.003);
    if (wall === 'front') mesh.position.set((a + b) / 2, (y0 + y1) / 2, state.room.length_m - 0.003);
    if (wall === 'left') {
      mesh.rotation.y = Math.PI / 2;
      mesh.position.set(0.003, (y0 + y1) / 2, (a + b) / 2);
    }
    if (wall === 'right') {
      mesh.rotation.y = Math.PI / 2;
      mesh.position.set(state.room.width_m - 0.003, (y0 + y1) / 2, (a + b) / 2);
    }
    mesh.userData = { role: 'renovation-surface', wall };
    group.add(mesh);
  }

  function wallBandCells(wall, y0, y1) {
    const roomHeight = finite(state.room.height_m, 2.5);
    y0 = clamp(finite(y0), 0, roomHeight);
    y1 = clamp(finite(y1), 0, roomHeight);
    if (y1 <= y0 + 0.005) return [];
    const wallLength = wall === 'back' || wall === 'front' ? finite(state.room.width_m, 3) : finite(state.room.length_m, 4);
    const openings = (state.openings || [])
      .filter((o) => o.enabled !== false && o.wall === wall)
      .map((o) => ({
        a: clamp(finite(o.offset_m), 0, wallLength),
        b: clamp(finite(o.offset_m) + finite(o.width_m, 0.8), 0, wallLength),
        y0: clamp(finite(o.sill_height_m), 0, roomHeight),
        y1: clamp(finite(o.sill_height_m) + finite(o.height_m, 2), 0, roomHeight),
      }))
      .filter((o) => o.b > o.a && o.y1 > o.y0);
    const xs = [...new Set([0, wallLength, ...openings.flatMap((o) => [o.a, o.b])])].sort((a, b) => a - b);
    const ys = [...new Set([y0, y1, ...openings.flatMap((o) => [clamp(o.y0, y0, y1), clamp(o.y1, y0, y1)])])].sort((a, b) => a - b);
    const cells = [];
    for (let xi = 0; xi < xs.length - 1; xi++) {
      const a = xs[xi], b = xs[xi + 1];
      if (b - a < 0.005) continue;
      const xm = (a + b) / 2;
      for (let yi = 0; yi < ys.length - 1; yi++) {
        const cy0 = ys[yi], cy1 = ys[yi + 1];
        if (cy1 <= y0 || cy0 >= y1 || cy1 - cy0 < 0.005) continue;
        const ym = (cy0 + cy1) / 2;
        if (openings.some((o) => xm > o.a + 1e-5 && xm < o.b - 1e-5 && ym > o.y0 + 1e-5 && ym < o.y1 - 1e-5)) continue;
        cells.push({ a, b, y0: Math.max(y0, cy0), y1: Math.min(y1, cy1) });
      }
    }
    return cells;
  }

  function addTiledWallBand(group, wall, y0, y1, config) {
    const color = resolveColor(config?.wall_tile_color, '#f5f5f2');
    const grout = resolveColor(state.materials?.grout_color, '#b9bbba');
    const tileW = positive(finite(config?.tile_width_cm, 30) / 100, 0.3);
    const tileH = positive(finite(config?.tile_height_cm, 60) / 100, 0.6);
    wallBandCells(wall, y0, y1).forEach((cell) => {
      const mat = tiledMaterial({
        color, grout, tileW, tileH,
        width: cell.b - cell.a,
        height: cell.y1 - cell.y0,
        offsetX: cell.a,
        offsetY: cell.y0,
        opacity: 0.34,
      });
      addWallPlane(group, wall, cell.a, cell.b, cell.y0, cell.y1, mat);
    });
  }

  function addPaintedWallBand(group, wall, y0, y1) {
    wallBandCells(wall, y0, y1).forEach((cell) => {
      addWallPlane(group, wall, cell.a, cell.b, cell.y0, cell.y1, paintedMaterial(0.12));
    });
  }

  function finishLooksPainted(value) {
    return /q\s*3|spachtel|streich|paint|anstrich/i.test(String(value || ''));
  }

  function addRenovationSurfaceVisuals() {
    const renovation = state.renovation;
    const surface = renovation?.surface_plan;
    if (!surface || typeof surface !== 'object') return;
    const group = new THREE.Group();
    group.name = 'kayi-renovation-surfaces';
    group.userData = { role: 'renovation-surfaces' };

    const roomW = finite(state.room.width_m, 3);
    const roomL = finite(state.room.length_m, 4);
    const roomH = finite(state.room.height_m, 2.5);
    const floor = surface.floor || {};
    const floorHasTiles = /fliese|tile|keramik|stein/i.test(String(floor.finish || '')) || (floor.tile_width_cm && floor.tile_height_cm);
    if (floorHasTiles) {
      const tileW = positive(finite(floor.tile_width_cm, 60) / 100, 0.6);
      const tileH = positive(finite(floor.tile_height_cm, 60) / 100, 0.6);
      const color = resolveColor(floor.tile_color, '#d7d9da');
      const grout = resolveColor(state.materials?.grout_color, '#b0b2b2');
      const mat = tiledMaterial({ color, grout, tileW, tileH, width: roomW, height: roomL, opacity: 0.96 });
      const plane = new THREE.Mesh(new THREE.PlaneGeometry(roomW, roomL), mat);
      plane.rotation.x = -Math.PI / 2;
      plane.position.set(roomW / 2, 0.006, roomL / 2);
      plane.receiveShadow = true;
      plane.renderOrder = 2;
      plane.userData = { role: 'renovation-surface', surface: 'floor' };
      group.add(plane);
    }

    const wet = surface.wet_zone || {};
    const other = surface.other_walls || {};
    const wetWalls = new Set(Array.isArray(wet.applies_to) ? wet.applies_to : []);
    const wetHeight = clamp(finite(wet.height_m, 0), 0, roomH);
    const otherHeight = clamp(finite(other.height_m, 0), 0, roomH);
    for (const wall of ['back', 'front', 'left', 'right']) {
      const isWet = Boolean(wet.present) && wetWalls.has(wall) && wetHeight > 0.01;
      const bandHeight = isWet ? wetHeight : otherHeight;
      const tileConfig = isWet ? wet : other;
      const hasTilePlan = bandHeight > 0.01 && (tileConfig.wall_tile_color || tileConfig.tile_width_cm || tileConfig.tile_height_cm);
      if (hasTilePlan) addTiledWallBand(group, wall, 0, bandHeight, tileConfig);
      const upperFinish = other.upper_finish || surface.ceiling?.finish || '';
      if (bandHeight < roomH - 0.01 && finishLooksPainted(upperFinish)) {
        addPaintedWallBand(group, wall, bandHeight, roomH);
      }
    }

    if (state.view.show_ceiling && finishLooksPainted(surface.ceiling?.finish)) {
      const mat = paintedMaterial(0.18);
      const ceiling = new THREE.Mesh(new THREE.PlaneGeometry(roomW, roomL), mat);
      ceiling.rotation.x = Math.PI / 2;
      ceiling.position.set(roomW / 2, roomH - 0.004, roomL / 2);
      ceiling.renderOrder = 2;
      ceiling.userData = { role: 'renovation-surface', surface: 'ceiling' };
      group.add(ceiling);
    }

    if (group.children.length) world.add(group);
  }

  rebuildScene = function rebuildSceneWithRenovationSurfaces(options = {}) {
    const result = legacyRebuildSceneForRenovation(options);
    addRenovationSurfaceVisuals();
    return result;
  };

  // Rebuild the already initialized scene so the current KI draft immediately
  // displays tile formats/heights and the smooth Q3+painted zones.
  rebuildScene({ keepCamera: true });
  queueRender();
})();

