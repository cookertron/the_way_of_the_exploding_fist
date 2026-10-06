#!/usr/bin/env python3
"""
callio.py -- what ONE routine reads and writes, measured over driven play.

Before a routine is ported, its interface is recorded (manual 5.1, 12.2):
the bytes it takes as inputs and the bytes it changes.  Reading that off the
disassembly misses the indexed reads (a table at HL+D) and the writes behind
a callee.  This brackets one CALL site and its return over driven play and
runs every call once more in an UNCONTENDED twin over a logging memory, as
rendfx.py does for $BF13:

  inputs   bytes read before the call wrote them -- instruction and operand
           fetches and the call's own stack frames
           (SP at entry - 128 .. SP + 1) excepted;
  outputs  every byte written outside the stack frames, with how many
           distinct values each took;
  code     the PCs executed, as runs -- the routine's extent including the
           callees it reached, and the paths that driven play never took
           (compare with adis).

Per address it reports in how many calls it was touched and the first PC
that touched it, so a run of the table points back at the instruction.  An
input that is also an output is a state variable the routine carries.

Fetches are the current instruction's own bytes, [PC, PC + length) with
the length decoded by z80dis -- not dataread.py's [PC, PC+3] window, which
drops DEC (HL) at $9CA3 reading Time at $9CA5.  The self-check line prints
how many reads were fetches.

Usage:
    python tools/callio.py --state NAME --call SITE RET [--frames 1500] [--keys D+W]
                           [--only in|out|code] [--gap N]
    python tools/callio.py --state s1 --call 0x9745 0x9748
"""
import os
import statistics
import sys

import z80dis.z80 as z

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Simulator, SP, PC, T                           # noqa: E402
from keyprobe import press                                         # noqa: E402
from probeutil import parse_target, boot_target, source_label, TARGET_HELP  # noqa: E402

FLAT = {'fast_djnz': False, 'fast_ldir': False}


class Logged:
    """Memory that logs data reads before any write, and every write,
    against the twin's registers; ROM writes are dropped as on the machine."""
    def __init__(self, data, stack):
        self.m = bytearray(data)
        self.regs = None
        self.stack = stack
        self.reads = {}            # addr -> first PC that read it before any write
        self.writes = {}           # addr -> first PC that wrote it
        self.fetches = 0
        self.lens = {}             # (pc, first 4 bytes) -> instruction length

    def __len__(self):
        return 0x10000

    def __getitem__(self, a):
        pc = self.regs[PC]
        if pc <= a < pc + 4 and a < pc + self.length(pc):
            self.fetches += 1
        elif a not in self.writes and a not in self.reads and a not in self.stack:
            self.reads[a] = pc
        return self.m[a]

    def length(self, pc):
        key = bytes(self.m[pc:pc + 4])
        n = self.lens.get((pc, key))
        if n is None:
            n = self.lens[pc, key] = z.decode(key, pc).len
        return n

    def __setitem__(self, a, v):
        if a >= 0x4000:
            if a not in self.writes and a not in self.stack:
                self.writes[a] = self.regs[PC]
            self.m[a] = v

    def __iter__(self):
        return iter(self.m)


def run_alone(mem, regs, ret, limit=20_000_000):
    sim = Simulator(mem, config=FLAT)
    sim.registers[:] = regs
    r, ops, t0 = sim.registers, sim.opcodes, regs[T]
    mem.regs = r
    pcs = set()
    for _ in range(limit):
        pc = r[PC]
        if pc == ret:
            return r[T] - t0, pcs
        pcs.add(pc)
        ops[mem.m[pc]]()
    sys.exit(f'callio: call never returned to ${ret:04X}')


def runs(addrs):
    out, lo, prev = [], None, None
    for a in sorted(addrs):
        if lo is None:
            lo = prev = a
        elif a == prev + 1:
            prev = a
        else:
            out.append((lo, prev)); lo = prev = a
    if lo is not None:
        out.append((lo, prev))
    return out


