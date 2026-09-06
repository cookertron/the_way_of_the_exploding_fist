#!/usr/bin/env python3
"""
simload.py -- the real loader, run for real: SkoolKit's simulated LOAD.

Phase 1-2 for a CUSTOM LOADER (manual 6.1 / Q1; TRAPS.md #2: "boot the real
loader, in order, unpatched").  tap2sna.py plays the TZX's pulses into a
simulated Spectrum running the ROM and the tape's own loader, and writes a
snapshot when the tape ends or the PC reaches --start.  Nothing here knows
the loader's format; that is the point.

Usage:
    python tools/simload.py [--machine 48|128] [--start ADDR] [--out FILE]
                            [--accelerator NAME|auto|none|list] [--cmio]
                            [--no-fast-load] [--trace FILE] [--tape FILE]

Defaults: machine 48, accelerator list (auto-select and report), output
build/boot48.z80 (build/boot128.z80 for --machine 128).  With --start the
load is run to the end of the tape and then to ADDR (finish-tape=1), which is
how the definitive hand-over snapshot is taken once ADDR is known.

Example (a Firebird Bleepload tape): the bleepload accelerator fired 892,782 times with 0
misses on both machines; the whole 375 s tape loads in about a minute.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                   # noqa: E402


def main():
    args = sys.argv[1:]
    if '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    machine, start, out, accel = '48', None, None, 'list'
    cmio, fast, trace, tape = False, True, None, None
    while args:
        a = args[0]
        if a == '--machine':
            machine = args[1]; del args[:2]
        elif a == '--start':
            start = int(args[1], 0); del args[:2]
        elif a == '--out':
            out = args[1]; del args[:2]
        elif a == '--accelerator':
            accel = args[1]; del args[:2]
        elif a == '--cmio':
            cmio = True; del args[:1]
        elif a == '--no-fast-load':
            fast = False; del args[:1]
        elif a == '--trace':
            trace = args[1]; del args[:2]
        elif a == '--tape':
            tape = args[1]; del args[:2]
        else:
            sys.exit(f'simload: unknown argument {a}')
    tape = tape or portconfig.path(portconfig.get('tape', 'path'))
    if tape is None or not os.path.exists(tape):
        portconfig.need('tape', 'path', what='the tape to load')
    out = out or portconfig.path(f'build/boot{machine}.z80')
    cfg = [f'machine={machine}', f'accelerator={accel}']
    if cmio:
        cfg.append('cmio=1')
    if not fast:
        cfg.append('fast-load=0')
    if trace:
        cfg.append(f'trace={trace}')
    if start is not None:
        cfg.append('finish-tape=1')
    argv = []
    for c in cfg:
        argv += ['-c', c]
    if start is not None:
        argv += ['--start', str(start)]
    argv += [tape, out]
    print('tap2sna.py ' + ' '.join(argv))
    from skoolkit import tap2sna
    tap2sna.main(argv)


if __name__ == '__main__':
    main()
