// The interactive 3D map of the museum.
// One THREE.Group per floor, built from data/floors.json:
//   galleries (numbered rooms, tappable, light up on search) · named spaces (courtyards, cafés…)
//   corridors · closed areas (grey on the PDF) · facility icons · wing names and notes.
// Public API (used by app.js):
//   new MuseumMap(canvas, museum, { onTap })      onTap({ kind: 'gallery'|'space'|'facility'|null, id, type })
//   showFloor(id)   highlight(Map<galleryId,count>)   select(id|null)   focusRoom(id)
//   frameRooms(ids) resetView()   setViewInsets({bottom,left})
//   highlightFacilities(Set<type>|null)   setFacilitiesVisible(bool)

import * as THREE from 'three';
import { OrbitControls } from '../vendor/OrbitControls.js';
import { MAP, FONTS, currentTheme, onThemeChange, reducedMotion } from './config.js';
import { drawFacility } from './icons.js';

const tmpColor = new THREE.Color();
let COLORS = currentTheme();
const C = {};
function setPalette(theme) {
  COLORS = theme;
  for (const k of ['roomTop', 'roomSide', 'accent', 'accentSide', 'selected', 'selectedPlain', 'spaceTop', 'spaceSide', 'visitedTop']) {
    C[k] = new THREE.Color(theme[k]);
  }
}
setPalette(COLORS);

const KIND = {
  gallery:  { height: () => MAP.roomHeight,    top: 'roomTop',    side: 'roomSide',    edges: 0.55 },
  space:    { height: () => MAP.spaceHeight,   top: 'spaceTop',   side: 'spaceSide',   edges: 0.4 },
  corridor: { height: () => MAP.serviceHeight, top: 'serviceTop', side: 'serviceSide', edges: 0.25 },
  closed:   { height: () => MAP.closedHeight,  top: 'closedTop',  side: 'closedSide',  edges: 0 },
};

