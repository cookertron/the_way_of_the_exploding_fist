#!/usr/bin/env python3
"""
sample.py -- named bytes sampled at every visit to one PC, over driven play.

The harness half of a differential gate (house rule 2): one sampler at the
main-loop top, the same rows printed by the engine, diffed row for row.  Also
the quick way to confirm a reading of a routine against the simulator: name
the variables it reads and writes, sample them at the pass top, and watch
them change (or not) the way the disassembly says.

Each --var is NAME=ADDR (one byte) or NAME=ADDR:N (N bytes, hex).  Rows are
"pass name=value ..."; --changes prints only rows where some variable moved
(pass numbers still count every visit).  --keys holds keys as keyprobe does.

--script "N:KEYS,N:KEYS,..." holds keys BY PASS, not by frame: each segment
holds its keys for N visits to --at, then all keys are released.  The engine
reads the same script by its own pass count, so the two halves see the same
keys on the same pass however long each pass takes (the timing is the
accumulator's business, 7.2, and is compared apart).

--json FILE writes the rows for the engine's half of the diff: the start
state at the first visit (RAM $4000-$FFFF as hex, R, SP -- tape-derived:
write it under build/ only where .gitignore keeps it out, rule 7), and per
visit the vars, R, the contended T since the previous visit, and an FNV-1a
hash of each --hash LO-HI range (repeatable) with --skip LO-HI ranges left
out of every hash.  Rows go to the file whether or not --changes is given.
--mark PC (repeatable) adds to each JSON row the marks executed since the
previous visit, in order ("m": [PC, ...]) -- a way out of the loop and back
in (a RET to the caller, a reset) shows there, not as a mystery row.
--also PC (repeatable) samples at more PCs without counting them as passes:
a loop the main loop calls that runs many times between two visits to --at
(a victory pose).  Each such visit is a sub-row of the next row ("s": [{pc,
v, r, t, h}, ...], in order); t is then always since the previous sample of
either kind, so the engine can charge each sub-loop pass its own T.

--poke ADDR=VAL[,...] sets data bytes before play, as callio.py --poke: a
start no saved state holds (P1 one point from the bout).  The JSON records
them as "poked"; the start state is constructed, so say so.

--start-here takes the JSON's start state as resumed, before play (with its
"pc"), not at the first visit, and times row 0 from there: the engine runs
from the start to the first visit itself (the boot: --state boot, $8800).

Usage:
    python tools/sample.py --state NAME --at PC --var NAME=ADDR [--var ...]
                           [--passes 1000] [--changes] [--keys D+W]
                           [--script "40:,60:D"] [--json FILE]
                           [--hash LO-HI ...] [--skip LO-HI ...] [--mark PC ...]
                           [--also PC ...] [--poke ADDR=VAL,...] [--start-here]
    python tools/sample.py --state s1 --at 0x9745 --var time=0x9CA5 --var cnt=0x9CA6 --changes
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from keyprobe import press                                         # noqa: E402
from harness import R, SP                                            # noqa: E402
from keyprobe import parse_script                                   # noqa: E402
from probeutil import parse_target, boot_target, source_label, TARGET_HELP  # noqa: E402


def parse_var(s):
    name, _, where = s.partition('=')
    addr, _, n = where.partition(':')
    if not name or not addr:
        sys.exit(f'sample.py: --var wants NAME=ADDR[:N], got {s!r}')
    return name, int(addr, 0), int(n, 0) if n else 1


def parse_range(s):
    lo, _, hi = s.partition('-')
    return int(lo, 0), int(hi, 0)


def fnv(m, lo, hi, skip):
    """FNV-1a 32 over m[lo..hi] inclusive, the skip ranges left out."""
    h = 0x811C9DC5
    for a in range(lo, hi + 1):
        if any(s <= a <= e for s, e in skip):
            continue
        h = ((h ^ m[a]) * 0x01000193) & 0xFFFFFFFF
    return h


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    target = parse_target(args)
    at, passes, changes, keys, vars_ = None, 1000, False, None, []
    script, out, hashes, skip, marks, also = None, None, [], [], [], []
    pokes, here = {}, False
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--at':
            at = int(args[i + 1], 0); i += 2
        elif a == '--var':
            vars_.append(parse_var(args[i + 1])); i += 2
        elif a == '--passes':
            passes = int(args[i + 1], 0); i += 2
        elif a == '--changes':
            changes = True; i += 1
        elif a == '--keys':
            keys = args[i + 1]; i += 2
        elif a == '--script':
            script = args[i + 1]; i += 2
        elif a == '--json':
            out = args[i + 1]; i += 2
        elif a == '--hash':
            hashes.append(parse_range(args[i + 1])); i += 2
        elif a == '--mark':
            marks.append(int(args[i + 1], 0)); i += 2
        elif a == '--also':
            also.append(int(args[i + 1], 0)); i += 2
        elif a == '--poke':
            for kv in args[i + 1].split(','):
                pa, pv = kv.split('=')
                pokes[int(pa, 0)] = int(pv, 0)
            i += 2
        elif a == '--start-here':
            here = True; i += 1
        elif a == '--skip':
            skip.append(parse_range(args[i + 1])); i += 2
        else:
            sys.exit(f'sample.py: unknown argument {a!r}; {TARGET_HELP}')
    if at is None or not vars_:
        sys.exit('sample.py: need --at PC and at least one --var')
    if keys and script:
        sys.exit('sample.py: --keys or --script, not both')
    h = boot_target(target, 'sample.py')
    for pa, pv in pokes.items():            # before play, as callio.py --poke: a start no saved state holds
        if pa < 0x4000:
            sys.exit(f'sample.py: --poke ${pa:04X} is ROM')
        h.memobj.m[pa] = pv
    for k in (keys.split('+') if keys else []):
        press(h.ports, k)
    plan = []                               # the keys held on each pass, by pass
    for n, names in (parse_script(script) if script else []):
        plan += [names] * n
    print(f'# sample.py at ${at:04X} over {passes} passes, {source_label(target)}'
          + (f', keys {keys}' if keys else '') + (f', script {script}' if script else ''))
    m = h.memobj.m
    prev, rows, start, t0 = None, [], None, None
    if here:                                # the state as resumed, before play: row 0's t is from here
        start = {'ram': bytes(m[0x4000:0x10000]).hex(), 'r': h.regs[R], 'sp': h.regs[SP], 'pc': h.pc()}
        t0 = h.tstates()
    hit, sub = [], []                       # marks and --also rows since the previous visit
    for p in range(passes):
        while True:
            reason, _ = h.run_until({at, *marks, *also}, limit=50_000_000)
            if reason != 'target' or h.pc() == at:
                break
            if h.pc() in marks:
                hit.append(h.pc())
            if h.pc() in also and out:
                sub.append({'pc': h.pc(), 'v': [bytes(m[a:a + n]).hex().upper() if n > 1 else f'{m[a]:02X}'
                                                for _, a, n in vars_], 'r': h.regs[R],
                            't': None if t0 is None else h.tstates() - t0,
                            'h': [fnv(m, lo, hi, skip) for lo, hi in hashes]})
                t0 = h.tstates()
            h.step(1)
        if reason != 'target':
            print(f'# stopped at pass {p}: {reason}'); break
        row = tuple(bytes(m[a:a + n]).hex().upper() if n > 1 else f'{m[a]:02X}'
                    for _, a, n in vars_)
        if not changes or row != prev:
            print(p, ' '.join(f'{v[0]}={x}' for v, x in zip(vars_, row)))
        prev = row
        if out:
            if start is None:
                start = {'ram': bytes(m[0x4000:0x10000]).hex(), 'r': h.regs[R], 'sp': h.regs[SP]}
            rows.append({'p': p, 'v': list(row), 'r': h.regs[R],
                         't': None if t0 is None else h.tstates() - t0,
                         'h': [fnv(m, lo, hi, skip) for lo, hi in hashes], 'm': hit,
                         **({'s': sub} if sub else {})})
            if hit:
                print(f'# pass {p}: marks ' + ' '.join(f'${x:04X}' for x in hit))
            if sub:
                print(f'# pass {p}: {len(sub)} --also rows')
            hit, sub = [], []
            t0 = h.tstates()
        if script:                          # the keys for the pass about to run
            h.ports.release_all()
            for k in (plan[p] if p < len(plan) else []):
                press(h.ports, k)
        h.step(1)
    if out:
        with open(out, 'w') as f:
            json.dump({'at': at, 'source': source_label(target), 'script': script,
                       'vars': [[nm, a, n] for nm, a, n in vars_],
                       'hash': hashes, 'skip': skip, 'marks': marks,
                       **({'also': also} if also else {}),
                       **({'poked': {f'{a:04x}': v for a, v in pokes.items()}} if pokes else {}), 'start': start, 'rows': rows}, f)
        print(f'# wrote {out}: {len(rows)} rows')


if __name__ == '__main__':
    main()
