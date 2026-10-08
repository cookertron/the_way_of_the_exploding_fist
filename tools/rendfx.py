#!/usr/bin/env python3
"""
rendfx.py -- render_fighters $BF13 called alone, frozen as a fixture: the
oracle of the JS renderFighters gate (manual 5.1, 7.2; ledger/BF13.toml).

There is no Python model here.  Each call runs once more in an UNCONTENDED
twin over a logging memory: the bytes it read before writing them are its
inputs, the bytes it wrote (stack excepted) its outputs, and the twin's T its
uncontended T.  The code ($8803-$8AE8, $BF13-$C2AF, $C2B5-$C406) and the
decoder tables $B500-$B9FF must be the same at every call; the tables go in
the fixture once, the code never does (tape-derived; --check takes it from
the target).

  --capture  run driven play; at every entry to $BF13 save the machine, run
             the call alone in the twin to its return at $9793, run it in the
             contended harness for its T in play, restore, run the real call
             with interrupts on, and carry on.  A case is kept per distinct
             set of PCs executed in $BF13-$C406 (the paths: separate/merged
             boxes, draw order, flip, floor-anchored parts, shadow overflow,
             x&3 shifts), at most --per of each; with --near N, also one
             case per distinct margin of either $C03B comparison within N px
             of its boundary (margin(): > 0 drawn apart).
  --check    replay every case in a blank 64K holding only the code, the
             tables, the inputs and the return address: every byte written
             and the T must agree, and no byte outside them may be read.
  --paths    with --check: how many cases take each render path.
  --stamp-r  with --check: write each case's M1 count mod 128 (m1: how far
             R advanced from $BF13 to $9793) into the fixture; once
             stamped, --check compares it.

Usage:
    python tools/rendfx.py --capture --state s1 [--frames 600] [--keys D+W]
                           [--per 2] [--near N] [--out build/rendfx_cases.json] [--append]
    python tools/rendfx.py --check --state s1 [--paths] [--stamp-r] [--fixture build/rendfx_cases.json]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Harness, Simulator, SP, PC, T, R              # noqa: E402,F401
from probeutil import parse_target, boot_target, source_label, TARGET_HELP  # noqa: E402
from sprdec import runs, unruns                                   # noqa: E402
import stamp as stamps                                            # noqa: E402

ENTRY, RET = 0xBF13, 0x9793
CODE = (range(0x8803, 0x8AE9), range(0xBF13, 0xC2B0), range(0xC2B5, 0xC407))
TABLES = range(0xB500, 0xBA00)
OWN = range(0xBF13, 0xC407)
FIXTURE = 'build/rendfx_cases.json'
FLAT = {'fast_djnz': False, 'fast_ldir': False}

# a path is named by a PC that only it executes
PATHS = {'separate': 0xC101, 'merged': 0xC055, 'p1-first': 0xC0D9, 'p2-first': 0xC0E2,
         'floor-part': 0xC3A4, 'flip': 0xC3C3, 'unflipped': 0xC3B7, 'overflow': 0xC244,
         'x&3=1': 0xC2E7, 'x&3=2': 0xC2E2, 'x&3=3': 0xC2DD}


def constant(a):
    return any(a in r for r in CODE) or a in TABLES


class Logged:
    """Memory that records the bytes read before any write to them and
    every address written; ROM writes are dropped as on the machine."""
    def __init__(self, data):
        self.m = bytearray(data)
        self.reads = {}
        self.written = set()

    def __len__(self):
        return 0x10000

    def __getitem__(self, a):
        if a not in self.written and a not in self.reads:
            self.reads[a] = self.m[a]
        return self.m[a]

    def __setitem__(self, a, v):
        if a >= 0x4000:
            self.written.add(a)
            self.m[a] = v

    def __iter__(self):
        return iter(self.m)


TEST = 0xC03B          # the overlap test: boxes in $C434/$C435 (P1 x) and $C438/$C439 (P2 x)


def margin(m):
    """Signed slack of each $C03B comparison: [P1 xmin - (P2 xmax + 11),
    P2 xmin - (P1 xmax + 11)], 8-bit as the code does it.  The boxes are
    drawn apart when either is > 0; a slack of 10 instead of 11 flips a
    comparison at 0, a slack of 12 one at 1."""
    return [m[0xC434] - ((m[0xC439] + 11) & 255), m[0xC438] - ((m[0xC435] + 11) & 255)]


def run_alone(mem, regs, limit=5_000_000):
    """Run the call in an uncontended twin over `mem` until PC = RET;
    return (T, PCs executed in OWN, margin at the overlap test)."""
    sim = Simulator(mem, config=FLAT)
    sim.registers[:] = regs
    r, ops, t0 = sim.registers, sim.opcodes, regs[T]
    pcs, mg = set(), None
    for _ in range(limit):
        pc = r[PC]
        if pc == RET:
            mem.exit_r = r[R]
            return r[T] - t0, pcs, mg
        if pc == TEST:
            mg = margin(mem.m)
        if pc in OWN:
            pcs.add(pc)
        ops[mem.m[pc]]()
    sys.exit(f'rendfx: call never returned to ${RET:04X}')


def path_names(pcs):
    return [k for k, a in PATHS.items() if a in pcs]


def capture(args):
    t = parse_target(args)
    frames, keys, out, append, per, near = 600, [], FIXTURE, False, 2, None
    while args:
        a = args[0]
        if a == '--frames':
            frames = int(args[1], 0); del args[:2]
        elif a == '--keys':
            keys = args[1].split('+'); del args[:2]
        elif a == '--out':
            out = args[1]; del args[:2]
        elif a == '--per':
            per = int(args[1]); del args[:2]
        elif a == '--near':
            near = int(args[1]); del args[:2]
        elif a == '--append':
            append = True; del args[:1]
        else:
            sys.exit(f'rendfx: unknown argument {a}  (target: {TARGET_HELP})')
    from keyprobe import press
    h = boot_target(t, 'rendfx')
    if not h.contended:
        sys.exit('rendfx: needs the contended harness for play')
    r, m = h.regs, h.memobj.m
    for k in keys:
        press(h.ports, k)
    fx = {'tables': None, 'cases': []}
    if append and os.path.exists(out):
        fx = json.load(open(out))
    seen, mseen, hist = {}, set(), {}
    for c in fx['cases']:
        for i, g in enumerate(c.get('margin') or ()):
            mseen.add((i, g))
        seen[c['sig']] = seen.get(c['sig'], 0) + 1
    code = None
    calls = new = 0
    sigs = set()
    end = r[T] + frames * h.frame_duration
    while r[T] < end:
        reason, _ = h.run_until([ENTRY], limit=200_000)
        if reason != 'target':
            continue
        st = h.save_state()
        pre, sp, t0 = bytes(m), r[SP], r[T]
        lm = Logged(pre)
        real_t, pcs, mg = run_alone(lm, list(r))
        h.run_until([RET], limit=5_000_000, interrupts=False)
        cont_t = r[T] - t0
        h.load_state(st)
        for k in keys:
            press(h.ports, k)
        h.run_until([RET], limit=5_000_000)        # the real call, interrupts on
        calls += 1
        c = bytes(pre[a] for rg in CODE for a in rg)
        if code is None:
            code = c
        elif code != c:
            sys.exit('rendfx: the code changed between calls -- it is not constant')
        tables = pre[TABLES.start:TABLES.stop].hex()
        if fx['tables'] is None:
            fx['tables'] = tables
        elif fx['tables'] != tables:
            sys.exit('rendfx: the tables at $B500-$B9FF changed between calls -- they are not constant')
        stack = range(sp - 64, sp + 2)
        sig = ''.join(f'{a:04x}' for a in sorted(pcs))
        sigs.add(sig)
        new_ms = set()
        for i, g in enumerate(mg or ()):
            hist[i, g] = hist.get((i, g), 0) + 1
            if near is not None and abs(g) <= near and (i, g) not in mseen:
                new_ms.add((i, g))
        close = bool(new_ms)
        if seen.get(sig, 0) >= per and not close:
            continue
        seen[sig] = seen.get(sig, 0) + 1
        mseen |= new_ms
        new += 1
        ins = {a: v for a, v in lm.reads.items() if not constant(a) and a not in stack}
        outs = {a: lm.m[a] for a in lm.written if a not in stack}
        fx['cases'].append({'sp': sp, 'sig': sig, 'paths': path_names(pcs), 'margin': mg,
                            'in': runs(ins), 'out': runs(outs), 't': real_t, 'tc': cont_t})
    print(f'rendfx: {source_label(t)}, {frames} frames: {calls} calls, {len(sigs)} distinct paths, '
          f'{new} new cases ({len(fx["cases"])} in {out})')
    for i in (0, 1):
        near_ms = sorted((g for j, g in hist if j == i), key=abs)[:8]
        print(f'nearest margins of $C03B test {i + 1} (margin:calls): ' + ' '.join(f'{g}:{hist[i, g]}' for g in near_ms))
    fx['about'] = ('Purpose: frozen oracle for render_fighters $BF13 -- one call per distinct path (at most a few each): '
                   'SP at entry, the bytes it read before writing them as [addr, hex] runs (in; code and the tables '
                   '$B500-$B9FF excepted), its margin at the $C03B overlap test, every byte it wrote outside the stack (out), its uncontended T (t) and its '
                   'T in play (tc). Read by: python tools/rendfx.py --check, and the JS renderFighters gate.')
    stamps.step(fx, 'append' if append else 'capture')
    with open(out, 'w') as f:
        json.dump(fx, f, separators=(',', ':'))


def check(args):
    t = parse_target(args)
    fixture, want_paths, stamp = FIXTURE, False, False
    while args:
        if args[0] == '--fixture':
            fixture = args[1]; del args[:2]
        elif args[0] == '--stamp-r':
            stamp = True; del args[:1]
        elif args[0] == '--paths':
            want_paths = True; del args[:1]
        else:
            sys.exit(f'rendfx: unknown argument {args[0]}')
    h = boot_target(t, 'rendfx')                   # the code comes from the target, never the fixture
    src = h.memobj.m
    fx = json.load(open(fixture))
    tables = bytes.fromhex(fx['tables'])
    tally, bad, margins = {}, 0, []
    for i, c in enumerate(fx['cases']):
        mem = bytearray(0x10000)
        for rg in CODE:
            mem[rg.start:rg.stop] = src[rg.start:rg.stop]
        mem[TABLES.start:TABLES.stop] = tables
        ins = unruns(c['in'])
        for a, v in ins.items():
            mem[a] = v
        sp = c['sp']
        mem[sp], mem[sp + 1] = RET & 0xFF, RET >> 8
        lm = Logged(mem)
        regs = list(h.regs)
        regs[PC], regs[SP], regs[T], regs[R] = ENTRY, sp, 0, 0
        rt, pcs, mg = run_alone(lm, regs)
        margins.append(mg)
        stack = range(sp - 64, sp + 2)
        want = unruns(c['out'])
        out = {a: lm.m[a] for a in lm.written if a not in stack}
        unread = sorted(a for a in lm.reads if not constant(a) and a not in stack and a not in ins)
        m1 = lm.exit_r & 0x7F                      # R from 0: the M1 count mod 128
        if stamp:
            c['m1'] = m1
        if out != want or rt != c['t'] or unread or c.get('m1', m1) != m1:
            bad += 1
            if bad <= 5:
                print(f'*** case {i}: T replay {rt} fixture {c["t"]}; writes agree: {out == want}; '
                      f'unrecorded reads {[hex(a) for a in unread[:6]]}')
        for p in c['paths']:
            tally[p] = tally.get(p, 0) + 1
    ts = [c['t'] for c in fx['cases']]
    if not bad:                                    # every case replayed: the check vouches for them (manual 12.3)
        stamps.step(fx, 'check')
        with open(fixture, 'w') as f:
            json.dump(fx, f, separators=(',', ':'))
    if stamp and not bad:
        print(f'rendfx: stamped the M1 count mod 128 (m1, R advanced from $BF13 to $9793) on every case')
    print(f'rendfx: {len(fx["cases"])} cases, {bad} disagree; T {min(ts)}-{max(ts)}')
    if want_paths:
        print('paths: ' + ', '.join(f'{k} {tally.get(k, 0)}' for k in PATHS))
        for i in (0, 1):
            print(f'margins of $C03B test {i + 1} (> 0 apart): ' + ' '.join(str(g[i]) for g in sorted(margins, key=lambda g: g[i])))
    sys.exit(1 if bad else 0)


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    if args[0] == '--capture':
        capture(args[1:])
    elif args[0] == '--check':
        check(args[1:])
    else:
        sys.exit('rendfx: --capture or --check (see --help)')


if __name__ == '__main__':
    main()