export class MuseumMap {
  constructor(canvas, museum, { onTap } = {}) {
    this.canvas = canvas;
    this.museum = museum;
    this.onTap = onTap;
    this.views = [];                 // every shape on every floor
    this.rooms = new Map();          // gallery/space id (and gallery aliases) -> view
    this.floorGroups = new Map();    // floorId -> THREE.Group
    this.markers = [];               // facility sprites
    this.doors = [];                 // thresholds between rooms
    this.visited = new Set();        // rooms checked off in the visit diary
    this.routeParts = [];            // meshes of the route being shown
    this.texts = [];                 // flat labels on the floor (wing names, notes)
    this.selected = null;
    this.currentFloor = null;
    this.floorOrder = new Map(museum.floors.map(f => [f.id, f.order ?? 0]));

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
    this.camera = new THREE.PerspectiveCamera(32, 1, 0.5, 800);

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0xd9d2c4, 2.1));
    const sun = new THREE.DirectionalLight(0xfff6ea, 1.6);
    sun.position.set(-24, 50, 32);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.radius = 6;
    sun.shadow.bias = -0.0005;
    Object.assign(sun.shadow.camera, { left: -50, right: 50, top: 50, bottom: -50, near: 1, far: 160 });
    this.scene.add(sun);
    this.sun = sun;

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(600, 600),
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
      maxDistance: 260,
    });
    // One finger rotates, two fingers pinch-zoom and pan.
    this.controls.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };
  }

  // All floors share one origin so rooms stay put when switching floors.
  #computeFrame() {
    const box = new THREE.Box2();
    for (const floor of this.museum.floors) {
      for (const shape of [...floor.rooms, ...(floor.closed ?? [])]) {
        for (const p of shape.poly) box.expandByPoint(this.#project(p, floor));
      }
    }
    this.origin = box.getCenter(new THREE.Vector2());
    const half = box.getSize(new THREE.Vector2()).multiplyScalar(0.5 * MAP.scale);
    this.panLimit = { x: half.x + 4, z: half.y + 4 };
  }

  // floor transform: [scale, dx, dy] (PDF points -> shared frame); older files used `offset`
  #project([x, y], floor) {
    const [s, dx, dy] = floor.transform ?? [1, ...(floor.offset ?? [0, 0])];
    return new THREE.Vector2(x * s + dx, y * s + dy);
  }

  toWorld(p, floor) {
    const v = this.#project(p, floor);
    return new THREE.Vector3((v.x - this.origin.x) * MAP.scale, 0, (v.y - this.origin.y) * MAP.scale);
  }

  #buildFloor(floor) {
    const group = new THREE.Group();
    group.visible = false;
    group.userData.floorId = floor.id;

    const bounds = new THREE.Box3();
    for (const area of floor.closed ?? []) {
      const view = this.#buildShape({ kind: 'closed', poly: area.poly, z: area.z }, floor);
      group.add(view.root);
      bounds.expandByObject(view.mesh);
    }
    const open = new THREE.Box3();   // public spaces only: what "home" frames when a floor has no homeView
    for (const room of floor.rooms) {
      const view = this.#buildShape(room, floor);
      group.add(view.root);
      bounds.expandByObject(view.mesh);
      open.expandByObject(view.mesh);
      if (room.kind === 'gallery' || room.kind === 'space') {
        for (const id of [room.id, ...(room.aliases ?? [])]) this.rooms.set(id, view);
      }
    }
    const byId = new Map(this.views.filter(v => v.floorId === floor.id).map(v => [v.id, v]));
    for (const door of floor.doors ?? []) {
      const a = byId.get(door.a), b = byId.get(door.b);
      if (!a || !b || door.implicit || (a.kind === 'corridor' && b.kind === 'corridor')) continue;
      const mesh = this.#makeDoor(door, floor, a, b);
      group.add(mesh);
      a.doors.push(mesh); b.doors.push(mesh);
    }
    for (const label of [...(floor.labels ?? []), ...(floor.notes ?? [])]) {
      const mesh = this.#makeText(label, floor);
      group.add(mesh);
    }
    const markers = new THREE.Group();
    for (const f of floor.amenities ?? []) {
      const sprite = this.#makeMarker(f, floor);
      markers.add(sprite);
    }
    group.add(markers);
    group.userData.markers = markers;

    group.userData.bounds = bounds;
    const home = new THREE.Box3();
    for (const id of floor.homeView ?? []) if (this.rooms.has(id)) home.expandByObject(this.rooms.get(id).mesh);
    group.userData.home = home.isEmpty() ? open : home;
    this.scene.add(group);
    this.floorGroups.set(floor.id, group);
  }

  #buildShape(room, floor) {
    const kind = KIND[room.kind] ?? KIND.corridor;
    const shape = new THREE.Shape(room.poly.map(p => {
      const v = this.toWorld(p, floor);
      return new THREE.Vector2(v.x, -v.z);
    }));
    const geo = new THREE.ExtrudeGeometry(shape, { depth: 1, bevelEnabled: false });
    geo.rotateX(-Math.PI / 2);

    // polygonOffset pushes faces a hair back so the outlines drawn on their edges never flicker
    const faces = { polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1, metalness: 0 };
    const top = new THREE.MeshStandardMaterial({ color: COLORS[kind.top], roughness: 0.92, ...faces });
    const side = new THREE.MeshStandardMaterial({ color: COLORS[kind.side], roughness: 0.95, ...faces });
    const mesh = new THREE.Mesh(geo, [top, side]);
    mesh.castShadow = room.kind !== 'closed';
    mesh.receiveShadow = true;

    const root = new THREE.Group();
    const body = new THREE.Group();   // scaled on Y to animate height
    body.add(mesh);
    let edges = null;
    if (kind.edges) {
      edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(geo, 30),
        new THREE.LineBasicMaterial({ color: COLORS.edge, transparent: true, opacity: kind.edges }),
      );
      body.add(edges);
    }
    root.add(body);

    const box = new THREE.Box3().setFromObject(mesh);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());

    // shapes that overlap in the PDF sit a little higher the later they're drawn (no flicker between them)
    const lift = (room.z ?? 0) * (room.kind === 'closed' ? 0.01 : 0.03);
    const view = {
      id: room.id, room, kind: room.kind, floorId: floor.id, root, body, mesh, edges, top, side,
      center, size, label: null, base: kind.height() + lift, lift, count: 0, litAmount: 0, targetLit: 0,
      doors: [],
    };
    view.height = view.targetHeight = view.base;
    body.scale.y = view.base;
    mesh.userData.view = view;

    if (room.kind === 'gallery') {
      view.labelText = galleryLabel(room);
      view.label = makeLabel(view.labelText, Math.min(size.x, size.z));
      view.label.position.set(center.x, 0, center.z);
      root.add(view.label);
    } else if (room.kind === 'space' && room.name) {
      view.label = makeNameLabel(room.name, size);
      view.label.position.set(center.x, 0, center.z);
      root.add(view.label);
    }
    this.views.push(view);
    return view;
  }

  // A threshold across the opening between two rooms: long side along the wall, short side crossing it.
  #makeDoor(door, floor, a, b) {
    const s = (floor.transform?.[0] ?? 1) * MAP.scale;
    const along = Math.max(0.4, door.width * s * 0.9);  // the opening itself, along the wall
    const across = 0.22;                                // a thin stroke, like a plan's door mark
    const geo = door.axis === 'h' ? new THREE.BoxGeometry(along, 0.04, across) : new THREE.BoxGeometry(across, 0.04, along);
    const mat = new THREE.MeshBasicMaterial({ color: COLORS.door });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(this.toWorld(door.at, floor));
    mesh.renderOrder = 1;
    mesh.userData = { door, a, b };
    this.doors.push(mesh);
    return mesh;
  }

  #makeText(label, floor) {
    const isArea = label.kind === 'area';
    const color = isArea ? COLORS.area : COLORS.note;
    const { texture, aspect } = drawText(label.text, {
      font: `${isArea ? '' : 'italic '}96px ${FONTS.display}`, color, maxWidth: isArea ? 2200 : 1400,
    });
    const h = isArea ? 1.5 : label.kind === 'place' ? 1.1 : 0.9;
    const mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(h * aspect, h),
      new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false }),
    );
    mesh.rotation.x = -Math.PI / 2;
    // wing names float just above the rooms; notes lie on the ground
    mesh.position.copy(this.toWorld(label.at, floor)).setY(isArea ? MAP.roomHeight + 0.02 : 0.02);
    mesh.renderOrder = 3;
    mesh.userData.text = label;
    this.texts.push(mesh);
    return mesh;
  }

  #makeMarker(facility, floor) {
    const material = new THREE.SpriteMaterial({ map: markerTexture(facility.type, false), depthTest: false, transparent: true });
    const sprite = new THREE.Sprite(material);
    sprite.scale.setScalar(MAP.markerSize);
    sprite.position.copy(this.toWorld(facility.at, floor)).setY(MAP.markerLift);
    sprite.renderOrder = 10;
    sprite.userData = { facility, floorId: floor.id, lit: false };
    this.markers.push(sprite);
    return sprite;
  }

  // ---------- input ----------

  #setupInput() {
    const ray = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    let down = null;
    let pointers = 0;

    // what's under a screen point: a facility icon, a room, or nothing
    const hitAt = (x, y) => {
      const rect = this.canvas.getBoundingClientRect();
      ndc.set(((x - rect.left) / rect.width) * 2 - 1, -((y - rect.top) / rect.height) * 2 + 1);
      ray.setFromCamera(ndc, this.camera);
      const group = this.floorGroups.get(this.currentFloor);
      if (group.userData.markers.visible) {
        const hitMarker = ray.intersectObjects(group.userData.markers.children, false)[0];
        if (hitMarker) {
          const { facility } = hitMarker.object.userData;
          return { kind: 'facility', type: facility.type, at: facility.at, floorId: this.currentFloor };
        }
      }
      const meshes = this.views.filter(v => v.floorId === this.currentFloor && (v.kind === 'gallery' || v.kind === 'space')).map(v => v.mesh);
      const view = ray.intersectObjects(meshes, false)[0]?.object.userData.view;
      return view ? { kind: view.kind, id: view.id, floorId: view.floorId } : { kind: null };
    };

    let pressTimer = null;
    this.canvas.addEventListener('pointerdown', e => {
      pointers++;
      clearTimeout(pressTimer);
      down = pointers === 1 ? { x: e.clientX, y: e.clientY, t: performance.now(), long: false } : null;
      if (!down) return;
      // press and hold on a room: a quick way to check it off during a visit
      pressTimer = setTimeout(() => {
        if (!down || down.moved) return;
        const hit = hitAt(down.x, down.y);
        if (hit.kind === 'gallery' || hit.kind === 'space') {
          down.long = true;
          this.onTap?.({ ...hit, long: true });
        }
      }, 550);
    });
    this.canvas.addEventListener('pointermove', e => {
      if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 9) down.moved = true;
    });
    const end = e => {
      pointers = Math.max(0, pointers - 1);
      clearTimeout(pressTimer);
      if (!down || e.type === 'pointercancel') { down = null; return; }
      const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
      const quick = performance.now() - down.t < 450;
      const wasLong = down.long;
      down = null;
      if (wasLong || moved > 9 || !quick) return;
      this.onTap?.(hitAt(e.clientX, e.clientY));
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
    this.lodDirty = true;
    next.visible = true;
    if (animate && prev) {
      const dir = (this.floorOrder.get(id) ?? 0) > (this.floorOrder.get(prev.userData.floorId) ?? 0) ? 1 : -1;
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

  // counts: Map(galleryId -> number of matches). Aliases share a room, so their counts add up.
  highlight(counts) {
    this.lodDirty = true;
    const totals = new Map();
    for (const [id, n] of counts) {
      const view = this.rooms.get(id);
      if (view?.kind === 'gallery') totals.set(view, (totals.get(view) ?? 0) + n);
    }
    for (const view of this.views) {
      if (view.kind !== 'gallery') continue;
      const n = totals.get(view) ?? 0;
      view.targetLit = n > 0 ? 1 : 0;
      view.targetHeight = n > 0 ? MAP.roomHeightLit + view.lift : view.base;
      if (view.count !== n) {
        view.count = n;
        updateLabel(view.label, view.labelText, n);
      }
    }
  }

  select(id) {
    this.lodDirty = true;
    this.selected = id ? this.rooms.get(id) ?? null : null;
  }

  // Facility types to emphasise (e.g. after searching "restroom"); null clears.
  highlightFacilities(types) {
    this.lodDirty = true;
    this.facilityFilter = types && types.size ? types : null;
    for (const sprite of this.markers) {
      const lit = !!this.facilityFilter?.has(sprite.userData.facility.type);
      if (lit !== sprite.userData.lit) {
        sprite.userData.lit = lit;
        sprite.material.map = markerTexture(sprite.userData.facility.type, lit);
        sprite.material.needsUpdate = true;
      }
      // when filtering, dim the other icons rather than hiding them
      sprite.material.opacity = this.facilityFilter && !lit ? 0.25 : 1;
      sprite.scale.setScalar(MAP.markerSize * (lit ? 1.35 : 1));
    }
  }

  // Rooms checked off in the visit diary get a soft tint.
  setVisited(ids) {
    this.visited = new Set();
    for (const id of ids ?? []) {
      const v = this.rooms.get(id);
      if (v) this.visited.add(v);
    }
  }

  // A still picture of one floor for the visit diary: tilted overview, visited rooms tinted.
  async snapshot(floorId, { width = 1080, height = 1080, route = [] } = {}) {
    const group = this.floorGroups.get(floorId);
    if (!group) return null;
    // show only this floor, fully drawn, without the search highlight
    const restore = [...this.floorGroups].map(([id, g]) => [g, g.visible, g.position.y]);
    for (const [id, g] of this.floorGroups) { g.visible = id === floorId; g.position.y = 0; setOpacity(g, 1); }
    const prevFloor = this.currentFloor;
    this.currentFloor = floorId;
    const lit = this.views.map(v => [v, v.height, v.litAmount]);
    for (const v of this.views) {
      if (v.floorId !== floorId || (v.kind !== 'gallery' && v.kind !== 'space')) continue;
      v.litAmount = 0; v.height = v.base; v.body.scale.y = v.base;
      if (v.label) { v.label.position.y = v.base + 0.012; v.label.userData.setInk?.(false); }
    }
    this.#paintRooms(floorId, true);
    // in the picture, visited rooms are drawn in full accent so they read at a glance
    const painted = [];
    for (const v of this.visited) {
      if (v.floorId !== floorId) continue;
      painted.push([v, v.top.color.clone()]);
      v.top.color.set(COLORS.accent);
      v.label?.userData.setInk?.(true);
    }
    // the route: a line through the centres of the rooms, in the order they were visited
    const pts = route.map(id => this.rooms.get(id)).filter(v => v && v.floorId === floorId)
      .map(v => new THREE.Vector3(v.center.x, MAP.roomHeight + 0.5, v.center.z));
    const extras = [];
    if (pts.length > 1) {
      const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal', 0.2);
      // white line with a dark edge: reads on the blue rooms and on everything else
      const tube = (r, color) => new THREE.Mesh(new THREE.TubeGeometry(curve, pts.length * 24, r, 10, false),
        new THREE.MeshBasicMaterial({ color }));
      extras.push(tube(0.2, COLORS.selected), tube(0.11, 0xffffff));
    }
    if (pts.length) {
      const dot = (p, r, color) => { const m = new THREE.Mesh(new THREE.SphereGeometry(r, 20, 12), new THREE.MeshBasicMaterial({ color })); m.position.copy(p); return m; };
      extras.push(dot(pts[0], 0.5, COLORS.selected), dot(pts[0], 0.32, 0xffffff), dot(pts.at(-1), 0.4, COLORS.selected));
    }
    for (const m of extras) group.add(m);

    const box = this.#openBounds(group);
    const center = box.getCenter(new THREE.Vector3()).setY(0);
    const size = box.getSize(new THREE.Vector3());
    const cam = new THREE.PerspectiveCamera(30, width / height, 0.5, 800);
    const tan = Math.tan(THREE.MathUtils.degToRad(15));
    const dist = Math.max(size.x * 0.58, size.z * 0.75) / tan;
    cam.position.copy(this.#orbitPosition(center, dist, 0.5, 0));
    cam.lookAt(center);

    const rt = new THREE.WebGLRenderTarget(width, height, { samples: 4 });
    rt.texture.colorSpace = THREE.SRGBColorSpace;
    this.renderer.setRenderTarget(rt);
    this.renderer.render(this.scene, cam);
    const pixels = new Uint8Array(width * height * 4);
    this.renderer.readRenderTargetPixels(rt, 0, 0, width, height, pixels);
    this.renderer.setRenderTarget(null);
    rt.dispose();

    // put everything back as it was
    for (const m of extras) { group.remove(m); m.geometry.dispose(); m.material.dispose(); }
    for (const [v, c] of painted) v.top.color.copy(c);
    for (const [g, vis, y] of restore) { g.visible = vis; g.position.y = y; }
    for (const [v, h, l] of lit) { v.height = h; v.litAmount = l; }
    this.currentFloor = prevFloor;

    const canvas = document.createElement('canvas');
    canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext('2d');
    const img = ctx.createImageData(width, height);
    for (let y = 0; y < height; y++) {  // WebGL rows run bottom-up
      img.data.set(pixels.subarray((height - 1 - y) * width * 4, (height - y) * width * 4), y * width * 4);
    }
    ctx.putImageData(img, 0, 0);
    return new Promise(res => canvas.toBlob(res, 'image/jpeg', 0.86));
  }

  #openBounds(group) {
    const box = new THREE.Box3();
    for (const v of this.views) {
      if (v.root.parent === group && v.kind !== 'closed') box.expandByObject(v.mesh);
    }
    return box;
  }

  // Walking directions: segments = [{ floorId, points: [[x, y], …] (floor PDF coords), arrivedBy? }].
  // Drawn as a white line with a dark edge, floating above the rooms so it never hides behind them.
  showRoute(segments) {
    this.clearRoute();
    segments.forEach((seg, i) => {
      const floor = this.museum.floor(seg.floorId);
      const group = this.floorGroups.get(seg.floorId);
      if (!floor || !group) return;
      const pts = seg.points.map(p => this.toWorld(p, floor).setY(1.5))
        .filter((p, j, all) => j === 0 || p.distanceTo(all[j - 1]) > 0.05);
      const parts = [];
      if (pts.length > 1) {
        const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal', 0.1);
        const tube = (r, color) => new THREE.Mesh(new THREE.TubeGeometry(curve, Math.max(24, pts.length * 20), r, 10, false),
          new THREE.MeshBasicMaterial({ color, depthTest: false, transparent: true }));
        parts.push(tube(0.24, COLORS.selected), tube(0.13, 0xffffff));
      }
      const dot = (p, r, color) => {
        const m = new THREE.Mesh(new THREE.SphereGeometry(r, 20, 12), new THREE.MeshBasicMaterial({ color, depthTest: false, transparent: true }));
        m.position.copy(p);
        return m;
      };
      if (pts.length) {
        // start of the whole route, or where the stairs/elevator arrive
        parts.push(dot(pts[0], 0.55, COLORS.selected), dot(pts[0], 0.33, 0xffffff));
        // end of the whole route, or where you take the stairs/elevator
        const last = i === segments.length - 1;
        parts.push(dot(pts.at(-1), last ? 0.7 : 0.55, last ? COLORS.accent : COLORS.selected));
        if (!last) parts.push(dot(pts.at(-1), 0.3, 0xffffff));
      }
      for (const m of parts) { m.renderOrder = 20; group.add(m); }
      this.routeParts.push(...parts);
    });
  }

  clearRoute() {
    for (const m of this.routeParts) { m.parent?.remove(m); m.geometry.dispose(); m.material.dispose(); }
    this.routeParts = [];
  }

  setFacilitiesVisible(on) {
    for (const g of this.floorGroups.values()) g.userData.markers.visible = on;
  }

  facilitiesOn(floorId, types) {
    return this.markers.filter(m => m.userData.floorId === floorId && types.has(m.userData.facility.type));
  }

  focusRoom(id, { zoom = true } = {}) {
    const view = this.rooms.get(id);
    if (!view) return;
    this.showFloor(view.floorId);
    const target = view.center.clone().setY(0);
    const span = Math.max(view.size.x, view.size.z);
    const dist = zoom ? THREE.MathUtils.clamp(span * 3.2, 16, 40) : this.camera.position.distanceTo(this.controls.target);
    this.#flyTo(target, dist);
  }

  // Glide so all the given rooms (or world points) on the current floor are in view.
  frameRooms(ids, points = []) {
    const box = new THREE.Box3();
    for (const id of ids) {
      const v = this.rooms.get(id);
      if (v && v.floorId === this.currentFloor) box.expandByObject(v.mesh);
    }
    for (const p of points) box.expandByPoint(p);
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3()).setY(0);
    const size = box.getSize(new THREE.Vector3());
    const vfov = THREE.MathUtils.degToRad(this.camera.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * this.#visibleAspect());
    const fit = Math.max((size.x * 0.65) / Math.tan(hfov / 2), (size.z * 0.8) / Math.tan(vfov / 2));
    // never closer than the home view, so the room keeps its neighbours for context
    this.#flyTo(center, THREE.MathUtils.clamp(Math.max(fit, this.homeDistance ?? 60), 16, 240));
  }

  // Frame the floor's home rooms (or the whole floor), looking north like the printed map.
  resetView({ animate = true, whole = false } = {}) {
    const group = this.floorGroups.get(this.currentFloor);
    const bounds = whole ? group?.userData.bounds : group?.userData.home;
    if (!bounds) return;
    const center = bounds.getCenter(new THREE.Vector3()).setY(0);
    const size = bounds.getSize(new THREE.Vector3());
    const vfov = THREE.MathUtils.degToRad(this.camera.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * this.#visibleAspect());
    // tilted view: the near edge comes closer to the camera, so leave extra margin
    const dist = Math.max((size.x * 0.5 * 1.18) / Math.tan(hfov / 2), (size.z * 0.5 * 1.5) / Math.tan(vfov / 2));
    this.homeDistance = Math.min(dist, 90);
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
    markerCache.clear();
    this.renderer.setClearColor(theme.paper);
    this.ground.material.opacity = theme.shadow;
    for (const v of this.views) {
      const kind = KIND[v.kind] ?? KIND.corridor;
      if (v.kind !== 'gallery') {
        v.top.color.set(theme[kind.top]);
        v.side.color.set(theme[kind.side]);
      }
      v.edges?.material.color.set(theme.edge);
      if (v.kind === 'gallery') updateLabel(v.label, v.labelText, v.count);
      if (v.kind === 'space' && v.label) {
        const fresh = makeNameLabel(v.room.name, v.size);
        v.label.material.map.dispose();
        v.label.material.map = fresh.material.map;
        v.label.material.needsUpdate = true;
      }
    }
    for (const mesh of this.texts) {
      const label = mesh.userData.text;
      const isArea = label.kind === 'area';
      const { texture } = drawText(label.text, {
        font: `${isArea ? '' : 'italic '}96px ${FONTS.display}`, color: isArea ? theme.area : theme.note,
        maxWidth: isArea ? 2200 : 1400,
      });
      mesh.material.map.dispose();
      mesh.material.map = texture;
      mesh.material.needsUpdate = true;
    }
    for (const d of this.doors) d.material.color.set(theme.door);
    for (const sprite of this.markers) {
      sprite.material.map = markerTexture(sprite.userData.facility.type, sprite.userData.lit);
      sprite.material.needsUpdate = true;
    }
  }

  // HIG maps: show more detail as you zoom in. Small rooms' numbers and the facility icons appear
  // when they have room to breathe; anything lit, selected or searched for always shows.
  #levelOfDetail() {
    const dist = this.camera.position.distanceTo(this.controls.target);
    if (Math.abs(dist - (this.lastLodDist ?? -1)) < 0.5 && !this.lodDirty) return;
    this.lastLodDist = dist;
    this.lodDirty = false;
    for (const v of this.views) {
      if (v.floorId !== this.currentFloor || !v.label) continue;
      const span = Math.min(v.size.x, v.size.z);
      const important = v.targetLit > 0 || this.selected === v || this.visited.has(v);
      v.label.visible = important || span / dist > (v.kind === 'space' ? 0.06 : 0.022);
    }
    const group = this.floorGroups.get(this.currentFloor);
    for (const m of group?.userData.markers.children ?? []) {
      m.visible = m.userData.lit || dist < 95;
    }
  }

  // Colours for galleries and spaces: base → visited tint → search highlight → selection.
  #paintRooms(floorId, plain) {
    for (const v of this.views) {
      if (v.floorId !== floorId || (v.kind !== 'gallery' && v.kind !== 'space')) continue;
      const sel = !plain && this.selected === v;
      const visited = this.visited.has(v);
      if (v.kind === 'gallery') {
        tmpColor.copy(visited ? C.visitedTop : C.roomTop).lerp(C.accent, v.litAmount);
        if (sel) tmpColor.lerp(v.litAmount > 0.5 ? C.selected : C.selectedPlain, 0.8);
        v.top.color.copy(tmpColor);
        v.side.color.copy(C.roomSide).lerp(C.accentSide, v.litAmount);
        v.label.userData.setInk(v.litAmount > 0.5);
      } else {
        v.top.color.copy(visited ? C.visitedTop : C.spaceTop);
        if (sel) v.top.color.lerp(C.selectedPlain, 0.8);
      }
      v.edges.material.color.set(sel ? COLORS.selected : visited ? COLORS.accent : COLORS.edge);
      v.edges.material.opacity = sel ? 1 : visited ? 0.8 : KIND[v.kind].edges;
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

  // Shift the projection so the map's centre sits in the visible area above (or beside) the sheet.
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

    for (const v of this.views) {
      if (v.floorId !== this.currentFloor || (v.kind !== 'gallery' && v.kind !== 'space')) continue;
      v.height += (v.targetHeight - v.height) * k;
      v.litAmount += (v.targetLit - v.litAmount) * k;
      v.body.scale.y = v.height;
      if (v.label) v.label.position.y = v.height + 0.012;
    }
    this.#paintRooms(this.currentFloor, false);
    this.#levelOfDetail();

    for (const d of this.doors) {
      const { a, b } = d.userData;
      if (a.floorId !== this.currentFloor) continue;
      d.position.y = Math.max(a.height, b.height) + 0.03;
      const sel = this.selected && (this.selected === a || this.selected === b);
      d.material.color.set(sel ? COLORS.accent : COLORS.door);
      const thick = sel ? 1.9 : 1;
      if (d.userData.door.axis === 'h') d.scale.set(1, sel ? 2 : 1, thick); else d.scale.set(thick, sel ? 2 : 1, 1);
    }

    // keep the camera over the building
    const t = this.controls.target;
    t.x = THREE.MathUtils.clamp(t.x, -this.panLimit.x, this.panLimit.x);
    t.z = THREE.MathUtils.clamp(t.z, -this.panLimit.z, this.panLimit.z);
    t.y = 0;
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }
}

// ---------- labels ----------

// "273" or, when one shape carries two numbers, "273 / 274"; more than two -> "214 +"
function galleryLabel(room) {
  const ids = [room.id, ...(room.aliases ?? [])];
  if (ids.length === 1) return room.id;
  if (ids.length === 2) return ids.join(' / ');
  return `${room.id} +`;
}

// A flat label lying on the room's roof. Two pre-rendered textures (dark ink / white ink)
// so lit rooms read clearly without re-rendering every frame.
function makeLabel(text, roomSpan) {
  const ink = drawLabel(text, 0, COLORS.label);
  const white = drawLabel(text, 0, COLORS.labelOnAccent);
  const height = THREE.MathUtils.clamp(roomSpan * 0.42, 0.7, 1.7);
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
  const font = `500 ${px}px ${FONTS.display}`;
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

// Name of a courtyard/café/shop, in italic, wrapped to fit the space.
function makeNameLabel(name, size) {
  const { texture, aspect } = drawText(name, {
    font: `italic 96px ${FONTS.display}`, color: COLORS.label, maxWidth: 1100,
  });
  const width = Math.min(size.x * 0.82, 9);
  const height = Math.min(width / aspect, size.z * 0.7, 1.2);
  const mesh = new THREE.Mesh(
    new THREE.PlaneGeometry(height * aspect, height),
    new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false }),
  );
  mesh.rotation.x = -Math.PI / 2;
  mesh.renderOrder = 2;
  return mesh;
}

