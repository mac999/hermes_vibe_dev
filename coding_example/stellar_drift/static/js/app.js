/* app.js — Stellar Drift wiring: keyboard, mouse-look, touch controls, audio, HUD, main loop. */
(function () {
  'use strict';

  var canvas = document.getElementById('space');
  var ctx = canvas.getContext('2d');
  var coarse = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);

  var scene = StellarScene.create(SpaceCore.CATALOG);
  scene.setQuality(coarse || Math.min(window.innerWidth, window.innerHeight) < 700);
  window.__scene = scene; // debug / verification handle
  var audio = StellarAudio.create();

  var speedVal = document.getElementById('speedVal');
  var thrFill = document.getElementById('thrFill');
  var targetName = document.getElementById('targetName');
  var targetInfo = document.getElementById('targetInfo');
  var toastEl = document.getElementById('toast');
  var soundBtn = document.getElementById('soundBtn');
  var hudBtn = document.getElementById('hudBtn');

  /* --------------------------------------------------------------- sizing */
  function resize() {
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(window.innerWidth * dpr);
    canvas.height = Math.round(window.innerHeight * dpr);
    canvas.style.width = window.innerWidth + 'px';
    canvas.style.height = window.innerHeight + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener('resize', resize);
  window.addEventListener('orientationchange', resize);
  resize();

  /* ----------------------------------------------------------- input state */
  var input = { thrust: 0, turn: 0, pitch: 0 };
  var kb = { thrust: 0, turn: 0, pitch: 0 };
  var joy = { turn: 0, pitch: 0 };       // virtual joystick (touch)
  var touchThr = 0;                      // THR+ / THR- holds
  var lookDelta = { x: 0, y: 0 };        // px accumulated, applied per frame
  var LOOK_SENS = 0.0032;                // rad per px

  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }

  function recompute() {
    input.thrust = clamp(kb.thrust + touchThr, -1, 1);
    input.turn = clamp(kb.turn + joy.turn, -1, 1);
    input.pitch = clamp(kb.pitch + joy.pitch, -1, 1);
  }

  function heldKey(code, on) {
    var k = code;
    if (k === 'KeyW') kb.thrust = on ? 1 : 0;
    else if (k === 'KeyS') kb.thrust = on ? -1 : 0;
    else if (k === 'KeyA' || k === 'ArrowLeft') kb.turn = on ? -1 : 0;
    else if (k === 'KeyD' || k === 'ArrowRight') kb.turn = on ? 1 : 0;
    else if (k === 'ArrowUp' || k === 'KeyI') kb.pitch = on ? 1 : 0;
    else if (k === 'ArrowDown' || k === 'KeyK') kb.pitch = on ? -1 : 0;
    recompute();
  }

  var toastTimer = null;
  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('show'); }, 3200);
  }

  function doWarp(idx) {
    if (scene.isWarping()) return;
    var star = idx < 0 ? scene.target.star : SpaceCore.CATALOG[idx];
    if (!star) return;
    audio.warp();
    scene.warp(star);
    toast('WARPING — ' + star.name.toUpperCase() + ' · ' + star.cls);
    setTimeout(function () { audio.chime(); }, 1900);
  }

  /* ---------------------------------------------------------- keyboard */
  window.addEventListener('keydown', function (e) {
    var c = e.code;
    if (c === 'Space' || c.indexOf('Arrow') === 0 || c.indexOf('Key') === 0) e.preventDefault();
    if (e.repeat) return;
    if (['KeyW', 'KeyS', 'KeyA', 'KeyD', 'KeyI', 'KeyK', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].indexOf(c) >= 0) {
      heldKey(c, true);
    }
    if (c === 'KeyT') doWarp(-1);
    if (c === 'KeyH') document.body.classList.toggle('help-hidden');
    if (c === 'Equal' || c === 'NumpadAdd') scene.zoomBy(1.25);
    if (c === 'Minus' || c === 'NumpadSubtract') scene.zoomBy(0.8);
    if (c.indexOf('Digit') === 0) {
      var n = parseInt(c.slice(5), 10);
      if (n >= 1 && n <= SpaceCore.CATALOG.length) doWarp(n - 1);
    }
  });

  window.addEventListener('keyup', function (e) {
    var c = e.code;
    if (['KeyW', 'KeyS', 'KeyA', 'KeyD', 'KeyI', 'KeyK', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].indexOf(c) >= 0) {
      heldKey(c, false);
    }
  });

  window.addEventListener('blur', function () {
    kb.thrust = kb.turn = kb.pitch = 0;
    recompute();
  });

  /* ------------------------------------------------------- mouse look */
  var mouseDown = false, mLastX = 0, mLastY = 0;
  canvas.addEventListener('mousedown', function (e) {
    if (e.button !== 0) return;
    mouseDown = true;
    mLastX = e.clientX; mLastY = e.clientY;
  });
  window.addEventListener('mousemove', function (e) {
    if (!mouseDown) return;
    lookDelta.x += e.clientX - mLastX;
    lookDelta.y += e.clientY - mLastY;
    mLastX = e.clientX; mLastY = e.clientY;
  });
  window.addEventListener('mouseup', function () { mouseDown = false; });

  window.addEventListener('wheel', function (e) {
    scene.zoomBy(e.deltaY > 0 ? 0.88 : 1.14);
  }, { passive: true });

  /* ----------------------------------------------------- touch controls */
  // Zones: left 45% = virtual joystick, right = look drag, two fingers = pinch zoom.
  var joyBase = document.getElementById('joybase');
  var joyKnob = document.getElementById('joyknob');
  var touchMode = null;      // 'joy' | 'look' | 'pinch' | null
  var joyOrigin = { x: 0, y: 0 }, joyTouchId = null;
  var lookTouchId = null, lookLast = { x: 0, y: 0 };
  var pinchLastDist = 0;

  function touchPos(e, i) {
    var t = e.touches[i] || e.changedTouches[i];
    return t ? { x: t.clientX, y: t.clientY } : null;
  }

  function pinchDist(e) {
    if (e.touches.length < 2) return 0;
    var dx = e.touches[0].clientX - e.touches[1].clientX;
    var dy = e.touches[0].clientY - e.touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function joySet(p) {
    var R = 44; // match CSS knob travel
    var dx = p.x - joyOrigin.x, dy = p.y - joyOrigin.y;
    var d = Math.sqrt(dx * dx + dy * dy) || 1;
    var m = Math.min(1, d / R);
    var ux = dx / d, uy = dy / d;
    joy.turn = clamp(ux * m, -1, 1);
    joy.pitch = clamp(-uy * m, -1, 1); // drag up = look up
    joyKnob.style.transform = 'translate(' + (ux * m * R) + 'px,' + (uy * m * R) + 'px)';
    recompute();
  }

  function joyReset() {
    joy.turn = 0; joy.pitch = 0;
    joyTouchId = null;
    joyKnob.style.transform = 'translate(0px,0px)';
    joyBase.style.opacity = '0.55';
    recompute();
  }

  canvas.addEventListener('touchstart', function (e) {
    e.preventDefault();
    // Any second finger cancels single-finger modes and starts pinch zoom.
    if (e.touches.length >= 2) {
      joyReset();
      lookTouchId = null;
      touchMode = 'pinch';
      pinchLastDist = pinchDist(e);
      return;
    }
    if (touchMode !== null) return;
    var p = touchPos(e, 0);
    if (!p) return;
    if (p.x < window.innerWidth * 0.45) {
      touchMode = 'joy';
      joyOrigin = p;
      joyTouchId = e.targetTouches[0] ? e.targetTouches[0].identifier : 0;
      joyBase.style.left = p.x + 'px';
      joyBase.style.top = p.y + 'px';
      joyBase.style.opacity = '0.9';
      joySet(p);
    } else {
      touchMode = 'look';
      lookTouchId = e.targetTouches[0] ? e.targetTouches[0].identifier : 0;
      lookLast = p;
    }
  }, { passive: false });

  canvas.addEventListener('touchmove', function (e) {
    e.preventDefault();
    if (touchMode === 'pinch') {
      if (e.touches.length >= 2) {
        var d = pinchDist(e);
        if (pinchLastDist > 0 && d > 0) scene.zoomBy(d / pinchLastDist);
        pinchLastDist = d;
      }
      return;
    }
    if (touchMode === 'joy') {
      for (var i = 0; i < e.touches.length; i++) {
        var t = e.touches[i];
        if (t.identifier === joyTouchId) { joySet({ x: t.clientX, y: t.clientY }); break; }
      }
      if (e.touches.length >= 2) { joyReset(); touchMode = 'pinch'; pinchLastDist = pinchDist(e); }
      return;
    }
    if (touchMode === 'look') {
      for (var j = 0; j < e.touches.length; j++) {
        var t2 = e.touches[j];
        if (t2.identifier === lookTouchId) {
          lookDelta.x += t2.clientX - lookLast.x;
          lookDelta.y += t2.clientY - lookLast.y;
          lookLast = { x: t2.clientX, y: t2.clientY };
          break;
        }
      }
      if (e.touches.length >= 2) { touchMode = 'pinch'; pinchLastDist = pinchDist(e); }
    }
  }, { passive: false });

  function touchEnd(e) {
    var released = {};
    for (var i = 0; i < e.changedTouches.length; i++) {
      released[e.changedTouches[i].identifier] = true;
    }
    if (touchMode === 'joy' && released[joyTouchId]) {
      joyReset();
      touchMode = null;
    }
    if (touchMode === 'look' && released[lookTouchId]) {
      touchMode = null;
    }
    if (touchMode === 'pinch' && e.touches.length < 2) {
      touchMode = null;
    }
    // A remaining single finger resumes a look drag from its current spot.
    if (touchMode === null && e.touches.length === 1) {
      var t = e.touches[0];
      touchMode = 'look';
      lookTouchId = t.identifier;
      lookLast = { x: t.clientX, y: t.clientY };
    }
  }
  canvas.addEventListener('touchend', touchEnd, { passive: false });
  canvas.addEventListener('touchcancel', touchEnd, { passive: false });

  /* ------------------------------------------------------- touch buttons */
  function wireHold(btn, set) {
    var down = function (e) { e.preventDefault(); set(1); };
    var up = function (e) { e.preventDefault(); set(0); };
    btn.addEventListener('pointerdown', down);
    btn.addEventListener('pointerup', up);
    btn.addEventListener('pointercancel', up);
    btn.addEventListener('pointerleave', up);
  }
  var thrUp = document.getElementById('thrUp');
  var thrDn = document.getElementById('thrDn');
  var warpBtn = document.getElementById('warpBtn');
  if (thrUp) wireHold(thrUp, function (v) { touchThr = v; recompute(); });
  if (thrDn) wireHold(thrDn, function (v) { touchThr = -v; recompute(); });
  if (warpBtn) warpBtn.addEventListener('click', function () { doWarp(-1); });

  /* ------------------------------------------------------------- buttons */
  soundBtn.addEventListener('click', function () {
    var on = audio.toggle();
    soundBtn.textContent = on ? 'SOUND: ON' : 'SOUND: OFF';
    soundBtn.classList.toggle('on', on);
    toast(on ? 'SHIP AMBIENCE: ONLINE' : 'SHIP AMBIENCE: MUTED');
  });

  hudBtn.addEventListener('click', function () {
    var dim = document.body.classList.toggle('dim');
    hudBtn.textContent = dim ? 'HUD: DIM' : 'HUD: BRIGHT';
  });

  if (coarse) document.body.classList.add('touch');

  /* ------------------------------------------------------------ main loop */
  var last = performance.now();
  function frame(now) {
    var dt = Math.min(0.05, (now - last) / 1000);
    last = now;

    // Direct mouse/touch look (FPS style).
    if (lookDelta.x !== 0 || lookDelta.y !== 0) {
      scene.ship.yaw += lookDelta.x * LOOK_SENS;
      scene.ship.pitch = clamp(scene.ship.pitch - lookDelta.y * LOOK_SENS, -1.35, 1.35);
      lookDelta.x = 0; lookDelta.y = 0;
    }

    scene.update(dt, input);
    audio.setThrottle(input.thrust);
    scene.render(ctx, window.innerWidth, window.innerHeight);

    // HUD
    speedVal.textContent = String(Math.round(scene.ship.speed)).padStart(4, '0') + ' u/s';
    thrFill.style.width = Math.round(Math.max(0, scene.ship.speed) / SpaceCore.MAX_SPEED * 100) + '%';
    var tg = scene.target;
    if (tg) {
      targetName.textContent = tg.star.name;
      targetInfo.textContent = tg.star.cls + ' · ' + (tg.dist / 1000).toFixed(1) + ' kU';
    }

    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  setTimeout(function () {
    toast(coarse
      ? 'DRAG RIGHT SIDE TO LOOK — LEFT JOYSTICK PIVOTS — T WARP TO STAR'
      : 'W/S THROTTLE · DRAG MOUSE TO LOOK · T WARPS TO THE NEAREST STAR');
  }, 600);
})();
