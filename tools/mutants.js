#!/usr/bin/env node
/*
 * mutants.js -- the JavaScript half of tools/mutants.py (manual 6.12).
 *
 *   node tools/mutants.js prepare SUITE SELECTABLE INFO
 *       Write a SELECTABLE copy of a test suite.  Every top-level statement that
 *       holds checks -- `if (A.x) { ... }`, `{ ... }`, an IIFE -- becomes a
 *       block; every other top-level statement (declarations, loading, helpers)
 *       runs first, in order, as the prelude.  Then the blocks named in
 *       ZX_BLOCKS (a JSON array of block numbers) run in that order, or all of
 *       them in file order, and the suite's own done() closes.  INFO gets the
 *       block table: lines, check counts, a hash of each block's text, and the
 *       blocks each one depends on through a top-level `let` it reads.
 *
 *   node tools/mutants.js cover SUITE SELECTABLE INFO CASES OUT [RAW]
 *       Run every block once with V8 coverage taken between blocks (or reuse
 *       RAW, the raw coverage of an earlier run of the same suite on the same
 *       page, when it exists; otherwise save it there), and write,
 *       per case, the blocks whose run executed its anchor -- "all" when the
 *       page load or the prelude did, because load-time code feeds every block --
 *       and each block's time.
 *
 * The selectable copy also honours ZX_FAILFAST (exit at the first FAIL line,
 * after printing it) and prints "  @@block N" before each block, so the runner
 * knows which block killed a case.  The original suite is never modified.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
const acorn = require(path.join(__dirname, 'vendor', 'acorn.js'));

function parse(src) {
  return acorn.parse(src, { ecmaVersion: 'latest', sourceType: 'script', locations: true, allowHashBang: true });
}

function each(node, fn) {
  (function walk(n) {
    if (!n || typeof n.type !== 'string') return;
    fn(n);
    for (const k in n) {
      const v = n[k];
      if (Array.isArray(v)) v.forEach(walk);
      else if (v && typeof v.type === 'string') walk(v);
    }
  })(node);
}

function isCheckCall(n) {
  if (n.type !== 'CallExpression') return false;
  const c = n.callee;
  const name = c.type === 'Identifier' ? c.name : c.type === 'MemberExpression' && c.property ? c.property.name : '';
  return name === 'check' || name === 'checkTrue';
}

function isDoneCall(st) {
  if (st.type !== 'ExpressionStatement' || st.expression.type !== 'CallExpression') return false;
  const c = st.expression.callee;
  return (c.type === 'Identifier' && c.name === 'done') ||
         (c.type === 'MemberExpression' && c.property && c.property.name === 'done');
}

function table(src) {
  const ast = parse(src);
  const lets = new Set();
  for (const st of ast.body)
    if (st.type === 'VariableDeclaration' && st.kind !== 'const')
      for (const d of st.declarations) if (d.id.type === 'Identifier') lets.add(d.id.name);
  const stmts = ast.body.map((st, i) => {
    let checks = 0;
    const reads = new Set(), writes = new Set();
    each(st, n => {
      if (isCheckCall(n)) checks++;
      if (n.type === 'Identifier' && lets.has(n.name)) reads.add(n.name);
      if (n.type === 'AssignmentExpression' && n.left.type === 'Identifier' && lets.has(n.left.name)) writes.add(n.left.name);
      if (n.type === 'UpdateExpression' && n.argument.type === 'Identifier' && lets.has(n.argument.name)) writes.add(n.argument.name);
    });
    const shape = st.type === 'IfStatement' || st.type === 'BlockStatement' ||
      (st.type === 'ExpressionStatement' && st.expression.type === 'CallExpression' && /Function/.test(st.expression.callee.type));
    return {
      i, start: st.start, end: st.end, line: st.loc.start.line, end_line: st.loc.end.line,
      checks, block: shape && checks > 0, done: isDoneCall(st),
      directive: st.type === 'ExpressionStatement' && typeof st.directive === 'string',
      reads: [...reads], writes: [...writes],
      sha: crypto.createHash('sha256').update(src.slice(st.start, st.end)).digest('hex').slice(0, 12),
    };
  });
  // a block that reads a top-level `let` another block writes runs after that writer
  for (const s of stmts) {
    s.deps = s.block ? stmts.filter(t => t.block && t.i !== s.i && t.writes.some(w => s.reads.includes(w))).map(t => t.i) : [];
  }
  return stmts;
}

const HEADER = `
const __ZX = { blocks: {}, cur: -1, cover: process.env.ZX_COVER || '', url: process.env.ZX_COVER_URL || '', iv: [] };
if (process.env.ZX_FAILFAST) {
  const __log = console.log;
  console.log = function (...a) {
    __log.apply(console, a);
    if (typeof a[0] === 'string' && a[0].startsWith('  FAIL')) { __log('  @@failfast'); process.exit(1); }
  };
}
if (__ZX.cover) {
  const insp = require('inspector');
  __ZX.session = new insp.Session(); __ZX.session.connect();
  __ZX.session.post('Profiler.enable');
  __ZX.session.post('Profiler.startPreciseCoverage', { callCount: true, detailed: true });
  __ZX.t = Number(process.hrtime.bigint() / 1000n);
}
function __zxTake(next) {
  if (!__ZX.cover) return;
  let got = null;
  __ZX.session.post('Profiler.takePreciseCoverage', (e, r) => { got = r; });
  const now = Number(process.hrtime.bigint() / 1000n);
  __ZX.iv.push({ block: __ZX.cur, ms: (now - __ZX.t) / 1000, scripts: got ? got.result
    .filter(s => s.url === __ZX.url || s.url.endsWith('/' + __ZX.url) || s.url.endsWith('\\\\' + __ZX.url))
    .map(s => ({ fns: s.functions.map(f => f.ranges.map(r => [r.startOffset, r.endOffset, r.count])) })) : [] });
  __ZX.t = now; __ZX.cur = next;
}
function __zxDrive() {
  const order = process.env.ZX_BLOCKS ? JSON.parse(process.env.ZX_BLOCKS)
                                      : Object.keys(__ZX.blocks).map(Number).sort((a, b) => a - b);
  __zxTake(-1);
  for (const i of order) {
    __ZX.cur = i;
    console.log('  @@block ' + i);
    __ZX.blocks[i]();
    __zxTake(-1);
  }
  if (__ZX.cover) require('fs').writeFileSync(__ZX.cover, JSON.stringify(__ZX.iv));
}
`;

function prepare(suite, out, info) {
  const src = fs.readFileSync(suite, 'utf8');
  const stmts = table(src);
  if (!stmts.some(s => s.done)) throw new Error(suite + ' does not end with done(): the selectable copy has nowhere to run its blocks');
  const parts = [];
  let last = 0, headerPlaced = false;
  for (const s of stmts) {
    parts.push(src.slice(last, s.start));
    if (!headerPlaced && !s.directive) { parts.push(HEADER); headerPlaced = true; }
    const text = src.slice(s.start, s.end);
    if (s.block) parts.push(`__ZX.blocks[${s.i}] = () => {\n${text}\n};`);
    else if (s.done) parts.push(`__zxDrive();\n${text}`);
    else parts.push(text);
    last = s.end;
  }
  parts.push(src.slice(last));
  fs.writeFileSync(out, parts.join(''));
  const blocks = stmts.filter(s => s.block).map(({ i, line, end_line, checks, sha, deps }) => ({ i, line, end_line, checks, sha, deps }));
  fs.writeFileSync(info, JSON.stringify({ suite, sha: crypto.createHash('sha256').update(src).digest('hex').slice(0, 12),
    blocks, prelude: stmts.filter(s => !s.block).map(s => s.i) }, null, 1));
  console.log('prepared %s: %d blocks, %d prelude statements', out, blocks.length, stmts.length - blocks.length);
}

function builtScript() {
  const cfg = JSON.parse(fs.readFileSync('port.json', 'utf8'));
  const file = cfg.out || ('web/' + (cfg.name || 'game') + '.html');
  const m = fs.readFileSync(file, 'utf8').match(/<script>([\s\S]*?)<\/script>\s*$/);
  if (!m) throw new Error(file + ': no engine <script> at the end of the page');
  return { code: m[1], url: path.basename(file) };
}

function cover(suite, selectable, infoPath, casesPath, outPath, keep) {
  const info = JSON.parse(fs.readFileSync(infoPath, 'utf8'));
  const { code, url } = builtScript();
  const raw = keep || outPath + '.raw';
  if (!(keep && fs.existsSync(keep))) {
    let failed = null;
    try {
      execFileSync('node', [selectable], { stdio: 'ignore', env: Object.assign({}, process.env,
        { ZX_COVER: raw, ZX_COVER_URL: url, ZX_BLOCKS: '', ZX_FAILFAST: '' }) });
    } catch (e) { failed = e.status; }
    if (failed !== null || !fs.existsSync(raw)) throw new Error('the coverage run of ' + selectable + ' did not pass (exit ' + failed + ')');
  }
  const iv = JSON.parse(fs.readFileSync(raw, 'utf8'));
  if (!keep) fs.unlinkSync(raw);

  // every function boundary seen in any interval: an offset belongs to its innermost one
  const fnMap = new Map();
  for (const v of iv) for (const s of v.scripts) for (const f of s.fns) fnMap.set(f[0][0] + ':' + f[0][1], f[0]);
  const fns = [...fnMap.values()].map(([a, b]) => [a, b]).sort((x, y) => x[0] - y[0]);
  const innermost = x => { let best = null; for (const [a, b] of fns) { if (a > x) break; if (x < b && (!best || b - a < best[1] - best[0])) best = [a, b]; } return best; };
  const index = iv.map(v => {
    const m = new Map();
    for (const s of v.scripts) for (const f of s.fns) m.set(f[0][0] + ':' + f[0][1], f);
    return m;
  });
  const ran = (k, x, fn) => {
    if (!fn) return false;
    const f = index[k].get(fn[0] + ':' + fn[1]);
    if (!f) return false;
    let best = null;
    for (const [a, b, c] of f) if (a <= x && x < b && (!best || b - a < best[1] - best[0])) best = [a, b, c];
    return !!best && best[2] > 0;
  };

  const src = fs.readFileSync(suite, 'utf8');
  const stmts = table(src);
  const blockSet = new Set(info.blocks.map(b => b.i));
  const cases = JSON.parse(fs.readFileSync(casesPath, 'utf8'));
  const result = { ms: {}, prelude_ms: 0, cases: {} };
  iv.forEach(v => { if (v.block === -1) result.prelude_ms += v.ms; else result.ms[v.block] = (result.ms[v.block] || 0) + v.ms; });
  const tally = {};
  for (const c of cases) {
    let res = 'all';
    if (/\.test\.js$/.test(c.file)) {
      const p = src.indexOf(c.old.replace(/\r?\n/g, src.includes('\r\n') ? '\r\n' : '\n'));
      if (p >= 0) { const st = stmts.find(s => s.start <= p && p < s.end); if (st && blockSet.has(st.i)) res = [st.i]; }
    } else {
      let o = c.old, p = code.indexOf(o);
      if (p < 0) { o = c.old.replace(/\r?\n/g, '\r\n'); p = code.indexOf(o); }
      if (p >= 0 && code.indexOf(o, p + 1) < 0) {
        const pts = [p, p + (o.length >> 1), p + Math.max(0, o.length - 1)];
        const owner = pts.map(innermost);
        const hit = new Set();
        let early = false;
        iv.forEach((v, k) => {
          if (pts.some((x, j) => ran(k, x, owner[j]))) { if (v.block === -1 || !blockSet.has(v.block)) early = true; else hit.add(v.block); }
        });
        res = early ? 'all' : [...hit].sort((a, b) => a - b);
      }
    }
    result.cases[c.id] = res;
    const key = res === 'all' ? 'all' : !res.length ? 'none' : res.length <= 3 ? '1-3' : res.length <= 10 ? '4-10' : '11+';
    tally[key] = (tally[key] || 0) + 1;
  }
  fs.writeFileSync(outPath, JSON.stringify(result));
  console.log('coverage: blocks per case %s; prelude %d ms; blocks %d ms', JSON.stringify(tally),
              Math.round(result.prelude_ms), Math.round(Object.values(result.ms).reduce((a, b) => a + b, 0)));
}

const [cmd, ...args] = process.argv.slice(2);
try {
  if (cmd === 'prepare' && args.length === 3) prepare(...args);
  else if (cmd === 'cover' && (args.length === 5 || args.length === 6)) cover(...args);
  else { console.error('usage: node tools/mutants.js prepare SUITE SELECTABLE INFO | cover SUITE SELECTABLE INFO CASES OUT'); process.exit(2); }
} catch (e) { console.error('mutants.js ' + cmd + ': ' + e.message); process.exit(1); }
