#!/usr/bin/env python3
"""
roster.py -- the roster manifest (manual 12.6): every saved state as a ROW,
its columns COMPUTED from the state itself, never remembered.

Per state (each NAME.pkl under z80.states):
  file, hash      the .pkl and the first 12 hex digits of its SHA-256
  machine         the harness's machine (48K: its frame length); a state
                  imported from a 128K snapshot is still a 48K state here --
                  where it came from is "source", which is DECLARED, not
                  computed (port.json roster.sources)
  pc, sp, stack   where the state resumes and the top four stack words
                  (TRAPS #67: a state is a moment, and can resume inside a
                  CALL that owes its caller a return), iff, im
  codediff        bytes that differ from the image (z80.image) inside the
                  code the walker reaches from tape.entry: a patched build
                  shows here (TRAPS #150), as do self-modified operands --
                  the first addresses are listed
  usable          the state runs: from it the heartbeat PC (roster.heartbeat,
                  the main loop's top) is reached within roster.frames
                  frames, and roster.steps instructions visit at least
                  roster.min_pcs distinct PCs (a hung capture visits three,
                  TRAPS #150); "beat" is the frames it took, "pcs" the count
  cols            one per world variable that has ever mattered
                  (roster.columns -- NAME: "ADDR" a byte, "ADDR:w" a word,
                  "ADDR:N" N bytes as hex)

Writes roster.file (build/roster.json), stamped like a fixture: a changed
.pkl or tool stales it.  An oracle that measures "on all states" takes them
from usable() and names them; stamp.step() records the roster rows of every
state a run read (12.3's "roster" field).

    python tools/roster.py            compute, print the table, write the file
    python tools/roster.py --check    recompute and compare with the file;
                                      exit 1 naming each state that moved
    python tools/roster.py --print    print the file's table, no simulation
    python tools/roster.py NAME ...   only those states (nothing written)
"""
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                   # noqa: E402
import stamp                                                        # noqa: E402


def cfg():
    r = portconfig.get('roster', default=None) or {}
    hb = r.get('heartbeat')
    return {
        'file': r.get('file', 'build/roster.json'),
        'heartbeat': portconfig.num(hb) if hb is not None else None,
        'frames': int(r.get('frames', 3000)),
        'steps': int(r.get('steps', 300000)),
        'min_pcs': int(r.get('min_pcs', 32)),
        'columns': r.get('columns', {}),
        'sources': r.get('sources', {}),
    }


def states_dir():
    return portconfig.path(portconfig.get('z80', 'states', default='build'))


def state_names():
    return sorted(os.path.splitext(os.path.basename(p))[0]
                  for p in glob.glob(os.path.join(states_dir(), '*.pkl')))


def file_sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def column(mem, spec):
    a, _, n = str(spec).partition(':')
    a = portconfig.num(a)
    if n == 'w':
        return '$%04X' % (mem[a] | mem[(a + 1) & 0xFFFF] << 8)
    n = int(n or 1)
    if n == 1:
        return '$%02X' % mem[a]
    return ''.join('%02X' % mem[(a + i) & 0xFFFF] for i in range(n))


_CODE = None


def code_set():
    """(image, sorted code addresses): the walker's lower bound on code from
    tape.entry over the image, kept to the bytes the tape loaded (a range
    the game fills at boot, its own copy of code, holds nothing of the
    tape's in the image to compare with)."""
    global _CODE
    if _CODE is None:
        from walk import walk
        with open(portconfig.path(portconfig.need('z80', 'image')), 'rb') as f:
            img = f.read()
        entry = portconfig.num(portconfig.get('tape', 'entry'))
        _, covered, _, _ = walk(img, [entry])
        spec = portconfig.blocks_spec()
        loaded = set()
        if spec != 'auto':
            for b in spec:
                loaded.update(range(b['dest'], b['dest'] + (b['len'] or 0)))
            for _, dst, n in portconfig.copies_spec():
                loaded.update(range(dst, dst + n))
        _CODE = (img, sorted(a for a in covered if a >= 0x4000 and (spec == 'auto' or a in loaded)))
    return _CODE


def heartbeat(h, c):
    """Frames from the state to the heartbeat PC, None if not within
    c['frames']."""
    from harness import T
    r = h.sim.registers
    start = r[T]
    budget = c['frames'] * h.frame_duration
    why, _ = h.run_until([c['heartbeat']], limit=1 << 40,
                         predicate=lambda hh: r[T] - start > budget)
    return round((r[T] - start) / h.frame_duration, 1) if why == 'target' else None


def distinct_pcs(h, c):
    from harness import PC
    r = h.sim.registers
    pcs = set()
    for _ in range(c['steps']):
        pcs.add(r[PC])
        h.step(1)
    return len(pcs)


def row(name, c):
    from harness import Harness, PC, SP, IFF, IM
    path = portconfig.state_path(name)
    h = Harness(deck=False)
    h.load_state_file(path)
    mem = h.memobj.m
    r = h.sim.registers
    img, code = code_set()
    sp = r[SP]
    diff = [a for a in code if mem[a] != img[a]]
    out = {
        'file': stamp.rel(path),
        'hash': file_sha(path),
        'machine': '48K' if h.frame_duration == 69888 else '%d T/frame' % h.frame_duration,
        'source': c['sources'].get(name),
        'pc': '$%04X' % r[PC], 'sp': '$%04X' % sp,
        'stack': ['$%04X' % (mem[(sp + 2 * i) & 0xFFFF] | mem[(sp + 2 * i + 1) & 0xFFFF] << 8)
                  for i in range(4)],
        'iff': r[IFF], 'im': r[IM],
        'codediff': len(diff),
        'codediff_at': ['$%04X=%02X' % (a, mem[a]) for a in diff[:12]],
        'cols': {k: column(mem, v) for k, v in c['columns'].items()},
    }
    # liveness: two probes, each from a fresh load of the state
    out['beat'] = heartbeat(h, c) if c['heartbeat'] is not None else None
    h.load_state_file(path)
    out['pcs'] = distinct_pcs(h, c)
    out['usable'] = (out['pcs'] >= c['min_pcs']
                     and (c['heartbeat'] is None or out['beat'] is not None))
    return out


