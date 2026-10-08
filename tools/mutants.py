#!/usr/bin/env python3
"""
mutants.py -- the mutation battery's runner (manual 6.9 step 9, 6.12).

  python tools/mutants.py                  every case
  python tools/mutants.py --affected       new cases, cases whose anchor lines changed,
                                           cases whose killing block changed -- since
                                           the last full run
  python tools/mutants.py --match TEXT     cases whose label contains TEXT ('||' = or)
  python tools/mutants.py --sample N       a random N cases (seeded): to check the runner
                                           against a full run's verdicts
  python tools/mutants.py --jobs N         worker trees (default: cores - 1)
  python tools/mutants.py --profile        manual 6.12 step 1: where a case's time goes
  python tools/mutants.py --full-suite     every case against the whole suite (the old
                                           way: slow, kept for comparison)
  python tools/mutants.py --background     detach; the one-line summary lands in
                                           build/mutants/summary.txt

WHAT MAKES A CASE CHEAP (manual 6.12).  The suite runs as a SELECTABLE copy
(tools/mutants.js): its helpers first, then only the blocks a case can affect.
One coverage pass per run records which blocks execute each case's anchor;
the block that killed a case last time runs first; the run stops at the first
FAIL.  A case whose anchor runs at load time -- a constant, a table -- can
reach every block, so it gets every block, killing block first once known.

WHAT KEEPS IT HONEST.  Selection only ever costs time, never a verdict: a case
that survives its selected blocks is run against the WHOLE suite before it is
called a survivor, and a case that only the whole suite kills is counted as a
MISS, so a hole in the selection is reported rather than hidden.  The selectable
copy must run exactly the checks the original runs, every block must pass on
its own at baseline, and the lessons of Bubble Bobble's runner all hold:
private worker trees, one run at a time, proof that each mutation landed, line
endings kept, timeouts that keep the FAIL lines already printed, crashes split
into DIAGNOSTIC / BROKEN-MUTANT / CRASH, a wall-clock floor, and an alarm when
every case survives.

Configuration, in port.json:
  "mutants": {"cases": "test/mutants.json", "suite": "test/game.test.js",
              "diagnostic": "BB_"}
Cases are a JSON list of {"file", "label", "old", "new"} (plus, ideally,
"increment" and "kills"), or a Python file holding MUTS = [(file, label, old,
new), ...].  A file ending in .test.js, and rig.js, live in test/; everything
else in web/.
"""
import ast
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE = os.path.join(ROOT, 'build', 'mutants')
WORKDIR = os.path.join(ROOT, 'scratch', 'mutants')
SELECTABLE = os.path.join('test', '.mutants_suite.js')
TMP = '.mutants'      # the runner's own files, at the tree root: never in build/ or test/,
                      # which suites may enumerate (Bubble Bobble's fixture guard lists build/)
CASE_TIMEOUT = 180
RUNNER_FILES = ('test/rig.js', 'tools/build.py', 'tools/mutants.py', 'tools/mutants.js')
GOOD = ('KILLED', 'DIAGNOSTIC', 'TIMEOUT-KILLED')


# ---------------------------------------------------------------------------
# configuration and cases
# ---------------------------------------------------------------------------
def config():
    try:
        cfg = json.load(io.open(os.path.join(ROOT, 'port.json'), encoding='utf-8'))
    except (OSError, ValueError):
        cfg = {}
    m = cfg.get('mutants', {}) if isinstance(cfg.get('mutants'), dict) else {}
    suite = m.get('suite')
    if not suite:
        found = sorted(f for f in os.listdir(os.path.join(ROOT, 'test'))
                       if f.endswith('.test.js') and f != 'kit.test.js')
        suite = 'test/' + found[0] if len(found) == 1 else None
    return {'cases': m.get('cases', 'test/mutants.json'), 'suite': suite,
            'diagnostic': m.get('diagnostic')}


