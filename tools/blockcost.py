#!/usr/bin/env python3
"""
blockcost.py -- T-states and R increments per instruction, measured.

A hand port that tallies T (D3) or tracks R (the game's only random source,
ledger/A3FF.toml) needs each instruction's cost on each path.  Reading them
from a table is an assumption; this executes every instruction once in an
UNCONTENDED SkoolKit Simulator (the callio.py twin's config) over the image,
with F = $00 and again with F = $FF, and prints per instruction:

  T      the T-states taken, as "fall/taken" when the two flag states
         differ (a conditional JR/JP/CALL/RET): the first is the fall-through
         to the next instruction, the second the branch;
  R      how much R advanced (M1 cycles: 1, or 2 for a CB/DD/ED/FD prefix);
  sumT   running totals from the first address, along the fall-through.
  sumR

DJNZ and the block repeats (LDIR ...) are shown as "Nr/M": N per repeat,
M for the last pass (B = 1 / BC = 1); the sums take the last pass.  CALLs
cost the CALL alone; the callee is its own block.

Usage:
    python tools/blockcost.py ADDR [END] [--image F]   every instruction in ADDR..END
    python tools/blockcost.py 0xA090 0xA0BD
"""
import os
import sys

import z80dis.z80 as z

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portconfig                                                  # noqa: E402
from harness import Simulator, PC, T, R                            # noqa: E402

FLAT = {'fast_djnz': False, 'fast_ldir': False}
F, B, C = 1, 2, 3                                                  # SkoolKit register indices
REPEATS = ('djnz', 'ldir', 'lddr', 'cpir', 'cpdr', 'inir', 'indr', 'otir', 'otdr')


def once(data, pc, f, b=0x02, c=0x00):
    sim = Simulator(bytearray(data), config=FLAT)
    r = sim.registers
    r[PC], r[F], r[B], r[C], r[T], r[R] = pc, f, b, c, 0, 0
    sim.opcodes[sim.memory[pc]]()
    return r[T], r[R] & 0x7F, r[PC]


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    image = portconfig.get('z80', 'image') or 'build/image.bin'
    if '--image' in args:
        i = args.index('--image'); image = args[i + 1]; del args[i:i + 2]
    lo = int(args[0], 0)
    hi = int(args[1], 0) if len(args) > 1 else lo
    data = bytes(open(image, 'rb').read()[:0x10000].ljust(0x10000, b'\0'))
    pc, st, sr = lo, 0, 0
    print(f'{"addr":<6}{"instruction":<24}{"T":>8}{"R":>4}{"sumT":>7}{"sumR":>6}')
    while pc <= hi:
        ins = z.decode(data[pc:pc + 4], pc)
        nxt = (pc + ins.len) & 0xFFFF
        text = z.disasm(ins)
        a, b = once(data, pc, 0x00), once(data, pc, 0xFF)
        rep = None
        if text.split(' ')[0].lower() in REPEATS:
            last = once(data, pc, 0x00, b=0x01, c=0x01) if text.lower().startswith('djnz') \
                else once(data, pc, 0x00, b=0x00, c=0x01)
            rep, a, b = (a[0], last[0]), last, last
        if a[2] == nxt and b[2] != nxt:
            fall, take = a, b
        elif b[2] == nxt and a[2] != nxt:
            fall, take = b, a
        else:
            fall, take = a, None
        tcol = f'{fall[0]}/{take[0]}' if take else (f'{rep[0]}r/{rep[1]}' if rep else f'{fall[0]}')
        st += fall[0]; sr += fall[1]
        print(f'{pc:04X}  {text:<24}{tcol:>8}{fall[1]:>4}{st:>7}{sr:>6}')
        pc = nxt


if __name__ == '__main__':
    main()
