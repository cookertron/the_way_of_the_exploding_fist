/* kit.test.js -- the platform runtime's own suite, run against the BUILT
 * starter page through the rig (manual phase 14).  A port keeps this file
 * and appends its game's checks after it; nothing here knows about any game.
 *
 *   node test/kit.test.js
 */
'use strict';
const { execFileSync } = require('child_process');
const path = require('path');
const rig = require('./rig');
const { check, checkTrue } = rig;

/* ---- the build is under test ------------------------------------------ */
let built = true;
try { execFileSync('python', [path.join(rig.ROOT, 'tools', 'build.py')],
                   { cwd: rig.ROOT, stdio: 'pipe' }); }
catch (e) { built = false; console.log(String(e.stdout || '') + String(e.stderr || '')); }
checkTrue('tools/build.py builds the page from port.json', built);

const { S, P, sandbox } = rig.loadBuilt();
const FRAME_HZ = S.FRAME_HZ;
check('the frame clock defaults to the 48K ULA', FRAME_HZ, 50.08);

/* =======================================================================
   THE DISPLAY FILE
   ======================================================================= */
{
  const SS = S.SpecScreen;
  check('pixelAddr: the ULA bit layout 010TTLLLRRRCCCCC',
        [SS.pixelAddr(0, 0), SS.pixelAddr(8, 0), SS.pixelAddr(0, 1),
         SS.pixelAddr(0, 8), SS.pixelAddr(0, 64), SS.pixelAddr(255, 191)],
        [0x4000, 0x4001, 0x4100, 0x4020, 0x4800, 0x57FF]);
  check('attrAddr: the third from bits 12:11, L carried through',
        [SS.attrAddr(0x4000), SS.attrAddr(0x4800), SS.attrAddr(0x50E5)],
        [0x5800, 0x5900, 0x5AE5]);
  check('attrAt: 32 a row', SS.attrAt(31, 23), 0x5AFF);
  check('nextRow: INC H within a character row, then L += $20 / H -= 8',
        [SS.nextRow(0x4000), SS.nextRow(0x4700), SS.nextRow(0x47E0)],
        [0x4100, 0x4020, 0x4800]);
  check('nextCol: INC L, and H += 8 when L wraps into the next third',
        [SS.nextCol(0x4000), SS.nextCol(0x40FF)], [0x4001, 0x4800]);
  const scr = new SS();
  scr.plot(3, 5, true);
  check('plot sets the right bit of the right byte', scr.get(SS.pixelAddr(3, 5)), 0x10);
  scr.plot(3, 5, false);
  check('...and clears it', scr.get(SS.pixelAddr(3, 5)), 0);
  const font = new Uint8Array([1,2,3,4,5,6,7,8, 9,10,11,12,13,14,15,16]);
  const p = scr.putGlyph(0x4000, font, 0);
  check('putGlyph writes eight rows down the pixel-row chain and steps right',
        [scr.get(0x4000), scr.get(0x4100), scr.get(0x4700), p], [1, 2, 8, 0x4001]);
  scr.clear();
  scr.print(0x4020, 'AB', font, 65);
  check('print indexes the font from its first code',
        [scr.get(0x4020), scr.get(0x4021), scr.get(0x4721)], [1, 9, 16]);
  scr.fillAttr(0x38);
  check('fillAttr touches attributes only',
        [scr.get(0x5800), scr.get(0x5AFF), scr.get(0x4020)], [0x38, 0x38, 1]);
}

/* ---- the renderer, at the draw-list level -------------------------- */
{
  const ctx = sandbox.document.getElementById('scr').getContext('2d');
  const scr = new S.SpecScreen();
  scr.put(0x4000, 0x80); scr.put(0x5800, 0x07);      // one ink pixel, white on black
  rig.record(true); S.renderScreen(ctx, scr, 0); rig.record(false);
  const has = (x, y, w, c) => rig.drawCalls.some(d => d[1] === x && d[2] === y && d[3] === w && d[5] === c);
  checkTrue('an ink pixel is one dim-white run of 1', has(0, 0, 1, '#d7d7d7'));
  checkTrue('...followed by a paper run of 7', has(1, 0, 7, '#000000'));
  checkTrue('an all-paper row is ONE call, not eight', has(8, 0, 8, '#000000'));
  scr.put(0x5800, 0x47);
  rig.record(true); S.renderScreen(ctx, scr, 0); rig.record(false);
  checkTrue('BRIGHT selects the second palette', has(0, 0, 1, '#ffffff'));
  scr.put(0x5800, 0x87);                              // FLASH
  rig.record(true); S.renderScreen(ctx, scr, 16); rig.record(false);
  checkTrue('FLASH swaps ink and paper when bit 4 of the frame counter is set',
            has(0, 0, 1, '#000000') && has(1, 0, 7, '#d7d7d7'));
  rig.record(true); S.renderScreen(ctx, scr, 15); rig.record(false);
  checkTrue('...and not otherwise', has(0, 0, 1, '#d7d7d7'));
  rig.record(true); S.renderScreen(ctx, scr, 0, 1); rig.record(false);
  checkTrue('`rows` clips the render', rig.drawCalls.every(d => d[2] < 8));
  S.paintBorder(2);
  check('the border paints the overscan element from the dim palette',
        sandbox.document.getElementById('overscan').style.background, '#d70000');
}

/* =======================================================================
   THE KEYBOARD MATRIX AND THE KEMPSTON PORT
   ======================================================================= */
{
  const kb = new S.Keyboard();
  kb.press('A');
  check('a key down is a ZERO bit in its half-row', [kb.halfrow(1), kb.bit(1, 0), kb.bit(1, 1)], [0xFE, 0, 1]);
  check('IN A,(C): a LOW select bit reads that half-row', kb.port(0xFD), 0xFE);
  check('...a HIGH one does not', kb.port(0xFE), 0xFF);
  kb.press('SPACE');
  check('...and several low bits AND their rows together, as the ULA does',
        [kb.port(0x7F), kb.port(0x00)], [0xFE, 0xFE]);
  kb.releaseAll();
  check('releaseAll clears keys and both Kempston bytes',
        [kb.port(0x00), kb.kempston, kb.kempston2], [0xFF, 0, 0]);
  const km = S.buildKeymap({ KeyZ: 'SYM' });
  check('the arrows ARE 5/6/7/8, the cursor keys', [km.ArrowLeft, km.ArrowDown, km.ArrowUp, km.ArrowRight], ['5', '6', '7', '8']);
  check('letters, digits, the shifts and the overrides', [km.KeyQ, km.Digit3, km.ShiftLeft, km.KeyZ], ['Q', '3', 'CAPS', 'SYM']);
  /* the page's own listeners, through the rig's event bus */
  const noop = { preventDefault(){} };
  rig.fire('keydown', Object.assign({ code: 'KeyQ', target: null }, noop));
  checkTrue('a keydown on the page presses the mapped key', P.keyboard.down('Q'));
  rig.fire('keyup', Object.assign({ code: 'KeyQ', target: null }, noop));
  checkTrue('...and keyup releases it', !P.keyboard.down('Q'));
  rig.fire('keydown', Object.assign({ code: 'KeyW', target: { tagName: 'INPUT' } }, noop));
  checkTrue('a keystroke aimed at a form field is NOT a game key', !P.keyboard.down('W'));
  rig.fire('keydown', Object.assign({ code: 'KeyE', target: null }, noop));
  rig.fire('blur', {});
  checkTrue('losing focus releases everything', !P.keyboard.down('E'));

  sandbox.navigator = { getGamepads(){ return [null, { connected: true, id: 'Test Pad One',
    axes: [0.9, -0.9], buttons: [{ pressed: true }] }]; } };
  const st = S.pollGamepads(kb);
  check('a gamepad feeds the Kempston byte: right, up, fire',
        [st.count, kb.kempston, st.names[0]], [1, S.KEMPSTON_RIGHT | S.KEMPSTON_UP | S.KEMPSTON_FIRE, 'TEST PAD ON']);
  check('padBits: B / the shoulders carry the ADDED $20 bit',
        S.padBits({ axes: [0, 0], buttons: [{ pressed: false }, { pressed: true }] }), S.KEMPSTON_POTION);
  check('padBits: the d-pad', S.padBits({ axes: [0, 0], buttons: Array.from({ length: 16 }, (_, i) => ({ pressed: i === 14 })) }), S.KEMPSTON_LEFT);
  delete sandbox.navigator;
  S.pollGamepads(kb);
  check('no navigator: the port byte is clear', kb.kempston, 0);
}

/* =======================================================================
   THE AY CHIP against the datasheet formula, measured out of its own
   samples by counting zero crossings -- an independent re-derivation of
   f = clock / (16 * TP), not a read-back of the constant.
   ======================================================================= */
{
  const sr = 44100;
  const measure = (tp) => {
    const c = new S.AyChip(sr, S.AY_CLOCK);
    c.write(0, tp & 0xFF); c.write(1, tp >> 8);
    c.write(7, 0x38); c.write(8, 15); c.write(9, 0); c.write(10, 0);
    const n = sr * 0.4, buf = new Float32Array(n);
    c.render(buf, 0, n);
    let mean = 0; for (let i = 0; i < n; i++) mean += buf[i];
    mean /= n;
    let cross = 0;
    for (let i = 1; i < n; i++) if ((buf[i - 1] - mean) <= 0 && (buf[i] - mean) > 0) cross++;
    return cross / 0.4;
  };
  for (const tp of [1625, 812, 404, 121]) {
    const want = S.AY_CLOCK / (16 * tp), got = measure(tp);
    checkTrue(`AyChip tone period ${tp} -> ${want.toFixed(1)} Hz`,
              Math.abs(got - want) / want < 0.02, `measured ${got.toFixed(1)} Hz`);
  }
  const wiggle = (r7) => {
    const c = new S.AyChip(sr, S.AY_CLOCK);
    c.write(0, 100); c.write(1, 0); c.write(7, r7); c.write(8, 15);
    const n = 4000, buf = new Float32Array(n);
    c.render(buf, 0, n);
    let lo = 1e9, hi = -1e9;
    for (let i = 200; i < n; i++) { lo = Math.min(lo, buf[i]); hi = Math.max(hi, buf[i]); }
    return hi - lo;
  };
  checkTrue('R7 bit 0 CLEAR = tone A ENABLED: the output swings', wiggle(0x38) > 0.1);
  checkTrue('R7 bit 0 SET = tone A disabled: a constant, not silence (the chip\'s AND gate)', wiggle(0x39) < 1e-6);
}

/* =======================================================================
   THE BEEPER CHIP: the box integral, the DC blocker, the speaker model
   ======================================================================= */
{
  const sr = 44100;
  const square = (hz, secs) => { const ed = []; let lv = 1;
    for (let t = 0; t < secs; t += 1 / (2 * hz)) { ed.push([t, lv]); lv ^= 1; } return ed; };
  /* measurement of the integral and the blocker runs with the ADDED
     speaker model OFF -- the at-unity bound is the blocker's passband */
  S.speakerFilter.set(false);
  for (const hz of [1000, 2500, 4000]) {
    const c = new S.BeeperChip(sr), n = Math.round(sr * 0.3), buf = new Float32Array(n);
    c.render(buf, 0, n, 0, square(hz, 0.3), 0);
    let cross = 0;
    for (let i = 1; i < n; i++) if (buf[i - 1] <= 0 && buf[i] > 0) cross++;
    checkTrue(`BeeperChip renders a ${hz} Hz square at ${hz} Hz`, Math.abs(cross / 0.3 - hz) / hz < 0.03, `measured ${(cross / 0.3).toFixed(1)}`);
  }
  {
    const c = new S.BeeperChip(sr, false), buf = new Float32Array(4);
    c.render(buf, 0, 4, 0, [[0.25 / sr, 1]], 0);
    checkTrue('the box integral is EXACT: an edge a quarter into a sample gives 0.75 high',
              Math.abs(buf[0] - 0.25) < 1e-6 && Math.abs(buf[1] - 0.5) < 1e-6, JSON.stringify([...buf]));
    const d = new S.BeeperChip(sr), b2 = new Float32Array(sr);
    d.render(b2, 0, sr, 0, [[0, 0]], 0);
    checkTrue('a constant level renders as SILENCE, not as a DC step', Math.abs(b2[sr - 1]) < 1e-6);
    const e2 = new S.BeeperChip(sr), b3 = new Float32Array(sr);
    e2.render(b3, 0, sr, 0, square(1588, 1), 0);
    let pk = 0; for (let i = sr / 2; i < sr; i++) pk = Math.max(pk, Math.abs(b3[i]));
    checkTrue('and a 1,588 Hz square passes the blocker at ~unity', pk > 0.48 && pk < 0.52, String(pk));
  }
  {
    const edges = square(100000, 0.05), n = Math.round(sr * 0.05);
    const raw = new S.BeeperChip(sr, false), b1 = new Float32Array(n);
    raw.render(b1, 0, n, 0, edges, 0);
    let pkRaw = 0; for (let i = 0; i < n; i++) pkRaw = Math.max(pkRaw, Math.abs(b1[i]));
    checkTrue('a 100 kHz square averages down instead of aliasing (bound 0.11, derived)', pkRaw < 0.12, String(pkRaw));
    const c = new S.BeeperChip(sr), b2 = new Float32Array(n);
    c.render(b2, 0, n, 0, edges, 0);
    const tau = sr / (2 * Math.PI * 20), settle = Math.ceil(5 * tau);
    let pk = 0; for (let i = settle; i < n; i++) pk = Math.max(pk, Math.abs(b2[i]));
    checkTrue('...and the DC-blocked path rejects it too, once settled (5 tau)', pk < 0.12, String(pk));
    const R = 1 - 2 * Math.PI * 20 / sr, h = b2[0];
    let worst = -Infinity;
    for (let i = 1; i < settle; i++) worst = Math.max(worst, Math.abs(b2[i]) - (Math.abs(h) * Math.pow(R, i) + 0.12));
    checkTrue('the startup transient decays as h*R^i, not as a whine', worst < 0, String(worst));
  }
  S.speakerFilter.set(true);
  /* the speaker model: shades the top octaves, passes the band, and its
     state carries across render() calls -- the anti-click property */
  const rms = (b, from) => { let s = 0; for (let i = from; i < b.length; i++) s += b[i] * b[i]; return Math.sqrt(s / (b.length - from)); };
  const render = (hz) => { const n = Math.round(sr * 0.2), b = new Float32Array(n);
    new S.BeeperChip(sr).render(b, 0, n, 0, square(hz, 0.2), 0); return rms(b, Math.round(sr * 0.1)); };
  S.speakerFilter.set(false); const hiRaw = render(8000), loRaw = render(500);
  S.speakerFilter.set(true);  const hiMod = render(8000), loMod = render(500);
  checkTrue('the speaker model shades an 8 kHz square well below the raw render', hiMod < hiRaw * 0.5, (hiMod / hiRaw).toFixed(3));
  checkTrue('...and passes a 500 Hz square nearly whole', loMod > loRaw * 0.85, (loMod / loRaw).toFixed(3));
  const n = Math.round(sr * 0.1), ed = square(2000, 0.1);
  const whole = new Float32Array(n), split = new Float32Array(n);
  new S.BeeperChip(sr).render(whole, 0, n, 0, ed, 0);
  const c2 = new S.BeeperChip(sr), h = n >> 1;
  const ei = c2.render(split, 0, h, 0, ed, 0);
  c2.render(split, h, n - h, h / sr, ed, ei);
  let same = true; for (let i = 0; i < n; i++) if (whole[i] !== split[i]) { same = false; break; }
  checkTrue('the model state carries across render calls: split === whole', same);
  check('speakerFilter is live-toggleable and reports its state', [S.speakerFilter.set(false), S.speakerFilter.set(true)], [false, true]);
}

/* =======================================================================
   THE BRIDGE, scheduled path: the voice cap, the whole-sample tiling, the
   adaptive lead, the latency class, the worklet init chain
   ======================================================================= */