def load_cases(path):
    """JSON, or a Python file's MUTS list -- read as data, never run."""
    full = os.path.join(ROOT, path)
    text = io.open(full, encoding='utf-8').read()
    if path.endswith('.json'):
        raw = json.loads(text)
        rows = [(c['file'], c['label'], c['old'], c['new'], c) for c in raw]
    else:
        tree = ast.parse(text)
        node = next((n.value for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'MUTS' for t in n.targets)), None)
        if node is None:
            raise SystemExit('%s: no MUTS = [...] list' % path)
        rows = [(f, l, o, n, {}) for (f, l, o, n) in ast.literal_eval(node)]
    labels = [r[1] for r in rows]
    if len(labels) != len(set(labels)):
        dup = sorted({l for l in labels if labels.count(l) > 1})[:3]
        raise SystemExit('case labels must be unique; repeated: %s' % '; '.join(dup))
    return [{'id': i, 'file': f, 'label': l, 'old': o, 'new': n,
             'kills': extra.get('kills'), 'increment': extra.get('increment')}
            for i, (f, l, o, n, extra) in enumerate(rows)]


def src_path(fn, root):
    # the suites and the rig they load live in test/; the page's sources in web/
    return os.path.join(root, 'test' if fn.endswith('.test.js') or fn == 'rig.js' else 'web', fn)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def git(*args):
    try:
        r = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, timeout=60)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]


def run_node(tree, script, env_extra, timeout=CASE_TIMEOUT):
    """(output, timed_out).  Output is decoded as UTF-8, never the console
    codepage: a label with U+201D once killed every reader thread (cp1252)."""
    env = dict(os.environ)
    env.update(env_extra)
    try:
        p = subprocess.run(['node', script], cwd=tree, capture_output=True, timeout=timeout, env=env)
        return (p.stdout + p.stderr).decode('utf-8', 'replace'), False
    except subprocess.TimeoutExpired as e:
        part = b''.join(h for h in (e.stdout, e.stderr) if isinstance(h, bytes))
        return part.decode('utf-8', 'replace'), True


def summary_of(out):
    m = re.findall(r'^(\d+)/(\d+) checks passed', out, re.M)
    return (int(m[-1][0]), int(m[-1][1])) if m else None