def table(title, touched, firstpc, extra=None, gap=None):
    """touched: addr -> calls; firstpc: addr -> PC.  Contiguous addresses
    that share a call count are one row; with gap, addresses within gap
    bytes of each other are one row whatever their counts (a table read at
    an index: the range of counts and the PCs that read it are shown)."""
    print(f'{title}: {len(touched)} bytes')
    rows, cur = [], None
    for a in sorted(touched):
        n = touched[a]
        if cur and (a <= cur[1] + gap if gap is not None else a == cur[1] + 1 and n == cur[2]):
            cur[1] = a
            cur[2], cur[3] = min(cur[2], n), max(cur[3], n)
            cur[4].setdefault(firstpc[a], None)
        else:
            cur = [a, a, n, n, {firstpc[a]: None}]; rows.append(cur)
    for lo, hi, n0, n1, pcs in rows:
        span = f'${lo:04X}' if lo == hi else f'${lo:04X}-${hi:04X}'
        calls = f'{n0}' if n0 == n1 else f'{n0}-{n1}'
        at = ' '.join(f'${pc:04X}' for pc in list(pcs)[:4]) + (' ...' if len(pcs) > 4 else '')
        more = f'  {extra(lo, hi)}' if extra else ''
        print(f'  {span:<13} {calls:>8} calls  first at {at}{more}')


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    t = parse_target(args)
    site = ret = None
    frames, keys, only, gap = 1500, [], None, None
    while args:
        a = args[0]
        if a == '--call':
            site, ret = int(args[1], 0), int(args[2], 0); del args[:3]
        elif a == '--frames':
            frames = int(args[1], 0); del args[:2]
        elif a == '--keys':
            keys = args[1].split('+'); del args[:2]
        elif a == '--gap':
            gap = int(args[1], 0); del args[:2]
        elif a == '--only':
            only = args[1]; del args[:2]
        else:
            sys.exit(f'callio: unknown argument {a}  (target: {TARGET_HELP})')
    if site is None:
        sys.exit('callio: need --call SITE RET')
    h = boot_target(t, 'callio')
    r, m = h.regs, h.memobj.m
    for k in keys:
        press(h.ports, k)
    ins, outs, firstin, firstout, vals, code = {}, {}, {}, {}, {}, set()
    ts, calls, fetches = [], 0, 0
    end = r[T] + frames * h.frame_duration
    while r[T] < end:
        reason, _ = h.run_until([site], limit=200_000)
        if reason != 'target':
            continue
        sp = r[SP]
        lm = Logged(bytes(m), {a & 0xFFFF for a in range(sp - 128, sp + 2)})
        dt, pcs = run_alone(lm, list(r), ret)
        h.run_until([ret], limit=20_000_000)           # the real call, interrupts on
        calls += 1
        ts.append(dt)
        fetches += lm.fetches
        code |= pcs
        for a, pc in lm.reads.items():
            ins[a] = ins.get(a, 0) + 1
            firstin.setdefault(a, pc)
        for a, pc in lm.writes.items():
            outs[a] = outs.get(a, 0) + 1
            firstout.setdefault(a, pc)
            vals.setdefault(a, set()).add(lm.m[a])
    if not calls:
        sys.exit(f'callio: ${site:04X} never reached in {frames} frames')
    print(f'callio: ${site:04X} -> ${ret:04X}, {source_label(t)}, {frames} frames'
          + (f', keys {"+".join(keys)}' if keys else '') + f': {calls} calls, '
          f'uncontended T min {min(ts)} median {int(statistics.median(ts))} max {max(ts)}')
    print(f'self-check: {fetches} reads dropped as fetches; {len(ins)} input and {len(outs)} output bytes kept')
    if only in (None, 'code'):
        print(f'code: {len(code)} PCs executed in ' + ' '.join(
            f'${lo:04X}' if lo == hi else f'${lo:04X}-${hi:04X}' for lo, hi in runs(code)))
    if only in (None, 'in'):
        table('inputs (read before written)', ins, firstin,
              lambda lo, hi: 'also written' if any(a in outs for a in range(lo, hi + 1)) else '', gap)
    if only in (None, 'out'):
        table('outputs (written)', outs, firstout,
              lambda lo, hi: 'values ' + '/'.join(str(len(vals[a])) if a in vals else '-'
                                                  for a in range(lo, min(hi, lo + 7) + 1))
              + ('...' if hi > lo + 7 else ''), gap)


if __name__ == '__main__':
    main()
