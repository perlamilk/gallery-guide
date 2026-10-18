// The interactive 3D gallery map.
// One THREE.Group per floor; rooms are extruded from the polygons in floors.json.
// Public API (used by app.js):
//   new MuseumMap(canvas, museum, { onRoomTap })
//   showFloor(id)            highlight(Map<galleryId,count>)
//   select(galleryId|null)   focusRoom(galleryId)        resetView()

import * as THREE from 'three';
import { OrbitControls } from '../vendor/OrbitControls.js';
import { MAP, FONTS, currentTheme, onThemeChange, reducedMotion } from './config.js';

const tmpColor = new THREE.Color();
let COLORS = currentTheme();
const C = {};
function setPalette(theme) {
  COLORS = theme;
  for (const k of ['roomTop', 'roomSide', 'accent', 'accentSide', 'selected', 'selectedPlain']) {
    C[k] = new THREE.Color(theme[k]);
  }
}
setPalette(COLORS);

export class MuseumMap {
  constructor(canvas, museum, { onRoomTap } = {}) {
    this.canvas = canvas;
    this.museum = museum;
    this.onRoomTap = onRoomTap;
    this.rooms = new Map();          // galleryId -> room view
    this.floorGroups = new Map();    // floorId -> THREE.Group
    this.lit = new Map();            // galleryId -> match count
    this.selected = null;
    this.currentFloor = null;

    this.#setupRenderer();
    this.#computeFrame();
    for (const floor of museum.floors) this.#buildFloor(floor);
    this.#setupInput();

    onThemeChange(theme => this.#applyTheme(theme));

    this.clock = new THREE.Clock();
    this.renderer.setAnimationLoop(() => this.#tick());
    new ResizeObserver(() => this.#resize()).observe(canvas);
    this.#resize();
  }

  // ---------- setup ----------

  #setupRenderer() {
    const r = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true, alpha: false });
    r.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    r.setClearColor(COLORS.paper);
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer = r;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(32, 1, 0.5, 600);

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0xd9d2c4, 2.1));
    const sun = new THREE.DirectionalLight(0xfff6ea, 1.6);
    sun.position.set(-18, 40, 26);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.radius = 6;
    sun.shadow.bias = -0.0005;
    Object.assign(sun.shadow.camera, { left: -40, right: 40, top: 40, bottom: -40, near: 1, far: 120 });
    this.scene.add(sun);
    this.sun = sun;

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(400, 400),
      new THREE.ShadowMaterial({ color: 0x3b3428, opacity: COLORS.shadow }),
    );
    this.ground = ground;
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.001;
    ground.receiveShadow = true;
    this.scene.add(ground);

    this.controls = new OrbitControls(this.camera, this.canvas);
    Object.assign(this.controls, {
      enableDamping: true,
      dampingFactor: 0.09,
      rotateSpeed: 0.7,
      zoomSpeed: 0.9,
      panSpeed: 0.9,
      screenSpacePanning: false,
      minPolarAngle: 0.05,
      maxPolarAngle: 1.22,
      minDistance: 8,
      maxDistance: 220,
    });
    // One finger rotates, two fingers pinch-zoom and pan.
    this.controls.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };
  }

  // All floors share one origin so rooms stay put when switching floors.
  #computeFrame() {
    const box = new THREE.Box2();
    for (const floor of this.museum.floors) {
      const [ox, oy] = floor.offset ?? [0, 0];
      for (const room of floor.rooms) for (const [x, y] of room.poly) box.expandByPoint(new THREE.Vector2(x + ox, y + oy));
    }
    this.origin = box.getCenter(new THREE.Vector2());
  }

  toWorld([x, y], [ox, oy] = [0, 0]) {
    return new THREE.Vector3((x + ox - this.origin.x) * MAP.scale, 0, (y + oy - this.origin.y) * MAP.scale);
  }

  #buildFloor(floor) {
    const group = new THREE.Group();
    group.visible = false;
    group.userData.floorId = floor.id;

    for (const room of floor.rooms) {
      const view = this.#buildRoom(room, floor);
      group.add(view.root);
      this.rooms.set(room.id, view);
    }
    for (const note of floor.notes ?? []) group.add(this.#makeNote(note, floor.offset));

    const bounds = new THREE.Box3();
    for (const room of floor.rooms) bounds.expandByObject(this.rooms.get(room.id).mesh);
    group.userData.bounds = bounds;
    const home = new THREE.Box3();
    for (const id of floor.homeView ?? []) if (this.rooms.has(id)) home.expandByObject(this.rooms.get(id).mesh);
    group.userData.home = home.isEmpty() ? bounds : home;
    this.scene.add(group);
    this.floorGroups.set(floor.id, group);
  }

  #buildRoom(room, floor) {
    const isGallery = room.kind === 'gallery';
    const shape = new THREE.Shape(room.poly.map(p => {
      const v = this.toWorld(p, floor.offset);
      return new THREE.Vector2(v.x, -v.z);
    }));
    const geo = new THREE.ExtrudeGeometry(shape, { depth: 1, bevelEnabled: false });
    geo.rotateX(-Math.PI / 2);

    const top = new THREE.MeshStandardMaterial({
      color: isGallery ? COLORS.roomTop : COLORS.serviceTop, roughness: 0.92, metalness: 0,
    });
    const side = new THREE.MeshStandardMaterial({
      color: isGallery ? COLORS.roomSide : COLORS.serviceSide, roughness: 0.95, metalness: 0,
    });
    const mesh = new THREE.Mesh(geo, [top, side]);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData.galleryId = isGallery ? room.id : null;

    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(geo, 30),
      new THREE.LineBasicMaterial({ color: COLORS.edge, transparent: true, opacity: 0.55 }),
    );

    const root = new THREE.Group();
    const body = new THREE.Group();   // scaled on Y to animate height
    body.add(mesh, edges);
    root.add(body);

    // centroid & size for label placement / camera focus
    const box = new THREE.Box3().setFromObject(mesh);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());

    let label = null;
    if (isGallery) {
      label = makeLabel(room.id, Math.min(size.x, size.z));
      label.position.set(center.x, 0, center.z);
      root.add(label);
    }

    const base = isGallery ? MAP.roomHeight : MAP.serviceHeight;
    body.scale.y = base;
    return {
      id: room.id, room, floorId: floor.id, isGallery, root, body, mesh, edges, top, side, label,
      center, size, base, height: base, targetHeight: base, litAmount: 0, targetLit: 0, count: 0,
    };
  }

  #makeNote(note, offset) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const font = `italic 64px ${FONTS.display}`;
    ctx.font = font;
    canvas.width = Math.ceil(ctx.measureText(note.text).width) + 20;
    canvas.height = 90;
    ctx.font = font;
    ctx.fillStyle = COLORS.note;
    ctx.textBaseline = 'middle';
    ctx.fillText(note.text, 10, 45);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    const h = 1.1;
    const mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(h * canvas.width / canvas.height, h),
      new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }),
    );
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.copy(this.toWorld(note.at, offset)).setY(0.01);
    return mesh;
  }

  // ---------- input ----------

  #setupInput() {
    const ray = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    let down = null;
    let pointers = 0;

    this.canvas.addEventListener('pointerdown', e => {
      pointers++;
      down = pointers === 1 ? { x: e.clientX, y: e.clientY, t: performance.now() } : null;
    });
    const end = e => {
      pointers = Math.max(0, pointers - 1);
      if (!down || e.type === 'pointercancel') { down = null; return; }
      const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
      const quick = performance.now() - down.t < 450;
      down = null;
      if (moved > 9 || !quick) return;

      const rect = this.canvas.getBoundingClientRect();
      ndc.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
      ray.setFromCamera(ndc, this.camera);
      const group = this.floorGroups.get(this.currentFloor);
      const meshes = [...this.rooms.values()].filter(r => r.floorId === this.currentFloor && r.isGallery).map(r => r.mesh);
      const hit = ray.intersectObjects(meshes, false)[0];
      this.onRoomTap?.(hit ? hit.object.userData.galleryId : null, group);
    };
    this.canvas.addEventListener('pointerup', end);
    this.canvas.addEventListener('pointercancel', end);

    // Stop iOS Safari from zooming the page while pinching the map.
    for (const ev of ['gesturestart', 'gesturechange']) {
      this.canvas.addEventListener(ev, e => e.preventDefault(), { passive: false });
    }
  }

  // ---------- public API ----------

  showFloor(id, { animate = true } = {}) {
    if (id === this.currentFloor) return;
    const prev = this.floorGroups.get(this.currentFloor);
    const next = this.floorGroups.get(id);
    if (!next) return;
    this.currentFloor = id;
    next.visible = true;
    if (animate && prev) {
      const dir = Number(id) > Number(prev.userData.floorId) ? 1 : -1;
      this.#tween(380, t => {
        const e = easeInOut(t);
        prev.position.y = -dir * 3 * e;
        next.position.y = dir * 3 * (1 - e);
        setOpacity(prev, 1 - e);
        setOpacity(next, e);
      }, () => { prev.visible = false; prev.position.y = 0; setOpacity(prev, 1); });
    } else {
      if (prev) prev.visible = false;
      setOpacity(next, 1);
    }
  }

  // counts: Map(galleryId -> number of matches). Empty map clears.
  highlight(counts) {
    this.lit = counts;
    for (const view of this.rooms.values()) {
      if (!view.isGallery) continue;
      const n = counts.get(view.id) ?? 0;
      view.targetLit = n > 0 ? 1 : 0;
      view.targetHeight = n > 0 ? MAP.roomHeightLit : view.base;
      if (view.count !== n) {
        view.count = n;
        updateLabel(view.label, view.id, n);
      }
    }
  }

  select(galleryId) {
    this.selected = galleryId;
  }

  focusRoom(galleryId, { zoom = true } = {}) {
    const view = this.rooms.get(galleryId);
    if (!view) return;
    this.showFloor(view.floorId);
    const target = view.center.clone().setY(0);
    const span = Math.max(view.size.x, view.size.z);
    const dist = zoom ? THREE.MathUtils.clamp(span * 3.2, 16, 40) : this.camera.position.distanceTo(this.controls.target);
    this.#flyTo(target, dist);
  }

  // Glide so all the given rooms on the current floor are in view (keeps the current angle).
  frameRooms(ids) {
    const box = new THREE.Box3();
    for (const id of ids) {
      const v = this.rooms.get(id);
      if (v && v.floorId === this.currentFloor) box.expandByObject(v.mesh);
    }
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3()).setY(0);
    const size = box.getSize(new THREE.Vector3());
    const vfov = THREE.MathUtils.degToRad(this.camera.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * this.#visibleAspect());
    const fit = Math.max((size.x * 0.65) / Math.tan(hfov / 2), (size.z * 0.8) / Math.tan(vfov / 2));
    // never closer than the home view, so the room keeps its neighbours for context
    this.#flyTo(center, THREE.MathUtils.clamp(Math.max(fit, this.homeDistance ?? 60), 16, 200));
  }

  // Frame the floor's home rooms (or the whole floor), looking north like the printed map.
  resetView({ animate = true, whole = false } = {}) {
    const group = this.floorGroups.get(this.currentFloor);
    const bounds = whole ? group?.userData.bounds : group?.userData.home;
    if (!bounds) return;
    const center = bounds.getCenter(new THREE.Vector3()).setY(0);
    const size = bounds.getSize(new THREE.Vector3());
    // fit the wing's width to the screen, accounting for the bottom sheet
    const vfov = THREE.MathUtils.degToRad(this.camera.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * this.#visibleAspect());
    // tilted view: the near edge comes closer to the camera, so leave extra margin
    const dist = Math.max((size.x * 0.5 * 1.18) / Math.tan(hfov / 2), (size.z * 0.5 * 1.5) / Math.tan(vfov / 2));
    if (!whole) this.homeDistance = dist;
    const pos = this.#orbitPosition(center, dist, 0.72, 0);
    if (animate) this.#flyTo(center, dist, pos);
    else { this.controls.target.copy(center); this.camera.position.copy(pos); }
  }

  // Screen padding (px) taken by overlays, so framing keeps rooms visible.
  setViewInsets({ bottom = 0, left = 0 } = {}) {
    this.insetLeft = left;
    this.insetTarget = bottom;
    if (this.insetBottom === undefined || reducedMotion()) {
      this.insetBottom = bottom;
      this.#applyViewOffset();
    }
  }

  // ---------- internals ----------

  #visibleAspect() {
    const w = this.canvas.clientWidth - (this.insetLeft ?? 0);
    return Math.max(0.3, w / Math.max(1, this.canvas.clientHeight));
  }

  #applyTheme(theme) {
    setPalette(theme);
    this.renderer.setClearColor(theme.paper);
    this.ground.material.opacity = theme.shadow;
    for (const v of this.rooms.values()) {
      if (!v.isGallery) {
        v.top.color.set(theme.serviceTop);
        v.side.color.set(theme.serviceSide);
      }
      v.edges.material.color.set(theme.edge);
      if (v.label) updateLabel(v.label, v.id, v.count);
    }
  }

  #orbitPosition(target, dist, polar, azimuth) {
    return new THREE.Vector3(
      target.x + dist * Math.sin(polar) * Math.sin(azimuth),
      target.y + dist * Math.cos(polar),
      target.z + dist * Math.sin(polar) * Math.cos(azimuth),
    );
  }

  #flyTo(target, dist, position) {
    const startT = this.controls.target.clone();
    const startP = this.camera.position.clone();
    let endP = position;
    if (!endP) {
      const offset = startP.clone().sub(startT).setLength(dist);
      endP = target.clone().add(offset);
    }
    this.#tween(650, t => {
      const e = easeInOut(t);
      this.controls.target.lerpVectors(startT, target, e);
      this.camera.position.lerpVectors(startP, endP, e);
    });
  }

  #tween(ms, step, done) {
    if (reducedMotion()) { step(1); done?.(); return; }
    const start = performance.now();
    const tick = now => {
      const t = Math.min(1, (now - start) / ms);
      step(t);
      if (t < 1) requestAnimationFrame(tick); else done?.();
    };
    requestAnimationFrame(tick);
  }

  #resize() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.#applyViewOffset();
  }

  // Shift the projection up so the map's centre sits in the visible area above the sheet.
  #applyViewOffset() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    if (!w || !h) return;
    const shift = Math.min(this.insetBottom ?? 0, h * 0.5) / 2;
    this.camera.setViewOffset(w, h, -(this.insetLeft ?? 0) / 2, shift, w, h);
    this.camera.updateProjectionMatrix();
  }

  #tick() {
    const dt = Math.min(this.clock.getDelta(), 0.05);
    const k = 1 - Math.exp(-dt * 10);

    // glide the map centre along with the bottom sheet
    if (this.insetTarget !== undefined && Math.abs(this.insetTarget - this.insetBottom) > 0.5) {
      this.insetBottom += (this.insetTarget - this.insetBottom) * (1 - Math.exp(-dt * 9));
      this.#applyViewOffset();
    }

    for (const v of this.rooms.values()) {
      if (v.floorId !== this.currentFloor) continue;
      v.height += (v.targetHeight - v.height) * k;
      v.litAmount += (v.targetLit - v.litAmount) * k;
      v.body.scale.y = v.height;
      if (v.label) v.label.position.y = v.height + 0.012;

      if (v.isGallery) {
        const sel = this.selected === v.id;
        tmpColor.copy(C.roomTop).lerp(C.accent, v.litAmount);
        if (sel) tmpColor.lerp(v.litAmount > 0.5 ? C.selected : C.selectedPlain, 0.8);
        v.top.color.copy(tmpColor);
        v.side.color.copy(C.roomSide).lerp(C.accentSide, v.litAmount);
        v.edges.material.color.set(sel ? COLORS.selected : COLORS.edge);
        v.edges.material.opacity = sel ? 1 : 0.55;
        v.label.userData.setInk(v.litAmount > 0.5);
      }
    }

    // keep the camera over the building
    const t = this.controls.target;
    t.x = THREE.MathUtils.clamp(t.x, -30, 30);
    t.z = THREE.MathUtils.clamp(t.z, -20, 25);
    t.y = 0;
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }
}

