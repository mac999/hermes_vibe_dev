import { test } from 'node:test';
import assert from 'node:assert';
import SC from '../static/js/spacecore.js';

test('mulberry32: deterministic, in [0,1), seed-sensitive', () => {
  const a = SC.mulberry32(42);
  const b = SC.mulberry32(42);
  const c = SC.mulberry32(43);
  for (let i = 0; i < 5; i++) {
    const x = a(), y = b(), z = c();
    assert.ok(x >= 0 && x < 1);
    assert.strictEqual(x, y);
  }
  assert.notStrictEqual(c(), b());
});

test('CATALOG: 8 unique giant stars with required fields', () => {
  assert.strictEqual(SC.CATALOG.length, 8);
  const names = new Set(SC.CATALOG.map((s) => s.name));
  const ids = new Set(SC.CATALOG.map((s) => s.id));
  assert.strictEqual(names.size, 8);
  assert.strictEqual(ids.size, 8);
  for (const s of SC.CATALOG) {
    assert.ok(Number.isFinite(s.x) && Number.isFinite(s.y));
    assert.ok(s.r >= 100 && s.r <= 300);
    assert.ok(s.planets >= 2 && s.planets <= 6);
    assert.ok(s.cls.length > 0);
    assert.ok(s.hue >= 0 && s.hue < 360);
  }
});

test('makeSystem: count, ordering, deterministic per seed', () => {
  const star = SC.CATALOG[0];
  const sys = SC.makeSystem(star, 7);
  assert.strictEqual(sys.length, star.planets);
  for (let i = 1; i < sys.length; i++) assert.ok(sys[i].orbitR > sys[i - 1].orbitR);
  for (const p of sys) {
    assert.ok(SC.PLANET_TYPES.includes(p.type));
    assert.ok(p.palette.length === 5);
    assert.ok(p.speed > 0 && p.size > 0);
    assert.ok(typeof p.ring === 'boolean');
    assert.ok(p.moons >= 0);
  }
  assert.deepStrictEqual(SC.makeSystem(star, 7), sys);
  assert.notDeepStrictEqual(SC.makeSystem(star, 8), sys);
});

test('orbitPos / planetPos: geometry', () => {
  assert.deepStrictEqual(SC.orbitPos(100, 0), { x: 100, y: 0 });
  const p = SC.orbitPos(100, Math.PI / 2);
  assert.ok(Math.abs(p.x) < 1e-9 && Math.abs(p.y - 100) < 1e-9);
  const planet = { orbitR: 200, angle0: 0, speed: 0.5 };
  assert.deepStrictEqual(SC.planetPos(planet, 0), { x: 200, y: 0 });
  const far = SC.planetPos(planet, 2 * Math.PI); // angle 0 + 0.5*2π = π
  assert.ok(Math.abs(far.x + 200) < 1e-9 && Math.abs(far.y) < 1e-9);
  const quarter = SC.planetPos(planet, Math.PI); // angle π/2
  assert.ok(Math.abs(quarter.x) < 1e-9 && Math.abs(quarter.y - 200) < 1e-9);
});

test('3D: CATALOG z, planetPos3D tilt geometry, dist3/nearestStar3, shipStep3D', () => {
  for (const s of SC.CATALOG) assert.ok(Number.isFinite(s.z), s.id + ' z');
  const star = { x: 100, y: 200, z: 300 };
  const p = { orbitR: 100, angle0: 0, speed: 0.5, tilt: 0 };
  assert.deepStrictEqual(SC.planetPos3D(p, 0, star), { x: 200, y: 200, z: 300 }); // angle 0
  const far = SC.planetPos3D(p, 2 * Math.PI, star); // angle π
  assert.ok(Math.abs(far.x - 0) < 1e-9 && Math.abs(far.y - 200) < 1e-9 && Math.abs(far.z - 300) < 1e-9);
  const tilted = SC.planetPos3D({ orbitR: 100, angle0: 0, speed: 0.5, tilt: Math.PI / 2 }, Math.PI, star); // angle π/2
  assert.ok(Math.abs(tilted.x - 100) < 1e-9 && Math.abs(tilted.y - 100) < 1e-9 && Math.abs(tilted.z - 300) < 1e-9);

  assert.strictEqual(SC.dist3({ x: 0, y: 0, z: 0 }, { x: 3, y: 4, z: 12 }), 13);
  const near3 = SC.nearestStar3({ x: 10, y: 0, z: 0 }, SC.CATALOG);
  assert.strictEqual(near3.star.id, 'aurelia');
  assert.ok(near3.dist < 20);

  const fwd = SC.shipStep3D({ x: 0, y: 0, z: 0, yaw: 0, pitch: 0, speed: 100 }, 1);
  assert.strictEqual(fwd.x, 100); assert.strictEqual(fwd.y, 0); assert.strictEqual(fwd.z, 0);
  const up = SC.shipStep3D({ x: 0, y: 0, z: 0, yaw: 0, pitch: Math.PI / 2, speed: 100 }, 1);
  assert.ok(Math.abs(up.y - 100) < 1e-9 && Math.abs(up.x) < 1e-9 && Math.abs(up.z) < 1e-9);
  const right = SC.shipStep3D({ x: 0, y: 0, z: 0, yaw: Math.PI / 2, pitch: 0, speed: 50 }, 2);
  assert.ok(Math.abs(right.z - 100) < 1e-9 && Math.abs(right.x) < 1e-9);
});

test('throttleStep: thrust up, damping, clamp at MAX_SPEED', () => {
  const v1 = SC.throttleStep(0, 1, 1);
  assert.ok(v1 > 0 && v1 < SC.MAX_SPEED);
  const v2 = SC.throttleStep(v1, 1, 1);
  assert.ok(v2 > v1);
  const vIdle = SC.throttleStep(v2, 0, 5);
  assert.ok(vIdle < v2 && vIdle >= 0);
  const vBig = SC.throttleStep(SC.MAX_SPEED, 1, 10);
  assert.strictEqual(vBig, SC.MAX_SPEED);
  const vNeg = SC.throttleStep(0, -1, 1);
  assert.strictEqual(vNeg, 0); // speed never negative
});

test('shipStep: heading + speed integrate position', () => {
  const ship = { x: 0, y: 0, heading: 0, speed: 100 };
  const next = SC.shipStep(ship, 1);
  assert.strictEqual(next.x, 100);
  assert.strictEqual(next.y, 0);
  const up = SC.shipStep({ x: 0, y: 0, heading: Math.PI / 2, speed: 50 }, 2);
  assert.ok(Math.abs(up.x) < 1e-9 && Math.abs(up.y - 100) < 1e-9);
});

test('nearestStar / warpDuration / formatSpeed / hexToRgba', () => {
  const ship = { x: 10, y: 5 };
  const near = SC.nearestStar(ship, SC.CATALOG);
  assert.strictEqual(near.star.id, 'aurelia'); // closest to origin
  assert.ok(near.dist < 20);
  assert.strictEqual(SC.warpDuration(1000, 500), 2);
  assert.strictEqual(SC.warpDuration(1000, 0), Infinity);
  assert.strictEqual(SC.formatSpeed(0.4), '0.40 u/s');
  assert.strictEqual(SC.formatSpeed(500), '500 u/s');
  assert.strictEqual(SC.hexToRgba('#ff0000', 0.5), 'rgba(255,0,0,0.5)');
});
