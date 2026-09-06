#!/usr/bin/env python3
"""
chaincost.py -- the T-state cost of each CALL in a dispatch chain, per pass.

Phase 9 (manual B2, Q11): "measure the cost of EACH PATH separately".  A
free-running main loop is a chain of CALLs; the pass cost is bimodal because
some routines take a long path on some passes.  This brackets every CALL in a
PC range (each CALL's site and its return address) while stepping driven play
and reports, per routine: passes, min / median / mean / max T, and the biggest
modes -- which names the routine that owns the long pass, without a variable map.

SELF-CHECK: the sum of the per-routine medians is printed against the MEASURED
pass period (median T between successive visits to the first CALL). The sum
should be a little under the period (the remainder is loop glue / dispatch); if
it exceeds it, the --range is wrong (overlapping or non-chain CALLs).

Usage (measure a LIVE state; a raw snapshot needs --arm/--warm to reach code):
    python tools/chaincost.py --state NAME    --range LO HI [--frames N] [--script "60:8"]
    python tools/chaincost.py --snapshot G.z80 --arm --warm 400 --range LO HI [--frames N]
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from harness import PC                                             # noqa: E402
from keyprobe import parse_script, press                          # noqa: E402
from probeutil import parse_target, boot_target, source_label, TARGET_HELP  # noqa: E402

T = 25


def find_calls(mem, lo, hi):
    """Every 'CALL nn' (CD) in [lo, hi): (site, target, return)."""
    out = []
    a = lo
    while a < hi:
        if mem[a] == 0xCD:
            tgt = mem[a + 1] | (mem[a + 2] << 8)
            out.append((a, tgt, a + 3))
            a += 3
        else:
            a += 1                  # good enough for a linear chain of CALLs
    return out


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    t = parse_target(args)
    script = None
    lo = hi = None
    frames = 200
    while args:
        if args[0] == '--range':
            lo, hi = int(args[1], 0), int(args[2], 0); del args[:3]
        elif args[0] == '--frames':
            frames = int(args[1], 0); del args[:2]
        elif args[0] == '--script':
            script = parse_script(args[1]); del args[:2]
        else:
            sys.exit(f'chaincost: unknown argument {args[0]}  (target: {TARGET_HELP})')
    if lo is None:
        sys.exit('chaincost: --range LO HI is required')
    h = boot_target(t, 'chaincost')
    m, r = h.memobj.m, h.regs
    calls = find_calls(m, lo, hi)
    if not calls:
        sys.exit(f'chaincost: no CALL nn in ${lo:04X}-${hi:04X}')
    sites = {site: (tgt, ret) for site, tgt, ret in calls}
    rets = {ret: site for site, tgt, ret in calls}
    first = calls[0][0]
    print(f'{len(calls)} CALLs in ${lo:04X}-${hi:04X} from {source_label(t)}:')
    for site, tgt, ret in calls:
        print(f'  ${site:04X}  CALL ${tgt:04X}')
    costs = {site: [] for site in sites}
    open_t = {}
    pass_t = []                         # T at each visit to the first CALL site
    fd = h.frame_duration
    if script:
        frames = sum(s[0] for s in script)
    segs = script or [(frames, [])]
    seg_i = 0
    for k in segs[0][1]:
        press(h.ports, k)
    t_end = r[T] + frames * fd
    while r[T] < t_end:
        pc = r[PC]
        if pc in rets:                  # close the previous CALL first: in a chain,
            site = rets[pc]             # each return address IS the next CALL site
            if site in open_t:
                costs[site].append(r[T] - open_t.pop(site))
        if pc in sites:
            if pc == first:
                pass_t.append(r[T])
            open_t[pc] = r[T]
        h.step(1, interrupts=True)
        if seg_i < len(segs) - 1 and r[T] >= t_end - sum(s[0] for s in segs[seg_i + 1:]) * fd:
            seg_i += 1
            h.ports.release_all()
            for k in segs[seg_i][1]:
                press(h.ports, k)
    passes = len(pass_t)
    print(f'\n{passes} passes over {frames} frames ({passes / frames:.2f} passes/frame)')
    print('site    routine   n     min    median   mean     max   | top modes (T x count)')
    total_med = 0
    for site, tgt, ret in calls:
        c = costs[site]
        if not c:
            print(f'${site:04X}  ${tgt:04X}   never returned through ${ret:04X}')
            continue
        buckets = {}
        for v in c:
            b = (v // 50) * 50
            buckets[b] = buckets.get(b, 0) + 1
        modes = ' '.join(f'{b}x{n}' for b, n in sorted(buckets.items(), key=lambda kv: -kv[1])[:3])
        med = statistics.median(c)
        total_med += med
        print(f'${site:04X}  ${tgt:04X}  {len(c):5d}  {min(c):6d}  {int(med):6d}  '
              f'{int(statistics.mean(c)):6d}  {max(c):6d}  | {modes}')
    period = None
    if len(pass_t) > 2:
        deltas = [pass_t[i + 1] - pass_t[i] for i in range(len(pass_t) - 1)]
        period = statistics.median(deltas)
    print(f'\nsum of per-routine medians {int(total_med)} T')
    never = [site for site, tgt, ret in calls if not costs[site]]
    if not period:
        print(f'*** only {passes} passes through the first CALL site ${first:04X}: this is not a running chain '
              f'(wrong --range, a conditional first CALL, or the state is not in this loop) ***')
        sys.exit(1)
    frac = 100.0 * total_med / period
    ok = total_med <= period * 1.05
    print(f'measured pass period {int(period)} T (median between visits to ${first:04X})'
          f'  -> routines are {frac:.0f}% of the pass, {int(period - total_med)} T is glue/dispatch'
          f'  {"OK" if ok else "*** sum EXCEEDS the pass -- the --range is not a clean chain ***"}'
          + (f'  ({len(never)} CALL sites never returned: not a linear chain)' if never else ''))
    sys.exit(0 if ok and not never else 1)


if __name__ == '__main__':
    main()
