#!/usr/bin/env python3
"""
snapimport.py -- bring a .z80/.szx/.sna snapshot into the harness world.

The SNAPSHOT ROUTE (manual 6.1, Q1): for a custom loader the post-loader
image is not built by copying blocks but by letting the real loader run in a
full simulation (SkoolKit's tap2sna.py, see simload.py) and taking a snapshot
at the hand-over.  This tool boots that snapshot in the kit's Harness and
writes what every phase-8 tool consumes:

    build/image.bin      the 64K image (real 48K ROM at $0000-$3FFF, read
                         locally from SkoolKit; the RAM from the snapshot) --
                         what adis.py / walk.py / grepbytes.py disassemble
    build/NAME.pkl       a saved harness state (--save NAME), resumable by
                         every --state tool (boot.py, battery.py, clock.py...)

It also prints the machine state the snapshot carries (PC, SP, IM, IFF, I,
border, T-states): the loader's postcondition, which phase 2 records.

Usage:
    python tools/snapimport.py SNAPSHOT [--image build/image.bin] [--save NAME]
                               [--run-to ADDR [--limit N]]

--run-to ADDR   step (interrupts off) until PC == ADDR before saving -- for a
                snapshot taken a little BEFORE the hand-over (tap2sna stops at
                the end of the tape; the loader's last block may still be in
                flight).  The definitive snapshot is better taken with
                simload.py --start ADDR once ADDR is known.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                   # noqa: E402
from harness import Harness, PC, SP, I, IM, IFF, T, CPU_HZ            # noqa: E402


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    image = save = run_to = None
    limit = 5_000_000
    pos = []
    while args:
        if args[0] == '--image':
            image = args[1]; del args[:2]
        elif args[0] == '--save':
            save = args[1]; del args[:2]
        elif args[0] == '--run-to':
            run_to = int(args[1], 0); del args[:2]
        elif args[0] == '--limit':
            limit = int(args[1], 0); del args[:2]
        else:
            pos.append(args[0]); del args[:1]
    if len(pos) != 1:
        sys.exit('snapimport: exactly one snapshot path, please')
    snap = pos[0]
    image = image or portconfig.path(portconfig.get('z80', 'image'))

    h = Harness(snapshot=snap, deck=False)
    print(h.image_lines[0])
    if run_to is not None:
        reason, steps = h.run_until([run_to], limit=limit, interrupts=False)
        print(f'run-to ${run_to:04X}: {reason} after {steps} instructions')
        if reason != 'target':
            sys.exit('snapimport: did not reach the address; not saving')
    r = h.regs
    print(f'PC=${r[PC]:04X} SP=${r[SP]:04X} I=${r[I]:02X} IM={r[IM]} IFF={r[IFF]} '
          f'T={r[T]} ({r[T]/CPU_HZ:.3f}s) border={h.border}')
    os.makedirs(os.path.dirname(image) or '.', exist_ok=True)
    open(image, 'wb').write(bytes(h.memobj.m))
    print(f'wrote {image} (65536 bytes; the ROM area is SkoolKit 48.rom, local only)')
    if save:
        p = portconfig.state_path(save)
        h.save_state_file(p)
        print(f'saved state {p}')


if __name__ == '__main__':
    main()
