/* rig.js -- run the BUILT artifact under Node with a stubbed DOM.
 *
 * Manual phase 14: "Load THE BUILT ARTIFACT, not your source modules, so the
 * build step is under test."  And: "A CANVAS STUB THAT RECORDS DRAW CALLS WHEN
 * ARMED ... for anything conditional, RENDER TWICE with only the flag changed
 * and DIFF THE TWO DRAW LISTS."
 *
 *   const rig = require('./rig');
 *   const { S, P, sandbox } = rig.loadBuilt();     // S = __SPEC__, P = __PORT__
 *   rig.check(name, got, want); rig.checkTrue(name, cond, detail);
 *   rig.done();                                      // prints N/N, sets exit code
 *
 * What the stub deliberately does NOT provide: a real AudioContext (tests
 * install their own mocks on `sandbox` and remove them), Blob/URL/btoa (so the
 * worklet gate's absence path is what runs by default), a timer that fires
 * rAF (it is CAPTURED -- tests drive the loop by calling rig.raf()).
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);

let checks = 0, failures = 0;
function check(name, got, want) {
  checks++;
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.log(`  FAIL  ${name}\n        got  ${JSON.stringify(got)}\n        want ${JSON.stringify(want)}`); }
  else console.log(`  ok    ${name}`);
}
function checkTrue(name, cond, detail) {
  checks++;
  if (cond) console.log(`  ok    ${name}`);
  else { failures++; console.log(`  FAIL  ${name}${detail ? '  ' + detail : ''}`); }
}
/* The gate stamp (manual 12.3): when the WHOLE suite passes -- not a block
   subset the mutation runner selected -- build/gate.json records the suite's
   hashes and the build it ran (build/built.json), so tools/stamp.py can say
   whether a fixture's gate is still fresh. */