const mockCtx = (state) => ({
  sampleRate: 44100, get currentTime() { return state.now; }, destination: {},
  createBuffer: (c, n) => { const d = new Float32Array(n); return { length: n, getChannelData: () => d }; },
  createBufferSource() { return { buffer: null, connect() {}, start(when) { state.started++;
    if (state.bufs) state.bufs.push({ when, data: this.buffer.getChannelData() }); } }; },
});
{
  const st = { now: 10, started: 0 };
  const bo = new S.SoundOut();
  bo.ctx = mockCtx(st); bo.gain = { connect() {} }; bo.chip = new S.BeeperChip(44100);
  bo.next = 0; bo.base = 0; bo.t0 = st.now + 0.05; bo.live = [];
  for (let i = 0; i < 60; i++) bo.live.push(st.now + 5);
  bo.flushBeeper([[0.2, 1], [0.4, 0], [0.6, 1]], 4);
  check('a full voice list drops instead of scheduling', st.started, 0);
  check('...and the dropped edges still leave the speaker at the right level', bo.chip.lvl, 1);
  check('...and the drop is counted', bo.dropped, 1);
  st.now = 20;
  bo.flushBeeper([[4.5, 0]], 8);
  check('voices expire by their scheduled END TIME, not by a callback', st.started, 1);
}
{
  /* THE TILING: buffers abut on the sample grid, and the whole schedule
     reconstructs ONE continuous render of the same edges.  The frame counts
     mix 1 (a per-frame front end) with 4..7 (a variable pass clock). */
  const SR = 44100, st = { now: 10, started: 0, bufs: [] };
  const out = new S.SoundOut();
  out.ctx = mockCtx(st); out.gain = { connect() {} }; out.chip = new S.BeeperChip(SR);
  const NF = [1, 4, 5, 4, 7, 1, 1, 6, 4, 5, 5, 4, 6, 1, 4, 5, 7, 4, 4, 5];
  const log = [], all = []; let f = 0, lv = 0;
  out.flushBeeper(log, 0);                          // originate the map
  for (const nf of NF) {
    for (let t = f + 0.0125; t < f + nf; t += 0.025) { lv ^= 1; log.push([t, lv]); all.push([t, lv]); }
    f += nf; out.flushBeeper(log, f);
  }
  check('every closed frame was scheduled', [out.resyncs, out.dropped, st.bufs.length], [0, 0, NF.length]);
  const s00 = Math.floor(st.bufs[0].when * SR);
  const total = Math.floor((out.t0 + f / FRAME_HZ) * SR) - s00;
  let abut = true, offset = 0;
  for (const b of st.bufs) { if (Math.round(b.when * SR) - s00 !== offset) abut = false; offset += b.data.length; }
  checkTrue('consecutive buffers abut on the sample grid, for every frame count', abut && offset === total, `${offset} vs ${total}`);
  const cat = new Float32Array(total);
  for (const b of st.bufs) cat.set(b.data, Math.round(b.when * SR) - s00);
  const ref = new Float32Array(total);
  new S.BeeperChip(SR).render(ref, 0, total, 0, all.map(e => [out.t0 + e[0] / FRAME_HZ - s00 / SR, e[1]]), 0);
  let worst = 0; for (let i = 0; i < total; i++) worst = Math.max(worst, Math.abs(cat[i] - ref[i]));
  checkTrue('the scheduled buffers reconstruct ONE continuous render, sample for sample', worst < 1e-6, 'worst ' + worst.toExponential(2));
}
{
  const st = { now: 0, started: 0 };
  const So = new S.SoundOut();
  So.ctx = mockCtx(st); So.gain = { connect() {} }; So.chip = new S.BeeperChip(44100);
  So.flushBeeper([], 10);
  check('the first flush originates at now + the DEFAULT lead', [So.lead, So.t0], [0.08, 0.08]);
  st.now = 0.02; So.flushBeeper([[12, 1]], 15);
  checkTrue('a healthy flush schedules and never ratchets', So.live.length === 1 && So.underruns === 0 && So.lead === 0.08);
  const cursor = 0.08 + 5 / FRAME_HZ;
  st.now = 0.30; So.flushBeeper([], 20);
  const expect = (0.30 - cursor) + 0.08;
  checkTrue('an underrun ratchets the lead by the MEASURED deficit + margin', So.underruns === 1 && Math.abs(So.lead - expect) < 1e-9, So.lead.toFixed(5));
  checkTrue('...and the re-origin schedules with the NEW lead', Math.abs(So.t0 - (0.30 + expect)) < 1e-9);
  st.now = 5; So.flushBeeper([], 25);
  checkTrue('a huge stall caps the lead at SND_LEAD_MAX', So.underruns === 2 && So.lead === S.SND_LEAD_MAX);
  const led = So.lead, und = So.underruns, rs = So.resyncs;
  So.flushBeeper([], 2);
  checkTrue('a clock restart re-origins but does NOT ratchet -- it is not a tear', So.resyncs === rs + 1 && So.underruns === und && So.lead === led);
  checkTrue('info() is one pasteable line naming the transport', /^mode=sched sr=44100 lead=/.test(So.info()) && So.info().includes('wk=off'));
}
{
  let captured = null;
  sandbox.AudioContext = class { constructor(opts) { captured = opts; this.sampleRate = 48000; this.destination = {}; }
    createGain() { return { gain: { value: 0 }, connect() {} }; } };
  const S2 = new S.SoundOut();
  checkTrue('start() brings the context up under the mock', S2.start() === true);
  checkTrue('...asks for the playback latency class, not the default', !!captured && captured.latencyHint === 'playback');
  checkTrue('...and with no audioWorklet on the context, stays on the scheduler', S2.mode === 'sched' && S2.initPending === false);
  checkTrue('...with a beeper chip for the default instrument', S2.chip instanceof S.BeeperChip);
  const S2a = new S.SoundOut({ instrument: 'ay', gain: 0.5 });
  S2a.start();
  checkTrue('instrument "ay" builds an AyChip and honours the gain option', S2a.chip instanceof S.AyChip && S2a.gain.gain.value === 0.5);
  delete sandbox.AudioContext;
}
{
  /* the worklet module's TWO URLs: blob first (http), data: as the file://
     fallback, MEASURED in headless Chrome; the mocks' addModule returns a
     SYNCHRONOUS thenable, which the init chain supports on purpose */
  const mkCtx = (verdict) => class {
    constructor() { this.sampleRate = 48000; this.destination = {}; this.tried = []; const tried = this.tried;
      this.audioWorklet = { addModule: (url) => ({ then(ok, err) { tried.push(url.slice(0, 5)); verdict(url) ? ok() : err({ name: 'AbortError' }); } }) }; }
    createGain() { return { gain: { value: 0 }, connect() {} }; }
  };
  sandbox.Blob = Blob; sandbox.URL = URL; sandbox.btoa = btoa;
  sandbox.AudioWorkletNode = class { constructor(ctx, name, opts) { this.name = name; this.opts = opts;
    this.port = { posted: [], onmessage: null, postMessage(m) { this.posted.push(m); } }; } connect() {} };
  sandbox.AudioContext = mkCtx(url => !url.startsWith('blob:'));
  const S3 = new S.SoundOut(); S3.start();
  checkTrue('a blob-refusing platform (file://) falls back to the data: module',
            S3.mode === 'worklet' && S3.initPending === false && S3.ctx.tried.join() === 'blob:,data:');
  checkTrue('...recording WHY blob was refused for info()', S3.workletErr.indexOf('blob:AbortError') === 0 && S3.info().includes('wk=on'));
  checkTrue('...the node is registered under the kit\'s processor name', S3.node.name === 'spec-beeper' && S.WORKLET_SRC.includes("registerProcessor('spec-beeper'"));
  checkTrue('...and got its refill gate on arrival', S3.node.port.posted.length === 1 && S3.node.port.posted[0].min === Math.floor(0.08 * 48000));
  sandbox.AudioContext = mkCtx(() => false);
  const S4 = new S.SoundOut(); S4.start();
  checkTrue('both URLs refused: the scheduler keeps the game audible', S4.mode === 'sched' && S4.initPending === false);
  checkTrue('...and info() names both failures instead of staying silent', S4.info().includes('wk=blob:AbortError data:AbortError'));
  sandbox.AudioContext = mkCtx(() => true);
  const S5 = new S.SoundOut({ instrument: 'ay' }); S5.start();
  checkTrue('the AY instrument never asks for the worklet (declared: scheduler only)', S5.mode === 'sched' && S5.ctx.tried.length === 0);
  delete sandbox.AudioContext; delete sandbox.AudioWorkletNode; delete sandbox.Blob; delete sandbox.URL; delete sandbox.btoa;
}

/* =======================================================================
   THE WORKLET PATH: one continuous pull-model stream
   ======================================================================= */
{
  const sr = 44100;
  {
    const So = new S.SoundOut(); const chunks = [];
    So.ctx = { sampleRate: sr }; So.chip = new S.BeeperChip(sr);
    So.node = { port: { postMessage(m) { if (m.chunk) chunks.push(m.chunk); } } }; So.mode = 'worklet';
    const edges = []; { let lv = 1; for (let f = 0.2; f < 60; f += 0.37) { edges.push([f, lv]); lv ^= 1; } }
    const log = []; let fed = 0;
    const feed = (upto) => { while (fed < edges.length && edges[fed][0] < upto) log.push(edges[fed++]); So.flushWorklet(log, upto); };
    So.flushWorklet([], 0);
    for (const u of [3, 8, 9, 15, 26, 41, 60]) feed(u);
    const total = Math.floor(60 / FRAME_HZ * sr);
    check('the stream sent exactly the whole-sample window of 60 frames', So.vsent, total);
    const cat = new Float32Array(total); { let o = 0; for (const c of chunks) { cat.set(c, o); o += c.length; } }
    const ref = new Float32Array(total);
    new S.BeeperChip(sr).render(ref, 0, total, 0, edges.map(e => [e[0] / FRAME_HZ, e[1]]), 0);
    let worst = 0; for (let i = 0; i < total; i++) worst = Math.max(worst, Math.abs(cat[i] - ref[i]));
    checkTrue('the chunk concatenation IS the one-shot render, sample for sample', worst < 1e-7, 'worst ' + worst.toExponential(2));
    const rs = So.resyncs, n0 = chunks.length;
    So.flushWorklet([[1, 1]], 2);
    checkTrue('a clock restart re-origins the stream map without emitting',
              So.resyncs === rs + 1 && chunks.length === n0 && So.vbase === 2 && So.vsent === 0 && So.chip.lvl === 1);
    /* flush() dispatches on mode, and a custom frame clock is honoured */
    const S128 = new S.SoundOut({ frameHz: S.FRAME_HZ_128K }); const c2 = [];
    S128.ctx = { sampleRate: sr }; S128.chip = new S.BeeperChip(sr);
    S128.node = { port: { postMessage(m) { if (m.chunk) c2.push(m.chunk); } } }; S128.mode = 'worklet';
    S128.flush([], 0); S128.flush([], 50);
    check('a 128K frame clock tiles the stream at its own rate', S128.vsent, Math.floor(50 / S.FRAME_HZ_128K * sr));
  }
  {
    const So = new S.SoundOut(); const posted = [];
    So.ctx = { sampleRate: sr }; So.node = { port: { postMessage(m) { posted.push(m); } } };
    So.ratchetSamples(Math.round(0.05 * sr));
    checkTrue('an underrun report ratchets lead to episode + margin', So.underruns === 1 && Math.abs(So.lead - 0.13) < 1e-3);
    checkTrue('...and posts the worklet its new refill gate', posted.length === 1 && posted[0].min === Math.floor(So.lead * sr));
    So.ratchetSamples(sr * 2);
    checkTrue('...and a huge episode caps at SND_LEAD_MAX', So.lead === S.SND_LEAD_MAX);
  }
  {
    /* the processor itself, eval'd from the SAME source string the page
       ships, with the worklet globals stubbed */
    let ProcCls = null; const reports = [];
    const AudioWorkletProcessor = class { constructor() { this.port = { onmessage: null, postMessage: m => reports.push(m) }; } };
    const registerProcessor = (name, cls) => { ProcCls = cls; };
    void AudioWorkletProcessor; void registerProcessor;
    eval(S.WORKLET_SRC);
    const p = new ProcCls();
    const msg = d => p.port.onmessage({ data: d });
    const spin = () => { const o = new Float32Array(128); p.process([], [[o]]); return o; };
    msg({ min: 100 });
    let o = spin();
    checkTrue('before anything arrives: silence, and NO underrun report', reports.length === 0 && o.every(v => v === 0));
    msg({ chunk: new Float32Array(60).fill(0.5) }); o = spin();
    checkTrue('below the refill gate the stream does not start yet', reports.length === 0 && o.every(v => v === 0));
    msg({ chunk: new Float32Array(80).fill(0.25) }); o = spin();
    checkTrue('at the gate it starts -- and boot silence was NOT an underrun', reports.length === 0 && o[0] === 0.5 && o[127] === 0.25);
    o = spin();
    checkTrue('a dry queue emits zeros mid-episode without reporting yet', reports.length === 0 && o[11] === 0.25 && o[12] === 0);
    msg({ chunk: new Float32Array(50).fill(0.75) }); o = spin();
    checkTrue('recovery ALSO waits for the refill gate -- no fragile resume', reports.length === 0 && o.every(v => v === 0));
    msg({ chunk: new Float32Array(80).fill(0.75) }); o = spin();
    checkTrue('resuming reports the episode length, once', reports.length === 1 && reports[0].underrun === 244 && o[0] === 0.75);
  }
}

/* =======================================================================
   THE LOOP, THE SETTINGS, AND THE STARTER DEMO END TO END
   ======================================================================= */
{
  const st = S.settingsStore('kit-test');
  checkTrue('settingsStore.save reports that the write LANDED', st.save({ a: 1 }) === true && rig.localStorageStore.has('kit-test'));
  check('...and load reads it back', st.load(), { a: 1 });
  st.clear();
  check('...and clear removes it', st.load(), null);
}
{
  const d = new P.Demo(); const kb = new S.Keyboard();
  check('the demo starts with its block at the centre', [d.x, d.y], [15, 11]);
  kb.press('P'); d.step(kb);
  check('P moves the block right on a movement frame', d.x, 16);
  d.step(kb); d.step(kb); d.step(kb);
  check('...and holds for the next three frames', d.x, 16);
  kb.releaseAll(); kb.kempston = S.KEMPSTON_UP; d.step(kb);
  check('the Kempston byte moves it too', d.y, 10);
  kb.releaseAll();
  const f0 = d.simFrame;
  kb.press('SPACE'); d.step(kb);
  const half = FRAME_HZ / (2 * 440), want = Math.ceil(1 / half);
  checkTrue('SPACE logs a 440 Hz edge stream on the SIMULATED clock, inside the frame',
            (d.sound.log.length === want || d.sound.log.length === want - 1) &&
            d.sound.log.every(e => e[0] >= f0 && e[0] < f0 + 1) && d.sound.log[0][1] === 1,
            `${d.sound.log.length} edges`);
  const n1 = d.sound.log.length; d.step(kb);
  checkTrue('...phase-continuous into the next frame (no edge repeats, no gap)',
            d.sound.log.length > n1 && d.sound.log[n1][0] - d.sound.log[n1 - 1][0] > half * 0.999 &&
            d.sound.log[n1][0] - d.sound.log[n1 - 1][0] < half * 1.001);
  check('...and reddens the border while firing', d.border, 2);
  kb.releaseAll(); d.step(kb);
  check('releasing leaves the speaker LOW with one closing edge', [d.sound.log[d.sound.log.length - 1][1], d.border], [0, 0]);
}
{
  /* the page's own loop, driven through the captured rAF: three and a half
     frames of wall time is three simulation steps, and the bridge is fed
     from draw with the simulated frame count */
  const st = { now: 10, started: 0 };
  /* the keydown tests above already gestured start() in a sandbox with no
     AudioContext, which correctly switched audio OFF; hand it a mock now */
  P.sound.on = true; P.sound.ctx = mockCtx(st); P.sound.gain = { connect() {} }; P.sound.chip = new S.BeeperChip(44100);
  /* the page runs the game now (round_loop $AE26): the same loop checks
     against it, the bridge fed with the engine's simulated frame */
  const cb = rig.raf();
  const before = P.game.frame;
  cb(0);
  check('the first rAF only sets the clock', P.game.frame - before, 0);
  cb(3.5 / FRAME_HZ * 1000);
  check('3.5 frames of wall time step the simulation exactly 3 frames', P.game.frame - before, 3);
  cb(40 / FRAME_HZ * 1000); cb(80 / FRAME_HZ * 1000);
  checkTrue('the game reaches the bridge: buffers were scheduled from draw at its simulated frame',
            st.started >= 1 && P.sound.next === P.game.simFrame, `${st.started} started, next ${P.sound.next}, sim ${P.game.simFrame}`);
  cb(4000);
  checkTrue('a long stall is capped at maxDt, not replayed', P.game.frame - before <= 80 + Math.ceil(0.25 * FRAME_HZ));
}

/* =======================================================================
   THE GAME: The Way of the Exploding Fist
   ======================================================================= */

/* ---- the sprite decoder $8803 against its frozen oracle (sprdec) ------
   Every case is replayed in a blank 64K holding only the tables and the
   bytes the real call read; the whole of memory outside the scratch
   $8AE9-$8B1C must then equal the bytes the real call left, and the T must
   equal its uncontended T (python tools/sprdec.py --capture). */
{
  const fx = P.assets.sprdec;
  const tables = Buffer.from(fx.tables, 'hex');
  const put = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
  const paths = {};
  let badBytes = 0, badT = 0, firstBytes = '', firstT = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000);
    m.set(tables, 0xB500); put(m, c.in);
    const want = m.slice(); put(want, c.out);
    const t = P.spriteDecode(m, c.hl, c.de, paths);
    let diff = -1;
    for (let a = 0; a < 0x10000; a++){
      if (a === 0x8AE9) a = 0x8B1D;
      if (m[a] !== want[a]){ diff = a; break; }
    }
    if (diff >= 0 && !badBytes++)
      firstBytes = `case ${i} HL=$${c.hl.toString(16)}: $${diff.toString(16)} = ${m[diff]} want ${want[diff]}`;
    if (t !== c.t && !badT++) firstT = `case ${i} HL=$${c.hl.toString(16)}: T ${t} want ${c.t}`;
  }
  check(`spriteDecode writes every byte the real $8803 wrote (${fx.cases.length} sprdec cases)`, [badBytes, firstBytes], [0, '']);
  check('spriteDecode tallies the uncontended T of every case exactly', [badT, firstT], [0, '']);
  check('the sprdec cases reach every row path seen in play',
        ['packed', 'edges', 'single', 'recolour', 'mirror', 'shift2', 'shift4', 'shift6'].filter(k => !paths[k]), []);
}

/* ---- render_fighters $BF13 against its frozen oracle (rendfx) ---------
   Every case is replayed in a blank 64K holding only the decoder tables and
   the bytes the real call read; the whole of memory outside the stack must
   then equal the bytes the real call left -- back buffer, display file,
   boxes and scratch -- and the T must equal its uncontended T (python
   tools/rendfx.py --capture). */
{
  const fx = P.assets.rendfx;
  const tables = Buffer.from(fx.tables, 'hex');
  const put = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
  const paths = {};
  let badBytes = 0, badT = 0, firstBytes = '', firstT = '', badM1 = 0, firstM1 = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000);
    m.set(tables, 0xB500); put(m, c.in);
    const want = m.slice(); put(want, c.out);
    P.M1.m1 = 0;
    const t = P.renderFighters(m, paths, c.sp);
    if ((P.M1.m1 & 0x7F) !== c.m1 && !badM1++) firstM1 = `case ${i} [${c.paths}]: M1 ${P.M1.m1} want ${c.m1} mod 128`;
    let diff = -1;
    for (let a = 0; a < 0x10000; a++){
      if (a === c.sp - 64) a = c.sp + 2;
      if (m[a] !== want[a]){ diff = a; break; }
    }
    if (diff >= 0 && !badBytes++)
      firstBytes = `case ${i} [${c.paths}]: $${diff.toString(16)} = ${m[diff]} want ${want[diff]}`;
    if (t !== c.t && !badT++) firstT = `case ${i} [${c.paths}]: T ${t} want ${c.t}`;
  }
  check(`renderFighters writes every byte the real $BF13 wrote (${fx.cases.length} rendfx cases)`, [badBytes, firstBytes], [0, '']);
  check('renderFighters tallies the uncontended T of every case exactly', [badT, firstT], [0, '']);
  /* R: the fixture's m1 is how far R advanced from $BF13 to $9793 (rendfx.py --stamp-r) */
  check('renderFighters counts the M1 cycles of every case as R advanced in the real $BF13', [badM1, firstM1], [0, '']);
  check('the rendfx cases reach every render path seen in play',
        ['separate', 'merged', 'p1-first', 'p2-first', 'floor-part', 'flip', 'unflipped'].filter(k => !paths[k]), []);
  /* per comparison, margin 0 is the last merged case and 1 the first drawn
     apart, so a slack of 10 or 12 in either must fail the byte check above */
  check('the rendfx cases straddle both $C03B overlap comparisons (margins 0 and 1)',
        ['1:0', '1:1', '2:0', '2:1'].filter(k => !fx.cases.some(c => c.margin && c.margin[k[0] - 1] === +k[2])), []);
}

/* ---- $BF13's T in play: the D4 charges against the contended T --------
   Each rendfx case also holds the call's T in the contended harness (tc),
   one sample of frame phase.  Charged, the fixture must pool within 0.25%
   of it (1.00026 measured; dropping the own-code charge alone gives 0.9954,
   the decoder's or the copy's 0.97-0.98), and no one call may miss by more
   than 3% (2.84% the worst of 614 play calls: frame phase). */
{
  const fx = P.assets.rendfx;
  const tables = Buffer.from(fx.tables, 'hex');
  const put = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
  let ch = 0, tc = 0, worst = 0, at = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000);
    m.set(tables, 0xB500); put(m, c.in);
    const cost = { dec: 0, copy: 0, ldir: 0 };
    const t = P.rfPlayT(P.renderFighters(m, null, c.sp, cost), cost);
    ch += t; tc += c.tc;
    const e = Math.abs(t - c.tc) / c.tc;
    if (e > worst){ worst = e; at = `case ${i} [${c.paths}]: T ${t.toFixed(0)} want ${c.tc}`; }
  }
  check('rfPlayT pools within 0.25% of the contended $BF13 T (rendfx cases)',
        Math.abs(ch / tc - 1) < 0.0025 ? '' : `charged/contended ${(ch / tc).toFixed(5)}`, '');
  check('rfPlayT misses no rendfx case by more than 3%',
        worst < 0.03 ? '' : `${(100 * worst).toFixed(2)}% at ${at}`, '');
}

