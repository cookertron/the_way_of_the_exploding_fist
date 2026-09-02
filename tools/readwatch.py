#!/usr/bin/env python3
"""
readwatch.py -- find working-RAM structures by watching MEMORY READS during
driven play, grouped by reading PC and by target region.

This is the complement to the manual's two discovery techniques (8.2): content
search needs bytes you have already decoded, and transition diff finds
variables that CHANGE.  A read-watch finds buffers that are only ever READ by
the renderer -- which is exactly what a level map is.

Usage:
    python tools/readwatch.py --state NAME [--lo 0x4000] [--hi 0x10000]
                              [--frames 40] [--keys D,Z]

Operand fetches count as reads, so a window that includes the code shows the
code pages lighting up; narrow --lo/--hi to the data side once you know where
the code is.
"""
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                             # noqa: E402
from harness import Harness, FRAME_T, PC, T, IFF, TAPE_CALL_PC   # noqa: E402
from keyprobe import KEYS, keymask, KEYMAP, press             # noqa: E402


class ReadMem:
    __slots__ = ('m', 'sim', 'lo', 'hi', 'by_pc', 'by_addr', 'pairs', 'on')

    def __init__(self, m, sim, lo, hi):
        self.m = m
        self.sim = sim
        self.lo = lo
        self.hi = hi
        self.by_pc = Counter()
        self.by_addr = Counter()
        self.pairs = defaultdict(Counter)
        self.on = True

    def __len__(self):
        return 0x10000

    def __getitem__(self, i):
        if self.on and self.lo <= i < self.hi:
            pc = self.sim.registers[PC]
            self.by_pc[pc] += 1
            self.by_addr[i] += 1
            self.pairs[pc][i & 0xFF00] += 1
        return self.m[i]

    def __setitem__(self, i, v):
        if i >= 0x4000:
            self.m[i] = v

    def __iter__(self):
        return iter(self.m)


def watch(h, rm, frames):
    """Run `frames` video frames with `rm` installed as the simulator's memory.
    The opcodes are re-created so they bind the new object (a plain
    assignment to sim.memory would be ignored by the already-built partials)."""
    h.sim.memory = rm
    h.sim.create_opcodes()
    h.sim.set_tracer(h.ports)
    sim = h.sim
    regs = sim.registers
    ops = sim.opcodes
    fd, ia = h.frame_duration, h.int_active
    end = regs[T] + frames * FRAME_T
    while regs[T] < end:
        pc = regs[PC]
        if h.deck is not None and pc == TAPE_CALL_PC:
            h._tape(); continue
        rm.on = False
        op = rm.m[pc]
        rm.on = True
        if op == 0x76 and regs[IFF]:
            h._fast_halt(); continue
        ops[op]()
        if regs[IFF] and regs[T] % fd < ia:
            sim.accept_interrupt(regs, rm.m, pc)


def main():
    args = sys.argv[1:]
    if '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    lo, hi = 0x4000, 0x10000
    frames = 40
    state = None
    keys = []
    while args:
        if args[0] == '--lo':
            lo = int(args[1], 0); del args[:2]
        elif args[0] == '--hi':
            hi = int(args[1], 0); del args[:2]
        elif args[0] == '--frames':
            frames = int(args[1]); del args[:2]
        elif args[0] == '--state':
            state = args[1]; del args[:2]
        elif args[0] == '--keys':
            keys = [k for k in args[1].split(',') if k]; del args[:2]
        else:
            del args[:1]
    if state is None:
        sys.exit('give --state NAME: a machine state saved by boot.py --save')

    h = Harness()
    h.load_state_file(portconfig.state_path(state))
    for k in keys:
        press(h.ports, k)

    rm = ReadMem(h.memobj.m, h.sim, lo, hi)
    watch(h, rm, frames)

    print(f'reads in ${lo:04X}-${hi:04X} over {frames} frames: '
          f'{sum(rm.by_pc.values())}')
    print('\n-- by 256-byte page --')
    pages = Counter()
    for a, n in rm.by_addr.items():
        pages[a & 0xFF00] += n
    for p, n in sorted(pages.items()):
        print(f'  ${p:04X}xx  {n:>8}  {"#" * min(60, n // 200)}')
    print('\n-- by reading PC (top 25) --')
    for pc, n in rm.by_pc.most_common(25):
        rng = rm.pairs[pc].most_common(3)
        print(f'  ${pc:04X}  x{n:<7} pages ' +
              ' '.join(f'${p:04X}xx({c})' for p, c in rng))
    lows = sorted(a for a in rm.by_addr)
    if lows:
        print(f'\naddress span actually touched: ${lows[0]:04X}..${lows[-1]:04X}')


if __name__ == '__main__':
    main()