// ---------- labels ----------

// A flat label lying on the room's roof. Two pre-rendered textures (dark ink / white ink)
// so lit rooms read clearly without re-rendering every frame.
function makeLabel(text, roomSpan) {
  const ink = drawLabel(text, 0, COLORS.label);
  const white = drawLabel(text, 0, COLORS.labelOnAccent);
  const height = THREE.MathUtils.clamp(roomSpan * 0.42, 0.9, 1.7);
  const geo = new THREE.PlaneGeometry(height * ink.aspect, height);
  const mat = new THREE.MeshBasicMaterial({ map: ink.texture, transparent: true, depthWrite: false });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.renderOrder = 2;
  mesh.userData = {
    text, height, ink, white, count: 0, onAccent: false,
    setInk(onAccent) {
      if (onAccent === this.onAccent) return;
      this.onAccent = onAccent;
      mat.map = onAccent ? this.white.texture : this.ink.texture;
      mat.needsUpdate = true;
    },
  };
  return mesh;
}

function updateLabel(mesh, text, count) {
  const u = mesh.userData;
  u.ink.texture.dispose();
  u.white.texture.dispose();
  u.ink = drawLabel(text, count, COLORS.label);
  u.white = drawLabel(text, count, COLORS.labelOnAccent);
  mesh.geometry.dispose();
  const h = u.height * (count ? 1.45 : 1);
  mesh.geometry = new THREE.PlaneGeometry(h * u.ink.aspect, h);
  mesh.material.map = u.onAccent ? u.white.texture : u.ink.texture;
  mesh.material.needsUpdate = true;
}