/* ---- fighter_step $97BB against its frozen oracle (callio) -----------
   Every case is replayed in a blank 64K holding only the bytes the real
   call read; the whole of memory must then equal the bytes it left, and the
   T its uncontended T from the CALL to the return (python tools/callio.py
   --capture --call 0x9763 0x9766 --call 0x976C 0x976F). */
{
  const fx = P.assets.step97bb;
  const put = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
  const iC = fx.regs.indexOf(3);                 // SkoolKit index of C
  let badBytes = 0, badT = 0, firstBytes = '', firstT = '', badM1 = 0, firstM1 = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);   // unread bytes poisoned: a stray 0 shows
    put(m, c.in);
    const want = m.slice(); put(want, c.out);
    P.M1.m1 = 0;
    const t = P.fighterStep(m, c.regs[iC]);
    if ((P.M1.m1 & 0x7F) !== ((c.rx - c.r) & 0x7F) && !badM1++) firstM1 = `case ${i}: M1 ${P.M1.m1} want ${(c.rx - c.r) & 0x7F} mod 128`;
    let diff = -1;
    for (let a = 0; a < 0x10000; a++) if (m[a] !== want[a]){ diff = a; break; }
    if (diff >= 0 && !badBytes++)
      firstBytes = `case ${i} ($${c.site.toString(16)}): $${diff.toString(16)} = ${m[diff]} want ${want[diff]}`;
    if (t !== c.t && !badT++) firstT = `case ${i} ($${c.site.toString(16)}): T ${t} want ${c.t}`;
  }
  check('fighterStep writes every byte the real $97BB wrote (callio cases)', [badBytes, firstBytes], [0, '']);
  check('fighterStep tallies the uncontended T of every case exactly', [badT, firstT], [0, '']);
  /* R: the fixture's R at the CALL and the return (callio.py --check --stamp-r) */
  check('fighterStep counts the M1 cycles of every case as R advanced in the real $97BB', [badM1, firstM1], [0, '']);
  /* every exit of every callee, play or derived (callio.py --derive: the
     real code on a constructed input, e.g. both fighters facing one way) */
  const ran = new Set();
  for (const c of fx.cases) for (let j = 0; j < c.sig.length; j += 4) ran.add(parseInt(c.sig.slice(j, j + 4), 16));
  check('the callio cases reach every exit of $9920 $9994 $9AA1 $9BA7',
        [0x992F, 0x9989, 0x998D, 0x9990, 0x9993, 0x993A, 0x9945, 0x9951, 0x9954, 0x995C, 0x9963, 0x9985,
         0x99BE, 0x99CC, 0x99D1, 0x99DC, 0x99DF, 0x99EB, 0x99FA, 0x99FC, 0x9A18, 0x9A1A, 0x9A1D, 0x9A26,
         0x9A3A, 0x9A3C, 0x9A6F, 0x9A8A, 0x9A8C, 0x9AA0, 0x9AB8, 0x9ACC, 0x9AD6,
         0x9BF1, 0x9BF4, 0x9C18, 0x9C1F, 0x9C23, 0x9C27].filter(a => !ran.has(a)).map(a => a.toString(16)), []);
  check('the callio cases call $97BB for both fighters (C = 0 and $40)',
        [0, 0x40].filter(v => !fx.cases.some(c => c.regs[iC] === v)), []);
}

/* ---- fighter_post $9AD7 + $9B9D against its frozen oracle (callio) ---
   As above, the pair bracketed from the CALL at $979A/$97A6 to $97A0/$97AC
   (python tools/callio.py --capture --call 0x979A 0x97A0 --call 0x97A6 0x97AC). */
{
  const fx = P.assets.post9ad7;
  const put = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
  const iC = fx.regs.indexOf(3);
  let badBytes = 0, badT = 0, firstBytes = '', firstT = '', badM1 = 0, firstM1 = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);   // unread bytes poisoned: a stray 0 shows
    put(m, c.in);
    const want = m.slice(); put(want, c.out);
    P.M1.m1 = 0;
    const t = P.fighterPost(m, c.regs[iC]);
    if ((P.M1.m1 & 0x7F) !== ((c.rx - c.r) & 0x7F) && !badM1++) firstM1 = `case ${i}: M1 ${P.M1.m1} want ${(c.rx - c.r) & 0x7F} mod 128`;
    let diff = -1;
    for (let a = 0; a < 0x10000; a++) if (m[a] !== want[a]){ diff = a; break; }
    if (diff >= 0 && !badBytes++)
      firstBytes = `case ${i} ($${c.site.toString(16)}): $${diff.toString(16)} = ${m[diff]} want ${want[diff]}`;
    if (t !== c.t && !badT++) firstT = `case ${i} ($${c.site.toString(16)}): T ${t} want ${c.t}`;
  }
  check('fighterPost writes every byte the real $9AD7+$9B9D wrote (callio cases)', [badBytes, firstBytes], [0, '']);
  check('fighterPost tallies the uncontended T of every case exactly', [badT, firstT], [0, '']);
  /* R: the fixture's R at the CALL and the return (callio.py --check --stamp-r) */
  check('fighterPost counts the M1 cycles of every case as R advanced in the real $9AD7+$9B9D', [badM1, firstM1], [0, '']);
  const ran = new Set();
  for (const c of fx.cases) for (let j = 0; j < c.sig.length; j += 4) ran.add(parseInt(c.sig.slice(j, j + 4), 16));
  check('the callio cases reach every exit and branch of $9AD7',
        [0x9AE3, 0x9AF4, 0x9AFD, 0x9B09, 0x9B0E, 0x9B1E, 0x9B23, 0x9B67, 0x9B71, 0x9B8A]
          .filter(a => !ran.has(a)).map(a => a.toString(16)), []);
  check('the callio cases call $9AD7 for both fighters (C = 0 and $40)',
        [0, 0x40].filter(v => !fx.cases.some(c => c.regs[iC] === v)), []);
}

/* ---- bout_timer $9C6F and its printer against its frozen oracle (callio) -
   Bracketed from the CALL at $9745 to $9748.  The screen is a blind range
   (D5): the fixture holds which bytes the real code wrote there, not their
   ROM-font values, so the gate checks that set of addresses, and separately
   that each cell shows the lookalike glyph of the character in $932C. */
{
  const fx = P.assets.timer9c6f;
  const put = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
  const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
  check('the lookalike font holds no $A5 byte (the poison marks screen writes)', P.font.includes(0xA5), false);
  let badBytes = 0, badBlind = 0, badT = 0, badGlyph = 0, firstBytes = '', firstBlind = '', firstT = '', firstGlyph = '';
  let badM1 = 0, firstM1 = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);   // unread bytes poisoned: a stray 0 shows
    put(m, c.in);
    const want = m.slice(); put(want, c.out);
    P.M1.m1 = 0;
    const t = P.boutTimer(m);
    if ((P.M1.m1 & 0x7F) !== ((c.rx - c.r) & 0x7F) && !badM1++) firstM1 = `case ${i}: M1 ${P.M1.m1} want ${(c.rx - c.r) & 0x7F} mod 128`;
    let diff = -1;
    for (let a = 0; a < 0x10000; a++) if (!inBlind(a) && m[a] !== want[a]){ diff = a; break; }
    if (diff >= 0 && !badBytes++)
      firstBytes = `case ${i}: $${diff.toString(16)} = ${m[diff]} want ${want[diff]}`;
    const wrote = [], blind = [];
    for (let a = 0; a < 0x10000; a++) if (inBlind(a) && m[a] !== 0xA5) wrote.push(a);
    for (const [lo, hi] of c.blind || []) for (let a = lo; a <= hi; a++) blind.push(a);
    if (wrote.join() !== blind.join() && !badBlind++)
      firstBlind = `case ${i}: wrote ${wrote.length} screen bytes, the real code ${blind.length}`;
    if (t !== c.t && !badT++) firstT = `case ${i}: T ${t} want ${c.t}`;
    if (blind.length) for (let k = 0; k < 5; k++) for (let r = 0; r < 8; r++){
      const ch = m[0x932C + k], a = 0x4000 + 0x0B + k + (r << 8);
      if (m[a] !== P.font[(ch - 0x20) * 8 + r] && !badGlyph++) firstGlyph = `case ${i}: char ${k} row ${r}`;
    }
  }
  check('boutTimer writes every byte the real $9C6F wrote outside the screen (callio cases)', [badBytes, firstBytes], [0, '']);
  check('boutTimer writes exactly the screen bytes the real $9C6F wrote', [badBlind, firstBlind], [0, '']);
  check('boutTimer tallies the uncontended T of every case exactly', [badT, firstT], [0, '']);
  /* R: the fixture's R at the CALL and the return (callio.py --check --stamp-r) */
  check('boutTimer counts the M1 cycles of every case as R advanced in the real $9C6F', [badM1, firstM1], [0, '']);
  check('each printed cell shows the lookalike glyph of its $932C character', [badGlyph, firstGlyph], [0, '']);
  const pcs = fx.cases.map(c => { const s = new Set();
    for (let j = 0; j < c.sig.length; j += 4) s.add(parseInt(c.sig.slice(j, j + 4), 16)); return s; });
  /* each RET of $9C6F: a case that passed the PC before it and not the one after */
  check('the callio cases take every early return of $9C6F',
        [[0x9C6F, 0x9C74], [0x9C74, 0x9C7C], [0x9C7C, 0x9C82], [0x9C82, 0x9C87]]
          .filter(([a, b]) => !pcs.some(s => s.has(a) && !s.has(b))).map(([a]) => a.toString(16)), []);
  check('the callio cases reach every branch of the tick and its printer',
        [0x9C8E, 0x9C93, 0x934E, 0x935E, 0x922F, 0x9235, 0xC31E]
          .filter(a => !pcs.some(s => s.has(a))).map(a => a.toString(16)), []);
}

/* ---- p2_hits_p1 $9ED2 against its frozen oracle (callio) ---------------
   Bracketed from the CALL at $9748 to $974B (python tools/callio.py
   --capture --call 0x9748 0x974B); derived cases reach the branches driven
   play did not (ledger/9ED2.toml). */
{
  const fx = P.assets.hit9ed2;
  const put = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
  let badBytes = 0, badT = 0, firstBytes = '', firstT = '', badM1 = 0, firstM1 = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);   // unread bytes poisoned: a stray 0 shows
    put(m, c.in);
    const want = m.slice(); put(want, c.out);
    P.M1.m1 = 0;
    const t = P.p2HitsP1(m);
    if ((P.M1.m1 & 0x7F) !== ((c.rx - c.r) & 0x7F) && !badM1++) firstM1 = `case ${i}: M1 ${P.M1.m1} want ${(c.rx - c.r) & 0x7F} mod 128`;
    let diff = -1;
    for (let a = 0; a < 0x10000; a++) if (m[a] !== want[a]){ diff = a; break; }
    if (diff >= 0 && !badBytes++) firstBytes = `case ${i}: $${diff.toString(16)} = ${m[diff]} want ${want[diff]}`;
    if (t !== c.t && !badT++) firstT = `case ${i}: T ${t} want ${c.t}`;
  }
  check('p2HitsP1 writes every byte the real $9ED2 wrote (callio cases)', [badBytes, firstBytes], [0, '']);
  check('p2HitsP1 tallies the uncontended T of every case exactly', [badT, firstT], [0, '']);
  /* R: the fixture's R at the CALL and the return (callio.py --check --stamp-r) */
  check('p2HitsP1 counts the M1 cycles of every case as R advanced in the real $9ED2', [badM1, firstM1], [0, '']);
  const pcs = fx.cases.map(c => { const s = new Set();
    for (let j = 0; j < c.sig.length; j += 4) s.add(parseInt(c.sig.slice(j, j + 4), 16)); return s; });
  /* each early RET: a case that passed the PC before it and not the one after */
  check('the callio cases take every early return of $9ED2',
        [[0x9ED2, 0x9EDF], [0x9EDF, 0x9EE4], [0x9EE4, 0x9EE9], [0x9EE9, 0x9EEE], [0x9EEE, 0x9EFA],
         [0x9F30, 0x9F3F], [0x9FAF, 0x9FBE]]
          .filter(([a, b]) => !pcs.some(s => s.has(a) && !s.has(b))).map(([a]) => a.toString(16)), []);
  check('the callio cases reach every branch of the range tests and the reel',
        [0x9F48, 0x9F51, 0x9F65, 0x9F69, 0x9F6B, 0x9F6C, 0x9F77, 0x9F82, 0x9F83, 0x9F87, 0x9F88, 0x9F93, 0x9F9E,
         0x9FC7, 0x9FD0, 0x9FE4, 0x9FE8, 0x9FE9, 0x9FF4, 0x9FFF, 0xA000, 0xA004, 0xA005, 0xA010, 0xA01B,
         0x9F9F, 0x9FA7, 0xA043, 0xA047, 0xA04B, 0xA056, 0xA05C, 0xA062, 0xA06C]
          .filter(a => !pcs.some(s => s.has(a))).map(a => a.toString(16)), []);
}

/* ---- p1_hits_p2 $9D29 against its frozen oracle (callio) ---------------
   Bracketed from the CALL at $974B to $974E (python tools/callio.py
   --capture --call 0x974B 0x974E).  After its 12-byte x prefix the body
   is $9ED2's, $19D lower, so the PC lists are $9ED2's moved down
   (ledger/9D29.toml). */
{
  const fx = P.assets.hit9d29;
  const put = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
  let badBytes = 0, badT = 0, firstBytes = '', firstT = '', badM1 = 0, firstM1 = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);   // unread bytes poisoned: a stray 0 shows
    put(m, c.in);
    const want = m.slice(); put(want, c.out);
    P.M1.m1 = 0;
    const t = P.p1HitsP2(m);
    if ((P.M1.m1 & 0x7F) !== ((c.rx - c.r) & 0x7F) && !badM1++) firstM1 = `case ${i}: M1 ${P.M1.m1} want ${(c.rx - c.r) & 0x7F} mod 128`;
    let diff = -1;
    for (let a = 0; a < 0x10000; a++) if (m[a] !== want[a]){ diff = a; break; }
    if (diff >= 0 && !badBytes++) firstBytes = `case ${i}: $${diff.toString(16)} = ${m[diff]} want ${want[diff]}`;
    if (t !== c.t && !badT++) firstT = `case ${i}: T ${t} want ${c.t}`;
  }
  check('p1HitsP2 writes every byte the real $9D29 wrote (callio cases)', [badBytes, firstBytes], [0, '']);
  check('p1HitsP2 tallies the uncontended T of every case exactly', [badT, firstT], [0, '']);
  /* R: the fixture's R at the CALL and the return (callio.py --check --stamp-r) */
  check('p1HitsP2 counts the M1 cycles of every case as R advanced in the real $9D29', [badM1, firstM1], [0, '']);
  const pcs = fx.cases.map(c => { const s = new Set();
    for (let j = 0; j < c.sig.length; j += 4) s.add(parseInt(c.sig.slice(j, j + 4), 16)); return s; });
  /* each early RET: a case that passed the PC before it and not the one after */
  check('the callio cases take every early return of $9D29',
        [[0x9D35, 0x9D42], [0x9D42, 0x9D47], [0x9D47, 0x9D4C], [0x9D4C, 0x9D51], [0x9D51, 0x9D5D],
         [0x9D93, 0x9DA2], [0x9E12, 0x9E21]]
          .filter(([a, b]) => !pcs.some(s => s.has(a) && !s.has(b))).map(([a]) => a.toString(16)), []);
  check('the callio cases reach every branch of $9D29\'s range tests and reel',
        [0x9DAB, 0x9DB4, 0x9DC8, 0x9DCC, 0x9DCE, 0x9DCF, 0x9DDA, 0x9DE5, 0x9DE6, 0x9DEA, 0x9DEB, 0x9DF6, 0x9E01,
         0x9E2A, 0x9E33, 0x9E47, 0x9E4B, 0x9E4C, 0x9E57, 0x9E62, 0x9E63, 0x9E67, 0x9E68, 0x9E73, 0x9E7E,
         0x9E02, 0x9E0A, 0x9EA6, 0x9EAA, 0x9EAE, 0x9EB9, 0x9EBF, 0x9EC5, 0x9ECF]
          .filter(a => !pcs.some(s => s.has(a))).map(a => a.toString(16)), []);
}

/* ---- fighter_motion $95D4 against its frozen oracle (callio) ----------
   Bracketed from the CALL at $978D to $9790 (python tools/callio.py
   --capture --call 0x978D 0x9790).  The ROM bytes it copies are all $FF
   and the fixture keeps its ROM reads as addresses (D5), so the port
   reads no ROM: the poison there would show (ledger/95D4.toml). */
{
  const fx = P.assets.motion95d4;
  const put = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
  let badBytes = 0, badT = 0, firstBytes = '', firstT = '', badM1 = 0, firstM1 = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);   // unread bytes poisoned: a stray 0 shows
    put(m, c.in);
    const want = m.slice(); put(want, c.out);
    P.M1.m1 = 0;
    const t = P.fighterMotion(m);
    if ((P.M1.m1 & 0x7F) !== ((c.rx - c.r) & 0x7F) && !badM1++) firstM1 = `case ${i}: M1 ${P.M1.m1} want ${(c.rx - c.r) & 0x7F} mod 128`;
    let diff = -1;
    for (let a = 0; a < 0x10000; a++) if (m[a] !== want[a]){ diff = a; break; }
    if (diff >= 0 && !badBytes++) firstBytes = `case ${i}: $${diff.toString(16)} = ${m[diff]} want ${want[diff]}`;
    if (t !== c.t && !badT++) firstT = `case ${i}: T ${t} want ${c.t}`;
  }
  check('fighterMotion writes every byte the real $95D4 wrote (callio cases)', [badBytes, firstBytes], [0, '']);
  check('fighterMotion tallies the uncontended T of every case exactly', [badT, firstT], [0, '']);
  /* R: the fixture's R at the CALL and the return (callio.py --check --stamp-r) */
  check('fighterMotion counts the M1 cycles of every case as R advanced in the real $95D4', [badM1, firstM1], [0, '']);
  const pcs = fx.cases.map(c => { const s = new Set();
    for (let j = 0; j < c.sig.length; j += 4) s.add(parseInt(c.sig.slice(j, j + 4), 16)); return s; });
  check('the callio cases reach every branch of $95D4 and its swap $971E',
        [0x95EE, 0x9605, 0x960F, 0x9613, 0x961F, 0x9623, 0x962A, 0x9639, 0x963F, 0x9642, 0x9648, 0x9658, 0x965C,
         0x971E, 0x9697, 0x96B7, 0x96BA, 0x96BE, 0x96C9, 0x96CC, 0x96CE, 0x96F3, 0x96FC, 0x9714, 0x9717]
          .filter(a => !pcs.some(s => s.has(a))).map(a => a.toString(16)), []);
  /* the RET Z at $95ED taken for both fighters: a case without $95EE */
  check('the callio cases include a pass with both fighters idle',
        pcs.some(s => s.has(0x95ED) && !s.has(0x95EE)), true);
}