def table(rows, c):
    cols = list(c['columns'])
    head = ['state', 'pc', 'sp', 'stack0', 'use', 'beat', 'pcs', 'code'] + cols
    lines = [head]
    for n, x in rows.items():
        lines.append([n, x['pc'], x['sp'], x['stack'][0], 'yes' if x['usable'] else 'NO',
                      '-' if x['beat'] is None else str(x['beat']), str(x['pcs']),
                      str(x['codediff'])] + [x['cols'].get(k, '') for k in cols])
    w = [max(len(l[i]) for l in lines) for i in range(len(head))]
    return '\n'.join(' '.join(v.ljust(w[i]) for i, v in enumerate(l)).rstrip() for l in lines)


def census(rows, c):
    """What the roster cannot show, over the usable states: columns that
    never vary (no state has the other value: a gate that needs one builds
    the world, TRAPS #183), and pairs whose values determine each other in
    every state (set together: a test of either one is a test of both until
    a world parts them, TRAPS #188)."""
    use = [x['cols'] for x in rows.values() if x['usable']]
    if len(use) < 2:                # one state cannot part anything
        return {'states': len(use), 'constant': {}, 'together': []}
    cols = list(c['columns'])
    vals = {k: [u.get(k) for u in use] for k in cols}
    const = {k: v[0] for k, v in vals.items() if v and len(set(v)) == 1}
    moving = [k for k in cols if k not in const]
    together = []
    for i, a in enumerate(moving):
        for b in moving[i + 1:]:
            pairs = set(zip(vals[a], vals[b]))
            if len(pairs) == len(set(vals[a])) == len(set(vals[b])):
                together.append([a, b])
    return {'states': len(use), 'constant': const, 'together': together}


def census_text(cz):
    out = ['census over %d usable states%s' % (
        cz['states'], ':' if cz['states'] > 1 else ' -- too few to part any column')]
    if cz['constant']:
        out.append('  never varies: ' + ', '.join('%s=%s' % kv for kv in cz['constant'].items()))
    for a, b in cz['together']:
        out.append('  set together in every state: %s and %s' % (a, b))
    return '\n'.join(out)


def load():
    """The roster file as a dict (None when absent)."""
    return stamp.load(cfg()['file'])


def usable():
    """Names of the usable states, from the roster file: what an oracle
    measuring "on all states" takes, and names in its own output."""
    r = load() or {}
    return [n for n, x in (r.get('states') or {}).items() if x.get('usable')]


def rows_for(paths):
    """The roster rows of the given state files, for stamp.step's "roster"
    field: name -> {hash, usable}.  None when there is no roster file."""
    r = load()
    if not r:
        return None
    by_file = {x['file']: (n, x) for n, x in (r.get('states') or {}).items()}
    out = {}
    for p in paths:
        if p in by_file:
            n, x = by_file[p]
            out[n] = {'hash': x['hash'], 'usable': x['usable']}
    return out


def main(argv):
    if '-h' in argv or '--help' in argv:
        print(__doc__.strip())
        return 0
    c = cfg()
    if '--print' in argv:
        r = load()
        if not r:
            print('roster: no %s -- run python tools/roster.py' % c['file'])
            return 1
        print(table(r['states'], c))
        print(census_text(census(r['states'], c)))
        return 0
    check = '--check' in argv
    names = [a for a in argv if not a.startswith('--')]
    pick = names or state_names()
    if not pick:
        print('roster: no states under %s' % states_dir())
        return 1
    rows = {}
    for n in pick:
        print('.. %s' % n, file=sys.stderr, flush=True)
        rows[os.path.splitext(os.path.basename(n))[0]] = row(n, c)
    print(table(rows, c))
    cz = census(rows, c)
    print(census_text(cz))
    bad = [n for n, x in rows.items() if not x['usable']]
    if bad:
        print('NOT USABLE: %s' % ', '.join(bad))
    if check:
        old = (load() or {}).get('states') or {}
        moved = []
        for n, x in rows.items():
            o = old.get(n)
            if o is None:
                moved.append('%s: not in %s' % (n, c['file']))
            elif o != x:
                ks = sorted(k for k in set(o) | set(x) if o.get(k) != x.get(k))
                moved.append('%s: %s differ' % (n, ', '.join(ks)))
        if not names:
            moved += ['%s: in the file, no .pkl' % n for n in old if n not in rows]
        for m in moved:
            print('MOVED ' + m)
        print('roster --check: %s' % ('%d moved' % len(moved) if moved else 'matches ' + c['file']))
        return 1 if moved else 0
    if names:
        return 0
    doc = {'_purpose': 'the roster manifest (manual 12.6), computed by python tools/roster.py; '
                       'read by oracles through roster.usable() and by stamp.step()',
           'columns': c['columns'],
           'heartbeat': '$%04X' % c['heartbeat'] if c['heartbeat'] is not None else None,
           'states': rows, 'census': cz}
    stamp.step(doc, 'capture')
    doc['_stamp']['steps'][-1].pop('roster', None)     # the old file's rows, not these
    with open(portconfig.path(c['file']), 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1)
        f.write('\n')
    print('wrote %s: %d states, %d usable' % (c['file'], len(rows), len(rows) - len(bad)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
