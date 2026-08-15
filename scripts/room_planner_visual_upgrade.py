from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI premium room object visuals 20260815"
VERSION = "20260815-2017-premium-objects"


JS = r'''

// KAYI premium room object visuals 20260815
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
'''


def patch_runtime_js() -> None:
    path = ROOT / "static" / "js" / "room-planner.js"
    if not path.exists():
        raise RuntimeError("Room Planner runtime JS is missing")
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        path.write_text(text.rstrip() + JS, encoding="utf-8")


def patch_template() -> None:
    path = ROOT / "templates" / "rebuild" / "room_planner.html"
    if not path.exists():
        raise RuntimeError("Room Planner template is missing")
    text = path.read_text(encoding="utf-8")
    text, count = re.subn(
        r"(\{%\s*static\s+'js/room-planner\.js'\s*%\}\?v=)[^\"']+",
        rf"\g<1>{VERSION}",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not cache-bust premium Room Planner JS")
    path.write_text(text, encoding="utf-8")


def guard() -> None:
    js = (ROOT / "static" / "js" / "room-planner.js").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "rebuild" / "room_planner.html").read_text(encoding="utf-8")
    required = [
        MARKER,
        "createObjectMesh = createPremiumObjectMesh",
        "function buildToilet",
        "function buildBathtub",
        "function buildShower",
        "function buildVanity",
        "MeshPhysicalMaterial",
        "kayi-premium-fill",
    ]
    for needle in required:
        if needle not in js:
            raise RuntimeError(f"Premium Room Planner visual missing: {needle}")
    if f"room-planner.js' %}}?v={VERSION}" not in template:
        raise RuntimeError("Premium Room Planner cache-bust was not applied")


patch_runtime_js()
patch_template()
guard()
print("Room Planner upgraded with premium sanitary geometry, PBR materials and softer lighting.")