/* ---- control_pass $97CB and the AI $A090 against its frozen oracle ----
   Bracketed from the CALL at $9757 to $975A (python tools/callio.py
   --capture --call 0x9757 0x975A).  Each case carries its port reads in
   order and R at the CALL and the return: the port is served the logged
   values and must ask for the same ports, and its R -- the AI's draws --
   must land where the machine's did (ledger/97CB.toml, A3FF.toml).  The
   bitmap is a blind range (D5), as for $9C6F: the set of screen bytes
   written is checked, and the menu's ($8C54, ledger/8C54.toml) last
   screen must show the lookalike glyphs of its strings. */
{
  const fx = P.assets.control97cb;
  const put = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
  const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
  const iA = fx.regs.indexOf(0);
  const scr = (y, x) => 0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | x;
  const screens = [                                // [PC that marks it, its strings as [text, pos]]
    [0x8D99, [[0x8F6B, 0x012D], [0x8F89, 0x0136], [0x8FA7, 0x013F], [0x9000, 0x055C]]],
    [0x8CDB, [[0x8ED6, 0x012D], [0x8EF4, 0x0136], [0x8F0F, 0x013F], [0x8F2A, 0x0148], [0x8F41, 0x0151], [0x8F59, 0x0371]]],
    [0x8C54, [[0x8E6B, 0x002D], [0x8E8C, 0x1436], [0x8E99, 0x143F], [0x8EA6, 0x1448], [0x8EB3, 0x055C], [0x8EC6, 0x0765]]]];
  const missed = P.fontMiss.count;
  let badBytes = 0, badT = 0, badA = 0, badR = 0, badPorts = 0, badBlind = 0, badGlyph = 0, menus = 0;
  let firstBytes = '', firstT = '', firstA = '', firstR = '', firstPorts = '', firstBlind = '', firstGlyph = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);   // unread bytes poisoned: a stray 0 shows
    put(m, c.in);
    const want = m.slice(); put(want, c.out);
    const log = c.ports || [];
    let j = 0, portErr = '';
    const io = { r: c.r, in: p => {
      if (j >= log.length || log[j][0] !== p){ portErr = portErr || `read ${j} of port $${p.toString(16)}`; j++; return 0xFF; }
      return log[j++][1];
    }, };
    /* a read far past the log cannot end: the menu polls until a key, and
       $FF is no key -- stop it, the port error above is already recorded */
    const serve = io.in;
    io.in = p => { if (j > log.length + 64) throw new Error(`read ${j} past the ${log.length} logged`); return serve(p); };
    let res;
    try { res = P.controlPass(m, io); } catch (e){ res = { t: -1, a: -1, r: -1 }; portErr = portErr || e.message; }
    if (j !== log.length) portErr = portErr || `${j} port reads, the machine ${log.length}`;
    if (portErr && !badPorts++) firstPorts = `case ${i}: ${portErr}`;
    let diff = -1;
    for (let a = 0; a < 0x10000; a++) if (!inBlind(a) && m[a] !== want[a]){ diff = a; break; }
    if (diff >= 0 && !badBytes++) firstBytes = `case ${i}: $${diff.toString(16)} = ${m[diff]} want ${want[diff]}`;
    const wrote = [], blind = [];
    for (let a = 0; a < 0x10000; a++) if (inBlind(a) && m[a] !== 0xA5) wrote.push(a);
    for (const [lo, hi] of c.blind || []) for (let a = lo; a <= hi; a++) blind.push(a);
    if (wrote.join() !== blind.join() && !badBlind++)
      firstBlind = `case ${i}: wrote ${wrote.length} screen bytes, the real code ${blind.length}`;
    const sig = new Set();
    for (let j = 0; j < c.sig.length; j += 4) sig.add(parseInt(c.sig.slice(j, j + 4), 16));
    const last = screens.find(([pc]) => sig.has(pc));
    if (last){
      menus++;
      for (const [text, pos] of last[1]) for (let k = 0, ch; (ch = want[text + k]); k++)
        for (let r = 0; r < 8; r++)
          if (m[scr((pos & 0xFF) + r, (pos >> 8) + k)] !== P.font[(ch - 0x20) * 8 + r] && !badGlyph++)
            firstGlyph = `case ${i}: $${text.toString(16)} char ${k} row ${r}`;
    }
    if (res.t !== c.t && !badT++) firstT = `case ${i}: T ${res.t} want ${c.t}`;
    if (res.a !== c.exit[iA] && !badA++) firstA = `case ${i}: A ${res.a} want ${c.exit[iA]}`;
    if (res.r !== c.rx && !badR++) firstR = `case ${i}: R ${res.r} want ${c.rx}`;
  }
  check('controlPass reads the same ports in the same order as the real $97CB', [badPorts, firstPorts], [0, '']);
  check('controlPass writes every byte the real $97CB wrote outside the screen (callio cases)', [badBytes, firstBytes], [0, '']);
  check('controlPass writes exactly the screen bytes the real $97CB wrote', [badBlind, firstBlind], [0, '']);
  check('the menu cases end with the lookalike glyphs of the strings of their last screen', [menus, badGlyph, firstGlyph], [13, 0, '']);
  check('every character controlPass printed has a lookalike glyph (fontMiss unchanged)',
        [P.fontMiss.count - missed, [...P.fontMiss.codes].map(x => x.toString(16)).join()], [0, '']);
  check('controlPass tallies the uncontended T of every case exactly', [badT, firstT], [0, '']);
  check('controlPass returns the A the real $97CB returned (the RET M at $975B)', [badA, firstA], [0, '']);
  check('controlPass counts R to the value the real $97CB left (the AI draws)', [badR, firstR], [0, '']);
  /* Every outcome of every conditional the cases executed, from python
     tools/branches.py --fixture build/callio_97cb.json --js.  Captured with
     --poke (2P: $9C2C=2 $AA46=0; Kempston: $8BD2=$8C42) and derived
     (callio --derive, 15 cases; the menu by --script, 13) where play
     never went; the starts (1, Kempston fire, 2) run New_Round $909E.
     The fixed strings printed from here (New_Round, the menu) never reach
     the bottom third ($C20B fall) or a code of $60 up ($C340, $C346 fall),
     and every one is non-empty, so no PC set shows the RET Z at $92F2
     taken without its fall.  Not here either: seven outcomes dead on
     hardware -- R bit 7 never set ($A174 $A185 $A3E2 $A56B taken, $A503
     fall), $A094 fall ($AA03/$AA43 are 0 whenever the AI is called),
     $A49F fall ($A614 < 7 on its only way in), $98A2 fall (no bit 5 from
     $8B1F) (ledger/97CB.toml). */
  const pcs = fx.cases.map(c => { const s = new Set();
    for (let j = 0; j < c.sig.length; j += 4) s.add(parseInt(c.sig.slice(j, j + 4), 16)); return s; });
  check('the callio cases reach every branch of $97CB, its controls $8B1F, the menu $8C54 and the AI $A090',
        [0x8B24, 0x8B2A, 0x8B3D, 0x8B42, 0x8B4C, 0x8B4E, 0x8B56, 0x8B5A, 0x8B62, 0x8B64, 0x8B6C, 0x8B70,
         0x8B78, 0x8B7A, 0x8B82, 0x8B86, 0x8B8E, 0x8B90, 0x8B98, 0x8B9C, 0x8BA4, 0x8BA6, 0x8BBA, 0x8BBF,
         0x8BCC, 0x8BCD, 0x8C95, 0x8C9E, 0x8CA6, 0x8CAF, 0x8CB7, 0x8CBF, 0x8CC7, 0x8CCF, 0x8CD7, 0x8CDA,
         0x8D1A, 0x8D22, 0x8D25, 0x8D2D, 0x8D30, 0x8D38, 0x8D3B, 0x8D43, 0x8D46, 0x8D4E, 0x8D63, 0x8D6C,
         0x8E27, 0x8E30, 0x8E33, 0x8E36, 0x8E45, 0x8E4B, 0x922F, 0x9235, 0x9239, 0x924A, 0x9254, 0x92F3,
         0x97D2, 0x97E3, 0x97EA, 0x97EF, 0x9801, 0x9808, 0x981A, 0x9821, 0x9827, 0x982E, 0x9835, 0x983D,
         0x9843, 0x9849, 0x984F, 0x9860, 0x9874, 0x987A, 0x9880, 0x9891, 0x98A6, 0x98BA, 0x9C64, 0x9C67,
         0x9C69, 0x9C6D, 0xA09A, 0xA0AC, 0xA0B3, 0xA0B8, 0xA0BE, 0xA0C5, 0xA0CC, 0xA0D9, 0xA0E0, 0xA0E4,
         0xA0F3, 0xA0FC, 0xA104, 0xA108, 0xA10C, 0xA110, 0xA116, 0xA11C, 0xA123, 0xA127, 0xA12E, 0xA132,
         0xA136, 0xA13A, 0xA13E, 0xA145, 0xA14C, 0xA152, 0xA155, 0xA15E, 0xA161, 0xA168, 0xA16D, 0xA177,
         0xA17C, 0xA181, 0xA188, 0xA18C, 0xA18E, 0xA195, 0xA1A1, 0xA1A5, 0xA1B5, 0xA1BB, 0xA1C1, 0xA1C8,
         0xA1CC, 0xA1D2, 0xA1F4, 0xA1FB, 0xA207, 0xA20D, 0xA21B, 0xA222, 0xA226, 0xA22A, 0xA231, 0xA23A,
         0xA23E, 0xA247, 0xA255, 0xA259, 0xA25D, 0xA263, 0xA26A, 0xA273, 0xA27F, 0xA292, 0xA2A0, 0xA2A6,
         0xA2AF, 0xA2BD, 0xA2C1, 0xA2C5, 0xA2C7, 0xA2CE, 0xA2DB, 0xA2E2, 0xA2F1, 0xA2F8, 0xA2FC, 0xA30C,
         0xA313, 0xA325, 0xA342, 0xA349, 0xA34E, 0xA353, 0xA358, 0xA35F, 0xA366, 0xA36D, 0xA37A, 0xA383,
         0xA38C, 0xA390, 0xA397, 0xA398, 0xA3A1, 0xA3AF, 0xA3CF, 0xA3D3, 0xA3DA, 0xA3E5, 0xA3E9, 0xA3ED,
         0xA3EF, 0xA3F7, 0xA484, 0xA488, 0xA48C, 0xA490, 0xA492, 0xA4A8, 0xA4BE, 0xA4C5, 0xA4E8, 0xA4F5,
         0xA50C, 0xA545, 0xA54E, 0xA553, 0xA567, 0xA56E, 0xA57B, 0xA598, 0xA59E, 0xA5A2, 0xA5B3, 0xA5BA,
         0xA5BE, 0xA5C0, 0xA5C3, 0xA5C9, 0xA5CD, 0xA5DE, 0xA5E5, 0xA5E9, 0xC209, 0xC214, 0xC21A, 0xC31E,
         0xC31F, 0xC324, 0xC325, 0xC32A, 0xC32B, 0xC330, 0xC331, 0xC336, 0xC337, 0xC33C, 0xC33D, 0xC343,
         0xC349]
          .filter(a => !pcs.some(s => s.has(a))).map(a => a.toString(16)), []);
  /* each RET cc taken: a case that passed it and not the instruction after */
  check('the callio cases take the early returns of $98A0 and $A090',
        [[0x98B9, 0x98BA], [0xA0B7, 0xA0B8]]
          .filter(([a, b]) => !pcs.some(s => s.has(a) && !s.has(b))).map(([a]) => a.toString(16)), []);
  check('the callio cases include the quit (H+G held), 2P and Kempston passes',
        [0x9835, 0x8B2A, 0x8BBF].filter(a => !pcs.some(s => s.has(a))).map(a => a.toString(16)), []);
}

/* ---- the 2P yin-yang award $976F-$978D against its frozen oracle -------
   Bracketed from $976F to $978D with Num_Players poked to 2 (python
   tools/callio.py --capture --poke 0x9C2C=2 --call 0x976F 0x978D).  Play
   reaches counts 1 and 2 only -- the pass clears both counts after each
   draw -- so derived cases (the real code on a set count) reach 3 and 4+,
   which $ABD2 and $AD22 can bring (ledger/900E.toml). */
{
  const fx = P.assets.yy976f;
  const put = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
  let badBytes = 0, badT = 0, firstBytes = '', firstT = '', badM1 = 0, firstM1 = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);   // unread bytes poisoned: a stray 0 shows
    put(m, c.in);
    const want = m.slice(); put(want, c.out);
    P.M1.m1 = 0;
    const t = P.yinYang2P(m);
    if ((P.M1.m1 & 0x7F) !== ((c.rx - c.r) & 0x7F) && !badM1++) firstM1 = `case ${i}: M1 ${P.M1.m1} want ${(c.rx - c.r) & 0x7F} mod 128`;
    let diff = -1;
    for (let a = 0; a < 0x10000; a++) if (m[a] !== want[a]){ diff = a; break; }
    if (diff >= 0 && !badBytes++) firstBytes = `case ${i}: $${diff.toString(16)} = ${m[diff]} want ${want[diff]}`;
    if (t !== c.t && !badT++) firstT = `case ${i}: T ${t} want ${c.t}`;
  }
  check('yinYang2P writes every byte the real $976F-$978D wrote (callio cases)', [badBytes, firstBytes], [0, '']);
  check('yinYang2P tallies the uncontended T of every case exactly', [badT, firstT], [0, '']);
  /* R: the fixture's R at $976F and at $978D (callio.py --check --stamp-r) */
  check('yinYang2P counts the M1 cycles of every case as R advanced in the real $976F-$978D', [badM1, firstM1], [0, '']);
  const pcs = fx.cases.map(c => { const s = new Set();
    for (let j = 0; j < c.sig.length; j += 4) s.add(parseInt(c.sig.slice(j, j + 4), 16)); return s; });
  check('the callio cases reach every branch of $976F, $900E and its copy $9255',
        [0x9776, 0x977C, 0x9783, 0x9015, 0x901E, 0x9028, 0x9036, 0x904D, 0x905C, 0x9065, 0x906F, 0x907D, 0x9094,
         0x922F, 0x9235, 0x9239]
          .filter(a => !pcs.some(s => s.has(a))).map(a => a.toString(16)), []);
  check('the callio cases take the 1P exit and the RET Z of Yin_Yang_2UP',
        [[0x9774, 0x9776], [0x905B, 0x905C]]
          .filter(([a, b]) => !pcs.some(s => s.has(a) && !s.has(b))).map(([a]) => a.toString(16)), []);
}

/* ---- the sound effect $B15A against its frozen oracle -------------------
   python tools/sfx.py --capture: each call alone, uncontended, from s1.
   The ROM effects run the real code over the D6 substitutes poked into
   the ROM (--measure checks they keep the real ROM's T); effect 4 runs a
   chain of LFSR states from play and two derived ones whose first delay
   wraps BC to 65536 passes. */
{
  const fx = P.assets.sfx;
  let badW = 0, badT = 0, badM = 0, firstW = '', firstT = '', firstM = '', badM1 = 0, firstM1 = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);
    m.set(Buffer.from(c.mem_in, 'hex'), 0xB150);
    m.set(Buffer.from(c.lfsr, 'hex'), 0xB153);
    m[0xB2FA] = c.flag;
    for (let j = 0; j < 12; j++) m[0xB144 + j] = [0x79, 0xB1, 0x85, 0xB1, 0x91, 0xB1, 0x9D, 0xB1, 0xFB, 0xB1, 0x21, 0xB2][j];
    const out = [];
    P.M1.m1 = 0;
    const t = P.soundEffect(m, c.a, out);
    if ((P.M1.m1 & 0x7F) !== c.m1 && !badM1++) firstM1 = `case ${i}: M1 ${P.M1.m1} want ${c.m1} mod 128`;
    const w = JSON.stringify(out), want = JSON.stringify(c.writes);
    if (w !== want && !badW++){
      const k = out.findIndex((e, j) => !c.writes[j] || e[0] !== c.writes[j][0] || e[1] !== c.writes[j][1]);
      firstW = `case ${i}: write ${k} ${JSON.stringify(out[k])} want ${JSON.stringify(c.writes[k])} (${out.length}/${c.writes.length})`;
    }
    if (t !== c.t && !badT++) firstT = `case ${i}: T ${t} want ${c.t}`;
    const mem = Buffer.from(m.slice(0xB150, 0xB15A)).toString('hex');
    if (mem !== c.mem_out && !badM++) firstM = `case ${i}: $B150-$B159 ${mem} want ${c.mem_out}`;
  }
  check('soundEffect makes every $FE write of the real $B15A at the same T (sfx cases)', [badW, firstW], [0, '']);
  check('soundEffect tallies the uncontended T of every case exactly', [badT, firstT], [0, '']);
  check('soundEffect leaves $B150-$B159 (request, delay, LFSR, end, mask) as the real code did', [badM, firstM], [0, '']);
  /* R: the fixture's m1 is how far R advanced from $B15A to the RET (sfx.py) */
  check('soundEffect counts the M1 cycles of every case as R advanced in the real $B15A', [badM1, firstM1], [0, '']);
  check('the sfx cases cover the early returns, all six effects and the BC wrap',
        [[0, 1], [2, 0], [1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [6, 1]]
          .filter(([a, f]) => !fx.cases.some(c => c.a === a && c.flag === f)).map(String)
          .concat(fx.cases.some(c => c.kind === 'derived') ? [] : ['derived']), []);
  /* D6: the substitutes keep the real ROM's count, sum and zeros per segment */
  check('every D6 substitute keeps its segment count, masked sum and zeros, with bits above the mask',
        Object.values(fx.segments).flat().filter(s => s.vals.length !== s.n || (s.mask < 0xFF && !s.vals.some(v => v > s.mask))
          || s.vals.reduce((a, v) => a + ((v & s.mask) || 1), 0) !== s.sum || s.vals.filter(v => !(v & s.mask)).length !== s.zeros)
          .map(s => s.de.toString(16)), []);
}

