/*
 * spacecore.js — pure logic for Stellar Drift (UMD: browser global + Node module).
 * Deterministic: fixed seeds, no Math.random. Testable under node.
 */
(function (global, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    global.SpaceCore = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* ---------------------------------------------------------- deterministic */

  function mulberry32(seed) {
    var a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* -------------------------------------------------------------- catalog */

  // 8 giant stars of the Drift. Positions in world units (x, y, z).
  var CATALOG = [
    { id: 'aurelia', name: 'Aurelia', cls: 'Yellow Giant', hue: 45, x: 0, y: 0, z: 0, r: 210, planets: 5 },
    { id: 'pyra', name: 'Pyra', cls: 'Red Supergiant', hue: 8, x: 5200, y: -1800, z: 900, r: 260, planets: 4 },
    { id: 'vantyr', name: 'Vantyr', cls: 'Blue Supergiant', hue: 205, x: -4600, y: 2600, z: -1400, r: 230, planets: 6 },
    { id: 'thalassa', name: 'Thalassa', cls: 'Orange Giant', hue: 24, x: 2900, y: 4300, z: 2200, r: 200, planets: 3 },
    { id: 'nyx', name: 'Nyx Prime', cls: 'White Giant', hue: 210, x: -5800, y: -2400, z: 600, r: 180, planets: 3 },
    { id: 'cassiope', name: 'Cassiope', cls: 'Blue Giant', hue: 195, x: 8400, y: 3100, z: -2000, r: 190, planets: 4 },
    { id: 'orun', name: 'Orun', cls: 'Red Giant', hue: 15, x: -8600, y: 1200, z: 1600, r: 240, planets: 5 },
    { id: 'aldara', name: 'Aldara', cls: 'Pale Giant', hue: 55, x: 1200, y: -6800, z: -3200, r: 170, planets: 2 }
  ];

  var PLANET_TYPES = ['gas', 'rock', 'ice', 'lava'];

  var TYPE_PALETTES = {
    gas: [
      ['#c98d4b', '#8a5a2b', '#e8c79a', '#a86a35', '#6e441f'],
      ['#7a9cc6', '#4a6a94', '#b8d0ea', '#3a5578', '#90b4d8'],
      ['#b08bb4', '#7a5a80', '#d8c0e0', '#5a3f60', '#c0a0c8']
    ],
    rock: [
      ['#8a7a66', '#5a4e40', '#a89880', '#403828', '#6e6050'],
      ['#9a8a70', '#665844', '#b8a88c', '#4a3e30', '#7a6c58'],
      ['#7a8a94', '#4a5860', '#9aaebc', '#363e44', '#5a6a74']
    ],
    ice: [
      ['#9fd4e8', '#6aa8c8', '#c8ecf8', '#4a88aa', '#b0d8ec'],
      ['#a8d8e0', '#70a8b4', '#d0eef4', '#507a88', '#88c0cc'],
      ['#c0d8e8', '#88a8bc', '#e0f0f8', '#68889c', '#a8c4d4']
    ],
    lava: [
      ['#c85a3a', '#7a2e1a', '#e8945a', '#4a1a0e', '#a04024'],
      ['#d86a30', '#8a3416', '#f0a860', '#54200c', '#b04e20'],
      ['#b84838', '#6e2618', '#e08050', '#421408', '#943828']
    ]
  };

  // Build the full planet list for one star. Deterministic per (starId, seed).
  function makeSystem(star, seed) {
    var rng = mulberry32(seed);
    var planets = [];
    var orbitR = 300;
    for (var i = 0; i < star.planets; i++) {
      orbitR += 120 + rng() * 160; // strictly increasing orbit radii
      var type = PLANET_TYPES[Math.floor(rng() * PLANET_TYPES.length)];
      var palette = TYPE_PALETTES[type][Math.floor(rng() * TYPE_PALETTES[type].length)];
      var size = 14 + rng() * 26 + (type === 'gas' ? 12 : 0);
      planets.push({
        type: type,
        palette: palette,
        orbitR: orbitR,
        angle0: rng() * Math.PI * 2,
        speed: Math.sqrt(900 / orbitR) * (0.6 + rng() * 0.8), // rad/s, Kepler-ish
        size: size,
        ring: rng() < 0.22,
        moons: rng() < 0.3 ? 1 + Math.floor(rng() * 2) : 0,
        tilt: (rng() - 0.5) * 0.9 // orbit plane inclination, rad
      });
    }
    return planets;
  }

  function orbitPos(radius, angle) {
    return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
  }

  // Planet position at time t relative to its star.
  function planetPos(planet, t) {
    return orbitPos(planet.orbitR, planet.angle0 + planet.speed * t);
  }

  // Absolute 3D planet position: orbit in a plane tilted by planet.tilt about the x-axis.
  function planetPos3D(planet, t, star) {
    var o = orbitPos(planet.orbitR, planet.angle0 + planet.speed * t);
    var st = Math.sin(planet.tilt || 0), ct = Math.cos(planet.tilt || 0);
    return {
      x: star.x + o.x,
      y: star.y - o.y * st,
      z: star.z + o.y * ct
    };
  }

  /* ------------------------------------------------------------- dynamics */

  var MAX_SPEED = 900;       // world units / s at full throttle
  var ACCEL = 500;           // thrust accel
  var DRAG = 0.55;           // exponential damping per second (steady full throttle ≈ ACCEL/DRAG, clamped at MAX)

  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }

  // Integrate ship velocity: thrust in [-1, 1], returns new speed.
  function throttleStep(speed, thrust, dt) {
    var v = speed * Math.exp(-DRAG * dt) + thrust * ACCEL * dt;
    return clamp(v, 0, MAX_SPEED);
  }

  // Integrate position from heading (radians) and speed.
  function shipStep(ship, dt) {
    return {
      x: ship.x + Math.cos(ship.heading) * ship.speed * dt,
      y: ship.y + Math.sin(ship.heading) * ship.speed * dt
    };
  }

  // 3D: forward = (cos(yaw)*cos(pitch), sin(pitch), sin(yaw)*cos(pitch)).
  function shipStep3D(ship, dt) {
    var cp = Math.cos(ship.pitch) * ship.speed * dt;
    return {
      x: ship.x + Math.cos(ship.yaw) * cp,
      y: ship.y + Math.sin(ship.pitch) * ship.speed * dt,
      z: ship.z + Math.sin(ship.yaw) * cp
    };
  }

  function dist(a, b) {
    var dx = a.x - b.x, dy = a.y - b.y;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function dist3(a, b) {
    var dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
  }

  function nearestStar(ship, stars) {
    var best = null, bestD = Infinity;
    for (var i = 0; i < stars.length; i++) {
      var d = dist(ship, stars[i]);
      if (d < bestD) { bestD = d; best = stars[i]; }
    }
    return { star: best, dist: bestD };
  }

  function nearestStar3(ship, stars) {
    var best = null, bestD = Infinity;
    for (var i = 0; i < stars.length; i++) {
      var d = dist3(ship, stars[i]);
      if (d < bestD) { bestD = d; best = stars[i]; }
    }
    return { star: best, dist: bestD };
  }

  function warpDuration(distance, speed) {
    if (speed <= 0) return Infinity;
    return distance / speed;
  }

  /* ------------------------------------------------------------- helpers */

  function formatSpeed(v) {
    if (v < 1) return v.toFixed(2) + ' u/s';
    return v.toFixed(0) + ' u/s';
  }

  function hexToRgba(hex, a) {
    var n = parseInt(hex.slice(1), 16);
    return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + a + ')';
  }

  return {
    mulberry32: mulberry32,
    CATALOG: CATALOG,
    PLANET_TYPES: PLANET_TYPES,
    makeSystem: makeSystem,
    orbitPos: orbitPos,
    planetPos: planetPos,
    planetPos3D: planetPos3D,
    MAX_SPEED: MAX_SPEED,
    ACCEL: ACCEL,
    DRAG: DRAG,
    clamp: clamp,
    throttleStep: throttleStep,
    shipStep: shipStep,
    shipStep3D: shipStep3D,
    dist: dist,
    dist3: dist3,
    nearestStar: nearestStar,
    nearestStar3: nearestStar3,
    warpDuration: warpDuration,
    formatSpeed: formatSpeed,
    hexToRgba: hexToRgba
  };
});
