#!/usr/bin/env python3
"""
dataread.py -- log DATA reads only, with instruction fetches filtered out.

readwatch.py counts every read in a window, so code and operand fetches drown
the data reads you care about (a tile-map lookup, a table index).  This logs a
read of address A at PC only when A is NOT one of the current instruction's own
bytes (A outside [PC, PC+3]) -- so what remains is genuine data access.  It is
how you find a collision map or a table that the physics reads: the hot data
target read by a physics PC.

Stack reads are filtered too: a POP, RET or EX (SP) reads the two bytes at SP,
and in a game whose stack sits inside the window those were the hottest
"data" of all (Starfox's attract mode: $FF76-$FF79, read by POP BC / RET).
They are counted and reported separately.

SELF-CHECK: prints kept (data) reads as a fraction of all reads in the window;
if ~everything is kept, either the filter is not doing its job or the window
holds no code (the game runs elsewhere) -- say which.  --verify makes it a
GATE for a game with a known structure and exits non-zero on failure:
  --verify ADDR      ADDR must be among the top data addresses (a scalar or a
                     fixed scratch slot: Bubble Bobble's $96D9);
  --verify LO HI     the range must take at least --verify-share percent of
                     the data reads (default 1.0).  Use this for a buffer or
                     a map: the physics reads the cells AROUND the player, so
                     no single address of a 672-byte level buffer is ever hot
                     (Chuckie Egg's $61A8-$6447: 2.2% of reads, top address
                     rank > 60) -- the exact-address form cannot pass there.

Usage (measure a LIVE state; a raw snapshot needs --arm/--warm to reach code):
    python tools/dataread.py --state NAME    [--lo A --hi B] [--keys 8] [--exclude LO HI]..
                                             [--verify ADDR | --verify LO HI] [--verify-share PCT]
    python tools/dataread.py --snapshot G.z80 --arm --warm 400 --lo 0x6000 --hi 0xC000
"""
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from harness import PC, SP, T, IFF                                  # noqa: E402
from keyprobe import press                                         # noqa: E402
from probeutil import parse_target, boot_target, source_label, TARGET_HELP  # noqa: E402