def make_tree(i):
    """A worker tree: everything the build and the suite read.  The real tree is
    read once and never written, so a kill at any moment leaves it pristine."""
    w = os.path.join(WORKDIR, 'w%s' % i)
    if os.path.isdir(w):
        shutil.rmtree(w, ignore_errors=True)
    os.makedirs(os.path.join(w, 'build'), exist_ok=True)
    for d in ('web', 'test', 'tools'):
        shutil.copytree(os.path.join(ROOT, d), os.path.join(w, d),
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.mutants_*'))
    shutil.copy(os.path.join(ROOT, 'port.json'), w)
    os.makedirs(os.path.join(w, TMP), exist_ok=True)
    for f in os.listdir(os.path.join(ROOT, 'build')):
        if f.endswith('.json'):
            shutil.copy(os.path.join(ROOT, 'build', f), os.path.join(w, 'build', f))
    return w


def build(tree):
    return subprocess.run([sys.executable, 'tools/build.py'], cwd=tree,
                          capture_output=True, timeout=CASE_TIMEOUT).returncode == 0


# ---------------------------------------------------------------------------
# applying a case: bytes in, bytes out, line endings kept
# ---------------------------------------------------------------------------
def apply_case(tree, case):
    """Returns (path, pristine bytes) or a verdict string."""
    p = src_path(case['file'], tree)
    raw = io.open(p, 'rb').read()
    crlf = b'\r\n' in raw
    old, new = case['old'], case['new']
    if crlf:
        old, new = old.replace('\r\n', '\n').replace('\n', '\r\n'), new.replace('\r\n', '\n').replace('\n', '\r\n')
    o, n = old.encode('utf-8'), new.encode('utf-8')
    count = raw.count(o)
    if count != 1:
        return 'ANCHOR' if count == 0 else 'AMBIGUOUS'
    io.open(p, 'wb').write(raw.replace(o, n))
    # *** AND PROVE IT LANDED. ***  A runner that writes nothing tests the
    # pristine tree and reports SURVIVED for every case (TRAPS #118).
    if io.open(p, 'rb').read() == raw:
        return 'NOT-APPLIED'
    return p, raw


def classify(out, timed_out, diagnostic):
    """(verdict, first failing row, block that was running)."""
    block, first = 'prelude', None
    for line in out.splitlines():
        if line.startswith('  @@block '):
            block = int(line.split()[1])
        elif line.lstrip().startswith('FAIL') and first is None:
            first = (line.strip()[4:].strip(), block)
    if timed_out:
        return ('TIMEOUT-KILLED', first[0], first[1]) if first else ('TIMEOUT', None, None)
    if first:
        return 'KILLED', first[0], first[1]
    if summary_of(out):
        return 'PASSED', None, None
    if 'SyntaxError' in out:
        return 'BROKEN-MUTANT', None, None
    if diagnostic and re.search(diagnostic, out) and 'Error' in out:
        tail = [l for l in out.splitlines() if re.search(diagnostic, l)]
        return 'DIAGNOSTIC', (tail[0].strip()[:160] if tail else None), block
    lines = out.strip().splitlines()
    return 'CRASH', (lines[-1][:160] if lines else '(no output)'), block


# ---------------------------------------------------------------------------
# ordering: killing block first, then the cheapest; dependencies before blocks
# ---------------------------------------------------------------------------
def order_blocks(cands, killer, ms, deps):
    seq = sorted(cands, key=lambda b: ms.get(str(b), ms.get(b, 0.0)))
    if killer is not None and killer in cands:
        seq.remove(killer)
        seq.insert(0, killer)
    out, seen = [], set()

    def add(b):
        if b in seen:
            return
        for d in sorted(deps.get(b, [])):
            add(d)
        seen.add(b)
        out.append(b)
    for b in seq:
        add(b)
    return out


def run_case(tree, case, plan, diagnostic, suite, full_suite):
    t0 = time.time()
    applied = apply_case(tree, case)
    if isinstance(applied, str):
        return {'label': case['label'], 'verdict': applied, 'seconds': 0.0}
    path, pristine = applied
    try:
        if case['file'].endswith('.test.js') and not full_suite:
            # the mutated suite needs its own selectable copy
            subprocess.run(['node', 'tools/mutants.js', 'prepare', suite, SELECTABLE,
                            os.path.join(TMP, 'info_case.json')], cwd=tree,
                           capture_output=True, timeout=CASE_TIMEOUT)
        build(tree)
        if full_suite:
            out, tmo = run_node(tree, suite, {'ZX_FAILFAST': '1'})
            verdict, row, block = classify(out, tmo, diagnostic)
            confirmed = False
        else:
            out, tmo = run_node(tree, SELECTABLE, {'ZX_BLOCKS': json.dumps(plan), 'ZX_FAILFAST': '1'})
            verdict, row, block = classify(out, tmo, diagnostic)
            confirmed = False
            if verdict == 'PASSED':
                # *** A SURVIVOR IS CONFIRMED AGAINST THE WHOLE SUITE. ***
                out, tmo = run_node(tree, suite, {'ZX_FAILFAST': '1'})
                verdict, row, block = classify(out, tmo, diagnostic)
                confirmed = True
        if verdict == 'PASSED':
            verdict = 'SURVIVED'
        return {'label': case['label'], 'verdict': verdict, 'row': row,
                'block': block if isinstance(block, int) else None,
                'miss': confirmed and verdict in GOOD, 'blocks_run': len(plan) if plan else 0,
                'seconds': round(time.time() - t0, 2)}
    finally:
        io.open(path, 'wb').write(pristine)
        if case['file'].endswith('.test.js') and not full_suite:
            subprocess.run(['node', 'tools/mutants.js', 'prepare', suite, SELECTABLE,
                            os.path.join(TMP, 'info_case.json')], cwd=tree,
                           capture_output=True, timeout=CASE_TIMEOUT)


def isolate(args):
    """Phase 1, per worker: build its tree, then run its share of blocks, each
    alone with its dependencies, on the pristine engine.  A block that fails
    alone depends on another block's leftovers; it is reported, and every case
    that needs it runs against the whole suite instead."""
    i, suite, share, full_suite = args
    tree = make_tree(i)
    if not build(tree):
        return {'worker': i, 'fatal': 'build failed in the worker tree', 'alone': []}
    if full_suite:
        return {'worker': i, 'fatal': None, 'alone': []}
    r = subprocess.run(['node', 'tools/mutants.js', 'prepare', suite, SELECTABLE,
                        os.path.join(TMP, 'info.json')], cwd=tree,
                       capture_output=True, timeout=CASE_TIMEOUT)
    if r.returncode:
        return {'worker': i, 'fatal': 'prepare failed in the worker tree', 'alone': []}
    alone = []
    for b, plan in share:
        out, tmo = run_node(tree, SELECTABLE, {'ZX_BLOCKS': json.dumps(plan)})
        s = summary_of(out)
        if tmo or not s or s[0] != s[1]:
            alone.append((b, (re.findall(r'^\s*FAIL.*$', out, re.M) or ['(no summary)'])[0].strip()[:160]))
    return {'worker': i, 'fatal': None, 'alone': alone}


def worker(args):
    """Phase 2, per worker: the same tree, its share of the cases."""
    i, cases, plans, diagnostic, suite, full_suite = args
    tree = os.path.join(WORKDIR, 'w%d' % i)
    rows = [run_case(tree, c, plans.get(c['id']), diagnostic, suite, full_suite or plans.get(c['id']) is None)
            for c in cases]
    return {'worker': i, 'fatal': None, 'rows': rows}


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------
def changed_lines(base, rel):
    """Lines of the current file that differ from revision `base`."""
    diff = git('diff', '-U0', base, '--', rel)
    if diff is None:
        return None
    lines = set()
    for m in re.finditer(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', diff, re.M):
        start, count = int(m.group(1)), int(m.group(2) or 1)
        lines.update(range(start, start + max(count, 1) + (1 if count == 0 else 0)))
    return lines


def affected(cases, last, block_sha):
    base = last.get('full_rev')
    if not base:
        return cases, 'no full run on record: every case'
    seen = last.get('cases', {})
    keep, why = [], {'new': 0, 'anchor lines': 0, 'killing block': 0, 'dead anchor': 0}
    texts, changes = {}, {}
    for c in cases:
        prev = seen.get(c['label'])
        if not prev:
            keep.append(c); why['new'] += 1
            continue
        if prev.get('killer_sha') and prev['killer_sha'] not in block_sha:
            keep.append(c); why['killing block'] += 1
            continue
        rel = os.path.relpath(src_path(c['file'], ROOT), ROOT).replace(os.sep, '/')
        if rel not in texts:
            texts[rel] = io.open(os.path.join(ROOT, rel), encoding='utf-8', newline='').read().replace('\r\n', '\n')
            changes[rel] = changed_lines(base, rel)
        p = texts[rel].find(c['old'].replace('\r\n', '\n'))
        if p < 0:                       # red stays red: a dead anchor is in every run
            keep.append(c); why['dead anchor'] += 1
            continue
        if changes[rel] is None:
            keep.append(c); why['anchor lines'] += 1
            continue
        first = texts[rel].count('\n', 0, p) + 1
        span = set(range(first, first + c['old'].count('\n') + 1))
        if span & changes[rel]:
            keep.append(c); why['anchor lines'] += 1
    return keep, ', '.join('%d %s' % (n, k) for k, n in why.items())


def prep_key(tree, suite):
    """A hash of everything preparation depends on."""
    h = hashlib.sha256()
    try:
        out = json.load(io.open(os.path.join(tree, 'port.json'), encoding='utf-8')).get('out')
    except (OSError, ValueError):
        out = None
    paths = [suite, 'test/rig.js', 'tools/mutants.js', 'port.json', out or '']   # not mutants.py: orchestration
    paths += sorted(os.path.join('build', f) for f in os.listdir(os.path.join(tree, 'build')) if f.endswith('.json'))
    for rel in paths:
        p = os.path.join(tree, rel)
        if rel and os.path.isfile(p):
            h.update(rel.encode('utf-8'))
            h.update(io.open(p, 'rb').read())
    return h.hexdigest()[:16]


def full_run_due(last):
    base = last.get('full_rev')
    if not base:
        return 'no full run on record'
    moved = [f for f in RUNNER_FILES if git('diff', '--quiet', base, '--', f) is None]
    return ('changed since the last full run: ' + ', '.join(moved)) if moved else None


def main(argv):
    if '-h' in argv or '--help' in argv:
        print(__doc__.strip())
        return 0
    if '--background' in argv:
        os.makedirs(STATE, exist_ok=True)
        log = io.open(os.path.join(STATE, 'run.log'), 'w', encoding='utf-8')
        kw = {'start_new_session': True} if os.name != 'nt' else {'creationflags': 0x00000008 | 0x00000200}
        p = subprocess.Popen([sys.executable, os.path.abspath(__file__)] + [a for a in argv if a != '--background'],
                             cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)
        print('mutants.py running in the background (pid %d); the one-line summary will be in '
              'build/mutants/summary.txt, the log in build/mutants/run.log' % p.pid)
        return 0
    cfg = config()
    if not cfg['suite']:
        raise SystemExit('no suite: set "mutants": {"suite": "test/<game>.test.js"} in port.json')
    jobs = int(argv[argv.index('--jobs') + 1]) if '--jobs' in argv else max(1, (os.cpu_count() or 2) - 1)
    full_suite = '--full-suite' in argv
    cases = load_cases(cfg['cases'])
    last_path = os.path.join(STATE, 'last.json')
    try:
        last = json.load(io.open(last_path, encoding='utf-8'))
    except (OSError, ValueError):
        last = {}

    os.makedirs(WORKDIR, exist_ok=True)
    lock = os.path.join(WORKDIR, '.running')
    if os.path.exists(lock):
        raise SystemExit('ANOTHER RUN IS IN PROGRESS (pid %s): worker trees are fixed paths, and two runs '
                         'corrupt each other silently.  Wait, or delete %s if it is stale.'
                         % (io.open(lock).read().strip(), lock))
    io.open(lock, 'w').write(str(os.getpid()))
    try:
        return run(argv, cfg, cases, last, last_path, jobs, full_suite)
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass


def run(argv, cfg, cases, last, last_path, jobs, full_suite):
    t0 = time.time()
    suite = cfg['suite']
    os.makedirs(STATE, exist_ok=True)
    prep = make_tree('prep')
    if not build(prep):
        raise SystemExit('tools/build.py fails on the clean tree')
    # *** PREPARATION IS CACHED BY WHAT IT DEPENDS ON. ***  The baseline, the
    # coverage and the isolation results depend only on the suite, the built
    # page, the rig, the fixtures and the runner; when none has changed, they
    # are reused rather than paid for again.
    key = prep_key(prep, suite)
    cache_path, raw_path = os.path.join(STATE, 'prep.json'), os.path.join(STATE, 'coverage_raw.json')
    try:
        cache = json.load(io.open(cache_path, encoding='utf-8'))
    except (OSError, ValueError):
        cache = {}
    hit = cache.get('key') == key and not full_suite and os.path.isfile(raw_path)
    if hit:
        base = tuple(cache['baseline'])
        print('preparation reused (nothing it depends on has changed): baseline %d/%d' % base, flush=True)
    else:
        for f in (cache_path, raw_path):
            if os.path.exists(f):
                os.remove(f)
        out, tmo = run_node(prep, suite, {}, timeout=CASE_TIMEOUT * 4)
        base = summary_of(out)
        if tmo or not base or base[0] != base[1]:
            raise SystemExit('BASELINE IS NOT GREEN: %s' % ((re.findall(r'^\s*FAIL.*$', out, re.M)
                             or [out.strip().splitlines()[-1] if out.strip() else '(no output)'])[0][:200]))
        print('baseline: %d/%d checks passed' % base, flush=True)

    info, cov = {'blocks': []}, {'cases': {}, 'ms': {}, 'prelude_ms': 0}
    if not full_suite:
        info_rel = os.path.join(TMP, 'info.json')
        r = subprocess.run(['node', 'tools/mutants.js', 'prepare', suite, SELECTABLE, info_rel], cwd=prep,
                           capture_output=True, text=True, timeout=CASE_TIMEOUT)
        if r.returncode:
            raise SystemExit('mutants.js prepare: ' + (r.stderr or r.stdout).strip()[:300])
        info = json.load(io.open(os.path.join(prep, info_rel), encoding='utf-8'))
        # *** THE SELECTABLE COPY MUST RUN EXACTLY THE CHECKS THE ORIGINAL RUNS. ***
        out2, _ = run_node(prep, SELECTABLE, {}, timeout=CASE_TIMEOUT * 4) if not hit else ('', False)
        sel = summary_of(out2) if not hit else base
        if sel != base:
            fails = re.findall(r'^\s*FAIL.*$', out2, re.M)
            raise SystemExit('the selectable copy ran %s, the suite %s: either the transformation changed the '
                             'suite or something in the tree differs between the two runs.  First failure: %s'
                             % (sel, base, fails[0].strip()[:200] if fails else '(none printed)'))
        io.open(os.path.join(prep, TMP, 'cases.json'), 'w', encoding='utf-8').write(
            json.dumps([{'id': c['id'], 'file': c['file'], 'old': c['old']} for c in cases]))
        r = subprocess.run(['node', 'tools/mutants.js', 'cover', suite, SELECTABLE, info_rel,
                            os.path.join(TMP, 'cases.json'), os.path.join(TMP, 'cover.json'), raw_path], cwd=prep,
                           capture_output=True, text=True, timeout=CASE_TIMEOUT * 8)
        if r.returncode:
            raise SystemExit('mutants.js cover: ' + (r.stderr or r.stdout).strip()[:300])
        print(r.stdout.strip(), flush=True)
        cov = json.load(io.open(os.path.join(prep, TMP, 'cover.json'), encoding='utf-8'))
        for f in ('info.json', 'cover.json'):
            shutil.copy(os.path.join(prep, TMP, f), os.path.join(STATE, f))
        if not hit:
            cache = {'key': key, 'baseline': list(base)}
            json.dump(cache, io.open(cache_path, 'w', encoding='utf-8'))

    blocks = [b['i'] for b in info['blocks']]
    deps = {b['i']: b['deps'] for b in info['blocks']}
    block_sha = {b['sha']: b['i'] for b in info['blocks']}
    sha_of = {b['i']: b['sha'] for b in info['blocks']}
    ms = cov.get('ms', {})

    if '--profile' in argv:
        b0 = time.time(); build(prep); bt = time.time() - b0
        total = cov['prelude_ms'] + sum(ms.values())
        print('\nSTEP 1, WHERE A CASE GOES (times under coverage, about twice normal; the ratios hold):\n'
              '   build %.2f s; suite %.1f s = helpers and loading %.1f s + %d blocks %.1f s'
              % (bt, total / 1000, cov['prelude_ms'] / 1000, len(ms), sum(ms.values()) / 1000))
        for b, t in sorted(ms.items(), key=lambda kv: -kv[1])[:10]:
            line = next((x['line'] for x in info['blocks'] if str(x['i']) == str(b)), '?')
            print('   %7.1f s  block %s (line %s)' % (t / 1000, b, line))
        per = []
        for c in cases:
            cand = cov['cases'].get(str(c['id']), 'all')
            cand = blocks if cand == 'all' else cand
            per.append(cov['prelude_ms'] + min([ms.get(str(b), 0) for b in cand] or [0]))
        print('   a case today: %.1f s; with coverage and the killing block first: about %.1f s (x%.0f)'
              % (total / 1000, sum(per) / len(per) / 1000, total / max(1, sum(per) / len(per))))
        return 0

    if '--affected' in argv:
        due = full_run_due(last)
        if due:
            print('*** A FULL RUN IS DUE: %s ***' % due, flush=True)
        cases, why = affected(cases, last, block_sha)
        kind = 'affected'
        print('affected: %d cases (%s)' % (len(cases), why), flush=True)
    elif '--sample' in argv:
        import random
        n = int(argv[argv.index('--sample') + 1])
        cases = random.Random(6.12).sample(cases, min(n, len(cases)))
        kind = 'sample'
    elif '--match' in argv:
        pat = argv[argv.index('--match') + 1].split('||')
        cases = [c for c in cases if any(m in c['label'] for m in pat)]
        kind = 'match'
    else:
        kind = 'full'
    if not cases:
        print('nothing to run')
        return 0

    jobs = max(1, min(jobs, len(cases)))
    bshares = [[] for _ in range(jobs)]
    for n, b in enumerate(sorted(blocks, key=lambda b: -ms.get(str(b), 0))):
        bshares[n % jobs].append((b, order_blocks([b], None, ms, deps)))
    unsafe, fatal = {}, []
    isolated = hit and 'unsafe' in cache
    if isolated:
        unsafe = {int(b): why for b, why in cache['unsafe'].items()}
        bshares = [[] for _ in range(jobs)]
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for f in as_completed([ex.submit(isolate, (k, suite, bshares[k], full_suite)) for k in range(jobs)]):
            r = f.result()
            if r['fatal']:
                fatal.append((r['worker'], r['fatal']))
            unsafe.update(dict(r['alone']))
    if fatal:
        for w, m in fatal:
            print('  !! WORKER %d FATAL: %s' % (w, m))
        raise SystemExit('a worker tree could not be set up; nothing was run')
    if not isolated and not full_suite:
        cache['unsafe'] = {str(b): w for b, w in unsafe.items()}
        json.dump(cache, io.open(cache_path, 'w', encoding='utf-8'))
    # *** A BLOCK THAT FAILS ALONE DEPENDS ON EARLIER BLOCKS: LEARN WHICH. ***
    # Tried in order, cheapest first: the earlier blocks that also fail alone (they
    # usually share one object, such as the page's own game), then widening
    # windows of the blocks just before it, then everything before it.  What
    # passes becomes the block's dependencies, run first in file order; a block
    # that passes with none of them sends its cases to the whole suite.
    learned = {int(b): d for b, d in cache.get('learned', {}).items()} if hit else {}
    hopeless = set(cache.get('hopeless', [])) if hit else set()
    line_of = {x['i']: x['line'] for x in info['blocks']}

    def closure(bs):
        out, todo = set(), list(bs)
        while todo:
            x = todo.pop()
            if x not in out:
                out.add(x)
                todo.extend(deps.get(x, []))
        return out
    for b in sorted(unsafe):
        if b in learned:
            deps[b] = sorted(set(deps.get(b, [])) | set(learned[b]))
            continue
        if b in hopeless:
            continue
        before = [x for x in blocks if x < b]
        chain = [u for u in sorted(unsafe) if u < b]
        trials = [chain] + [list(set(chain) | set(before[-w:])) for w in (1, 2, 4, 8, 16) if w < len(before)]
        trials.append(before)
        found = None
        for trial in trials:
            need = sorted((closure(set(trial) | set(deps.get(b, []))) - {b}) & set(before))
            out, tmo = run_node(prep, SELECTABLE, {'ZX_BLOCKS': json.dumps(need + [b])})
            s = summary_of(out)
            if not tmo and s and s[0] == s[1]:
                found = need
                break
        if found is None:
            hopeless.add(b)
            print('  !! block %d (line %s) fails even after every earlier block: its cases run the whole suite: %s'
                  % (b, line_of.get(b, '?'), unsafe[b]), flush=True)
        else:
            learned[b] = found
            deps[b] = found
            print('  block %d (line %s) depends on earlier blocks %s; they run before it whenever it runs '
                  '(make it self-contained to cut the cost)' % (b, line_of.get(b, '?'), found if len(found) <= 8 else
                                                                 '%d of them' % len(found)), flush=True)
        if not full_suite:          # saved after every block, so a cut-off run loses nothing learned
            cache['learned'] = {str(x): d for x, d in learned.items()}
            cache['hopeless'] = sorted(hopeless)
            json.dump(cache, io.open(cache_path, 'w', encoding='utf-8'))

    seen = last.get('cases', {})
    plans, cost = {}, {}
    for c in cases:
        cand = cov['cases'].get(str(c['id']), 'all') if not full_suite else []
        cand = blocks if cand == 'all' else list(cand)
        prev = seen.get(c['label'], {})
        killer = block_sha.get(prev.get('killer_sha'))
        whole = full_suite or any(b in hopeless for b in cand)
        plans[c['id']] = None if whole else order_blocks(cand, killer, ms, deps)
        full_ms = cov.get('prelude_ms', 0) + sum(ms.values())
        cost[c['id']] = full_ms if whole else cov.get('prelude_ms', 0) + (
            ms.get(str(killer), 0) if killer is not None else sum(ms.get(str(b), 0) for b in cand))
    # balance the workers: longest expected cases first, each to the least loaded
    shares, load = [[] for _ in range(jobs)], [0.0] * jobs
    for c in sorted(cases, key=lambda c: -cost[c['id']]):
        k = load.index(min(load))
        shares[k].append(c)
        load[k] += cost[c['id']] or 1
    print('%d cases, %d workers, %s run%s' % (len(cases), jobs, kind, ' (whole suite per case)' if full_suite else ''),
          flush=True)

    rows, done = [], 0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(worker, (k, shares[k], plans, cfg['diagnostic'], suite, full_suite)) for k in range(jobs)]
        for f in as_completed(futs):
            r = f.result()
            if r['fatal']:
                fatal.append((r['worker'], r['fatal']))
            rows.extend(r['rows'])
            done += 1
            print('  worker %d finished (%d/%d)  %.1f min elapsed' % (r['worker'], done, jobs, (time.time() - t0) / 60),
                  flush=True)
    shutil.rmtree(prep, ignore_errors=True)

    dt = (time.time() - t0) / 60
    by = {}
    for r in rows:
        by.setdefault(r['verdict'], []).append(r)
    misses = [r for r in rows if r.get('miss')]
    for r in sorted(rows, key=lambda r: r['label']):
        if r['verdict'] not in GOOD:
            print('  !! %-13s %s' % (r['verdict'], r['label']), flush=True)
    for r in misses:
        print('  !! MISS: only the whole suite killed it -- %s' % r['label'], flush=True)
    for w, m in fatal:
        print('  !! WORKER %d FATAL: %s' % (w, m), flush=True)
    killed = sum(len(by.get(v, [])) for v in GOOD)
    line = ('%s %s run: LISTED %d  KILLED %d  SURVIVORS %d  DEAD ANCHORS %d  TIMEOUTS %d  BROKEN %d  CRASHES %d  '
            'MISSES %d  -- %.1f min on %d workers' % (
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), kind, len(rows), killed,
                len(by.get('SURVIVED', [])), len(by.get('ANCHOR', [])) + len(by.get('AMBIGUOUS', [])),
                len(by.get('TIMEOUT', [])), len(by.get('BROKEN-MUTANT', [])), len(by.get('CRASH', [])),
                len(misses), dt, jobs))
    print('\n' + line)
    if dt * 60 < 20 and len(rows) > 200 and not fatal:
        print('*** %d CASES IN %.0f SECONDS: CHECK THAT THE RUN RAN ***' % (len(rows), dt * 60))
    if rows and len(by.get('SURVIVED', [])) == len(rows):
        print('  !! EVERY CASE SURVIVED -- suspect the RUNNER, not the suite')

    # record: killing rows and blocks per case, and the last full run's revision
    rev = (git('rev-parse', 'HEAD') or '').strip() or None
    recorded = dict(last.get('cases', {}))
    for r in rows:
        b = r.get('block')
        recorded[r['label']] = {'verdict': r['verdict'], 'row': r.get('row'),
                                'killer_sha': sha_of.get(b) if isinstance(b, int) else None,
                                'seconds': r.get('seconds')}
    state = {'cases': recorded, 'full_rev': last.get('full_rev'), 'full_time': last.get('full_time'),
             'last_kind': kind, 'last_time': datetime.datetime.now().isoformat(timespec='seconds')}
    if kind == 'full' and not fatal:
        state['full_rev'], state['full_time'] = rev, state['last_time']
    json.dump(state, io.open(last_path, 'w', encoding='utf-8'), indent=1)
    io.open(os.path.join(STATE, 'summary.txt'), 'w', encoding='utf-8').write(line + '\n')
    bad = by.get('SURVIVED') or by.get('ANCHOR') or by.get('AMBIGUOUS') or by.get('CRASH') or \
        by.get('BROKEN-MUTANT') or by.get('NOT-APPLIED') or fatal
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
