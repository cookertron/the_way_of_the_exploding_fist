#!/usr/bin/env python3
"""srctrace.py -- how did we get HERE?  Keep a ring buffer of the last N PCs
(with SP at each) and dump it when a target PC is reached -- optionally only
when SP lies in a given range.

Written to answer "what code sets SP for the player's sprite blit?" in the
case study, whose 16x16 blitter used SP as its SOURCE pointer (a stack blit):
the condition "SP inside the sprite bank" picked out the one call per pass
that drew the player, and the ring showed the routine that computed it.  The
same shape answers any "who set this up" question.

Usage:
    python tools/srctrace.py --state NAME --pc ADDR [--sp LO HI] [--depth 60]
                             [--frames 4]
"""
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                    # noqa: E402
from harness import (Harness, FRAME_T, PC, T, IFF, SP, B as RB, C as RC,
                     D as RD, E as RE, H as RH, L as RL, TAPE_CALL_PC)   # noqa: E402


def trace(h, target_pc, depth=60, frames=4, sp_lo=None, sp_hi=None):
    """Run up to `frames` frames; return (ring, regs snapshot) at the first
    hit of target_pc satisfying the SP condition, or None."""
    sim = h.sim
    regs = sim.registers
    ops = sim.opcodes
    mem = sim.memory
    fd, ia = h.frame_duration, h.int_active
    end = regs[T] + frames * FRAME_T
    ring = deque(maxlen=depth)
    while regs[T] < end:
        pc = regs[PC]
        sp = regs[SP]
        if pc == target_pc and (sp_lo is None or sp_lo <= sp < sp_hi):
            return (list(ring), {'SP': sp, 'BC': regs[RC] + 256 * regs[RB],
                                 'DE': regs[RE] + 256 * regs[RD],
                                 'HL': regs[RL] + 256 * regs[RH]})
        ring.append((pc, sp))
        if h.deck is not None and pc == TAPE_CALL_PC:
            h._tape()
            continue
        if mem[pc] == 0x76 and regs[IFF]:
            h._fast_halt()
            continue
        ops[mem[pc]]()
        if regs[IFF] and regs[T] % fd < ia:
            sim.accept_interrupt(regs, mem, pc)
    return None


def main():
    args = sys.argv[1:]
    if '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    state = target = None
    depth, frames = 60, 4
    sp_lo = sp_hi = None
    while args:
        if args[0] == '--state':
            state = args[1]; del args[:2]
        elif args[0] == '--pc':
            target = int(args[1], 0); del args[:2]
        elif args[0] == '--sp':
            sp_lo = int(args[1], 0); sp_hi = int(args[2], 0); del args[:3]
        elif args[0] == '--depth':
            depth = int(args[1]); del args[:2]
        elif args[0] == '--frames':
            frames = int(args[1]); del args[:2]
        else:
            del args[:1]
    if state is None or target is None:
        sys.exit('give --state NAME (saved by boot.py --save) and --pc ADDR (the routine entry)')

    h = Harness()
    h.load_state_file(portconfig.state_path(state))
    hit = trace(h, target, depth, frames, sp_lo, sp_hi)
    if hit is None:
        print(f'target ${target:04X} not reached in {frames} frames'
              + (f' with SP in ${sp_lo:04X}..${sp_hi:04X}' if sp_lo is not None else ''))
        return
    ring, r = hit
    print(f'target ${target:04X}: SP=${r["SP"]:04X}  BC=${r["BC"]:04X}  '
          f'DE=${r["DE"]:04X}  HL=${r["HL"]:04X}')
    print('preceding PCs (oldest first), with SP at each:')
    for pc, s in ring:
        print(f'   ${pc:04X}  SP=${s:04X}')


if __name__ == '__main__':
    main()