/* ---- play_pass $9745, the whole pass, against its frozen oracle --------
   Bracketed from the CALL at $AE29 to $AE2C (python tools/callio.py
   --capture, s1, p1 and 2P by --poke; the quit derived by --script H+G,
   and P1 on frame 3 against a P2 with $AA56 set by --set $AA03, $AA56,
   so P1's step reads the opponent through $9C29 at $9930;
   shrunk by --cover to the cases that reach every PC).  Each callee is
   gated alone above; this checks the composition: the glue, the order, SP
   into $BF13, R carried through the AI draws, and where the effect's
   writes land.  The effect cases are ROM effects, whose inner edges move
   with the D6 substitutes (the sfx gate holds those): their writes must
   match in count and value, the first at the same T. */
{
  const fx = P.assets.pass9745;
  const put = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
  const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
  const iA = fx.regs.indexOf(0);
  let badBytes = 0, badBlind = 0, badT = 0, badA = 0, badR = 0, badPorts = 0, badOuts = 0;
  let firstBytes = '', firstBlind = '', firstT = '', firstA = '', firstR = '', firstPorts = '', firstOuts = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);   // unread bytes poisoned: a stray 0 shows
    put(m, c.in);
    const want = m.slice(); put(want, c.out);
    const log = c.ports || [];
    let j = 0, portErr = '';
    const io = { r: c.r, out: [], in: p => {
      if (j >= log.length || log[j][0] !== p){ portErr = portErr || `read ${j} of port $${p.toString(16)}`; j++; return 0xFF; }
      return log[j++][1];
    }, };
    const res = P.playPass(m, io, c.sp);
    if (j !== log.length) portErr = portErr || `${j} port reads, the machine ${log.length}`;
    if (portErr && !badPorts++) firstPorts = `case ${i}: ${portErr}`;
    let diff = -1;
    for (let a = 0; a < 0x10000; a++){
      if (a === c.sp - 128) a = c.sp + 2;            // the call's own stack frames (callio)
      if (!inBlind(a) && m[a] !== want[a]){ diff = a; break; }
    }
    if (diff >= 0 && !badBytes++) firstBytes = `case ${i}: $${diff.toString(16)} = ${m[diff]} want ${want[diff]}`;
    const wrote = [], blind = [];
    for (let a = 0; a < 0x10000; a++) if (inBlind(a) && m[a] !== 0xA5) wrote.push(a);
    for (const [lo, hi] of c.blind || []) for (let a = lo; a <= hi; a++) blind.push(a);
    if (wrote.join() !== blind.join() && !badBlind++)
      firstBlind = `case ${i}: wrote ${wrote.length} screen bytes, the real code ${blind.length}`;
    const outs = c.outs || [];
    if ((io.out.length !== outs.length || io.out.some((e, k) => e[1] !== outs[k][1])
         || (outs.length && io.out[0][0] !== outs[0][0])) && !badOuts++)
      firstOuts = `case ${i}: ${io.out.length} writes, first ${JSON.stringify(io.out[0])}; the machine ${outs.length}, ${JSON.stringify(outs[0])}`;
    if (res.t !== c.t && !badT++) firstT = `case ${i}: T ${res.t} want ${c.t}`;
    if (res.a !== c.exit[iA] && !badA++) firstA = `case ${i}: A ${res.a} want ${c.exit[iA]}`;
    if (res.r !== c.rx && !badR++) firstR = `case ${i}: R ${res.r} want ${c.rx}`;
    /* stop at the first bad case: a pass gone wrong reads bytes the case
       never held, and over the $A5 poison a sprite walk finds no end */
    if (badPorts + badBytes + badBlind + badOuts + badT + badA + badR) break;
  }
  check('playPass reads the same ports in the same order as the real $9745', [badPorts, firstPorts], [0, '']);
  check('playPass writes every byte the real $9745 wrote outside the timer cells (callio cases)', [badBytes, firstBytes], [0, '']);
  check('playPass writes exactly the timer-cell bytes the real $9745 wrote', [badBlind, firstBlind], [0, '']);
  check('playPass makes the effect\'s $FE writes in number and value, the first at the machine\'s T', [badOuts, firstOuts], [0, '']);
  check('playPass tallies the uncontended T of every case exactly', [badT, firstT], [0, '']);
  check('playPass returns the A the real $9745 returned (the RET M at $AE2D)', [badA, firstA], [0, '']);
  check('playPass counts R to the value the real $9745 left (the AI draws carried)', [badR, firstR], [0, '']);
  const pcs = fx.cases.map(c => { const s = new Set();
    for (let j = 0; j < c.sig.length; j += 4) s.add(parseInt(c.sig.slice(j, j + 4), 16)); return s; });
  check('the pass cases cover 1P, 2P, a timer print, an effect and both fighter draws',
        [0x975C, 0x9776, 0x9C93, 0xB15C, 0x9790, 0x97A6].filter(a => !pcs.some(s => s.has(a))).map(a => a.toString(16)), []);
  check('the pass cases take the RET M at $975B (the quit)',
        pcs.some(s => s.has(0x975B) && !s.has(0x975C)), true);
  check('the pass cases wrap R\'s low seven bits between $AE29 and $AE2C (the carry is mod 128)',
        fx.cases.some(c => (c.rx & 0x7F) < (c.r & 0x7F)), true);
}

/* ---- round_loop $AE26, the body from $AE2C, against its frozen oracle ----
   python tools/callio.py --capture --call 0xAE2C 0xAE29 (p1, s1; the $AA44
   = $11 arm derived: no play reached it).  Exact: $C427, T, R. */
{
  const fx = P.assets.tail_ae2c;
  const iA = fx.regs.indexOf(0);
  let bad = 0, first = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);
    for (const [a, h] of c.in) m.set(Buffer.from(h, 'hex'), a);
    const want = m.slice(); for (const [a, h] of c.out) want.set(Buffer.from(h, 'hex'), a);
    const res = P.roundTail(m, c.regs[iA], c.r);
    const got = [res.exit, res.t, res.r, m.findIndex((v, a) => v !== want[a])];
    if (JSON.stringify(got) !== JSON.stringify([null, c.t, c.rx, -1]) && !bad++)
      first = `case ${i}: exit, T, R, first bad byte ${JSON.stringify(got)} want ${JSON.stringify([null, c.t, c.rx, -1])}`;
  }
  check('roundTail matches the real $AE2C-$AE65 on every case: $C427, T and R exactly', [bad, first], [0, '']);
  check('...and the cases reach both $11 arms ($AA04, and $AA44 derived)',
        [0xAA04, 0xAA44].map(a => fx.cases.some(c => c.in.some(([x, h]) => x === a && h === '11'))), [true, true]);
}

/* ---- the point path $AD1B back to $AE29, against its frozen oracle -----
   python tools/callio.py --capture --call 0xAD1B 0xAE29,0xAD5F,0xAD94,0xAD44
   (p1: both points of the script; the other arms derived, port.json).
   Exact: every byte outside the score row, the score-row bytes written (D5:
   ROM glyphs), the way out (xpc), T and R. */
{
  const fx = P.assets.point_ad1b;
  const iA = fx.regs.indexOf(0);
  const EXIT = { 0xAE29: null, 0xAD5F: 'p1', 0xAD94: 'p2', 0xAD44: 'time' };
  const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
  let bad = 0, first = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);
    for (const [a, h] of c.in) m.set(Buffer.from(h, 'hex'), a);
    const want = m.slice(); for (const [a, h] of c.out) want.set(Buffer.from(h, 'hex'), a);
    const res = P.pointPath(m, c.regs[iA], c.r);
    let diff = -1;
    for (let a = 0; a < 0x10000; a++){
      if (a === c.sp - 128) a = c.sp + 2;            // the call's own stack frames (callio)
      if (!inBlind(a) && m[a] !== want[a]){ diff = a; break; }
    }
    const wrote = [], blind = [];
    for (let a = 0; a < 0x10000; a++) if (inBlind(a) && m[a] !== 0xA5) wrote.push(a);
    for (const [lo, hi] of c.blind || []) for (let a = lo; a <= hi; a++) blind.push(a);
    const got = [res.exit, res.t, res.r, diff, wrote.join() === blind.join()];
    const w = [EXIT[c.xpc], c.t, c.rx, -1, true];
    if (JSON.stringify(got) !== JSON.stringify(w) && !bad++)
      first = `case ${i}: exit, T, R, first bad byte, score row ${JSON.stringify(got)} want ${JSON.stringify(w)}`;
  }
  check('pointPath matches the real $AD1B to $AE29 (or its way out) on every case: bytes, exit, T and R exactly', [bad, first], [0, '']);
  check('...and the cases take every way out: back in, P1 wins, P2 wins, time up',
        [0xAE29, 0xAD5F, 0xAD94, 0xAD44].map(x => fx.cases.some(c => c.xpc === x)), [true, true, true, true]);
  const set = c => (c.derived || {}).set || {};
  check('...and the derived cases hold a count of 3 (no win), a binary carry into DAA and a half-carry under 10',
        [fx.cases.some(c => set(c).aa08 === 1 && set(c).aa01 === 2), fx.cases.some(c => set(c).b030 === 0xF5),
         fx.cases.some(c => set(c).b019 === 8 && set(c).b030 === 9)], [true, true, true]);
}

/* ---- the 2UP game's ways on from $AE17, against its frozen oracle -------
   python tools/callio.py --capture --state p1 --call 0xAE17 0xAE29,0xAC34
   (the 2UP game of live_2up's script: its time ups into the next bout; a
   point back in, the quit and the game ends at rank 3 -- both posed, P1,
   P2, a high score -- derived, the RETs to $ADE0 and $AC34 with --up,
   port.json).  twoOn, and for time up stageStep, the tune, twoNext and
   stage2 with roundIn, or twoEnd, the pose's loop (winPass at the SP of
   $AD9C's level, the call's) and twoOut, as the live engine runs them.
   Exact as pointPath's, and the tune's $FE writes at their T. */
{
  const fx = P.assets.round_ae17;
  const iA = fx.regs.indexOf(0);
  const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
  let bad = 0, first = '', badO = 0;
  const kinds = [];
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);
    for (const [a, h] of c.in) m.set(Buffer.from(h, 'hex'), a);
    const want = m.slice(); for (const [a, h] of c.out) want.set(Buffer.from(h, 'hex'), a);
    const u = P.twoOn(m, c.regs[iA], c.r), outs = [];
    let t = u.t, at = u.exit === 'quit' ? 0xAC34 : u.exit === null ? 0xAE29 : 0, kind = u.exit || 'point';
    if (u.exit === 'time'){
      t += P.stageStep(m);
      t += P.introMusic(m, outs, t);
      const n = P.twoNext(m);
      t += n.t;
      if (!n.end){ t += P.stage2(m) + P.roundIn(m, c.r); at = 0xAE29; }
      else {
        const e = P.twoEnd(m);
        t += e.t; kind = e.A ? `pose ${e.A.toString(16)}` : 'both';
        for (;;){ const w = P.winPass(m, e.A || 0xAA00, c.sp); t += w.t; if (w.out) break; }
        t += P.twoOut(e.A); at = 0xAC34;
      }
    }
    kinds.push(kind);
    const r = (c.r & 0x80) | ((c.r + P.M1.m1) & 0x7F);
    let diff = -1;
    for (let a = 0; a < 0x10000; a++){
      if (a === c.sp - 128) a = c.sp + 2;            // the call's own stack frames (callio)
      if (!inBlind(a) && m[a] !== want[a]){ diff = a; break; }
    }
    const wrote = [], blind = [];
    for (let a = 0; a < 0x10000; a++) if (inBlind(a) && m[a] !== 0xA5) wrote.push(a);
    for (const [lo, hi] of c.blind || []) for (let a = lo; a <= hi; a++) blind.push(a);
    const got = [at, t, r, diff, wrote.join() === blind.join()];
    const w = [c.xpc, c.t, c.rx, -1, true];
    if (JSON.stringify(got) !== JSON.stringify(w) && !bad++)
      first = `case ${i}: PC, T, R, first bad byte, score row ${JSON.stringify(got)} want ${JSON.stringify(w)}`;
    if (JSON.stringify(outs) !== JSON.stringify(c.outs || [])) badO++;
  }
  check('twoOn and the 2UP game\'s ways on match the real $AE17 to $AE29 or $AC34 on every case: bytes, PC, T and R exactly', [bad, first], [0, '']);
  check('...and the tune\'s $FE writes at their T from $AE17, on every case', badO, 0);
  check('...and the cases take every way: a point back in, the quit, time up into the next bout, and the game end both posed, P1\'s pose and P2\'s',
        ['point', 'quit', 'time', 'both', 'pose aa00', 'pose aa40'].map(x => kinds.includes(x)), [true, true, true, true, true, true]);
}

/* ---- the demo's point path $ABCB back to $AE29, against its oracle -----
   python tools/callio.py --capture --call 0xABCB 0xAE29,0xABB9,0xAC00,0xABE5
   (p1, the demo after the lost bout: 7 points back in, 2 won by P1; the
   other arms derived, the RETs to $ABB9 with --up, port.json).  Exact as
   pointPath's: every byte outside the score row, the way out, T and R. */
{
  const fx = P.assets.demo_abcb;
  const iA = fx.regs.indexOf(0);
  const EXIT = { 0xAE29: null, 0xAC00: 'p1', 0xABE5: 'p2' };
  const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
  let bad = 0, first = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);
    for (const [a, h] of c.in) m.set(Buffer.from(h, 'hex'), a);
    const want = m.slice(); for (const [a, h] of c.out) want.set(Buffer.from(h, 'hex'), a);
    const res = P.demoPoint(m, c.regs[iA], c.r);
    let diff = -1;
    for (let a = 0; a < 0x10000; a++){
      if (a === c.sp - 128) a = c.sp + 2;            // the call's own stack frames (callio)
      if (!inBlind(a) && m[a] !== want[a]){ diff = a; break; }
    }
    const wrote = [], blind = [];
    for (let a = 0; a < 0x10000; a++) if (inBlind(a) && m[a] !== 0xA5) wrote.push(a);
    for (const [lo, hi] of c.blind || []) for (let a = lo; a <= hi; a++) blind.push(a);
    const out = c.xpc === 0xABB9 ? (c.exit[iA] & 0x80 ? 'quit' : 'time') : EXIT[c.xpc];   // the RET: A says which
    const got = [res.exit, res.t, res.r, diff, wrote.join() === blind.join()];
    const w = [out, c.t, c.rx, -1, true];
    if (JSON.stringify(got) !== JSON.stringify(w) && !bad++)
      first = `case ${i}: exit, T, R, first bad byte, score row ${JSON.stringify(got)} want ${JSON.stringify(w)}`;
  }
  check("demoPoint matches the real $ABCB to $AE29 (or its way out) on every case: bytes, exit, T and R exactly", [bad, first], [0, '']);
  const set = c => (c.derived || {}).set || {};
  check('...and the cases take every way out: back in, P1 wins, P2 wins, time up with and without a point, the RET M',
        [[0xAE29, 0xAC00, 0xABE5].map(x => fx.cases.some(c => c.xpc === x)),
         fx.cases.filter(c => c.xpc === 0xABB9).map(c => [c.exit[iA], set(c).aa03 === 0])],
        [[true, true, true], [[0, false], [0, true], [0x80, false]]]);
  check('...and P1 at 4 with $AA03 set is not looked at: back in, faithful',
        fx.cases.filter(c => set(c).aa03 === 1).map(c => c.xpc), [0xAE29]);
}

/* ---- the demo's ways on $ABB9, against its oracle ----------------------
   python tools/callio.py --capture --call 0xABB9 0xAE29,0xAC27 (p1, the
   demo's three stage changes after the lost bout; the RET at rank 4, the
   stage's wrap with it and the quit derived with --up 0xAC27, port.json).
   Every byte outside the text cells (D5), the cells written, T, R, and
   where it left. */
{
  const fx = P.assets.demo_abb9;
  const iA = fx.regs.indexOf(0);
  const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
  let bad = 0, first = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);
    for (const [a, h] of c.in) m.set(Buffer.from(h, 'hex'), a);
    const want = m.slice(); for (const [a, h] of c.out) want.set(Buffer.from(h, 'hex'), a);
    P.M1.m1 = 0;
    let res;
    try { res = P.demoOn(m, c.regs[iA], c.r); }
    catch (e){ if (!bad++) first = `case ${i}: ${e.message}`; continue; }
    let diff = -1;
    for (let a = 0; a < 0x10000; a++){
      if (a === c.sp - 128) a = c.sp + 2;            // the call's own stack frames (callio)
      if (!inBlind(a) && m[a] !== want[a]){ diff = a; break; }
    }
    const wrote = [], blind = [];
    for (let a = 0; a < 0x10000; a++) if (inBlind(a) && m[a] !== 0xA5) wrote.push(a);
    for (const [lo, hi] of c.blind || []) for (let a = lo; a <= hi; a++) blind.push(a);
    const got = [res.at, res.t, (c.r & 0x80) | ((c.r + P.M1.m1) & 0x7F), diff, wrote.join() === blind.join()];
    const w = [c.xpc, c.t, c.rx, -1, true];
    if (JSON.stringify(got) !== JSON.stringify(w) && !bad++)
      first = `case ${i}: at, T, R, first bad byte, text cells ${JSON.stringify(got)} want ${JSON.stringify(w)}`;
  }
  check("demoOn matches the real $ABB9 to the next stage's $AE29 or $AC27 on every case: bytes, text cells, at, T and R exactly", [bad, first], [0, '']);
  const set = c => (c.derived || {}).set || {};
  check('...and the cases take every way: each stage 1-3 next, the RET at rank 4 (with and without the stage wrap), the quit',
        [fx.cases.filter(c => c.xpc === 0xAE29).length, fx.cases.filter(c => c.xpc === 0xAC27).map(c => [set(c).b05f, set(c).af34, ((c.derived || {}).reg || {})[0]])],
        [3, [[3, undefined, undefined], [undefined, undefined, 128], [3, 3, undefined]]]);
}

/* ---- P2 wins the 1UP bout: $AD94, the victory pose $AE9D, to $ACA6 -----
   python tools/callio.py --capture --state p1 --call 0xAD94 0xACA6 (the
   call the live script makes, 66 passes of the pose).  winStart, winPass
   until its RET, winEnd, composed as the engine runs them: every byte
   outside the stack frames, T and R exactly. */
{
  const fx = P.assets.win_ad94;
  let bad = 0, first = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);
    for (const [a, h] of c.in) m.set(Buffer.from(h, 'hex'), a);
    const want = m.slice(); for (const [a, h] of c.out) want.set(Buffer.from(h, 'hex'), a);
    P.M1.m1 = 0;
    let t = P.winStart(m, 0xAA40), n = 0, w;       // the CALL at $AD94 and $AE9D's body
    try {                                          // a pose longer than the machine's, or one that draws garbage, fails
      do { w = P.winPass(m, 0xAA40, c.sp - 2, null); t += w.t; n++; } while (!w.out && t <= c.t);
    } catch (e){ if (!bad++) first = `case ${i}: pass ${n}: ${e.message}`; continue; }
    t += P.winEnd();
    let diff = -1;
    for (let a = 0; a < 0x10000; a++){
      if (a === c.sp - 128) a = c.sp + 2;
      if (m[a] !== want[a]){ diff = a; break; }
    }
    const got = [t, (c.r & 0x80) | ((c.r + P.M1.m1) & 0x7F), diff, n];
    const wnt = [c.t, c.rx, -1, 66];
    if (JSON.stringify(got) !== JSON.stringify(wnt) && !bad++)
      first = `case ${i}: T, R, first bad byte, passes ${JSON.stringify(got)} want ${JSON.stringify(wnt)}`;
  }
  check('winStart, winPass and winEnd match the real $AD94 to $ACA6 (P2 wins, 66 passes of the pose): bytes, T and R exactly',
        [bad, first], [0, '']);
  check('...and the machine left for $ACA6 with A = 0 (the 1UP bout lost: winEnd)',
        fx.cases.map(c => c.exit[fx.regs.indexOf(0)]), [0]);
}

