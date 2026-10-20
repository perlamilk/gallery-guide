// Walking directions inside the museum.
// A graph of every room on every floor: doorways (from floors.json `doors`) connect rooms on a floor,
// stairs and elevators connect matching icons on floors above and below.
// Distances are in PDF points; METERS_PER_POINT turns them into an estimate for people.

const METERS_PER_POINT = 0.35;
const WALK_SPEED = 0.9;              // m/s, an unhurried museum pace
const STAIRS_COST = 110;             // per floor, in PDF points of walking (~40 m: climbing is tiring)
const ELEVATOR_COST = 140;           // waiting for it takes longer than climbing
const LINK_DISTANCE = 30;            // stairs/elevators on two floors count as one if this close (points)

export class Router {
  constructor(museum) {
    this.museum = museum;
    this.nodes = new Map();          // key -> { key, floor, room, center }
    this.edges = new Map();          // key -> [{ to, cost, via, kind }]
    this.#build();
  }

  static key(floorId, roomId) { return `${floorId}|${roomId}`; }

  #build() {
    const { museum } = this;
    for (const floor of museum.floors) {
      for (const room of floor.rooms) {
        const key = Router.key(floor.id, room.id);
        this.nodes.set(key, { key, floor, room, center: innerPoint(room.poly) });
        this.edges.set(key, []);
      }
      for (const d of floor.doors ?? []) {
        const a = this.nodes.get(Router.key(floor.id, d.a));
        const b = this.nodes.get(Router.key(floor.id, d.b));
        if (!a || !b) continue;
        const s = floor.transform?.[0] ?? 1;
        const cost = (dist(a.center, d.at) + dist(d.at, b.center)) * s;
        this.#link(a, b, cost, { kind: 'door', at: d.at, floor: floor.id });
      }
    }

    // stairs and elevators: the room each icon sits in, matched with the same icon on the next floor
    const vertical = [];
    for (const floor of museum.floors) {
      for (const f of floor.amenities ?? []) {
        if (f.type !== 'stairs' && f.type !== 'elevator') continue;
        const room = floor.rooms.find(r => r.kind !== undefined && pointInPoly(f.at, r.poly))
          ?? nearestRoom(floor, f.at);
        if (room) vertical.push({ type: f.type, floor, room, at: f.at, shared: toShared(floor, f.at) });
      }
    }
    const ordered = [...museum.floors].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    for (let i = 0; i + 1 < ordered.length; i++) {
      const lower = vertical.filter(v => v.floor === ordered[i]);
      const upper = vertical.filter(v => v.floor === ordered[i + 1]);
      for (const a of lower) {
        let best = null;
        for (const b of upper) {
          if (b.type !== a.type) continue;
          const d = dist(a.shared, b.shared);
          if (d < LINK_DISTANCE && (!best || d < best.d)) best = { b, d };
        }
        if (!best) continue;
        const na = this.nodes.get(Router.key(a.floor.id, a.room.id));
        const nb = this.nodes.get(Router.key(best.b.floor.id, best.b.room.id));
        const cost = a.type === 'stairs' ? STAIRS_COST : ELEVATOR_COST;
        this.#link(na, nb, cost, { kind: a.type, at: a.at, toAt: best.b.at, floor: a.floor.id, toFloor: best.b.floor.id });
      }
    }
  }

  #link(a, b, cost, info) {
    this.edges.get(a.key).push({ to: b.key, cost, ...info });
    // the way back: swap the two ends of a stairs/elevator link
    const back = info.kind === 'door' ? info
      : { ...info, at: info.toAt, toAt: info.at, floor: info.toFloor, toFloor: info.floor };
    this.edges.get(b.key).push({ to: a.key, cost, ...back });
  }

  // Shortest way between two rooms (ids may be gallery aliases). Returns null if there's no way.
  route(fromId, toId, { avoidStairs = false } = {}) {
    const start = this.#nodeFor(fromId);
    const goal = this.#nodeFor(toId);
    if (!start || !goal) return null;
    if (start === goal) return { nodes: [start], legs: [], cost: 0 };

    const distTo = new Map([[start.key, 0]]);
    const prev = new Map();
    const open = new Set([start.key]);
    while (open.size) {
      let cur = null, best = Infinity;
      for (const k of open) { const d = distTo.get(k); if (d < best) { best = d; cur = k; } }
      open.delete(cur);
      if (cur === goal.key) break;
      for (const e of this.edges.get(cur) ?? []) {
        if (avoidStairs && e.kind === 'stairs') continue;
        // don't cut through closed areas or other people's offices: only walk in public rooms
        const next = this.nodes.get(e.to);
        if (!next || next.room.kind === 'closed') continue;
        const d = best + e.cost;
        if (d < (distTo.get(e.to) ?? Infinity)) {
          distTo.set(e.to, d);
          prev.set(e.to, { from: cur, edge: e });
          open.add(e.to);
        }
      }
    }
    if (!distTo.has(goal.key)) return null;

    const legs = [];
    for (let k = goal.key; k !== start.key;) {
      const p = prev.get(k);
      legs.unshift({ from: this.nodes.get(p.from), to: this.nodes.get(k), edge: p.edge });
      k = p.from;
    }
    return { nodes: [start, ...legs.map(l => l.to)], legs, cost: distTo.get(goal.key) };
  }

  // A route through several rooms in the given order.
  routeThrough(ids, options) {
    const parts = [];
    for (let i = 0; i + 1 < ids.length; i++) {
      const r = this.route(ids[i], ids[i + 1], options);
      if (r) parts.push(r);
    }
    if (!parts.length) return null;
    return {
      nodes: parts.flatMap((p, i) => (i ? p.nodes.slice(1) : p.nodes)),
      legs: parts.flatMap(p => p.legs),
      cost: parts.reduce((s, p) => s + p.cost, 0),
    };
  }

  // Order stops so the walk is short: start from `from`, always go to the nearest unvisited stop.
  orderStops(fromId, ids, options) {
    const left = [...new Set(ids)].filter(id => this.#nodeFor(id));
    const order = [];
    let cur = fromId ?? left[0];
    while (left.length) {
      let best = 0, bestCost = Infinity;
      left.forEach((id, i) => {
        const r = this.route(cur, id, options);
        if (r && r.cost < bestCost) { bestCost = r.cost; best = i; }
      });
      cur = left.splice(best, 1)[0];
      order.push(cur);
    }
    return order;
  }

  // Polylines per floor, in each floor's own PDF coordinates: what the map draws.
  segments(route) {
    if (!route) return [];
    const segs = [];
    let cur = { floorId: route.nodes[0].floor.id, points: [route.nodes[0].center] };
    for (const leg of route.legs) {
      const e = leg.edge;
      if (e.kind === 'door') {
        cur.points.push(e.at, leg.to.center);
      } else {
        cur.points.push(e.at);
        segs.push(cur);
        cur = { floorId: e.toFloor, points: [e.toAt, leg.to.center], arrivedBy: e.kind };
      }
    }
    segs.push(cur);
    return segs;
  }

  // Human steps: rooms you walk into (corridors folded together) and floor changes.
  steps(route) {
    if (!route) return [];
    const out = [];
    for (const leg of route.legs) {
      const e = leg.edge;
      if (e.kind !== 'door') {
        const up = (this.museum.floor(e.toFloor)?.order ?? 0) > (this.museum.floor(e.floor)?.order ?? 0);
        out.push({ kind: e.kind, text: `Take the ${e.kind === 'stairs' ? 'stairs' : 'elevator'} ${up ? 'up' : 'down'} to ${this.museum.floor(e.toFloor).label}` });
        continue;
      }
      const room = leg.to.room;
      if (room.kind === 'corridor') {
        if (out.at(-1)?.kind !== 'corridor') out.push({ kind: 'corridor', text: 'Continue through the corridor' });
        continue;
      }
      out.push({ kind: room.kind, id: room.id, text: `${out.length ? 'Into' : 'Go into'} ${roomName(room)}` });
    }
    return out;
  }

  meters(route) { return route ? Math.round(route.cost * METERS_PER_POINT) : 0; }
  minutes(route) { return route ? Math.max(1, Math.round(this.meters(route) / WALK_SPEED / 60)) : 0; }

  #nodeFor(id) {
    const info = this.museum.roomInfo(id);
    if (info) return this.nodes.get(Router.key(info.floor.id, info.room.id));
    for (const n of this.nodes.values()) if (n.room.id === id) return n;
    return null;
  }
}