// Multi-line text texture (wraps at maxWidth px, splits on " · " first).
function drawText(text, { font, color, maxWidth }) {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  ctx.font = font;
  const lines = [];
  for (const part of text.split(' · ')) {
    let line = '';
    for (const word of part.split(' ')) {
      const test = line ? `${line} ${word}` : word;
      if (ctx.measureText(test).width > maxWidth && line) { lines.push(line); line = word; } else line = test;
    }
    lines.push(line);
  }
  const lh = parseInt(font.match(/(\d+)px/)[1], 10) * 1.1;
  const w = Math.ceil(Math.max(...lines.map(l => ctx.measureText(l).width))) + 20;
  const h = Math.ceil(lh * lines.length) + 10;
  canvas.width = w;
  canvas.height = h;
  ctx.font = font;
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  lines.forEach((l, i) => ctx.fillText(l, w / 2, 5 + lh * (i + 0.5)));
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return { texture, aspect: w / h };
}

// Round facility badge: card-coloured disc with the line pictogram; accent disc when highlighted.
const markerCache = new Map();
function markerTexture(type, lit) {
  const key = `${type}:${lit}`;
  if (markerCache.has(key)) return markerCache.get(key);
  const s = 128;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = s;
  const ctx = canvas.getContext('2d');
  const accent = `#${new THREE.Color(COLORS.accent).getHexString()}`;
  ctx.beginPath();
  ctx.arc(s / 2, s / 2, s / 2 - 6, 0, Math.PI * 2);
  ctx.fillStyle = lit ? accent : COLORS.markerBg;
  ctx.fill();
  ctx.lineWidth = 4;
  ctx.strokeStyle = lit ? accent : COLORS.markerRing;
  ctx.stroke();
  drawFacility(ctx, type, s / 2, s / 2, s * 0.56, lit ? '#ffffff' : COLORS.markerInk, 2);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  markerCache.set(key, texture);
  return texture;
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