/* ---- P1 wins the 1UP bout: $AD5F, the pose $AE7A, the time bonus -------
   python tools/callio.py --capture --state p1 --poke 0xAA01=4 --call
   0xAD5F 0xACA6 (the start constructed: P1's count at 4, so the script's
   first point wins), and Time 0 derived.  winStart, winPass until its RET,
   bonusStart, bonusPass until out: every byte outside the stack frames and
   the score row, the score-row bytes written (D5), T and R exactly. */
{
  const fx = P.assets.win_ad5f;
  const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
  let bad = 0, first = '';
  const secs = [];
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);
    for (const [a, h] of c.in) m.set(Buffer.from(h, 'hex'), a);
    const want = m.slice(); for (const [a, h] of c.out) want.set(Buffer.from(h, 'hex'), a);
    P.M1.m1 = 0;
    let t = P.winStart(m, 0xAA00), n = 0, k = 0, w;  // the CALL at $AD5F and $AE7A's body
    try {
      do { w = P.winPass(m, 0xAA00, c.sp - 2, null); t += w.t; n++; } while (!w.out && t <= c.t);
      w = P.bonusStart(m); t += w.t;
      while (!w.out && t <= c.t){ w = P.bonusPass(m); t += w.t; k++; }
    } catch (e){ if (!bad++) first = `case ${i}: pose ${n}, second ${k}: ${e.message}`; continue; }
    secs.push(k);
    let diff = -1;
    for (let a = 0; a < 0x10000; a++){
      if (a === c.sp - 128) a = c.sp + 2;
      if (!inBlind(a) && m[a] !== want[a]){ diff = a; break; }
    }
    const wrote = [], blind = [];
    for (let a = 0; a < 0x10000; a++) if (inBlind(a) && m[a] !== 0xA5) wrote.push(a);
    for (const [lo, hi] of c.blind || []) for (let a = lo; a <= hi; a++) blind.push(a);
    const got = [t, (c.r & 0x80) | ((c.r + P.M1.m1) & 0x7F), diff, wrote.join() === blind.join(), n];
    const wnt = [c.t, c.rx, -1, true, 66];
    if (JSON.stringify(got) !== JSON.stringify(wnt) && !bad++)
      first = `case ${i}: T, R, first bad byte, score row, passes ${JSON.stringify(got)} want ${JSON.stringify(wnt)}`;
  }
  check('winStart, winPass, bonusStart and bonusPass match the real $AD5F to $ACA6 (P1 wins, 66 passes of the pose, the clock counted): bytes, T and R exactly',
        [bad, first], [0, '']);
  const clock = c => { for (const [a, h] of c.in) if (a <= 0x9CA5 && 0x9CA5 < a + h.length / 2) return parseInt(h.substr((0x9CA5 - a) * 2, 2), 16); };
  check('...and the machine left for $ACA6 with A = 1 (the bout won), a second counted for each left on the clock, played and none (Time 0 derived)',
        [fx.cases.map(c => c.exit[fx.regs.indexOf(0)]), secs, fx.cases.map(c => (c.derived || {}).set), secs[0] > 1],
        [[1, 1], fx.cases.map(clock), [undefined, { '9ca5': 0 }], true]);
}

/* ---- time up: the round end $AE67 and the decision $AD44 ----------------
   python tools/callio.py --capture --state p1 --poke 0x9CA5=1 --call 0xAE67
   0xAD1B, and --call 0xAD44 0xACA6 with the counts poked (port.json; every
   start constructed and played).  endStart, winPass on $AA0D one CALL
   deeper, endTail; timeUp, then the pose (and P1's bonus) or the draw,
   composed as the engine runs them: every byte outside the stack frames
   and the score row, the score-row bytes written (D5), T, R and A. */
{
  const load = (fx, c) => {
    const m = new Uint8Array(0x10000).fill(0xA5);
    for (const [a, h] of c.in) m.set(Buffer.from(h, 'hex'), a);
    const want = m.slice(); for (const [a, h] of c.out) want.set(Buffer.from(h, 'hex'), a);
    return [m, want];
  };
  const verdict = (fx, c, m, want) => {             // first bad byte outside frames and blind, and the blind bytes written
    const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
    let diff = -1;
    for (let a = 0; a < 0x10000; a++){
      if (a === c.sp - 128) a = c.sp + 2;
      if (!inBlind(a) && m[a] !== want[a]){ diff = a; break; }
    }
    const wrote = [], blind = [];
    for (let a = 0; a < 0x10000; a++) if (inBlind(a) && m[a] !== 0xA5) wrote.push(a);
    for (const [lo, hi] of c.blind || []) for (let a = lo; a <= hi; a++) blind.push(a);
    return [diff, wrote.join() === blind.join()];
  };
  const rx = c => (c.r & 0x80) | ((c.r + P.M1.m1) & 0x7F);
  {
    const fx = P.assets.end_ae67, iA = fx.regs.indexOf(0);
    let bad = 0, first = '', passes = [];
    for (let i = 0; i < fx.cases.length; i++){
      const c = fx.cases[i], [m, want] = load(fx, c);
      P.M1.m1 = 0;
      let t = P.endStart(m), n = 0, w, e;
      try {
        do { w = P.winPass(m, 0xAA00, c.sp - 2, null); t += w.t; n++; } while (!w.out && t <= c.t);
        e = P.endTail(m); t += e.t;
      } catch (err){ if (!bad++) first = `case ${i}: pass ${n}: ${err.message}`; continue; }
      passes.push(n);
      const got = [t, rx(c), ...verdict(fx, c, m, want), e.a], wnt = [c.t, c.rx, -1, true, c.exit[iA]];
      if (JSON.stringify(got) !== JSON.stringify(wnt) && !bad++)
        first = `case ${i}: T, R, first bad byte, score row, A ${JSON.stringify(got)} want ${JSON.stringify(wnt)}`;
    }
    check('endStart, winPass on $AA0D and endTail match the real $AE67 to $AD1B (time up, the round end): bytes, T, R and A = (IX) exactly',
          [bad, first], [0, '']);
    checkTrue('...over a loop of many passes, the start constructed (Time poked to 1)',
              passes[0] > 1 && fx.cases.every(c => (c.poked || {})['9ca5'] === 1), `passes ${passes}`);
  }
  {
    const fx = P.assets.time_ad44, iA = fx.regs.indexOf(0);
    let bad = 0, first = '';
    const ways = [];
    for (let i = 0; i < fx.cases.length; i++){
      const c = fx.cases[i], [m, want] = load(fx, c);
      P.M1.m1 = 0;
      const u = P.timeUp(m);
      let t = u.t, w, a = 0x81;
      ways.push(u.exit);
      try {
        if (u.exit !== 'draw'){
          const A = u.exit === 'p1' ? 0xAA00 : 0xAA40;
          t += P.winStart(m, A);
          do { w = P.winPass(m, A, c.sp - 2, null); t += w.t; } while (!w.out && t <= c.t);
          if (A === 0xAA40){ t += P.winEnd(); a = 0; }
          else {
            w = P.bonusStart(m); t += w.t;
            while (!w.out && t <= c.t){ w = P.bonusPass(m); t += w.t; }
            a = 1;
          }
        }
      } catch (err){ if (!bad++) first = `case ${i}: ${err.message}`; continue; }
      const got = [t, rx(c), ...verdict(fx, c, m, want), a], wnt = [c.t, c.rx, -1, true, c.exit[iA]];
      if (JSON.stringify(got) !== JSON.stringify(wnt) && !bad++)
        first = `case ${i}: T, R, first bad byte, score row, A ${JSON.stringify(got)} want ${JSON.stringify(wnt)}`;
    }
    check('timeUp, then the pose (and the bonus) or the draw, match the real $AD44 to $ACA6 on every case: bytes, T, R and A exactly',
          [bad, first], [0, '']);
    check('...and the cases take every arm: the draw, P1 and P2 ahead on the count, then on the tally ($AD5C, $AD91)',
          [ways, fx.cases.map(c => c.exit[iA])], [['draw', 'p1', 'p2', 'p1', 'p2'], [0x81, 1, 0, 1, 0]]);
  }
  {
    const fx = P.assets.draw_ad44;
    let bad = 0, first = '', passes = [];
    for (let i = 0; i < fx.cases.length; i++){
      const c = fx.cases[i], [m, want] = load(fx, c);
      P.M1.m1 = 0;
      const u = P.timeUp(m);
      let t = u.t, n = 0, w;
      if (u.exit !== 'draw'){ if (!bad++) first = `case ${i}: timeUp ${u.exit}`; continue; }
      t += P.drawStart(m);                          // $ACA6, $ACCF and the CALL $ACE8 at $ACD3
      try {
        do { w = P.winPass(m, 0xAA00, c.sp, null); t += w.t; n++; } while (!w.out && t <= c.t);   // $BF13 at SP - 4 + 2
      } catch (err){ if (!bad++) first = `case ${i}: pass ${n}: ${err.message}`; continue; }
      passes.push(n);
      const got = [t, rx(c), ...verdict(fx, c, m, want)], wnt = [c.t, c.rx, -1, true];
      if (JSON.stringify(got) !== JSON.stringify(wnt) && !bad++)
        first = `case ${i}: T, R, first bad byte, score row ${JSON.stringify(got)} want ${JSON.stringify(wnt)}`;
    }
    check('timeUp, drawStart and winPass on $AA0D match the real $AD44 to the return of the CALL $ACE8 at $ACD3 (the draw: both to script $19): bytes, T and R exactly, 66 passes',
          [bad, first, passes], [0, '', [66]]);
  }
}

{
  /* the page's IN: what tools/harness.py Ports.read_port answers */
  const kb = new S.Keyboard(); kb.press('Q'); kb.kempston = 0x10;
  check('specPort answers as the harness Ports do: Kempston on $1F, half-rows on even ports, $FF elsewhere',
        [0x001F, 0xFBFE, 0xF7FE, 0xFBFD, 0x00FF].map(p => P.specPort(kb, p)), [0x10, 0xFE, 0xFF, 0xFF, 0xFF]);
}

/* ---- the 1UP game after a bout: $ACA6 to $AC5F or $AC39 ----------------
   python tools/callio.py --capture --state p1 --call 0xACA6 0xAC5F,0xAC39
   (port.json: played, then the starts constructed by pokes: P1's count,
   the bouts left $AA3C, the stage $AF34, the rank $B05F, Time).  boutNext
   for A = 0 / 1; drawStart, winPass on $AA0D and the JP for the draw:
   every byte outside the stack frames and the score row, T, R and the PC
   left by. */
{
  const fx = P.assets.next_aca6, iA = fx.regs.indexOf(0);
  const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
  let bad = 0, first = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);
    for (const [a, h] of c.in) m.set(Buffer.from(h, 'hex'), a);
    const want = m.slice(); for (const [a, h] of c.out) want.set(Buffer.from(h, 'hex'), a);
    P.M1.m1 = 0;
    const a = c.regs[iA];
    let t, at, n = 0;
    try {
      if (a === 0x81){                              // $ACCF, CALL $ACE8, its loop, JP $AC5F
        t = P.drawStart(m); let w;
        do { w = P.winPass(m, 0xAA00, c.sp - 2, null); t += w.t; n++; } while (!w.out && t <= c.t);
        t += 10; P.M1.m1 += 1; at = 0xAC5F;
      } else { const b = P.boutNext(m, a, c.r); t = b.t; at = b.at; }
    } catch (e){ if (!bad++) first = `case ${i}: ${e.message}`; continue; }
    let diff = -1;
    for (let x = 0; x < 0x10000; x++){
      if (x === c.sp - 128) x = c.sp + 2;
      if (!inBlind(x) && m[x] !== want[x]){ diff = x; break; }
    }
    const got = [t, (c.r & 0x80) | ((c.r + P.M1.m1) & 0x7F), diff, at];
    const wnt = [c.t, c.rx, -1, c.xpc];
    if (JSON.stringify(got) !== JSON.stringify(wnt) && !bad++)
      first = `case ${i}: T, R, first bad byte, PC ${JSON.stringify(got)} want ${JSON.stringify(wnt)}`;
  }
  check("boutNext (and the draw's pose) match the real $ACA6 to $AC5F / $AC39 on every case: bytes, T, R and the PC left by exactly",
        [bad, first], [0, '']);
  check("...and the cases take every arm: lost, won with bouts left, rank up, rank up with the stage wrapping, the top rank's random, the draw; and from a real snapshot (stage2, not poked): rank up, then lost",
        [fx.cases.map(c => c.regs[iA]), fx.cases.map(c => c.t), fx.cases.map(c => c.source)],
        [[0, 1, 0, 1, 1, 1, 0x81, 1, 1, 0], [40, 54, 40, 222, 240, 251, fx.cases[6].t, 222, 222, 40], [...Array(8).fill(undefined), 'stage2', 'stage2']]);
  check('...and one derived: the rank from 9 to $10, a BCD carry through DAA',
        [fx.cases[7].derived, fx.cases[7].out.find(([a]) => a === 0xB05F)], [{ from: 3, set: { b05f: 9 } }, [0xB05F, '10']]);
}

/* ---- the lost bout's way on: Check_HighScore, $AC39 to $AC3C ----------
   python tools/callio.py --capture --state p1 --call 0xAC39 0xAC3C
   (port.json: played below the table and with the table poked to 0, the
   rest derived: below, a tie, above, a higher top byte with a lower bottom
   one, and 2UP).  checkHighScore: every byte outside the stack frames and
   the text cells (D5), the score buffer the text is drawn from, T and R. */
{
  const fx = P.assets.hiscore_ac39;
  const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
  let bad = 0, first = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);
    for (const [a, h] of c.in) m.set(Buffer.from(h, 'hex'), a);
    const want = m.slice(); for (const [a, h] of c.out) want.set(Buffer.from(h, 'hex'), a);
    P.M1.m1 = 0;
    let t;
    try { t = P.checkHighScore(m); } catch (e){ if (!bad++) first = `case ${i}: ${e.message}`; continue; }
    let diff = -1;
    for (let x = 0; x < 0x10000; x++){
      if (x === c.sp - 128) x = c.sp + 2;
      if (!inBlind(x) && m[x] !== want[x]){ diff = x; break; }
    }
    const got = [t, (c.r & 0x80) | ((c.r + P.M1.m1) & 0x7F), diff];
    const wnt = [c.t, c.rx, -1];
    if (JSON.stringify(got) !== JSON.stringify(wnt) && !bad++)
      first = `case ${i}: T, R, first bad byte ${JSON.stringify(got)} want ${JSON.stringify(wnt)}`;
  }
  check('checkHighScore matches the real $AC39 to $AC3C on every case: bytes, T and R exactly',
        [bad, first], [0, '']);
  const hi = c => (c.out.find(([a]) => a === 0xB024) || [, ''])[1].slice(0, 16);
  check("...and the cases take every arm: below (twice), the table beaten (played, a tie, above), a higher top byte not enough; 2UP: a tie, P2 higher (copied over P1) beating and tying the table, P1 higher beating it and not",
        [fx.cases.map(c => c.t), fx.cases.map(c => c.derived && c.derived.from), fx.cases.map(hi)],
        [[368, 11336, 368, 11208, 11106, 343, 807, 11596, 11621, 11597, 783, 11597],
         [undefined, undefined, 0, 0, 0, 0, 0, 6, 6, 6, 6, 6],
         ['', '2020202020202030', '', '2020202031303030', '2020203131353030', '', '', '2020202032303030', '2020202031303030', '2020202035303030', '', '2020202035303030']]);
}

/* ---- the next bout's setup: $AC5F to the CALL $AD18 --------------------
   python tools/callio.py --capture --state p1 --call 0xAC5F 0xAD18 (port.json:
   the starts constructed, P1 winning the last bout at a rank, each stage;
   no new stage, sound off and novice derived).  setupMusic then setupRest:
   every byte outside the stack frames and the text cells (D5), the text
   cells written, T, R and every $FE write of the tune at its T. */
{
  const fx = P.assets.setup_ac5f;
  const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
  let bad = 0, first = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);
    for (const [a, h] of c.in) m.set(Buffer.from(h, 'hex'), a);
    const want = m.slice(); for (const [a, h] of c.out) want.set(Buffer.from(h, 'hex'), a);
    P.M1.m1 = 0;
    const outs = [];
    let t;
    try { const s = P.setupMusic(m, outs); t = s.t + P.setupRest(m, s.stage); }
    catch (e){ if (!bad++) first = `case ${i}: ${e.message}`; continue; }
    let diff = -1;
    for (let x = 0; x < 0x10000; x++){
      if (x === c.sp - 128) x = c.sp + 2;
      if (!inBlind(x) && m[x] !== want[x]){ diff = x; break; }
    }
    const wrote = [], blind = [];
    for (let x = 0; x < 0x10000; x++) if (inBlind(x) && m[x] !== 0xA5) wrote.push(x);
    for (const [lo, hi] of c.blind || []) for (let x = lo; x <= hi; x++) blind.push(x);
    const got = [t, (c.r & 0x80) | ((c.r + P.M1.m1) & 0x7F), diff, wrote.join() === blind.join(), JSON.stringify(outs) === JSON.stringify(c.outs || [])];
    const wnt = [c.t, c.rx, -1, true, true];
    if (JSON.stringify(got) !== JSON.stringify(wnt) && !bad++)
      first = `case ${i}: T, R, first bad byte, text cells, tune ${JSON.stringify(got)} want ${JSON.stringify(wnt)}`;
  }
  check("setupMusic and setupRest match the real $AC5F to the CALL $AD18 on every case: bytes, text cells, T, R and the tune's $FE writes exactly",
        [bad, first], [0, '']);
  const at = (c, x) => { for (const [a, h] of c.in) if (a <= x && x < a + h.length / 2) return parseInt(h.substr((x - a) * 2, 2), 16); };
  check('...and the cases take every arm: each stage (2, 3, the wrap to 1) and rank suffix, the tune played, and derived: no new stage (neither read), sound off, novice; and stage 3 from a real snapshot (stage2, not poked)',
        [fx.cases.map(c => at(c, 0xAF34)), fx.cases.map(c => at(c, 0xB05F)), fx.cases.map(c => (c.outs || []).length),
         fx.cases.map(c => c.derived && c.derived.set), fx.cases.map(c => c.source)],
        [[2, 3, 1, 1, undefined, 2, 2, 3], [1, 2, 3, 6, undefined, 1, 0, 1], [3422, 3422, 3422, 3422, 0, 0, 3422, 3422],
         [undefined, undefined, undefined, undefined, { af35: 0 }, { b2fa: 0 }, { b05f: 0 }, undefined], [...Array(7).fill(undefined), 'stage2']]);
}

/* ---- the attract demo after a lost bout: $AC3C to its first $AE29 -------
   python tools/callio.py --capture --state p1 --call 0xAC3C 0xAE29 (port.json:
   one played, the rest derived with R at the JR set, so the two draws for
   the demo's ranks take each value).  demoIn: every byte outside the stack
   frames and the text cells (D5), the text cells written, T and R. */
function demoEntry(fx, run){
  const inBlind = a => fx.blind.some(([lo, hi]) => lo <= a && a <= hi);
  let bad = 0, first = '';
  for (let i = 0; i < fx.cases.length; i++){
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(0xA5);
    for (const [a, h] of c.in) m.set(Buffer.from(h, 'hex'), a);
    const want = m.slice(); for (const [a, h] of c.out) want.set(Buffer.from(h, 'hex'), a);
    P.M1.m1 = 0;
    let t;
    try { t = run(m, c.r); }
    catch (e){ if (!bad++) first = `case ${i}: ${e.message}`; continue; }
    let diff = -1;
    for (let x = 0; x < 0x10000; x++){
      if (x === c.sp - 128) x = c.sp + 2;
      if (!inBlind(x) && m[x] !== want[x]){ diff = x; break; }
    }
    const wrote = [], blind = [];
    for (let x = 0; x < 0x10000; x++) if (inBlind(x) && m[x] !== 0xA5) wrote.push(x);
    for (const [lo, hi] of c.blind || []) for (let x = lo; x <= hi; x++) blind.push(x);
    const got = [t, (c.r & 0x80) | ((c.r + P.M1.m1) & 0x7F), diff, wrote.join() === blind.join()];
    const wnt = [c.t, c.rx, -1, true];
    if (JSON.stringify(got) !== JSON.stringify(wnt) && !bad++)
      first = `case ${i}: T, R, first bad byte, text cells ${JSON.stringify(got)} want ${JSON.stringify(wnt)}`;
  }
  return [bad, first];
}
{
  const fx = P.assets.demo_ac3c;
  check("demoIn matches the real $AC3C (Main_Game_Loop's rows, Demo_Mode) to the demo's first $AE29 on every case: bytes, text cells, T and R exactly",
        demoEntry(fx, P.demoIn), [0, '']);
  const outAt = (c, x) => { for (const [a, h] of c.out) if (a <= x && x < a + h.length / 2) return parseInt(h.substr((x - a) * 2, 2), 16); };
  check('...and the cases draw each demo rank 7-10 for both sides ($AA94, Also_Rank $AA80), R at the JR 94 played, 95, 96, 97 and $7F derived',
        [[0xAA94, 0xAA80].map(x => [...new Set(fx.cases.map(c => outAt(c, x)))].sort()), fx.cases.map(c => c.r)],
        [[[10, 7, 8, 9], [10, 7, 8, 9]], [94, 95, 96, 97, 127]]);
}

