#!/usr/bin/env python3
"""
stamp.py -- every fixture says what produced it, and whether that still holds
(manual 12.3).

A tool that writes evidence calls stamp.step(fx, by) on the dict it is about
to write.  That puts into fx["_stamp"]["steps"] one step:

    {"by": "capture", "args": ["callio.py", "--capture", "--state", "p1", ...],
     "files": {"tools/callio.py": "3f2a9c01d4e7", "tools/harness.py": ...,
               "pip:skoolkit": "10.0", "build/p1.pkl": ..., ".../48.rom": ...},
     "content": "5d03e1f2c9b4"}

"files" is every module the run loaded from tools/ (the tool, the harness,
the helpers), the simulator's and disassembler's installed versions
("pip:skoolkit"), the contention switch ("env:PORT_CONTENDED"), and every
file the harness read (the ROM, a snapshot, an image, a saved state:
harness.py notes each here through note()).  Each hash is the first 12 hex digits of the SHA-256 of the file's
bytes.  "content" is the same hash of the fixture itself, _stamp left out,
as canonical JSON: a hand edit (TRAPS #97) breaks it.

Steps accumulate while a fixture is built over several runs (--append,
--derive, --cover).  A fresh capture (by="capture") starts the list again,
and so does a replay check (by="check"): it vouches for everything before it.

A fixture is FRESH while every file of every step still hashes the same and
its content matches the last step's; STALE from the moment one does not,
and the reason names the file.  UNSTAMPED: written before stamps existed.

The gate half: build.py writes build/built.json (the page's hash, each
asset's content hash, the build's own inputs); rig.done() copies it into
build/gate.json with the suite's own hashes when the WHOLE suite passes.  A
fixture's gate is fresh while that chain still matches the disk.

Not covered yet: port.json (the harness reads its tape and z80 sections; a
change there stales nothing), and the "engine", "roster" and "branches"
fields of 12.3, which arrive with measure() and the roster manifest.

    python tools/stamp.py                  every asset in port.json
    python tools/stamp.py KEY|FILE ...     just those
Each line: key, fixture state, gate state, file; then every reason.  Exit 1
when any is not fresh.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
READ = []                       # files the harness read during this run, in order
BUILT = 'build/built.json'
GATE = 'build/gate.json'


def rel(path):
    """Repository-relative with forward slashes; absolute when outside it."""
    p = os.path.abspath(path)
    try:
        r = os.path.relpath(p, ROOT)
    except ValueError:          # another drive
        return p.replace(os.sep, '/')
    return p.replace(os.sep, '/') if r.startswith('..') else r.replace(os.sep, '/')


def absolute(path):
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def note(path):
    """The harness read this file: it goes into the next step's files.  An
    installed package's own file (SkoolKit's ROM) is covered by its "pip:"
    version, and an absolute path would not match on another machine."""
    if 'site-packages' in os.path.abspath(path).split(os.sep):
        return
    r = rel(path)
    if r not in READ:
        READ.append(r)


def hash_bytes(b):
    return hashlib.sha256(b).hexdigest()[:12]


def file_hash(path):
    """A file's hash; two kinds of entry are not files: "pip:NAME" is an
    installed package's version (the simulator), "env:NAME" a variable's
    value (PORT_CONTENDED switches contention off)."""
    if path.startswith('pip:'):
        try:
            from importlib.metadata import version
            return version(path[4:])
        except Exception:
            return None
    if path.startswith('env:'):
        return os.environ.get(path[4:], '')
    try:
        with open(absolute(path), 'rb') as f:
            return hash_bytes(f.read())
    except OSError:
        return None


def content_hash(fx):
    """A fixture's own hash, _stamp left out: canonical JSON of what a reader
    sees (round-tripped first, so int keys hash as the file's string keys).
    fx is the dict, or a path to read it from."""
    if isinstance(fx, str):
        with open(absolute(fx), encoding='utf-8') as f:
            fx = json.load(f)
    if isinstance(fx, dict):
        fx = {k: v for k, v in fx.items() if k != '_stamp'}
    canon = json.dumps(json.loads(json.dumps(fx)), sort_keys=True, separators=(',', ':'))
    return hash_bytes(canon.encode('utf-8'))


def code_files():
    """Every module this process loaded from tools/, the running tool first
    (not this one: a stamp does not change what was measured)."""
    out = []
    main = getattr(sys.modules.get('__main__'), '__file__', None)
    if main:
        out.append(rel(main))
    for m in list(sys.modules.values()):
        f = getattr(m, '__file__', None)
        if not f or not f.endswith('.py'):
            continue
        p = os.path.abspath(f)
        if p.startswith(HERE + os.sep) and rel(p) not in out and os.path.basename(p) != 'stamp.py':
            out.append(rel(p))
    out = out[:1] + sorted(out[1:])
    for pkg in ('skoolkit', 'z80dis'):
        if pkg in sys.modules:
            out.append('pip:' + pkg)
    if 'harness' in sys.modules:
        out.append('env:PORT_CONTENDED')
    return out


def step(fx, by, argv=None):
    """Stamp fx (the dict about to be written) with this run as a step.
    by: 'capture' (starts the list), 'check' (a replay that vouches for all
    before it: starts the list), anything else appends ('append', 'derive',
    'cover', 'stamp-r')."""
    if argv is None:
        argv = [os.path.basename(sys.argv[0])] + sys.argv[1:]
    files = {f: file_hash(f) for f in code_files() + READ}
    st = {'by': by, 'args': list(argv), 'files': files, 'content': content_hash(fx)}
    old = fx.get('_stamp') if isinstance(fx.get('_stamp'), dict) else {}
    steps = [] if by in ('capture', 'check') else list(old.get('steps', []))
    fx['_stamp'] = {'steps': steps + [st]}
    return fx


def stale_reasons(stamp, fx):
    """Why a stamped fixture is stale ([] when fresh)."""
    steps = stamp.get('steps') if isinstance(stamp, dict) else None
    if not steps:
        return ['its _stamp has no steps']
    why, seen = [], {}
    for s in steps:
        for f, h in (s.get('files') or {}).items():
            if f in seen:
                if seen[f] is not None and seen[f] != h:
                    why.append('%s differs between its steps (%s)' % (f, s.get('by')))
                continue
            now = seen[f] = file_hash(f)
            if now is None:
                why.append('%s is gone (read by %s)' % (f, s.get('by')))
            elif now != h:
                why.append('%s changed since %s' % (f, s.get('by')))
    if content_hash(fx) != steps[-1].get('content'):
        why.append('the fixture changed after its last step: a hand edit? (TRAPS #97)')
    return why


def freshness(path):
    """('fresh'|'stale'|'unstamped'|'missing'|'unreadable', [reasons])."""
    try:
        with open(absolute(path), encoding='utf-8') as f:
            fx = json.load(f)
    except OSError:
        return 'missing', ['%s does not exist' % path]
    except ValueError as e:
        return 'unreadable', ['%s: %s' % (path, e)]
    if not isinstance(fx, dict) or '_stamp' not in fx:
        return 'unstamped', ['written before stamps (manual 12.3): --check or re-run its tool']
    why = stale_reasons(fx['_stamp'], fx)
    return ('stale' if why else 'fresh'), why


def load(path):
    try:
        with open(absolute(path), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def gate_freshness(key, path):
    """Whether the last green full suite ran a page built from this fixture
    as it is now: ('fresh'|'stale'|'none', [reasons])."""
    gate = load(GATE)
    if not gate:
        return 'none', ['no green full suite on record (%s): build, then node test/kit.test.js' % GATE]
    why = []
    built = gate.get('built') or {}
    for f, h in list((gate.get('files') or {}).items()) + list((built.get('files') or {}).items()):
        if file_hash(f) != h:
            why.append('%s changed since the last green suite' % f)
    out = built.get('out')
    if out and file_hash(out) != built.get('html'):
        why.append('%s was rebuilt since the last green suite' % out)
    a = (built.get('assets') or {}).get(key)
    if a is None:
        why.append('%s was not in the page the suite ran' % key)
    else:
        try:
            now = content_hash(path)
        except (OSError, ValueError):
            now = None
        if now != a[1]:
            why.append('%s changed since the page the suite ran was built' % path)
    return ('stale' if why else 'fresh'), why


def assets():
    sys.path.insert(0, HERE)
    import portconfig
    return {a['key']: a['file'] for a in (portconfig.get('assets') or [])}


def main(argv):
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__.strip())
        return 0
    have = assets()
    bad = 0
    for n in (argv or list(have)):
        key = n if n in have else next((k for k, v in have.items() if v == rel(n)), n)
        path = have.get(key, n)
        st, why = freshness(path)
        g, gwhy = gate_freshness(key, path)
        print('%-13s %-9s gate %-5s %s' % (key, st, g, path))
        for w in why + gwhy:
            print('    ' + w)
        bad += st != 'fresh' or g != 'fresh'
    return 1 if bad else 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