function hash12(rel) {
  return require('crypto').createHash('sha256').update(fs.readFileSync(path.join(ROOT, rel))).digest('hex').slice(0, 12);
}
function gateStamp() {
  const suite = path.relative(ROOT, process.argv[1] || '').split(path.sep).join('/');
  if (failures || process.env.ZX_BLOCKS || !/^test\/[^/]+\.test\.js$/.test(suite)) return;
  let built;
  try { built = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/built.json'), 'utf8')); } catch (e) { return; }
  if (hash12(built.out) !== built.html) return;      // the page on disk is not the one built.json describes
  const gate = { Purpose: 'the last green full suite and the build it ran; read by tools/stamp.py and tools/status.py',
                 checks, files: { [suite]: hash12(suite), 'test/rig.js': hash12('test/rig.js') }, built };
  fs.writeFileSync(path.join(ROOT, 'build/gate.json'), JSON.stringify(gate, null, 1));
}
function done() {
  console.log(`\n${checks - failures}/${checks} checks passed`);
  gateStamp();
  process.exit(failures ? 1 : 0);
}

/* ---------- the DOM stub ---------------------------------------------- */
const drawCalls = [];
let recording = false;
const ctxStub = {
  set fillStyle(v) { this._fill = v; },
  get fillStyle() { return this._fill; },
  fillRect(x, y, w, h) { if (recording) drawCalls.push(['fillRect', x, y, w, h, this._fill]); },
};
function makeEl(id) {
  const set = new Set();
  return {
    id, _text: '', innerHTML: '',
    get textContent() { return this._text; },
    set textContent(v) { this._text = String(v); },
    getContext() { return ctxStub; },
    style: {},
    classList: { add: c => set.add(c), remove: c => set.delete(c), contains: c => set.has(c) },
    blur() {}, focus() {},
    width: 256, height: 192,
  };
}
const els = new Map();
let rafCallback = null;
/* A real, if minimal, localStorage: settings code guards every call in
   try/catch, so WITHOUT this the round trip fails silently and every
   persistence check passes because there is nothing to fail on. */
const localStorageStore = new Map();
const localStorage = {
  getItem(k) { return localStorageStore.has(k) ? localStorageStore.get(k) : null; },
  setItem(k, v) { localStorageStore.set(k, String(v)); },
  removeItem(k) { localStorageStore.delete(k); },
  clear() { localStorageStore.clear(); },
};
const listeners = {};
const sandbox = {
  console,
  atob: s => Buffer.from(s, 'base64').toString('binary'),
  document: {
    getElementById(id) {
      if (!els.has(id)) els.set(id, makeEl(id));
      return els.get(id);
    },
  },
  addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
  requestAnimationFrame(cb) { rafCallback = cb; return 1; },   // CAPTURE, don't fire
  localStorage,
  Math, JSON, Uint8Array, Float32Array, Buffer, String, Number, Array, Object, Error, Set, Map,
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

/* ---------- load the built artifact ----------------------------------- */
function builtPath() {
  const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'port.json'), 'utf8'));
  return path.join(ROOT, cfg.out || ('web/' + (cfg.name || 'game') + '.html'));
}
function loadBuilt(file) {
  const BUILT = file || builtPath();
  const html = fs.readFileSync(BUILT, 'utf8');
  checkTrue('built file says it is generated', html.startsWith('<!-- GENERATED'));
  const jsonMatch = html.match(/<script type="application\/json" id="assets">([\s\S]*?)<\/script>/);
  checkTrue('asset payload present in the built file', !!jsonMatch);
  checkTrue('asset payload contains no unescaped "</"', !!jsonMatch && !jsonMatch[1].includes('</'));
  els.set('assets', Object.assign(makeEl('assets'), { _text: jsonMatch[1].replace(/<\\\//g, '</') }));
  const codeMatch = html.match(/<script>([\s\S]*?)<\/script>\s*$/);
  checkTrue('engine script present', !!codeMatch);
  vm.runInContext(codeMatch[1], sandbox, { filename: path.basename(BUILT) });
  const S = sandbox.globalThis.__SPEC__, P = sandbox.globalThis.__PORT__;
  checkTrue('platform hook exported (__SPEC__)', !!S);
  checkTrue('port hook exported (__PORT__)', !!P);
  checkTrue('rAF captured, not fired', rafCallback !== null);
  return { S, P, sandbox, html };
}

/* ---------- gate helpers (CLAUDE.md's still-to-build table; map: gate) -
   They COMPUTE and return what a row asserts; the block keeps its own
   check() calls, because tools/mutants.js finds a block by the check calls
   written in it, and mutants.json names the rows that kill.  Each helper
   makes one failure from docs/TRAPS.md unwritable, named beside it; each
   is gated against a known-wrong input in kit.test.js (T100).

   An empty measurement THROWS rather than returning a pass (T110): a
   coverage list with no addresses, a replay with no cases, a table of
   nothing.  A throw is a crash, and a crash is never green. */
const POISON = 0xA5;
function nonEmpty(what, n) {
  if (!n) throw new Error(`gate: ${what} is empty -- a check over nothing passes (T110)`);
  return n;
}
const putRuns = (m, runs) => { for (const [a, h] of runs) m.set(Buffer.from(h, 'hex'), a); };
const hex = v => '$' + v.toString(16);

/* replay(fx, run, opts) -- every case of a frozen oracle fixture (callio,
   sprdec: cases of {in, out} byte runs) replayed in a POISONED 64K (T125,
   T140, T159): memory holds only the bytes the real call read, every other
   byte is the poison, and afterwards the WHOLE of memory must equal in+out
   -- the cells it wrote and no others (T133, T140).
     run(m, c, i)   drives the engine; returns an object of observations
     opts.expect    { name: c => wanted } compared with run's observation
     opts.skip      a => next address to compare (the call's own stack, a
                    scratch range); return a unchanged to compare it
     opts.base      (m, c) => seeds shared tables before the case's bytes
     opts.blind     [[lo, hi], ...] a blind range (D5: ROM glyphs on the
                    screen): its values are not compared; instead the SET
                    of its addresses the call changed from the poison must
                    be the case's c.blind, reported as res.screen
     opts.only      case indices to replay
     opts.fill      the poison (0xA5); opts.stop stops at the first bad case
   A run that throws is a bad case in res.bytes, named with the message:
   one engine fault must not hide the cases after it.
   Returns { n, bytes: [bad, first], <name>: [bad, first], masked, still }.
     masked  out bytes the call wrote over a byte it never read, equal to
             the poison: an engine that skips that store still passes (T131)
     still   out bytes equal to the in byte they overwrote: a store whose
             target already agreed, invisible to the diff (T131, T140) */
function replay(fx, run, opts = {}) {
  const fill = opts.fill === undefined ? POISON : opts.fill;
  const expect = opts.expect || {};
  const idx = opts.only || fx.cases.map((_, i) => i);
  nonEmpty('replay: the fixture\'s cases', idx.length);
  const res = { n: 0, bytes: [0, ''], masked: 0, still: 0 };
  for (const k in expect) res[k] = [0, ''];
  let blind = null;
  if (opts.blind){
    nonEmpty('replay: the blind ranges', opts.blind.length);
    blind = new Uint8Array(0x10000);
    for (const [lo, hi] of opts.blind) blind.fill(1, lo, hi + 1);
    res.screen = [0, ''];
  }
  const name = (i, c) => `case ${i}${c.site !== undefined ? ' (' + hex(c.site) + ')' : ''}`;
  for (const i of idx) {
    const c = fx.cases[i];
    const m = new Uint8Array(0x10000).fill(fill);
    if (opts.base) opts.base(m, c);
    putRuns(m, c.in);
    const read = m.slice(), want = m.slice();
    putRuns(want, c.out);
    for (const [a0, h] of c.out) for (let k = 0; k < h.length / 2; k++) {
      const a = a0 + k, v = parseInt(h.substr(2 * k, 2), 16);
      if (v === read[a]) { if (v === fill && !inRuns(c.in, a)) res.masked++; else res.still++; }
    }
    let got;
    res.n++;
    try { got = run(m, c, i) || {}; }
    catch (e) {
      if (!res.bytes[0]++) res.bytes[1] = `${name(i, c)}: threw ${e.message}`;
      if (opts.stop) break; else continue;
    }
    let bad = false;
    for (let a = 0; a < 0x10000; a++) {
      if (opts.skip) { a = opts.skip(a, c); if (a > 0xFFFF) break; }
      if (blind && blind[a]) continue;
      if (m[a] !== want[a]) {
        if (!res.bytes[0]++) res.bytes[1] = `${name(i, c)}: ${hex(a)} = ${m[a]} want ${want[a]}`;
        bad = true; break;
      }
    }
    if (blind) {
      /* both as ascending sets: a fixture lists its ranges in capture order */
      const real = new Uint8Array(0x10000);
      for (const [lo, hi] of c.blind || []) real.fill(1, lo, hi + 1);
      let nw = 0, nr = 0, odd = -1;
      for (let a = 0; a < 0x10000; a++) {
        const w = blind[a] && m[a] !== fill ? 1 : 0;
        nw += w; nr += real[a];
        if (w !== real[a] && odd < 0) odd = a;
      }
      if (odd >= 0) {
        if (!res.screen[0]++) res.screen[1] = `${name(i, c)}: wrote ${nw} blind bytes, the real code ${nr}, first apart ${hex(odd)}`;
        bad = true;
      }
    }
    for (const k in expect) {
      const w = expect[k](c), g = got[k];
      if (JSON.stringify(g) !== JSON.stringify(w)) {
        if (!res[k][0]++) res[k][1] = `case ${i}: ${k} ${JSON.stringify(g)} want ${JSON.stringify(w)}`;
        bad = true;
      }
    }
    if (bad && opts.stop) break;
  }
  return res;
}
/* failed(r, ...keys) -- a replay folded into one row's [bad, first]: the
   bytes, the blind set when replayed with one, then each named observation;
   the first that failed, or [0, ''] when none did. */
function failed(r, ...keys) {
  for (const k of ['bytes', 'screen', ...keys]) {
    if (k !== 'screen' && !r[k]) throw new Error(`gate: failed: no observation ${k}`);
    if (r[k] && r[k][0]) return r[k];
  }
  return [0, ''];
}
/* frames(a, c) -- an opts.skip over the call's own stack frames, the 130
   bytes below and at c.sp a callio bracket pushes into. */
function frames(a, c) {
  return a === c.sp - 128 ? c.sp + 2 : a;
}
function inRuns(runs, a) {
  return runs.some(([a0, h]) => a0 <= a && a < a0 + h.length / 2);
}

/* corrupt(fx) -- a one-case copy of fx: its first case that writes, with
   the first out byte's bit 0 flipped.  A replay of it must report
   bytes[0] = 1 (T100: feed the gate a value known wrong and require it to
   fail).  Throws when no case writes anything. */
function corrupt(fx) {
  const c = fx.cases.find(c => c.out.length);
  if (!c) nonEmpty('corrupt: the writes of the cases', 0);
  const [a0, h] = c.out[0];
  const out = c.out.slice();
  out[0] = [a0, (parseInt(h.slice(0, 2), 16) ^ 1).toString(16).padStart(2, '0') + h.slice(2)];
  return Object.assign({}, fx, { cases: [Object.assign({}, c, { out })] });
}

/* negative(fx, run, opts) -- the gate's negative control as a row's value:
   the bad-case count of a replay of corrupt(fx), 1 when the gate works,
   or the message when corrupt or the run throws -- a row, not a crash. */
function negative(fx, run, opts) {
  try { return replay(corrupt(fx), run, opts).bytes[0]; }
  catch (e) { return e.message; }
}

/* ran(cases) -- the set of PCs a fixture's cases executed (each case's
   sig, four hex digits a PC); missing(required, have) -- the required
   addresses (or values) not in have, as hex strings, [] when all are.
   Coverage is measured against what the MACHINE ran (T175), and the list
   must be non-empty (T110, T138). */
function ran(cases) {
  nonEmpty('ran: the cases', cases.length);
  const s = new Set();
  for (const c of cases)
    for (let j = 0; j < c.sig.length; j += 4) s.add(parseInt(c.sig.slice(j, j + 4), 16));
  return s;
}
function missing(required, have) {
  nonEmpty('missing: the required list', required.length);
  const has = typeof have === 'function' ? have : v => have.has(v);
  return required.filter(v => !has(v)).map(v => v.toString(16));
}

/* distinct(values) -- how many different values a lookup produced: a
   table whose output does not vary with its index is not a lookup (T122).
   A row asserts distinct(...) >= the count the source holds. */
function distinct(values) {
  nonEmpty('distinct: the values', values.length);
  return new Set(Array.from(values, v => JSON.stringify(v))).size;
}

/* sameSource(a, b) -- true when a gate's two sides are one capture: a row
   asserts it false before comparing them (T104). */
function sameSource(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

/* unnamed(found, named) -- a category enumerated IN CODE against the list
   a row names (T169): [found but unnamed, named but not found], both []
   when the list is the category. */
function unnamed(found, named) {
  nonEmpty('unnamed: the enumeration', found.length);
  const f = new Set(found), n = new Set(named);
  return [found.filter(v => !n.has(v)).map(v => v.toString(16)),
          named.filter(v => !f.has(v)).map(v => v.toString(16))];
}

/* untouched(m, lo, hi, v, wrote) -- after poisoning lo..hi with v (T125),
   the addresses in the range that changed but are not in wrote (T140). */
function untouched(m, lo, hi, v, wrote) {
  const w = new Set(wrote), bad = [];
  for (let a = lo; a <= hi; a++) if (m[a] !== v && !w.has(a)) bad.push(a);
  return bad.map(hex);
}

/* ---------- world builders (map: gate, the BUILD rows) -------------------
   A world is the input a case must hold: { addr: byte, ... }, a partial
   assignment of the bytes the real call READ.  The builders make the list
   a routine's guards and fields call for; worlds(fx, want) names the ones
   no case of the fixture holds, each in the syntax of callio.py --derive
   --set, so a miss is the oracle command that fills it (the oracle is
   still the machine code; the world is constructed, so the case says so).
     world.at(a, ...vs)      one world per value: a wrap's boundary (T157),
                             a guard's other arm (T124)
     world.bounds(a, k, d)   k - d, k, k + d as bytes: the exact threshold
                             and both sides of it (T141, T128); d is 1
     world.both(ws, lo, hi, off)  each world and its mirror, lo..hi moved
                             by +off and lo+off..hi+off by -off: the other
                             player, the other instance (T132)
     world.cross(as, bs)     every a joined with every b: one field at its
                             boundary while another holds each value (T129)
   A world with no bytes, or a list with no worlds, throws (T110).
   unseeded(fx) -- the out addresses no case wrote over a different value:
   in every case the store left what was there (the byte read, else the
   poison), so an engine that drops it passes every case (T44, T91, T131).
   A store seen writing back two different bytes it read is not named: it
   follows its input, dropping it changes nothing, and the cases show it.
   Nor is one a derived case shows guarding itself: that case changed only
   this byte (no port, R or register; callers' returns above the entry SP,
   which the parent never read, may be given) and its parent wrote it: if
   that case stores it too, the rules above pass it; if not, it is made
   only when the byte already holds it ($9CAE under $AD3E).
   callio.py --seed derives all three kinds. */
function caseByte(c, a) {
  for (const [a0, h] of c.in) if (a0 <= a && a < a0 + h.length / 2) return parseInt(h.substr(2 * (a - a0), 2), 16);
  return undefined;
}
const setSyntax = w => Object.keys(w).map(Number).sort((x, y) => x - y)
  .map(a => `0x${a.toString(16).toUpperCase()}=0x${w[a].toString(16).toUpperCase()}`).join(',');
const world = {
  at(a, ...vs) { nonEmpty('world.at: the values', vs.length); return vs.map(v => ({ [a]: v & 0xFF })); },
  bounds(a, k, d = 1) { return [k - d, k, k + d].map(v => ({ [a]: v & 0xFF })); },
  both(ws, lo, hi, off) {
    nonEmpty('world.both: the worlds', ws.length);
    const move = a => a >= lo && a <= hi ? a + off : a >= lo + off && a <= hi + off ? a - off : a;
    const out = [];
    for (const w of ws) {
      const m = {};
      for (const a in w) m[move(Number(a))] = w[a];
      out.push(w, m);
    }
    return out;
  },
  cross(as, bs) {
    nonEmpty('world.cross: the first worlds', as.length); nonEmpty('world.cross: the second worlds', bs.length);
    return as.flatMap(a => bs.map(b => Object.assign({}, a, b)));
  },
};
function worlds(fx, want) {
  nonEmpty('worlds: the wanted worlds', want.length);
  nonEmpty('worlds: the fixture\'s cases', fx.cases.length);
  const seen = new Set(), miss = [];
  for (const w of want) {
    const keys = Object.keys(w).map(Number);
    nonEmpty('worlds: a world\'s bytes', keys.length);
    const s = setSyntax(w);
    if (seen.has(s)) continue;
    seen.add(s);
    if (!fx.cases.some(c => keys.every(a => caseByte(c, a) === w[a]))) miss.push(s);
  }
  return miss;
}
function unseeded(fx, fill = POISON) {
  nonEmpty('unseeded: the fixture\'s cases', fx.cases.length);
  const seen = new Map(), follows = new Map();
  for (const c of fx.cases)
    for (const [a0, h] of c.out) for (let k = 0; k < h.length / 2; k++) {
      const a = a0 + k, v = parseInt(h.substr(2 * k, 2), 16), was = caseByte(c, a);
      seen.set(a, seen.get(a) || v !== (was === undefined ? fill : was));
      if (v === was) follows.set(a, (follows.get(a) || new Set()).add(v));
    }
  nonEmpty('unseeded: the writes of the cases', seen.size);
  const writes = (c, a) => c.out.some(([a0, h]) => a0 <= a && a < a0 + h.length / 2), guards = new Set();
  for (const c of fx.cases) {
    const d = c.derived, set = d ? Object.keys(d.set || {}) : [];
    if (!d || set.length !== 1 || Object.keys(d).some(k => !['from', 'set', 'up'].includes(k))) continue;
    const a = parseInt(set[0], 16), p = fx.cases[d.from];
    if (writes(p, a) && caseByte(c, a) !== caseByte(p, a)) guards.add(a);
  }
  return [...seen].filter(([a, s]) => !s && (follows.get(a) || new Set()).size < 2 && !guards.has(a))
    .map(([a]) => a).sort((x, y) => x - y).map(hex);
}

const gate = { POISON, replay, failed, frames, corrupt, negative, ran, missing, distinct, sameSource, unnamed, untouched, nonEmpty,
               world, worlds, unseeded };

module.exports = {
  ROOT, sandbox, els, drawCalls, listeners, localStorageStore,
  check, checkTrue, done, loadBuilt, builtPath, gate,
  record(on) { recording = on; if (on) drawCalls.length = 0; },
  raf() { return rafCallback; },
  fire(type, ev) { for (const fn of (listeners[type] || [])) fn(ev); },
};
