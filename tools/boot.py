#!/usr/bin/env python3
"""
boot.py -- boot the original in the harness, optionally drive it with a key
script, and dump the LIVE memory image and/or a saved machine state.

A game may relocate itself at start-up (in the case study, five LDIR/LDDR
blocks from $BDED onwards), in which case the static block-copy image is NOT
the runtime layout and disassembling it gives plausible nonsense in the moved
regions.  Everything downstream should disassemble against the live image
produced here.

The saved state (--save) is what the phase-8 tools resume from: filmstrip,
readwatch, battery, blitprobe, srctrace and clock all take --state NAME.
Save one at the menu, one at a live level, and so on; restoring is exact
(manual 6.4: boot once, then poke).

Usage:
    python tools/boot.py [--steps N] [--ints] [--script "40:,60:SPACE,120:1"]
                         [--out FILE] [--save NAME]

--steps N   run N instructions first (default 400000; interrupts per --ints,
            default OFF)
--script    then hold keys for frames with interrupts ON: FRAMES:KEY+KEY,...
            (names as keyprobe.py prints them: A..Z 0..9 SPACE ENTER CAPS SYM)
--out       write the 64K image (default live.bin in z80.states)
--save      also pickle the full machine state as NAME.pkl in z80.states
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                   # noqa: E402
from harness import Harness, CPU_HZ, top, I, IM, IFF, SP, T         # noqa: E402
from keyprobe import parse_script, drive                            # noqa: E402


def main():
    args = sys.argv[1:]
    if '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    steps = 400_000
    out = save = None
    ints = False
    script = []
    while args:
        if args[0] == '--steps':
            steps = int(args[1], 0); del args[:2]
        elif args[0] == '--out':
            out = args[1]; del args[:2]
        elif args[0] == '--save':
            save = args[1]; del args[:2]
        elif args[0] == '--script':
            script = parse_script(args[1]); del args[:2]
        elif args[0] == '--ints':
            ints = True; del args[:1]
        else:
            del args[:1]
    out = out or os.path.join(portconfig.path(portconfig.get('z80', 'states')), 'live.bin')

    h = Harness()
    for line in h.image_lines:
        print(line)
    hist = h.profile(steps, interrupts=ints) if steps else {}
    if script:
        drive(h, script)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    open(out, 'wb').write(bytes(h.memobj.m))
    print(f'ran {steps} instructions (interrupts {"ON" if ints else "OFF"})'
          + (f', then script {script}' if script else ''))
    print(f'PC=${h.pc():04X}  SP=${h.regs[SP]:04X}  I=${h.regs[I]:02X}  '
          f'IM={h.regs[IM]}  IFF={h.regs[IFF]}  T={h.regs[T]} ({h.regs[T]/CPU_HZ:.3f}s)')
    print(f'ports read: {sorted("$%04X" % p for p in h.ports.reads)}')
    print(f'writes into ROM (ignored): {h.memobj.rom_writes}')
    if hist:
        print('hot addresses:')
        for a, c in top(hist, 25):
            print(f'  ${a:04X}  {c}')
    print(f'wrote {out}')
    if save:
        p = portconfig.state_path(save)
        h.save_state_file(p)
        print(f'saved state {p}')


if __name__ == '__main__':
    main()
