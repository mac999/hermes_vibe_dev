/*
 * audio.js — procedural calm starship ambience (browser global StellarAudio).
 * Web Audio only; context is created on first user toggle (autoplay-safe).
 */
(function (global) {
  'use strict';

  function createAudio() {
    var AC = global.AudioContext || global.webkitAudioContext;
    var ctx = null;
    var master = null;
    var engineGain = null, engineOscA = null, engineOscB = null, engineFilter = null;
    var on = false;

    function noiseBuffer(seconds) {
      var b = ctx.createBuffer(1, Math.floor(ctx.sampleRate * seconds), ctx.sampleRate);
      var d = b.getChannelData(0);
      for (var i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      return b;
    }

    function build() {
      ctx = new AC();
      master = ctx.createGain();
      master.gain.value = 0;
      master.connect(ctx.destination);

      /* --- ambient drone: slow breathing low tones ---------------------- */
      var drone = ctx.createGain();
      drone.gain.value = 0.5;
      var lp = ctx.createBiquadFilter();
      lp.type = 'lowpass'; lp.frequency.value = 420; lp.Q.value = 0.4;
      drone.connect(lp); lp.connect(master);

      function tone(freq, type, vol) {
        var o = ctx.createOscillator(); o.type = type; o.frequency.value = freq;
        var g = ctx.createGain(); g.gain.value = vol;
        o.connect(g); g.connect(drone); o.start();
        return { o: o, g: g };
      }
      var t1 = tone(55, 'sine', 0.06);
      var t2 = tone(82.5, 'sine', 0.045);
      var t3 = tone(110, 'triangle', 0.018);
      // slow LFO breathing on each partial
      [[t1, 0.06, 0.4], [t2, 0.09, 0.5], [t3, 0.05, 0.45]].forEach(function (pair) {
        var lfo = ctx.createOscillator(); lfo.type = 'sine'; lfo.frequency.value = pair[1];
        var lg = ctx.createGain(); lg.gain.value = pair[0].g.gain.value * pair[2];
        lfo.connect(lg); lg.connect(pair[0].g.gain); lfo.start();
      });

      /* --- faint space "hiss" ------------------------------------------ */
      var nsrc = ctx.createBufferSource();
      nsrc.buffer = noiseBuffer(2); nsrc.loop = true;
      var nlp = ctx.createBiquadFilter(); nlp.type = 'lowpass'; nlp.frequency.value = 260;
      var ng = ctx.createGain(); ng.gain.value = 0.012;
      nsrc.connect(nlp); nlp.connect(ng); ng.connect(master); nsrc.start();
      var nlfo = ctx.createOscillator(); nlfo.frequency.value = 0.04;
      var nlg = ctx.createGain(); nlg.gain.value = 90;
      nlfo.connect(nlg); nlg.connect(nlp.frequency); nlfo.start();

      /* --- engine hum, follows throttle --------------------------------- */
      engineGain = ctx.createGain();
      engineGain.gain.value = 0;
      engineFilter = ctx.createBiquadFilter();
      engineFilter.type = 'lowpass'; engineFilter.frequency.value = 190;
      engineOscA = ctx.createOscillator(); engineOscA.type = 'sawtooth'; engineOscA.frequency.value = 30;
      engineOscB = ctx.createOscillator(); engineOscB.type = 'sawtooth'; engineOscB.frequency.value = 30.35;
      var eg = ctx.createGain(); eg.gain.value = 0.5;
      engineOscA.connect(eg); engineOscB.connect(eg);
      eg.connect(engineFilter); engineFilter.connect(engineGain); engineGain.connect(master);
      engineOscA.start(); engineOscB.start();
    }

    function ensure() {
      if (!ctx) build();
      if (ctx.state === 'suspended') ctx.resume();
    }

    function toggle() {
      ensure();
      on = !on;
      var now = ctx.currentTime;
      master.gain.cancelScheduledValues(now);
      master.gain.setValueAtTime(master.gain.value, now);
      master.gain.linearRampToValueAtTime(on ? 0.9 : 0, now + 0.6);
      return on;
    }

    // thrust in [-1, 1]
    function setThrottle(v) {
      if (!ctx) return;
      var now = ctx.currentTime;
      var m = Math.abs(v);
      engineGain.gain.setTargetAtTime(0.015 + m * 0.11, now, 0.25);
      var f = 28 + m * 30 + (v > 0 ? 0 : 6);
      engineOscA.frequency.setTargetAtTime(f, now, 0.3);
      engineOscB.frequency.setTargetAtTime(f * 1.012, now, 0.3);
      engineFilter.frequency.setTargetAtTime(150 + m * 260, now, 0.3);
    }

    // 1.1s whoosh: filtered noise sweep + rising sine gliss
    function warp() {
      ensure();
      var now = ctx.currentTime;
      var src = ctx.createBufferSource(); src.buffer = noiseBuffer(1.2);
      var bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 1.2;
      bp.frequency.setValueAtTime(140, now);
      bp.frequency.exponentialRampToValueAtTime(5200, now + 0.9);
      var g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, now);
      g.gain.exponentialRampToValueAtTime(0.22, now + 0.28);
      g.gain.exponentialRampToValueAtTime(0.0001, now + 1.15);
      src.connect(bp); bp.connect(g); g.connect(master);
      src.start(now); src.stop(now + 1.2);

      var o = ctx.createOscillator(); o.type = 'sine';
      o.frequency.setValueAtTime(220, now);
      o.frequency.exponentialRampToValueAtTime(1500, now + 0.95);
      var og = ctx.createGain();
      og.gain.setValueAtTime(0.0001, now);
      og.gain.exponentialRampToValueAtTime(0.07, now + 0.3);
      og.gain.exponentialRampToValueAtTime(0.0001, now + 1.1);
      o.connect(og); og.connect(master);
      o.start(now); o.stop(now + 1.2);
    }

    // soft arrival ping
    function chime() {
      if (!ctx || !on) return;
      var now = ctx.currentTime;
      [[660, 0.04], [990, 0.022]].forEach(function (pair) {
        var o = ctx.createOscillator(); o.type = 'sine'; o.frequency.value = pair[0];
        var g = ctx.createGain();
        g.gain.setValueAtTime(0.0001, now);
        g.gain.exponentialRampToValueAtTime(pair[1], now + 0.05);
        g.gain.exponentialRampToValueAtTime(0.0001, now + 1.6);
        o.connect(g); g.connect(master);
        o.start(now); o.stop(now + 1.7);
      });
    }

    return {
      toggle: toggle,
      isOn: function () { return on; },
      setThrottle: setThrottle,
      warp: warp,
      chime: chime
    };
  }

  global.StellarAudio = { create: createAudio };
})(typeof window !== 'undefined' ? window : this);