export function roomName(room) {
  if (room.kind === 'space') return room.name;
  if (room.kind === 'gallery') return `Gallery ${[room.id, ...(room.aliases ?? [])].join(' / ')}`;
  return 'the corridor';
}

// ---------- geometry ----------

const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

function toShared(floor, [x, y]) {
  const [s, dx, dy] = floor.transform ?? [1, 0, 0];
  return [x * s + dx, y * s + dy];
}

export function pointInPoly([x, y], poly) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i]; const [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}

function nearestRoom(floor, at) {
  let best = null, bd = Infinity;
  for (const r of floor.rooms) {
    const c = innerPoint(r.poly);
    const d = dist(c, at);
    if (d < bd) { bd = d; best = r; }
  }
  return bd < 40 ? best : null;
}

// A point inside the shape near its middle (the centroid can fall outside L-shaped rooms).
export function innerPoint(poly) {
  let a = 0, cx = 0, cy = 0;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const f = poly[j][0] * poly[i][1] - poly[i][0] * poly[j][1];
    a += f; cx += (poly[j][0] + poly[i][0]) * f; cy += (poly[j][1] + poly[i][1]) * f;
  }
  if (Math.abs(a) > 1e-6) {
    const c = [cx / (3 * a), cy / (3 * a)];
    if (pointInPoly(c, poly)) return c;
  }
  const xs = poly.map(p => p[0]), ys = poly.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const mid = [(x0 + x1) / 2, (y0 + y1) / 2];
  let best = null, bd = Infinity;
  for (let i = 1; i < 12; i++) {
    for (let j = 1; j < 12; j++) {
      const p = [x0 + ((x1 - x0) * i) / 12, y0 + ((y1 - y0) * j) / 12];
      if (!pointInPoly(p, poly)) continue;
      const d = dist(p, mid);
      if (d < bd) { bd = d; best = p; }
    }
  }
  return best ?? mid;
}