class DataMem:
    __slots__ = ('m', 'sim', 'lo', 'hi', 'excl', 'by_addr', 'pairs', 'on', 'total',
                 'stack_by_addr', 'stack_pairs')

    def __init__(self, m, sim, lo, hi, excl):
        self.m, self.sim, self.lo, self.hi, self.excl = m, sim, lo, hi, excl
        self.by_addr = Counter()             # data-class reads: LD, ADD, CP ... from memory
        self.pairs = defaultdict(Counter)
        self.stack_by_addr = Counter()       # stack-class reads: the two bytes at SP (POP / RET / EX (SP))
        self.stack_pairs = defaultdict(Counter)
        self.on = True
        self.total = 0                       # every read in the window (fetches included)

    def __len__(self):
        return 0x10000

    def __getitem__(self, i):
        if self.on and self.lo <= i < self.hi:
            self.total += 1
            regs = self.sim.registers
            pc = regs[PC]
            if not (pc <= i <= pc + 3) and not any(a <= i < b for a, b in self.excl):
                if ((i - regs[SP] + 2) & 0xFFFF) < 4:   # SP-2..SP+1: the simulator bumps SP before a POP/RET reads
                    self.stack_by_addr[i] += 1
                    self.stack_pairs[pc][i] += 1
                else:
                    self.by_addr[i] += 1
                    self.pairs[pc][i] += 1
        return self.m[i]

    def __setitem__(self, i, v):
        if i >= 0x4000:
            self.m[i] = v

    def __iter__(self):
        return iter(self.m)


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    t = parse_target(args)
    lo, hi = 0x5B00, 0x10000
    frames, top = 30, 25
    keys, excl = [], []
    verify = None
    share_min = 1.0
    while args:
        if args[0] == '--lo':
            lo = int(args[1], 0); del args[:2]
        elif args[0] == '--hi':
            hi = int(args[1], 0); del args[:2]
        elif args[0] == '--frames':
            frames = int(args[1], 0); del args[:2]
        elif args[0] == '--keys':
            keys = [k.strip() for k in args[1].split(',') if k.strip()]; del args[:2]
        elif args[0] == '--exclude':
            excl.append((int(args[1], 0), int(args[2], 0))); del args[:3]
        elif args[0] == '--top':
            top = int(args[1], 0); del args[:2]
        elif args[0] == '--verify':
            if len(args) > 2 and not args[2].startswith('--'):
                verify = (int(args[1], 0), int(args[2], 0)); del args[:3]
            else:
                verify = int(args[1], 0); del args[:2]
        elif args[0] == '--verify-share':
            share_min = float(args[1]); del args[:2]
        else:
            sys.exit(f'dataread: unknown argument {args[0]}  (target: {TARGET_HELP})')
    h = boot_target(t, 'dataread')
    for k in keys:
        press(h.ports, k)
    rm = DataMem(h.memobj.m, h.sim, lo, hi, excl)
    h.sim.memory = rm
    h.sim.create_opcodes()
    h.sim.set_tracer(h.ports)
    sim, regs, ops = h.sim, h.sim.registers, h.sim.opcodes
    fd, ia = h.frame_duration, h.int_active
    end = regs[T] + frames * fd
    while regs[T] < end:
        pc = regs[PC]
        rm.on = False
        op = rm.m[pc]
        rm.on = True
        if op == 0x76 and regs[IFF]:
            h._fast_halt(); continue
        ops[op]()
        if regs[IFF] and regs[T] % fd < ia:
            sim.accept_interrupt(regs, rm.m, pc)
    kept = sum(rm.by_addr.values())
    stack = sum(rm.stack_by_addr.values())
    print(f'DATA reads (fetches filtered) in ${lo:04X}-${hi:04X} over {frames} frames from '
          f'{source_label(t)}' + (f', keys {keys}' if keys else '') + ':')
    fetches = rm.total - kept - stack
    print(f'  kept {kept} data reads of {rm.total} total ({100.0 * kept / max(rm.total, 1):.1f}%); '
          f'{fetches} instruction/operand fetches filtered; {stack} stack-class reads (POP/RET/EX (SP)) listed apart'
          + ('  -- NOTE no fetches in the window: the code runs outside it, so the ratio says nothing'
             if rm.total and fetches == 0 else ''))
    print('  top target addresses:')
    for a, n in rm.by_addr.most_common(top):
        print(f'    ${a:04X}  x{n}')
    print('  top (reader PC -> its hottest data targets):')
    hot_pc = sorted(rm.pairs.items(), key=lambda kv: -sum(kv[1].values()))[:top]
    for pc, tgts in hot_pc:
        top3 = ' '.join(f'${a:04X}x{c}' for a, c in tgts.most_common(3))
        print(f'    ${pc:04X}  x{sum(tgts.values()):-5d}  -> {top3}')
    if stack:
        print(f'  stack-class reads (POP/RET/EX (SP) at SP): {stack} -- the call stack, or SP parked on data '
              f'(manual 3.10; Bubble Bobble reads its $96D1-$96DA scratch this way).  top:')
        for a, n in rm.stack_by_addr.most_common(min(top, 8)):
            readers = ' '.join(f'${pc:04X}x{c}' for pc, c in
                               sorted(((pc, cs[a]) for pc, cs in rm.stack_pairs.items() if cs[a]), key=lambda kv: -kv[1])[:2])
            print(f'    ${a:04X}  x{n}   by {readers}')
    if verify is None:
        return
    if isinstance(verify, tuple):
        vlo, vhi = verify
        in_data = sum(n for a, n in rm.by_addr.items() if vlo <= a < vhi)
        in_stack = sum(n for a, n in rm.stack_by_addr.items() if vlo <= a < vhi)
        distinct = len({a for a in list(rm.by_addr) + list(rm.stack_by_addr) if vlo <= a < vhi})
        share_d = 100.0 * in_data / max(kept, 1)
        share_s = 100.0 * in_stack / max(stack, 1)
        found = (share_d >= share_min and in_data > 0) or (share_s >= share_min and in_stack > 0)
        how = ('data-class' if share_d >= share_min and in_data else
               'stack-class (SP parked on it)' if found else 'neither class')
        print(f'\nverify ${vlo:04X}-${vhi - 1:04X}: {in_data} data-class reads ({share_d:.2f}% of data reads) and '
              f'{in_stack} stack-class reads ({share_s:.2f}% of stack-class reads) at {distinct} addresses; '
              f'threshold {share_min}%: {"PASS" if found else "FAIL"} ({how})')
    else:
        rank_d = next((i + 1 for i, (a, _) in enumerate(rm.by_addr.most_common()) if a == verify), None)
        rank_s = next((i + 1 for i, (a, _) in enumerate(rm.stack_by_addr.most_common()) if a == verify), None)
        found = (rank_d is not None and rank_d <= top) or (rank_s is not None and rank_s <= top)
        print(f'\nverify ${verify:04X}: data-class rank {rank_d or "unread"}, stack-class rank {rank_s or "unread"} '
              f'(top {top}): ' + ('PASS' + (' -- read with SP parked on it (POP/RET/EX (SP)), manual 3.10'
                                            if not (rank_d and rank_d <= top) else '') if found else 'FAIL'))
    sys.exit(0 if found else 1)


if __name__ == '__main__':
    main()