/* ---- Main_Game_Loop's dispatch $AC27 after the demo's RET ------------
   python tools/callio.py --capture --state p1 --call 0xAC27 0xAE29
   (port.json demo_ac27: the demo's fourth stage over, Num_Players 0, the
   JR Z to $AC09 and a new demo).  gameDispatch as demoIn's gate. */
{
  const fx = P.assets.demo_ac27;
  check("gameDispatch matches the real $AC27 (Num_Players 0: JR Z, a new demo) to its first $AE29: bytes, text cells, T and R exactly",
        demoEntry(fx, (m, r) => { const d = P.gameDispatch(m, r); return d.at === 0xAE29 ? d.t : -1; }), [0, '']);
}
/* python tools/callio.py --capture --state p1 --call 0xAC27 0xAE29 --keys 2
   (port.json start2_ac27: the demo quit by key 2, Num_Players 2).
   gameDispatch to $ADB1, then Intro_Music, start2Rest, stage2 and roundIn
   as the live engine runs them: start_ac27's gate. */
{
  const fx = P.assets.start2_ac27;
  const outs = [], all = [];
  check("gameDispatch, Num_Players 2 (Start_2UP_Game $AD9C, its tune, New_Round, Reset_Score), on through the stage $ADBA to the game's first $AE29 matches the real $AC27: bytes, text cells, T and R exactly",
        demoEntry(fx, (m, r) => {
          const d = P.gameDispatch(m, r);
          if (d.at !== 0xADB1) return -1;
          outs.length = 0;
          const u = P.introMusic(m, outs, 0);
          all.push(JSON.stringify(outs.map(([t, v]) => [t + d.t, v])));
          return d.t + u + P.start2Rest(m) + P.stage2(m) + P.roundIn(m, r);
        }), [0, '']);
  check("...and the tune's $FE writes at their T from $AC27, on every case",
        [all.length, fx.cases.every((c, i) => all[i] === JSON.stringify(c.outs || [])), fx.cases.map(c => (c.outs || []).length)],
        [fx.cases.length, true, [3422]]);
}
/* python tools/callio.py --capture --state p1 --call 0xAC27 0xAE29 --keys 1
   (port.json start_ac27: the demo quit by key 1, Num_Players 1).
   gameDispatch to $AC5F, then setupMusic, setupRest and roundIn as the live
   engine runs them: demoIn's gate, and the tune's $FE writes at their T. */
{
  const fx = P.assets.start_ac27;
  const outs = [], all = [];
  check("gameDispatch, Num_Players 1 (Start_1UP_Game $AC3E, Reset_Score), on through $AC5F's setup to the game's first $AE29 matches the real $AC27: bytes, text cells, T and R exactly",
        demoEntry(fx, (m, r) => {
          const d = P.gameDispatch(m, r);
          if (d.at !== 0xAC5F) return -1;
          outs.length = 0;
          const s = P.setupMusic(m, outs);
          all.push(JSON.stringify(outs.map(([u, v]) => [u + d.t, v])));
          return d.t + s.t + P.setupRest(m, s.stage) + P.roundIn(m, r);
        }), [0, '']);
  check("...and the tune's $FE writes at their T from $AC27, on every case",
        [all.length, fx.cases.every((c, i) => all[i] === JSON.stringify(c.outs || [])), fx.cases.map(c => (c.outs || []).length)],
        [fx.cases.length, true, [3422]]);
}

/* ---- round_loop $AE26, the live loop, against the machine pass by pass --
   House rule 2: python tools/sample.py --state p1 --at 0xAE29 --script
   (keys BY PASS) --json build/live_p1.json samples the machine at every
   visit to $AE29; the engine starts from the first visit's RAM, R and SP and
   runs roundPass with the same keys on the same pass.  Every row: the named
   bytes, R, and FNV hashes of $5C00-$FFFF and the display file (the timer
   cells left out: D5).  The first differing row names the bug.  T is
   compared apart: the engine charges D4's means, the machine is contended.
   Run over three fixtures: live (the script's second point wins for P2,
   the pose $AEB2, out to $ACA6 lost, the high score checked
   to $AC3C, sampled there), live_p1w (P1's count poked to 4: the
   first point wins for P1, the pose $AE8E, the time bonus $AD6E, out won)
   and live_time (Time poked to 1: no point, the round end $AE67 and its
   loop $AD0B, the draw at $AD44 and both posing again at $AD0B, out at
   $AC5F to the next bout); and live_1up (live's, with key 1 pressed in the
   demo: its quit to $ABB9, $AC27 with Num_Players 1, the 1UP game's tune
   and setup to the CALL $AD18, sampled there, and the game played on). */
function liveGate(L, who, how){
  const fnv = (m, lo, hi) => { let h = 0x811C9DC5;
    for (let a = lo; a <= hi; a++){
      if (L.skip.some(([s, e]) => s <= a && a <= e)) continue;
      h = Math.imul(h ^ m[a], 0x01000193) >>> 0;
    } return h; };
  const plan = [];
  for (const seg of (L.script || '').split(',')){
    const [n, keys] = seg.split(':');
    for (let i = 0; i < +n; i++) plan.push(keys ? keys.split('+') : []);
  }
  const row = (m, r) => [...L.vars.map(([, a, n]) => n > 1
      ? Buffer.from(m.subarray(a, a + n)).toString('hex').toUpperCase()
      : m[a].toString(16).toUpperCase().padStart(2, '0')), r, ...L.hash.map(([lo, hi]) => fnv(m, lo, hi))];
  const want = r => [...r.v, r.r, ...r.h];
  const g = new P.Fist(L.start), kb = new S.Keyboard();
  let first = '', exit = null, ratio = [];
  /* the menu's keys by port read from $8C54 (sample.py --reads), through
     the engine's hook: the nth read of the menu sees the nth entry */
  const rplan = [];
  for (const seg of (L.reads || '').split(',').filter(Boolean)){
    const [n, keys] = seg.split(':');
    for (let i = 0; i < +n; i++) rplan.push(keys ? keys.split('+') : []);
  }
  let menuReads = 0, menuSteps = 0;
  const menuPaid = [];
  if (L.reads) g.menuRead = n => { kb.releaseAll(); for (const x of rplan[n] || []) kb.press(x); menuReads = n + 1; };
  /* boot: the start is the tape's hand-over at $8800 (sample.py
     --start-here), and row 0 the demo's first $AE29: bootPass runs to it */
  const bootT = how === 'boot' ? g.pass(kb) / L.rows[0].t : 1, bootBorder = g.border;
  /* ...its text rows in the font (D5): the display checked below them, $4800- */
  const blind0 = (got, w) => { if (how === 'boot'){ const d = L.vars.length + 1 + L.hash.findIndex(([lo]) => lo === 0x4000); got[d] = w[d]; } return got; };
  check(`${who}: the engine ${how === 'boot' ? 'reaches' : 'starts from'} the first row the machine sampled`, blind0(row(g.m, g.r), want(L.rows[0])), want(L.rows[0]));
  /* the machine's samples in order: each row's --also rows (sample.py: the
     victory pose's loop top $AEB2) before it */
  const seq = [], setupAt = r => r.m.includes(0xACA6) || r.m.includes(0xAC27);
  /* $AD18 is sampled after the setup (a bout's end, or a game's start at
     $AC27) and inside every point played on
     ($AD42 JR Z): the second is mid-pass in pointPath, so dropped, its T
     carried into the sample after it; the same for the 2UP game's $AE14,
     kept after its start ($AC27) and time up ($ADE2) */
  const subsOf = r => (r.s || []).filter(x => x.pc === 0xAD18 ? setupAt(r)
    : x.pc === 0xAE14 ? r.m.includes(0xADE2) || r.m.includes(0xAC27) : true);   // the 2UP's: its next bouts and its start, not its points
  const IN = how === 'start2' ? 0xAE14 : 0xAD18;   // the setup's CALL: $AD18, the 2UP game's $AE14
  L.rows.slice(1).forEach((r, i) => {
    let carry = 0;
    (r.s || []).forEach((x, j) => {
      if (!subsOf(r).includes(x)){ carry += x.t; return; }
      seq.push({ ...x, t: x.t + carry, p: i + 1, sub: true, j }); carry = 0;
    });
    seq.push({ ...r, t: r.t + carry, pc: L.at, p: i + 1 });
  });
  /* the machine's way out: the first row whose marks (sample.py --mark)
     show a return from $AE26 to one of its three callers, or $AE67 */
  const RETS = [0xABCB, 0xAD1B, 0xAE17];
  const marked = L.rows.map((r, i) => r.m.some(x => RETS.includes(x) || x === 0xAE67) ? i : -1).filter(i => i >= 0);
  /* a point ($AD1B) is played through by pointPath; the winning point
     takes the pose and, for P1, the time bonus, and $ACA6 is reached with
     A = 0 (P2 won: the 1UP bout lost) or 1 (P1 won); time up ($AE67) with
     the counts and tallies level is the draw, $81 there */
  const bout = marked.find(i => L.rows[i].m.includes(0xACA6));   // the bout's end; rows after it are the next bout's
  const out = bout ?? marked[marked.length - 1] ?? -1;
  const outKind = out < 0 ? null : L.rows[out].m.includes(0xACA6) ? how
    : L.rows[out].m.includes(0xAE67) ? 'end' : 'point';
  const pcNow = () => g.exit ? g.exit.at : g.enter ? IN : g.demoAt ? 0xAC3C : g.demoNext !== null ? 0xABB9 : g.bonus ? 0xAD6E : g.both ? 0xAD0B : g.win === 0xAA00 ? 0xAE8E : g.win ? 0xAEB2 : L.at;
  /* won and drawn bouts go on through the setup's tune (charged in the
     pass that reaches $AC5F) and its rest (a pass of its own) to the CALL
     $AD18, sampled there; with a new stage the text rows are in the font
     (D5), so the display is checked by the hash below them, $4800-.  A
     pass of its own then enters the next bout's round_loop at $AE29, and
     the gate follows that bout to the fixture's last row */
  const disp = L.hash.findIndex(([lo, hi]) => lo === 0x4000);
  let at = -1, k = 0, round = 0, subs = 0, setupT = 0, setupM = 0, edges = -1, logN = 0, tail = -1, enters = [], enterT = [], blind = how === 'boot', demoP = -1, demoT = 0, stageAt = [], stageT = [], setups = [];
  for (; k < seq.length; k++){
    if (!g.win && !g.bonus && !g.both && !g.setup && !g.enter && !g.demoAt && g.demoNext === null){ kb.releaseAll(); for (const x of plan[round] || []) kb.press(x); round++; }
    logN = g.sound.log.length;
    let cost;
    try {                                          // a pass that throws (the menu's replay guard) is this row's failure
      cost = g.pass(kb);
      if (g.menu){                                 // the menu up: run it step by step, as the frames would
        while (g.menu){ cost += g.pass(kb); menuSteps++; }
        menuPaid.push([seq[k].p, cost / seq[k].t]);
      }
    } catch (e){ first = `row ${seq[k].p}: the pass threw: ${e.message}`; break; }
    const textUp = menuPaid.length && menuPaid[menuPaid.length - 1][0] === seq[k].p && seq[k].sub;
    if (g.setup){
      const t1 = g.simT, e = g.sound.log.slice(logN).filter(([f]) => f * P.T_FRAME <= t1);
      edges = e.length; if (edges) tail = t1 - e[edges - 1][0] * P.T_FRAME;
      cost += g.pass(kb); setupT = cost; setupM = seq[k].t;
      setups.push([seq[k].p, cost / seq[k].t, edges]);
    }
    if (g.exit && g.exit.at !== seq[k].pc){ exit = g.exit.exit; at = seq[k].p; break; }
    if ((g.win || g.bonus || g.both) && seq[k].p <= out) subs++;
    if (g.enter) enters.push(seq[k].p);
    if (g.demo && demoP < 0){ demoP = seq[k].p; demoT = cost / seq[k].t; }
    else if (seq[k - 1] && seq[k - 1].pc === IN) enterT.push(cost / seq[k].t);
    if (seq[k - 1] && seq[k - 1].pc === 0xABB9){ stageAt.push(seq[k].p); stageT.push(cost / seq[k].t); }
    ratio.push(cost / seq[k].t);
    const got = [pcNow(), ...row(g.m, g.r)], w = [seq[k].pc, ...want(seq[k])];
    if (g.stage) blind = true;                     // the new stage's text rows stay on screen
    if (blind) got[1 + L.vars.length + 1 + disp] = w[1 + L.vars.length + 1 + disp];
    /* the menu's last screen, still up at $ABB9, is text in the font (D5):
       the display unchecked there (the menu's screens are gated glyph by
       glyph on callio_97cb's cases); the new demo redraws it */
    if (textUp) L.hash.forEach(([lo], i) => { if (lo >= 0x4000 && lo < 0x5B00) got[1 + L.vars.length + 1 + i] = w[1 + L.vars.length + 1 + i]; });
    if (JSON.stringify(got) !== JSON.stringify(w)){
      const names = ['PC', ...L.vars.map(v => v[0]), 'R', ...L.hash.map(([lo, hi]) => `hash $${lo.toString(16)}-$${hi.toString(16)}`)];
      const j = got.findIndex((x, i) => x !== w[i]);
      first = `${seq[k].sub ? `sub-row ${seq[k].j} ($${seq[k].pc.toString(16).toUpperCase()}) before row` : 'row'} ${seq[k].p}: ${names[j]} ${got[j]} want ${w[j]}`; break;
    }
    if (g.exit){ exit = g.exit.exit; at = seq[k].p; break; }   // stopped where the machine was sampled: the row compared first
  }
  const what = { menu: ' and the victory pose', boot: ' and the demo', won: ', the victory pose and the time bonus', lost: ' and the victory pose', start: ' and the victory pose', start2: ' and the victory pose', draw: ', the round end and the draw' }[how];
  check(`${who}: roundPass${what} follow the machine sample for sample over keyed 1P play until the bout ends`, first, '');
  /* lost: the high score checked, sampled at $AC3C; Main_Game_Loop's rows
     and Demo_Mode (demoIn, a pass of its own) into the demo's $AE29, the
     row of the bout's end; the demo played on, its points by demoPoint
     (the machine's returns from $AE26 to $ABCB), its poses to $ABB9 and
     on into the next stage by demoOn, to the fixture's last row */
  const demoRet = L.rows.map((r, i) => i > out && r.m.includes(0xABCB) ? i : -1).filter(i => i >= 0);
  const startAt = L.rows.findIndex((r, i) => i > out && r.m.includes(0xAC27));
  if (how === 'start'){
    /* the demo quit by key 1 (sample.py's script: one pass), RET M to
       $ABB9 and out to $AC27, Num_Players 1: gameDispatch's 1UP start and
       the tune in that pass, the setup's rest to the CALL $AD18 (sampled
       there), roundIn into the game's first $AE29; the game played on
       with no keys, P2 winning it back into the demo */
    const lostAt = L.rows.findIndex((r, i) => i > startAt && r.m.includes(0xACA6));
    const wantIn = L.rows.map((r, i) => subsOf(r).some(x => x.pc === 0xAD18) ? i : -1).filter(i => i >= 0);
    check(`${who}: ...and leave the bout into the demo, quit it by key 1 to $ABB9 and $AC27 (row ${startAt}), start the 1UP game there through its tune and setup to the CALL $AD18 and on into its first $AE29, and play the game on, lost to P2 back into the demo (row ${lostAt}), to the fixture's last row with no way out`,
          [demoP, at, exit, k, startAt > out, wantIn[0] === startAt, enters[0] === startAt, L.rows[startAt].m.includes(0xABCB), lostAt > startAt, L.rows[lostAt].m.includes(0xAC09), g.demo],
          [out, -1, null, seq.length, true, true, true, true, true, true, true]);
    /* the start's pass is mostly the tune and the scenery, as the won
       bout's (D4's SETUP_K and SCEN_K, measured there) */
    check(`${who}: ...and the pass from $ABB9 through the start's tune and setup is charged within 0.05% of the contended machine, the tune's edges inside it`,
          [Math.abs(setupT / setupM - 1) < 0.0005, edges], [true, 3422]);
    /* roundIn: 8020 T uncontended, gated exact; the machine 8152 here
       (1.6% over), 8080 and 8020 after the won and drawn bouts */
    check(`${who}: ...and the pass from the CALL $AD18 into the game's first $AE29 is charged within 2% of the contended machine`,
          enterT.map(x => Math.abs(x - 1) < 0.02), [true]);
  }
  if (how === 'menu'){
    /* the demo's key 0 (sample.py's script: one pass) runs the options menu
       $8C54 inside that pass, DI: the engine suspends the pass there
       (MenuSuspend) and runs the menu a step at a time, each step to its
       next port read or past a Configs_Delay, as the live frames would;
       then the whole pass again, its reads replayed.  The menu's keys come
       by read (sample.py --reads): P1, 4 (reconfigure), nine keys.  At its
       RET, $80: RET M to $ABB9, Num_Players still 0, out to $AC27 and a
       new demo by gameDispatch, played on to the fixture's last row */
    const want = [...[0xFB01, 0xFB02, 0xDF01, 0xBF02, 0xFD01, 0xFE02, 0xDF02, 0xF701, 0x7F01].flatMap(v => [v & 0xFF, v >> 8])];
    check(`${who}: ...and leave the bout into the demo, open the options menu by key 0 (row ${startAt}), run it across ${menuSteps} steps with its keys by port read (${L.reads_used} reads), P1's keyboard reconfigured, out by $ABB9 to $AC27 into a new demo, played on to the fixture's last row with no way out`,
          [demoP, at, exit, k, startAt > out, menuPaid.map(([p]) => p), menuReads, menuSteps > 100, L.rows[startAt].m.includes(0xABCB), (L.rows[startAt].s || []).map(x => x.pc), g.demo, g.menu,
           [...g.m.subarray(0x8BD2, 0x8BD4)], [...g.m.subarray(0x8BD4, 0x8BD4 + 18)]],
          [out, -1, null, seq.length, true, [startAt], L.reads_used, true, true, [0xABB9], true, null,
           [0xD4, 0x8B], want]);
    /* the menu's pass is the delays' (uncontended code above $8000) and
       the screens' (the clears and prints into contended RAM, at the
       listing's T) */
    check(`${who}: ...and the menu's pass is charged within 0.5% of the contended machine, its steps charged to the clock as they ran`,
          menuPaid.map(([, x]) => Math.abs(x - 1) < 0.005 ? '' : `ratio ${x}`), ['']);
    /* the page's own frames: the script to key 0's pass, then step() as
       the loop calls it, no keys held -- the menu stays up, a frame's T
       spent per frame (it polls, DI), the keyboard read live; E, then
       one frame: its RET, the pass replayed, on to $ABB9 */
    const f = new P.Fist(L.start), kf = new S.Keyboard();
    for (let n = 0; n <= startAt - 1 && !f.menu; ){
      if (!f.win && !f.bonus && !f.both && !f.setup && !f.enter && !f.demoAt && f.demoNext === null){ kf.releaseAll(); for (const x of plan[n] || []) kf.press(x); n++; }
      f.pass(kf);
    }
    const up = !!f.menu, sim0 = f.simT, passes0 = f.passes;
    kf.releaseAll();
    for (let i = 0; i < 100; i++) f.step(kf);
    const held = [!!f.menu, Math.abs((f.simT - sim0) / P.T_FRAME - 100) <= 1, f.passes === passes0];
    kf.press('E'); f.step(kf); kf.releaseAll();
    check(`${who}: ...and on the page's frames the menu opened by key 0 stays up over 100 frames with no key (a frame's T each, no pass completed), and E closes it in a frame, out to $ABB9`,
          [up, ...held, f.menu, f.demoNext === 0x80 || f.passes > passes0], [true, true, true, true, null, true]);
  }
  if (how === 'start2'){
    /* the demo quit by key 2, out to $AC27, Num_Players 2: gameDispatch's
       2UP start to its tune, the tune in that pass, start2Rest and stage2
       to the CALL $AE14 (sampled there), roundIn into the game's first
       $AE29.  P1 scores a point: the RET to $AE17, twoOn back into $AE29 in
       the pass.  Time up three times: $AE67's loop, the RET to $AE17, out
       to $ADE2, the stage step and the tune in that pass, twoNext and
       stage2 to the CALL $AE14 (sampled there), roundIn the pass after.
       The fourth, rank 4: twoEnd's high score and P1's pose ($AE8E) in the
       pass after the tune, then out by $AE12 to $AC34, demoIn in the pose's
       last pass, and the demo played on to the fixture's last row */
    const wantIn = L.rows.map((r, i) => subsOf(r).some(x => x.pc === 0xAE14) ? i : -1).filter(i => i >= 0);
    const point = L.rows.map((r, i) => i > startAt && r.m.includes(0xAE17) && !r.m.includes(0xAE67) ? i : -1).filter(i => i >= 0);
    const ups = L.rows.map((r, i) => r.m.includes(0xADE2) ? i : -1).filter(i => i >= 0);
    const endAt = L.rows.findIndex(r => r.m.includes(0xADF3)), endSub = (L.rows[endAt] || {}).s || [];
    const back = L.rows.map((r, i) => i > endAt && r.m.includes(0xABCB) ? i : -1).filter(i => i >= 0);
    check(`${who}: ...and leave the bout into the demo, quit it by key 2 to $ABB9 and $AC27 (row ${startAt}), start the 2UP game there to the CALL $AE14 and its first $AE29, play P1's point on through $AE17 (row ${point}), time up through $ADE2 into the next bout by the CALL $AE14 (rows ${ups.slice(0, -1)}), at rank 4 the game's end, P1's pose and out by $AC34 into the demo (row ${endAt}), the demo played on (returns to $ABCB on rows ${back}) to the fixture's last row with no way out`,
          [demoP, at, exit, k, startAt > out, enters, L.rows[startAt].m.includes(0xABCB), point, ups, ups[ups.length - 1] === endAt,
           [0xAC34, 0xAC09].map(x => L.rows[endAt].m.includes(x)), endSub.filter(x => x.pc === 0xAE8E).length, back.length > 0, g.two, g.demo],
          [out, -1, null, seq.length, true, wantIn, true, [599], [880, 1301, 1722, 2143], true,
           [true, true], 66, true, false, true]);
    /* the passes with a tune: the start's (Start_2UP_Game's head to $ADB1)
       and each time up's (the round end's last loop pass, the delays, twoOn
       and the stage step), at SETUP_K.tune; the setup's rest, mostly the
       scenery, at SETUP_K.rest and SCEN_K (measured on the 1UP's) -- or,
       at the game's end, twoEnd to the pose's loop top */
    check(`${who}: ...and the passes from $ABB9 and from each round end's last through the tune and setup are charged within 0.05% of the contended machine, the tune's edges inside them`,
          setups.map(([p, x, e]) => [p, Math.abs(x - 1) < 0.0005, e]),
          [startAt, ...ups].map(p => [p, true, 3422]));
    check(`${who}: ...and the passes from the CALL $AE14 into each bout's first $AE29 are charged within 2% of the contended machine`,
          enterT.map(x => Math.abs(x - 1) < 0.02), wantIn.map(() => true));
    /* the pose's last pass, $AE12 out to $AC34, and demoIn (charged as
       demoPass: mostly the scenery).  0.5%: 0.37% under here (1040240 T
       charged, 1044135 on the machine); the pose's own passes are 0.988 to
       1.008 of the machine's one by one, mean 0.998 (the engine's passes
       against row 2143's $AE8E sub-rows, unit AE17), and the same demoIn path took 771382 and
       768438 T on the machine (the boot gate's frame-phase spread) */
    const endK = seq.findIndex(x => x.p === endAt && !x.sub);
    check(`${who}: ...and the pass out of the game's end into the demo's $AE29 is charged within 0.5% of the contended machine`,
          Math.abs(ratio[endK] - 1) < 0.005 ? '' : `ratio ${ratio[endK]}`, '');
  }
  if (how === 'lost'){
    check(`${who}: ...and leave the bout on the sample the machine left (P2 wins, out to $ACA6 lost, the high score checked at $AC3C), into the demo by Main_Game_Loop and Demo_Mode on that row, and play the demo through its points (returns to $ABCB on rows ${demoRet.join(', ')}) to the fixture's last row with no way out`,
          [demoP, at, exit, k, demoRet.length > 0, g.demo, g.demoAt, g.win, g.bonus, g.both, g.setup, L.rows[out].m.includes(0xAC09)],
          [out, -1, null, seq.length, true, true, false, 0, false, null, null, true]);
    /* the demo's pass is mostly the scenery: 640994 T uncontended
       (build/callio_ac3c.json), 768438 on the machine */
    check(`${who}: ...and the pass from $AC3C into the demo's $AE29 is charged within 0.2% of the contended machine`, Math.abs(demoT - 1) < 0.002, true);
    /* the machine's samples at $ABB9: P2's pose (row 801) and P1's (1407,
       2142), each on into the next stage (demoOn, a pass of its own, mostly
       the scenery: charged as demoPass); at 2543 the demo's fourth, the RET
       to $AC27 and a new demo (gameDispatch), whose first pose is 2830.
       0.7%: the machine itself takes 744631 and 740536 T for the identical
       stage-3 pass of rows 801 and 2830 (614767 T uncontended, the same PCs:
       python tools/callio.py --capture --call 0xABB9 0xAE29,0xAC27 --frames
       15000), the contention phase's spread, which D4's means cannot follow;
       the first demo's stage rows, before it, are held to 0.2% */
    const wantStage = L.rows.map((r, i) => (r.s || []).some(x => x.pc === 0xABB9) ? i : -1).filter(i => i >= 0);
    const newDemo = wantStage.find(i => L.rows[i].m.includes(0xAC27)) + 1;
    const poses = wantStage.map(i => [...new Set(L.rows[i].s.map(x => x.pc))].filter(x => x !== 0xABB9));
    check(`${who}: ...and leave the demo's bouts by both poses (sampled at $ABB9 on rows ${wantStage.join(', ')}) on into the next demo stage at $AE29 (at the fourth through $AC27 into a new demo), the stage pass charged within 0.2% of the contended machine (0.7% in the new demo)`,
          [stageAt, poses, stageT.map((x, j) => Math.abs(x - 1) < (wantStage[j] < newDemo ? 0.002 : 0.007)), wantStage.map(i => L.rows[i].m.includes(0xAC27))],
          [wantStage, [[0xAEB2], [0xAE8E], [0xAE8E], [0xAE8E], [0xAEB2]], wantStage.map(() => true), [false, false, false, true, false]]);
  }
  else if (how === 'boot'){
    /* Game_Start, Main_Game_Loop and Demo_Mode's first stage are one pass:
       999601 T on the machine from $8800, mostly the scenery (charged as
       demoPass, D4) and the $2100-byte LDIR at $9C43 (its own measured
       charge).  0.5%: the machine takes 771382 T from $9C45 to $AE29 here
       and 768438 for the same path from $AC3C after the lost bout (0.38%
       apart: frame phase, which D4's means cannot follow) */
    const wantStage = L.rows.map((r, i) => (r.s || []).some(x => x.pc === 0xABB9) ? i : -1).filter(i => i >= 0);
    check(`${who}: ...from $8800 through Game_Start (border 5), Main_Game_Loop and Demo_Mode into the demo's first $AE29 (row 0), the demo played on through its stages (sampled at $ABB9 on rows ${wantStage.join(', ')}) to the fixture's last row with no way out`,
          [at, exit, k, g.demo, g.boot, bootBorder, wantStage.length > 0, stageAt],
          [-1, null, seq.length, true, false, 5, true, wantStage]);
    check(`${who}: ...and the boot pass is charged within 0.5% of the contended machine`, Math.abs(bootT - 1) < 0.005 ? '' : `ratio ${bootT.toFixed(5)}`, '');
  }
  else if (how !== 'start' && how !== 'start2' && how !== 'menu'){
    /* the machine's samples at the CALL $AD18: the setup's ends */
    const wantIn = L.rows.map((r, i) => subsOf(r).some(x => x.pc === 0xAD18) ? i : -1).filter(i => i >= 0);
    check(`${who}: ...and ${how === 'draw' ? 'out at $AC5F drawn' : 'P1 wins, out to $ACA6 won, on to $AC5F'}, the setup to the CALL $AD18 and on into the next bout at $AE29, to the fixture's last row with no way out (CALL $AD18 sampled on rows ${wantIn.join(', ')})`,
          [at, exit, k, enters, enters[0] === out, g.win, g.bonus, g.both, g.setup, g.enter],
          [-1, null, seq.length, wantIn, true, 0, false, null, null, false]);
  }
  const sub = ((L.rows[out] || {}).s || []).filter(x => x.pc !== 0xAD18 && x.pc !== 0xAC3C);
  const end = how === 'draw' ? sub.findIndex(x => x.t > 1e6) : 0;   // the round end's loop: to the delays
  if (how !== 'boot') check(`${who}: ...which the script reaches ${how === 'draw' ? 'by the clock, no point played, the round end loop then' : 'through points played on, the way out the last, after'} 66 passes of the pose${how === 'won' ? ' and a pass a second' : ''}`,
        [marked.filter(i => i <= out).length, outKind, subs, sub.filter(x => x.pc !== 0xAD6E).length - end, sub.filter(x => x.pc === 0xAD6E).length > 1, end],
        { won: [1, 'won', sub.length, 66, true, 0], lost: [2, 'lost', sub.length, 66, false, 0], start: [2, 'start', sub.length, 66, false, 0], menu: [2, 'menu', sub.length, 66, false, 0], start2: [2, 'start2', sub.length, 66, false, 0], draw: [1, 'draw', sub.length, 66, false, 3] }[how]);
  if (how === 'won' || how === 'draw')
    /* the draw's segment is mostly the pose's last pass, at the D4 means:
       0.16% off; the won one is mostly the tune and the scenery: 0.007%.
       The tune ends on a rest after its last write: 76022 T uncontended
       (build/callio_ac5f.json case 0: T 12260038 at the RET, 12184016) */
    check(`${who}: ...and the pass to $AC5F with ${how === 'won' ? 'the tune (a new stage: the scenery after)' : 'no tune (no new stage)'} and the setup's rest are charged within ${how === 'won' ? '0.05' : '0.2'}% of the contended machine, the tune's edges inside the first, its last at the end of the pass`,
          [Math.abs(setupT / setupM - 1) < (how === 'won' ? 0.0005 : 0.002), edges, how === 'won' ? tail > 70000 && tail < 80000 : tail], [true, how === 'won' ? 3422 : 0, how === 'won' ? true : -1]);
  if (how === 'won' || how === 'draw')
    /* roundIn is pointPath's tail, its uncontended T gated exact there
       (build/callio_ad1b.json); the machine's $AD18 to $AE29: 8080 T (P1,
       0.74% over) and 8020 (time, equal) */
    check(`${who}: ...and the pass from the CALL $AD18 into the next bout's $AE29 is charged within 1% of the contended machine`,
          enterT.map(x => Math.abs(x - 1) < 0.01), [true]);
  const sum = ratio.reduce((a, b) => a + b, 0) / ratio.length, worst = Math.max(...ratio.map(x => Math.abs(x - 1)));
  checkTrue(`${who}: the 7.2 charge (uncontended T, $BF13 at the D4 means) is within 0.5% of the contended machine over the round${{ won: ', the pose and the bonus', lost: ' and the pose', start: ', the pose, the demo and the game started', start2: ', the pose, the demo and the 2UP game to time up', menu: ', the pose, the demo, the options menu and the new demo', boot: ' of the demo from the boot', draw: ', the round end and the draw' }[how]}`,
            Math.abs(sum - 1) < 0.005, `mean ${sum.toFixed(5)}, worst pass ${(worst * 100).toFixed(2)}% off`);
}
liveGate(P.assets.live, 'P2', 'lost');
liveGate(P.assets.live_p1w, 'P1', 'won');
liveGate(P.assets.live_time, 'time', 'draw');
liveGate(P.assets.live_1up, '1UP', 'start');
liveGate(P.assets.live_2up, '2UP', 'start2');
liveGate(P.assets.live_menu, 'menu', 'menu');
liveGate(P.assets.live_boot, 'boot', 'boot');

