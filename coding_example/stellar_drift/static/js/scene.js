/*
 * scene.js — 3D first-person renderer for Stellar Drift (browser global).
 * Pure motion/geometry logic lives in spacecore.js; this file owns all pixels.
 * API: StellarScene.create(catalog) -> scene
 *   scene.update(dt, input)   input = { thrust, turn, pitch }
 *   scene.render(ctx, w, h)   w/h in CSS pixels
 *   scene.warp(star) / scene.warpNearest() / scene.isWarping()
 *   scene.zoom(v) / scene.zoomBy(f) / scene.getZoom()
 *   scene.ship / scene.target { star, dist } / scene.setQuality(mobile)
 * Pure canvas 2D with a manual perspective camera — no dependencies.
 */
(function (global) {
  'use strict';

  var SC = global.SpaceCore;

  var TWO_PI = Math.PI * 2;
  var FOV = 1.15;              // vertical field of view, rad (~66 deg)
  var ZOOM_MIN = 0.35, ZOOM_MAX = 5;
  var NEAR = 2;
  var FAR = 90000;
  var TURN_RATE = 1.5;         // rad/s at full turn input
  var PITCH_RATE = 1.1;

  function clamp01(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function smoothstep(e) { return e * e * (3 - 2 * e); }
  function lerpAngle(a, b, t) {
    var d = (b - a) % TWO_PI;
    if (d > Math.PI) d -= TWO_PI;
    if (d < -Math.PI) d += TWO_PI;
    return a + d * t;
  }
  function norm3(x, y, z) {
    var l = Math.sqrt(x * x + y * y + z * z) || 1;
    return { x: x / l, y: y / l, z: z / l };
  }
  // Deterministic hash in [0,1).
  function hash2(x, y) {
    var h = (x * 374761393 + y * 668265263) | 0;
    h = (h ^ (h >> 13)) * 1274126177;
    return ((h ^ (h >> 16)) >>> 0) / 4294967296;
  }
  function capName(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  /* ------------------------------------------------------------ textures */

  // Pre-render one nebula tile: additive color blobs + dust filaments.
  function makeNebulaTile(hue, seed, S) {
    var c = document.createElement('canvas');
    c.width = c.height = S;
    var g = c.getContext('2d');
    var rng = SC.mulberry32(seed);
    g.globalCompositeOperation = 'lighter';
    var blobs = 24 + Math.floor(rng() * 16);
    for (var i = 0; i < blobs; i++) {
      var x = rng() * S, y = rng() * S, R = S * (0.09 + rng() * 0.22);
      var h = hue + (rng() - 0.5) * 70;
      if (rng() < 0.16) h = 18 + rng() * 34; // warm accent pockets
      var a = 0.05 + rng() * 0.11;
      var gr = g.createRadialGradient(x, y, 0, x, y, R);
      gr.addColorStop(0, 'hsla(' + h + ',' + (58 + rng() * 30) + '%,' + (48 + rng() * 22) + '%,' + a + ')');
      gr.addColorStop(0.55, 'hsla(' + h + ',70%,42%,' + (a * 0.5) + ')');
      gr.addColorStop(1, 'hsla(' + h + ',70%,40%,0)');
      g.fillStyle = gr;
      g.fillRect(0, 0, S, S);
    }
    g.strokeStyle = 'rgba(130,150,210,0.045)';
    for (var f = 0; f < 8; f++) {
      var x0 = rng() * S, y0 = rng() * S, ang = rng() * TWO_PI, len = S * (0.3 + rng() * 0.5);
      g.lineWidth = 2 + rng() * 14;
      g.beginPath();
      g.moveTo(x0, y0);
      g.lineTo(x0 + Math.cos(ang) * len, y0 + Math.sin(ang) * len);
      g.stroke();
    }
    return c;
  }

  /* ------------------------------------------------------------- factory */

  function create(catalog) {
    var stars = catalog;
    var systems = {};
    for (var i = 0; i < stars.length; i++) {
      systems[stars[i].id] = SC.makeSystem(stars[i], 1013 + i * 7919);
    }

    var starfield = [];
    var nebs = [];        // per star: billboard list
    var haze = [];        // camera-following ambient haze
    var bgCanvas = null, vignette = null;

    // Ship / camera. Starts above Aurelia's z-axis, nose on the star.
    var ship = { x: 0, y: 180, z: 2800, yaw: -Math.PI / 2, pitch: -0.045, speed: 0 };
    var cam = { x: ship.x, y: ship.y, z: ship.z };
    var camYaw = ship.yaw, camPitch = ship.pitch;
    var zoom = 1, zoomTarget = 1;

    var t = 0;
    var warp = null;
    var shake = 0;
    var lastThrust = 0;
    var fpx = 1;          // focal scale: pixels per world unit at depth 1
    var target = { star: stars[0], dist: 0 };

    // Camera basis (recomputed each update).
    var F = { x: 0, y: 0, z: 1 }, R = { x: 1, y: 0, z: 0 }, U = { x: 0, y: 1, z: 0 };
    var W2 = 0, H2 = 0;   // half sizes, set in render()

    /* ---------------------------------------------------- static assets */

    function buildStarfield(n) {
      var rng = SC.mulberry32(987654);
      var arr = [];
      for (var i = 0; i < n; i++) {
        var u = rng() * 2 - 1;
        var th = rng() * TWO_PI;
        var s = Math.sqrt(1 - u * u);
        var hueRoll = rng();
        arr.push({
          x: s * Math.cos(th), y: u, z: s * Math.sin(th),
          size: 0.4 + rng() * 1.7,
          color: hueRoll < 0.72 ? '#cfd8ea' : hueRoll < 0.87 ? '#9fc0ff' : '#ffd9a8',
          a: 0.3 + rng() * 0.7,
          tw: 0.4 + rng() * 2.4,
          ph: rng() * TWO_PI
        });
      }
      starfield = arr;
    }

    function buildNebulae(mobile) {
      nebs = [];
      var S = mobile ? 512 : 1024;
      for (var i = 0; i < stars.length; i++) {
        var star = stars[i];
        var rng = SC.mulberry32(500 + i * 977);
        var tiles = [
          makeNebulaTile(star.hue, 9000 + i * 31, S),
          makeNebulaTile(star.hue, 4100 + i * 57, S)
        ];
        var boards = [];
        var n = mobile ? 4 : 6;
        for (var b = 0; b < n; b++) {
          var u = rng() * 2 - 1, th = rng() * TWO_PI, s2 = Math.sqrt(1 - u * u);
          var dx = s2 * Math.cos(th), dy = u * 0.55, dz = s2 * Math.sin(th);
          boards.push({
            tile: tiles[b % 2],
            ox: dx * star.r * (1.4 + rng() * 2.8),
            oy: dy * star.r * (0.8 + rng() * 2.2),
            oz: dz * star.r * (1.4 + rng() * 2.8),
            size: star.r * (2.4 + rng() * 3.4),
            rot: rng() * TWO_PI,
            alpha: 0.3 + rng() * 0.3,
            spin: (rng() - 0.5) * 0.04
          });
        }
        nebs.push(boards);
      }
    }

    function buildHaze(mobile) {
      var S = mobile ? 512 : 768;
      var tiles = [makeNebulaTile(230, 777, S), makeNebulaTile(285, 888, S), makeNebulaTile(205, 999, S)];
      haze = [];
      for (var i = 0; i < 3; i++) {
        haze.push({
          tile: tiles[i],
          az: (i - 1) * 0.75,
          size: mobile ? 26000 : 34000,
          alpha: 0.05 + i * 0.012,
          spin: 0.01 + i * 0.006
        });
      }
    }

    function buildBackground() {
      var S = 512;
      bgCanvas = document.createElement('canvas');
      bgCanvas.width = bgCanvas.height = S;
      var g = bgCanvas.getContext('2d');
      var gr = g.createLinearGradient(0, 0, 0, S);
      gr.addColorStop(0, '#05070f');
      gr.addColorStop(0.45, '#070a18');
      gr.addColorStop(0.55, '#060914');
      gr.addColorStop(1, '#020309');
      g.fillStyle = gr;
      g.fillRect(0, 0, S, S);
      g.globalCompositeOperation = 'lighter';
      var band = g.createLinearGradient(0, S * 0.32, 0, S * 0.62);
      band.addColorStop(0, 'rgba(70,90,150,0)');
      band.addColorStop(0.5, 'rgba(80,100,170,0.05)');
      band.addColorStop(1, 'rgba(70,90,150,0)');
      g.fillStyle = band;
      g.fillRect(0, 0, S, S);

      vignette = document.createElement('canvas');
      vignette.width = vignette.height = S;
      var vg = vignette.getContext('2d');
      var vr = vg.createRadialGradient(S / 2, S / 2, S * 0.32, S / 2, S / 2, S * 0.72);
      vr.addColorStop(0, 'rgba(0,0,6,0)');
      vr.addColorStop(1, 'rgba(0,0,6,0.55)');
      vg.fillStyle = vr;
      vg.fillRect(0, 0, S, S);
    }

    function setQuality(mobile) {
      buildStarfield(mobile ? 480 : 950);
      buildNebulae(mobile);
      buildHaze(mobile);
      buildBackground();
    }

    /* ---------------------------------------------------------- camera */

    function project(wx, wy, wz) {
      var dx = wx - cam.x, dy = wy - cam.y, dz = wz - cam.z;
      var z2 = dx * F.x + dy * F.y + dz * F.z;
      if (z2 < NEAR || z2 > FAR) return null;
      var x2 = dx * R.x + dy * R.y + dz * R.z;
      var y2 = dx * U.x + dy * U.y + dz * U.z;
      var sc = fpx / z2;
      return {
        x: W2 + x2 * sc,
        y: H2 - y2 * sc,
        d: z2,
        s: sc
      };
    }

    /* ----------------------------------------------------------- update */

    function update(dt, input) {
      input = input || {};
      dt = Math.min(dt, 0.1);
      t += dt;
      lastThrust = input.thrust || 0;

      zoom = lerp(zoom, zoomTarget, Math.min(1, 5 * dt));
      shake = Math.max(0, shake - 3 * dt);

      if (warp) {
        warp.t += dt / warp.dur;
        if (warp.t >= 1) {
          ship.x = warp.tx; ship.y = warp.ty; ship.z = warp.tz;
          ship.yaw = warp.tya; ship.pitch = warp.tp;
          cam.x = ship.x; cam.y = ship.y; cam.z = ship.z;
          camYaw = ship.yaw; camPitch = ship.pitch;
          zoomTarget = 1.6;
          warp = null;
          ship.speed = 0;
        } else {
          var e = smoothstep(clamp01(warp.t));
          ship.x = lerp(warp.fx, warp.tx, e);
          ship.y = lerp(warp.fy, warp.ty, e);
          ship.z = lerp(warp.fz, warp.tz, e);
          ship.yaw = lerpAngle(warp.fya, warp.tya, e);
          ship.pitch = lerp(warp.fp, warp.tp, e);
          ship.speed = SC.MAX_SPEED;
        }
      } else {
        ship.yaw += (input.turn || 0) * TURN_RATE * dt;
        ship.pitch = SC.clamp(ship.pitch + (input.pitch || 0) * PITCH_RATE * dt, -1.35, 1.35);
        ship.speed = SC.throttleStep(ship.speed, lastThrust, dt);
        var n = SC.shipStep3D(ship, dt);
        ship.x = n.x; ship.y = n.y; ship.z = n.z;
      }

      // Smooth camera follows the ship.
      var cl = Math.min(1, 6 * dt);
      cam.x = lerp(cam.x, ship.x, cl);
      cam.y = lerp(cam.y, ship.y, cl);
      cam.z = lerp(cam.z, ship.z, cl);
      camYaw = lerpAngle(camYaw, ship.yaw, cl);
      camPitch = lerp(camPitch, ship.pitch, cl);

      var cy = Math.cos(camYaw), sy = Math.sin(camYaw);
      var cp = Math.cos(camPitch), sp = Math.sin(camPitch);
      F = { x: cy * cp, y: sp, z: sy * cp };
      R = { x: -sy * cp, y: 0, z: cy * cp };
      U = { x: -cy * sp, y: cp, z: -sy * sp };

      target = SC.nearestStar3(cam, stars);
    }

    function warpTo(star) {
      if (!star) return;
      var dx = cam.x - star.x, dy = cam.y - star.y, dz = cam.z - star.z;
      var d = norm3(dx, dy, dz);
      var hd = Math.sqrt(dx * dx + dz * dz) || 1;
      warp = {
        fx: cam.x, fy: cam.y, fz: cam.z, fya: camYaw, fp: camPitch,
        tx: star.x + d.x * star.r * 3.2,
        ty: star.y + d.y * star.r * 3.2,
        tz: star.z + d.z * star.r * 3.2,
        // Face the star head-on after the warp.
        tya: Math.atan2(-dz, -dx),
        tp: Math.atan2(-dy, hd),
        t: 0,
        dur: Math.min(2.4, Math.max(1.2, SC.warpDuration(SC.dist3(cam, star), 6000)))
      };
      shake = 1;
      zoomTarget = 1;
    }

    function warpNearest() { warpTo(target.star); }
    function isWarping() { return !!warp; }

    /* -------------------------------------------------------- star glow */

    function drawStar(g, p, s) {
      var R0 = p.s * s.r;
      var pulse = 1 + 0.04 * Math.sin(t * 0.8 + hash2(s.x | 0, s.z | 0) * TWO_PI);
      var rad = Math.min(R0 * pulse, Math.max(W2, H2) * 2.5);
      var glowR = rad * 2.7;
      g.globalCompositeOperation = 'lighter';
      var gr = g.createRadialGradient(p.x, p.y, 0, p.x, p.y, glowR);
      gr.addColorStop(0, 'hsla(' + s.hue + ',95%,88%,0.5)');
      gr.addColorStop(0.22, 'hsla(' + s.hue + ',90%,64%,0.2)');
      gr.addColorStop(0.6, 'hsla(' + s.hue + ',85%,55%,0.06)');
      gr.addColorStop(1, 'hsla(' + s.hue + ',85%,50%,0)');
      g.fillStyle = gr;
      g.beginPath(); g.arc(p.x, p.y, glowR, 0, TWO_PI); g.fill();

      g.globalCompositeOperation = 'source-over';
      var core = g.createRadialGradient(p.x, p.y, rad * 0.1, p.x, p.y, rad);
      core.addColorStop(0, 'hsla(' + s.hue + ',100%,97%,1)');
      core.addColorStop(0.55, 'hsla(' + s.hue + ',95%,82%,1)');
      core.addColorStop(0.9, 'hsla(' + s.hue + ',90%,62%,1)');
      core.addColorStop(1, 'hsla(' + s.hue + ',85%,48%,0.95)');
      g.fillStyle = core;
      g.beginPath(); g.arc(p.x, p.y, rad, 0, TWO_PI); g.fill();

      // Anamorphic streak when the star dominates the view.
      if (rad > H2 * 0.4) {
        g.globalCompositeOperation = 'lighter';
        var k = Math.min(1, (rad - H2 * 0.4) / (H2 * 0.8));
        var st = g.createLinearGradient(p.x - W2 * 1.4, p.y, p.x + W2 * 1.4, p.y);
        st.addColorStop(0, 'hsla(' + s.hue + ',90%,75%,0)');
        st.addColorStop(0.5, 'hsla(' + s.hue + ',90%,85%,' + (0.28 * k).toFixed(3) + ')');
        st.addColorStop(1, 'hsla(' + s.hue + ',90%,75%,0)');
        g.fillStyle = st;
        g.fillRect(p.x - W2 * 1.4, p.y - rad * 0.05, W2 * 2.8, rad * 0.1);
      }
      g.globalCompositeOperation = 'source-over';
    }

    /* --------------------------------------------------------- planets */

    function drawRing(g, p, pl, pr, frontHalf) {
      var squish = 0.22 + 0.78 * Math.abs(Math.sin((pl.tilt || 0) + camYaw));
      var rot = hash2(pl.orbitR | 0, Math.round(pl.angle0 * 97)) * Math.PI + camYaw * 0.25;
      g.save();
      g.translate(p.x, p.y);
      g.rotate(rot);
      g.scale(1, squish);
      g.globalCompositeOperation = 'lighter';
      g.strokeStyle = 'rgba(210,190,150,0.5)';
      g.lineWidth = pr * 0.5;
      g.beginPath();
      g.arc(0, 0, pr * 1.9, frontHalf ? 0 : Math.PI, frontHalf ? Math.PI : TWO_PI);
      g.stroke();
      g.strokeStyle = 'rgba(250,230,190,0.28)';
      g.lineWidth = pr * 0.16;
      g.beginPath();
      g.arc(0, 0, pr * 2.15, frontHalf ? 0 : Math.PI, frontHalf ? Math.PI : TWO_PI);
      g.stroke();
      g.restore();
      g.globalCompositeOperation = 'source-over';
    }

    function drawPlanet(g, e) {
      var pl = e.pl, s = e.s, p = e.p;
      var pr = p.s * pl.size;
      var pal = pl.palette;

      if (pl.ring && pr > 1.5) drawRing(g, p, pl, pr, false);

      if (pr < 0.7) {
        g.fillStyle = pal[0];
        g.globalAlpha = 0.25 + clamp01((0.5 * p.d) / FAR);
        g.fillRect(p.x, p.y, 1.5, 1.5);
        g.globalAlpha = 1;
        return;
      }

      // Direction to the star, in camera space -> lit crescent.
      var L = norm3(s.x - e.pos.x, s.y - e.pos.y, s.z - e.pos.z);
      var lrx = L.x * R.x + L.y * R.y + L.z * R.z;
      var luy = L.x * U.x + L.y * U.y + L.z * U.z;
      var offX = lrx * pr * 0.75;
      var offY = -luy * pr * 0.75;

      var gr = g.createRadialGradient(p.x + offX, p.y + offY, pr * 0.08, p.x, p.y, pr * 1.02);
      gr.addColorStop(0, pal[2]);
      gr.addColorStop(0.4, pal[0]);
      gr.addColorStop(0.78, pal[1]);
      gr.addColorStop(1, pal[4]);
      g.fillStyle = gr;
      g.beginPath(); g.arc(p.x, p.y, pr, 0, TWO_PI); g.fill();

      if (pl.ring && pr > 1.5) drawRing(g, p, pl, pr, true);

      // Gas bands for large disks.
      if (pr > 14 && pl.type === 'gas') {
        g.save();
        g.beginPath(); g.arc(p.x, p.y, pr * 0.98, 0, TWO_PI); g.clip();
        g.globalAlpha = 0.14;
        g.fillStyle = pal[3];
        for (var b = -2; b <= 2; b++) {
          var by = p.y + b * pr * 0.34;
          g.fillRect(p.x - pr, by - pr * 0.06, pr * 2, pr * 0.12);
        }
        g.restore();
        g.globalAlpha = 1;
      }
      if (pr > 20 && pl.type === 'lava') {
        g.globalCompositeOperation = 'lighter';
        var lg = g.createRadialGradient(p.x + offX, p.y + offY, 0, p.x, p.y, pr);
        lg.addColorStop(0, 'rgba(255,150,60,0.35)');
        lg.addColorStop(1, 'rgba(255,80,20,0)');
        g.fillStyle = lg;
        g.beginPath(); g.arc(p.x, p.y, pr, 0, TWO_PI); g.fill();
        g.globalCompositeOperation = 'source-over';
      }
    }

    function drawMoon(g, e) {
      var pr = e.p.s * e.m.size;
      if (pr < 0.7) {
        g.fillStyle = '#b9bfc9';
        g.globalAlpha = 0.8;
        g.fillRect(e.p.x, e.p.y, 1.5, 1.5);
        g.globalAlpha = 1;
        return;
      }
      var gr = g.createRadialGradient(e.p.x - pr * 0.3, e.p.y - pr * 0.3, pr * 0.1, e.p.x, e.p.y, pr);
      gr.addColorStop(0, '#cfd5df');
      gr.addColorStop(0.7, '#9aa3b2');
      gr.addColorStop(1, '#4c5260');
      g.fillStyle = gr;
      g.beginPath(); g.arc(e.p.x, e.p.y, pr, 0, TWO_PI); g.fill();
    }

    /* ------------------------------------------------------------- main */

    function render(g, w, h) {
      W2 = w / 2; H2 = h / 2;
      fpx = (h / 2) / Math.tan(FOV / 2) * zoom;
      var minWH = Math.min(w, h);

      // Background (guard: assets built via setQuality before first render).
      g.globalCompositeOperation = 'source-over';
      g.globalAlpha = 1;
      if (bgCanvas) {
        g.drawImage(bgCanvas, 0, 0, w, h);
      } else {
        g.fillStyle = '#04060f';
        g.fillRect(0, 0, w, h);
      }

      // Ambient haze (camera-anchored billboards, slow spin).
      if (haze.length) {
        g.globalCompositeOperation = 'lighter';
        for (var i = 0; i < haze.length; i++) {
          var hz = haze[i];
          var ang = hz.az + t * hz.spin;
          var ca = Math.cos(ang), sa = Math.sin(ang);
          var bx = (F.x * ca + R.x * sa) * hz.size * 0.6 + U.x * hz.size * 0.12 * Math.sin(t * 0.05 + i * 2);
          var by = (F.y * ca + R.y * sa) * hz.size * 0.6 + U.y * hz.size * 0.12 * Math.sin(t * 0.05 + i * 2);
          var bz = (F.z * ca + R.z * sa) * hz.size * 0.6 + U.z * hz.size * 0.12 * Math.sin(t * 0.05 + i * 2);
          var p = project(cam.x + bx, cam.y + by, cam.z + bz);
          if (!p) continue;
          var sz = p.s * hz.size;
          if (sz < 10) continue;
          g.save();
          g.translate(p.x, p.y);
          g.rotate(t * hz.spin + i * 2.1);
          g.globalAlpha = hz.alpha;
          g.drawImage(hz.tile, -sz / 2, -sz / 2, sz, sz);
          g.restore();
        }
        g.globalAlpha = 1;
      }

      // Distant starfield (directions on the unit sphere).
      for (var k = 0; k < starfield.length; k++) {
        var st = starfield[k];
        var z2 = st.x * F.x + st.y * F.y + st.z * F.z;
        if (z2 < 0.04) continue;
        var x2 = st.x * R.x + st.y * R.y + st.z * R.z;
        var y2 = st.x * U.x + st.y * U.y + st.z * U.z;
        var sx = W2 + (x2 / z2) * fpx;
        var sy = H2 - (y2 / z2) * fpx;
        if (sx < -20 || sx > w + 20 || sy < -20 || sy > h + 20) continue;
        var twk = st.a * (0.72 + 0.28 * Math.sin(t * st.tw + st.ph));
        g.globalAlpha = twk;
        g.fillStyle = st.color;
        var rr = st.size * Math.min(1.6, Math.max(0.6, zoom * 0.8));
        if (rr < 1.15) {
          g.fillRect(sx, sy, rr + 0.4, rr + 0.4);
        } else {
          g.beginPath(); g.arc(sx, sy, rr, 0, TWO_PI); g.fill();
        }
      }
      g.globalAlpha = 1;
      g.globalCompositeOperation = 'source-over';

      // Per-star nebula billboards (additive, far to near).
      var nebItems = [];
      for (var nbi = 0; nbi < nebs.length; nbi++) {
        var star = stars[nbi];
        var boards = nebs[nbi];
        for (var b2 = 0; b2 < boards.length; b2++) {
          var bd = boards[b2];
          var bp = project(star.x + bd.ox, star.y + bd.oy, star.z + bd.oz);
          if (bp) nebItems.push({ d: bp.d, bd: bd, p: bp });
        }
      }
      nebItems.sort(function (a, b) { return b.d - a.d; });
      g.globalCompositeOperation = 'lighter';
      for (var ni = 0; ni < nebItems.length; ni++) {
        var it = nebItems[ni];
        var nsz = it.p.s * it.bd.size;
        if (nsz < 8 || nsz > minWH * 12) continue;
        g.save();
        g.translate(it.p.x, it.p.y);
        g.rotate(it.bd.rot + t * it.bd.spin);
        g.globalAlpha = it.bd.alpha * clamp01((FAR - it.d) / (FAR * 0.5));
        g.drawImage(it.bd.tile, -nsz / 2, -nsz / 2, nsz, nsz);
        g.restore();
      }
      g.globalAlpha = 1;
      g.globalCompositeOperation = 'source-over';

      // Composite bodies: stars, planets, moons — painter's sort far->near.
      var list = [];
      for (var si = 0; si < stars.length; si++) {
        var sp_ = project(stars[si].x, stars[si].y, stars[si].z);
        if (sp_) list.push({ d: sp_.d, kind: 'star', s: stars[si], p: sp_ });
      }
      for (var pi = 0; pi < stars.length; pi++) {
        var star2 = stars[pi];
        var planets = systems[star2.id];
        for (var pj = 0; pj < planets.length; pj++) {
          var pl = planets[pj];
          var pos = SC.planetPos3D(pl, t, star2);
          var pp = project(pos.x, pos.y, pos.z);
          if (!pp) continue;
          list.push({ d: pp.d, kind: 'planet', pl: pl, s: star2, p: pp, pos: pos });
          if (pp.s * pl.size > 3 && pl.moons > 0) {
            for (var mj = 0; mj < pl.moons; mj++) {
              var mr = pl.size * (2.4 + mj * 1.7);
              var ma = t * (0.9 + mj * 0.4) + mj * 2.1 + pl.angle0;
              var mx = pos.x + Math.cos(ma) * mr;
              var my = pos.y + Math.sin(ma) * mr * 0.35;
              var mz = pos.z + Math.sin(ma + 1.7) * mr * 0.8;
              var mp = project(mx, my, mz);
              if (mp) list.push({ d: mp.d, kind: 'moon', m: { size: Math.max(2.5, pl.size * 0.22) }, p: mp });
            }
          }
        }
      }
      list.sort(function (a, b) { return b.d - a.d; });
      for (var li = 0; li < list.length; li++) {
        var e = list[li];
        if (e.kind === 'star') drawStar(g, e.p, e.s);
        else if (e.kind === 'planet') drawPlanet(g, e);
        else drawMoon(g, e);
      }

      // Labels for nearby bodies.
      for (var lj = 0; lj < list.length; lj++) {
        var e2 = list[lj];
        if (e2.kind === 'planet' && e2.p.s * e2.pl.size > 12) {
          var pr2 = e2.p.s * e2.pl.size;
          g.strokeStyle = 'rgba(170,195,235,0.45)';
          g.lineWidth = 1;
          g.beginPath();
          g.moveTo(e2.p.x, e2.p.y - pr2 - 4);
          g.lineTo(e2.p.x, e2.p.y - pr2 - 14);
          g.stroke();
          g.fillStyle = 'rgba(190,210,245,0.85)';
          g.font = '12px "Inter", system-ui, sans-serif';
          g.fillText(capName(e2.pl.type) + ' world — ' + (e2.p.d / 1000).toFixed(1) + ' kU',
            e2.p.x + 6, e2.p.y - pr2 - 12);
        }
        if (e2.kind === 'star' && e2.p.s * e2.s.r > 26) {
          g.fillStyle = 'rgba(200,218,248,0.9)';
          g.font = '13px "Inter", system-ui, sans-serif';
          g.fillText(e2.s.name + ' · ' + e2.s.cls + ' — ' + (e2.p.d / 1000).toFixed(1) + ' kU',
            e2.p.x + 10, e2.p.y - e2.p.s * e2.s.r - 12);
        }
      }

      drawSpeedFX(g, w, h);

      // Vignette.
      g.globalCompositeOperation = 'source-over';
      if (vignette) g.drawImage(vignette, 0, 0, w, h);
    }

    /* ------------------------------------------------------ speed FX */

    function drawSpeedFX(g, w, h) {
      var cx = W2, cy2 = H2;
      var minWH = Math.min(w, h);
      var sp = ship.speed / SC.MAX_SPEED;
      var warping = isWarping();

      // Screen shake while warping.
      if (shake > 0 && warping) {
        var amp = 6 * shake;
        cx += (Math.random() - 0.5) * amp;
        cy2 += (Math.random() - 0.5) * amp;
      }

      // Motion streaks radiating from center.
      var n = warping ? 46 : sp > 0.03 ? Math.floor(5 + 38 * sp) : 0;
      if (n > 0) {
        g.globalCompositeOperation = 'lighter';
        for (var i = 0; i < n; i++) {
          var a = hash2(i, 7) * TWO_PI;
          var r0 = (0.16 + 0.55 * hash2(i, 13)) * minWH;
          var len = (0.2 + 0.8 * hash2(i, 29)) * minWH * (warping ? 1.2 : 0.25 + sp);
          var ca = Math.cos(a), sa = Math.sin(a);
          var x0 = cx + ca * r0, y0 = cy2 + sa * r0 * 0.8;
          var al = (warping ? 0.32 : 0.05 + 0.3 * sp) * (0.4 + 0.6 * hash2(i, 31));
          g.strokeStyle = 'rgba(150,185,255,' + al.toFixed(3) + ')';
          g.lineWidth = 1 + hash2(i, 3) * 1.2;
          g.beginPath();
          g.moveTo(x0, y0);
          g.lineTo(cx + ca * (r0 + len), cy2 + sa * (r0 + len) * 0.8);
          g.stroke();
        }
        g.globalCompositeOperation = 'source-over';
      }

      // Engine glow at full throttle.
      if (lastThrust > 0.05 && !warping) {
        g.globalCompositeOperation = 'lighter';
        var eg = g.createRadialGradient(cx, h * 1.15, 0, cx, h * 1.15, h * 0.9);
        eg.addColorStop(0, 'rgba(90,140,255,' + (0.12 * lastThrust).toFixed(3) + ')');
        eg.addColorStop(1, 'rgba(90,140,255,0)');
        g.fillStyle = eg;
        g.fillRect(0, 0, w, h);
        g.globalCompositeOperation = 'source-over';
      }

      // Reticle (hidden while warping).
      if (!warping) {
        g.strokeStyle = 'rgba(180,205,245,0.4)';
        g.lineWidth = 1;
        var rl = 7;
        g.beginPath();
        g.moveTo(cx - rl - 6, cy2); g.lineTo(cx - 6, cy2);
        g.moveTo(cx + 6, cy2); g.lineTo(cx + rl + 6, cy2);
        g.moveTo(cx, cy2 - rl - 6); g.lineTo(cx, cy2 - 6);
        g.moveTo(cx, cy2 + 6); g.lineTo(cx, cy2 + rl + 6);
        g.stroke();
        g.fillStyle = 'rgba(180,205,245,0.55)';
        g.beginPath(); g.arc(cx, cy2, 1.2, 0, TWO_PI); g.fill();
      }
    }

    /* ------------------------------------------------------------- api */

    return {
      ship: ship,
      // Live getter: update() reassigns the closure variable, so a snapshot
      // property would always return the initial {star, dist} object.
      get target() { return target; },
      setQuality: setQuality,
      update: update,
      render: render,
      warp: warpTo,
      warpNearest: warpNearest,
      isWarping: isWarping,
      zoom: function (v) { zoomTarget = SC.clamp(v, ZOOM_MIN, ZOOM_MAX); },
      zoomBy: function (f) { zoomTarget = SC.clamp(zoomTarget * f, ZOOM_MIN, ZOOM_MAX); },
      getZoom: function () { return zoom; }
    };
  }

  global.StellarScene = { create: create };
})(typeof self !== 'undefined' ? self : this);
