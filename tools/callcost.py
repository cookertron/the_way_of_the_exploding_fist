#!/usr/bin/env python3
"""
callcost.py -- is ONE call's cost a function of its inputs?  (manual Q11, 3.8)

chaincost.py names the routine that owns the pass's spread.  When that spread
is broad rather than multi-modal (a sprite plotter whose cost follows the
frames drawn), per-path constants do not exist, and the question becomes:
given the routine's INPUTS, is its cost fixed?  This brackets one CALL site
and its return address over driven play, keys each call by the bytes of a
memory range read at the return (the routine's inputs and parameter block),
and reports the cost spread within each key.

Contention makes the same path cost different amounts at different points in
the frame (3.8).  --sub PC END brackets an instruction inside the call (an
LDIR into the display file) whose time is reported apart and excluded from a
second spread: if the spread collapses without it, the remainder is fixed by
the inputs and only that instruction is frame-phase dependent.  For an LDIR
the bytes moved (BC at entry) and T per byte are reported (21 uncontended).

Usage:
    python tools/callcost.py --state NAME --call SITE RET --key LO HI
                             [--sub PC END] [--frames 3000] [--keys D+W]
    python tools/callcost.py --state s1 --call 0x9790 0x9793 --key 0xC41B 0xC43C --sub 0xC3F0 0xC3F2
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import PC                                             # noqa: E402
from keyprobe import press                                         # noqa: E402
from probeutil import parse_target, boot_target, source_label, TARGET_HELP  # noqa: E402

T, B, C = 25, 2, 3


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    t = parse_target(args)
    call = key = sub = None
    frames, keys = 3000, []
    while args:
        a = args[0]
        if a == '--call':
            call = (int(args[1], 0), int(args[2], 0)); del args[:3]
        elif a == '--key':
            key = (int(args[1], 0), int(args[2], 0)); del args[:3]
        elif a == '--sub':
            sub = (int(args[1], 0), int(args[2], 0)); del args[:3]
        elif a == '--frames':
            frames = int(args[1], 0); del args[:2]
        elif a == '--keys':
            keys = args[1].split('+'); del args[:2]
        else:
            sys.exit(f'callcost: unknown argument {a}  (target: {TARGET_HELP})')
    if call is None or key is None:
        sys.exit('callcost: --call SITE RET and --key LO HI are required')
    h = boot_target(t, 'callcost')
    m, r = h.memobj.m, h.regs
    for k in keys:
        press(h.ports, k)
    site, ret = call
    rows = []                           # (cost, sub T, sub bytes, key bytes, sub runs)
    t0 = s_in = None
    s_t = s_n = s_k = 0
    end = r[T] + frames * h.frame_duration
    while r[T] < end:
        pc = r[PC]
        if pc == site:
            t0, s_t, s_n, s_k = r[T], 0, 0, 0
        elif pc == ret and t0 is not None:
            rows.append((r[T] - t0, s_t, s_n, bytes(m[key[0]:key[1]]), s_k))
            t0 = None
        if sub and t0 is not None and pc == sub[0] and s_in is None:
            s_in = r[T]
            s_n += r[B] * 256 + r[C]
            s_k += 1
        h.step(1)
        if s_in is not None and r[PC] == sub[1]:
            s_t += r[T] - s_in
            s_in = None
    print(f'callcost: ${site:04X} -> ${ret:04X} from {source_label(t)}, {frames} frames, '
          f'key ${key[0]:04X}-${key[1] - 1:04X}')
    if len(rows) < 2:
        print(f'*** only {len(rows)} calls returned through ${ret:04X}: wrong --call, or not reached ***')
        sys.exit(1)
    costs = [c for c, _, _, _, _ in rows]
    print(f'{len(rows)} calls: min {min(costs)} median {int(statistics.median(costs))} max {max(costs)} T')
    if sub:
        per = [st / sn for _, st, sn, _, _ in rows if sn]
        share = statistics.median(st / c for c, st, _, _, _ in rows)
        print(f'sub ${sub[0]:04X}: median {share:.1%} of the call'
              + (f'; T per byte min {min(per):.2f} median {statistics.median(per):.2f} max {max(per):.2f}'
                 if per else ''))
        tn, tt, tk = (sum(x[i] for x in rows) for i in (2, 1, 4))
        if tn:                          # an LDIR run of n bytes is 21n-5 T uncontended
            print(f'sub ${sub[0]:04X} pooled over {tk} runs, {tn} bytes: {tt / tn:.4f} T per byte, '
                  f'{(tt - 21 * tn + 5 * tk) / tn:.4f} over uncontended')
    groups = {}
    for c, st, _, k, _ in rows:
        groups.setdefault(k, []).append((c, c - st))
    rep = [v for v in groups.values() if len(v) > 1]
    print(f'{len(groups)} distinct keys; {len(rep)} repeat, covering {sum(map(len, rep))} calls')
    if not rep:
        print('*** no key repeats: widen the window or narrow --key ***')
        sys.exit(1)
    whole = [max(a for a, _ in v) - min(a for a, _ in v) for v in rep]
    print(f'within-key spread, whole call:  median {int(statistics.median(whole))}  max {max(whole)} T')
    if sub:
        rest = [max(b for _, b in v) - min(b for _, b in v) for v in rep]
        print(f'within-key spread, without sub: median {int(statistics.median(rest))}  max {max(rest)} T'
              f'  ({100.0 * max(rest) / statistics.median(costs):.2f}% of the median call)')


if __name__ == '__main__':
    main()