function drawLabel(text, count, color) {
  const px = 120;
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  const font = `${px}px ${FONTS.display}`;
  const countFont = `600 ${Math.round(px * 0.3)}px -apple-system, "Helvetica Neue", sans-serif`;
  const countText = `${count} ${count === 1 ? 'MATCH' : 'MATCHES'}`;
  ctx.font = font;
  let w = ctx.measureText(text).width;
  if (count) { ctx.font = countFont; w = Math.max(w, ctx.measureText(countText).width); }
  w = Math.ceil(w) + 24;
  const h = count ? Math.round(px * 1.45) : px;
  canvas.width = w;
  canvas.height = h;
  ctx.font = font;
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, w / 2, px * 0.52);
  if (count) {
    ctx.font = countFont;
    ctx.globalAlpha = 0.85;
    ctx.fillText(countText, w / 2, px * 1.17);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return { texture, aspect: w / h };
}

function setOpacity(group, o) {
  group.traverse(obj => {
    const mats = Array.isArray(obj.material) ? obj.material : obj.material ? [obj.material] : [];
    for (const m of mats) {
      if (m.userData.baseOpacity === undefined) {
        m.userData.baseOpacity = m.opacity;
        m.userData.baseTransparent = m.transparent;
      }
      const t = o < 1 || m.userData.baseTransparent;
      if (t !== m.transparent) { m.transparent = t; m.needsUpdate = true; }
      m.opacity = m.userData.baseOpacity * o;
    }
  });
}

const easeInOut = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