/* bouts at dans 2-8, from the user's snapshots (in the new stage's tune
   after a won bout; optional fixtures, absent from a fresh clone): the
   machine's samples followed row for row as liveGate's, through whatever
   the bout reaches in 400 passes -- points, P2's win into the demo (dan
   6) -- and the 7.2 charge within 0.5% of the contended machine.  The AI
   at Also_Rank 2-8, never sampled from the tape's state */
function followGate(L, who){
  const fnv = (m, lo, hi) => { let h = 0x811C9DC5;
    for (let a = lo; a <= hi; a++){
      if (L.skip.some(([s, e]) => s <= a && a <= e)) continue;
      h = Math.imul(h ^ m[a], 0x01000193) >>> 0;
    } return h; };
  const plan = [];
  for (const seg of (L.script || '').split(',')){
    const [n, keys] = seg.split(':');
    for (let i = 0; i < +n; i++) plan.push(keys ? keys.split('+') : []);
  }
  const row = (m, r) => [...L.vars.map(([, a, n]) => n > 1
      ? Buffer.from(m.subarray(a, a + n)).toString('hex').toUpperCase()
      : m[a].toString(16).toUpperCase().padStart(2, '0')), r, ...L.hash.map(([lo, hi]) => fnv(m, lo, hi))];
  const want = r => [...r.v, r.r, ...r.h];
  const names = ['PC', ...L.vars.map(v => v[0]), 'R', ...L.hash.map(([lo, hi]) => `hash $${lo.toString(16)}-$${hi.toString(16)}`)];
  const seq = [];                                  // as liveGate's: $AD18 kept only after the setup
  L.rows.slice(1).forEach((r, i) => {
    let carry = 0;
    (r.s || []).forEach(x => {
      if (x.pc === 0xAD18 && !r.m.includes(0xACA6)){ carry += x.t; return; }
      seq.push({ ...x, t: x.t + carry, p: i + 1, sub: true }); carry = 0;
    });
    seq.push({ ...r, t: r.t + carry, pc: L.at, p: i + 1 });
  });
  const g = new P.Fist(L.start), kb = new S.Keyboard();
  const pcNow = () => g.exit ? g.exit.at : g.enter ? 0xAD18 : g.demoAt ? 0xAC3C : g.demoNext !== null ? 0xABB9 : g.bonus ? 0xAD6E : g.both ? 0xAD0B : g.win === 0xAA00 ? 0xAE8E : g.win ? 0xAEB2 : L.at;
  const disp = L.hash.findIndex(([lo]) => lo === 0x4000);
  let first = '', k = 0, round = 0, blind = false, sum = 0;
  check(`${who}: the engine starts from the first row the machine sampled`, row(g.m, g.r), want(L.rows[0]));
  for (; k < seq.length; k++){
    if (!g.win && !g.bonus && !g.both && !g.setup && !g.enter && !g.demoAt && g.demoNext === null){ kb.releaseAll(); for (const x of plan[round] || []) kb.press(x); round++; }
    let cost = g.pass(kb);
    if (g.setup) cost += g.pass(kb);
    if (g.exit && g.exit.at !== seq[k].pc){ first = `row ${seq[k].p}: the engine stopped (${g.exit.exit} at $${g.exit.at.toString(16)})`; break; }
    sum += cost / seq[k].t;
    const got = [pcNow(), ...row(g.m, g.r)], w = [seq[k].pc, ...want(seq[k])];
    if (g.stage) blind = true;                     // a new stage's text rows stay in the font (D5)
    if (blind) got[1 + L.vars.length + 1 + disp] = w[1 + L.vars.length + 1 + disp];
    if (JSON.stringify(got) !== JSON.stringify(w)){
      const j = got.findIndex((x, i) => x !== w[i]);
      first = `${seq[k].sub ? `sub-row ($${seq[k].pc.toString(16).toUpperCase()}) of ` : ''}row ${seq[k].p}: ${names[j]} ${got[j]} want ${w[j]}`; break;
    }
  }
  const pts = L.rows.filter(r => r.m.includes(0xAD1B)).length;
  check(`${who}: the engine follows the machine sample for sample over keyed 1P play to the fixture's last row (${pts} point(s) played${L.rows.some(r => r.m.includes(0xAC09)) ? ', P2 wins into the demo' : ''})`,
        [first, k], ['', seq.length]);
  checkTrue(`${who}: ...and the 7.2 charge is within 0.5% of the contended machine`, Math.abs(sum / k - 1) < 0.005, `mean ${(sum / k).toFixed(5)}`);
}
for (let n = 2; n <= 8; n++){
  const L = P.assets[`live_dan${n}`];
  if (L) followGate(L, `dan ${n}`);
  else console.log(`  note  live_dan${n} absent (the user's snapshot, not in the repository): its gate not run`);
}

/* the demo's ways on that live play has not reached yet (its bouts so far
   end by a pose): time up and the quit to $ABB9 with A = 0 / negative, the
   round end into $ACF0's loop at endStart's T.  Wiring only: demoPoint and
   demoOn are each gated against the machine above */
{
  const ways = ['time', 'quit', 'end'].map(e => {
    const g = new P.Fist(P.assets.live.start), res = { exit: e, r: 0 };
    g.demo = true;
    const t = g.demoOut(res);
    P.M1.m1 = 0;
    return [res.exit, g.demoNext, g.both, t === (e === 'end' ? P.endStart(new Uint8Array(0x10000)) : 0)];
  });
  check("Fist.demoOut: the demo's time up and quit go to $ABB9 (A = 0, $80), its round end into $ACF0's loop",
        ways, [[null, 0, null, true], [null, 0x80, null, true], [null, null, 'end', true]]);
}

rig.done();
