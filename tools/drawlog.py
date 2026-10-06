#!/usr/bin/env python3
"""
drawlog.py -- characterise a random source by logging every draw it returns
during driven play (manual Q18, E1).

Stops at the generator's RET (--pc), and logs register A, the caller (the
return address on the stack, less 3 for the CALL) and the frame.  Reports
what a substitute generator must reproduce:

    - each bit's set count, so a stuck bit (R bit 7 with no LD R,A) shows
    - the spread of values and the callers that draw
    - for draws in the SAME frame, the delta between consecutive draws per
      caller pair -- a constant delta means the two draws are correlated,
      and an independent substitute is wrong (E1)

Usage:
    python tools/drawlog.py --state NAME --pc 0xA401 [--frames 3000]
                            [--keys D,Z] [--first 12]
"""
import sys
import os
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Harness, A, SP
import portconfig
from keyprobe import press


def main():
    args = sys.argv[1:]
    if '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    state, pc, frames, keys, first = None, None, 3000, [], 12
    while args:
        if args[0] == '--state':
            state = args[1]; del args[:2]
        elif args[0] == '--pc':
            pc = int(args[1], 0); del args[:2]
        elif args[0] == '--frames':
            frames = int(args[1]); del args[:2]
        elif args[0] == '--keys':
            keys = [k for k in args[1].split(',') if k]; del args[:2]
        elif args[0] == '--first':
            first = int(args[1]); del args[:2]
        else:
            sys.exit(f'unknown argument {args[0]!r}; see --help')
    if state is None or pc is None:
        sys.exit('give --state NAME and --pc ADDR (the generator\'s RET)')

    h = Harness()
    h.load_state_file(portconfig.state_path(state))
    for k in keys:
        press(h.ports, k)
    fd = h.frame_duration
    end = h.tstates() + frames * fd
    log = []
    while h.tstates() < end:
        why, _ = h.run_until(pc, limit=200_000)
        if why != 'target':
            continue
        log.append((h.tstates() // fd, (h.peek16(h.regs[SP]) - 3) & 0xFFFF,
                    h.regs[A]))
        h.step(1)

    print(f'draws at ${pc:04X} over {frames} frames of {state}: {len(log)}')
    if not log:
        return
    print('bit set counts (7..0):',
          ' '.join(str(sum(1 for *_, a in log if a >> b & 1))
                   for b in range(7, -1, -1)))
    print('distinct values:', len(set(a for *_, a in log)))
    print('callers:', ' '.join(f'${c:04X}x{n}' for c, n in
                               sorted(Counter(c for _, c, _ in log).items())))
    # with bit 7 stuck clear (R with no LD R,A) a source wraps in 7 bits
    mod = 0x80 if not any(a & 0x80 for *_, a in log) else 0x100
    pairs = defaultdict(Counter)
    for (f0, c0, a0), (f1, c1, a1) in zip(log, log[1:]):
        if f0 == f1:
            pairs[(c0, c1)][(a1 - a0) % mod] += 1
    print(f'\n-- same-frame consecutive draws: delta (mod {mod}) x count --')
    for (c0, c1), d in sorted(pairs.items()):
        print(f'  ${c0:04X} -> ${c1:04X}  ' +
              ' '.join(f'{k}x{n}' for k, n in sorted(d.items())))
    print(f'\n-- first {first} --')
    for f, c, a in log[:first]:
        print(f'  frame {f}  ${c:04X}  ${a:02X}')


if __name__ == '__main__':
    main()
