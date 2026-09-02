#!/usr/bin/env python3
"""blitprobe.py -- where does the sprite draw actually WRITE?  Histogram every
write above $4000 by (writer PC -> destination region) over a few frames of
driven play.

Uses harness.Mem.watch(), NOT a wrapper: SkoolKit's Simulator binds
self.memory into its opcode partials at construction, so replacing
sim.memory afterwards silently logs nothing (measured in the case study:
6 writes a pass instead of thousands).

Regions: the real display file and attributes are labelled; a shadow screen
(an off-screen 6912-byte copy the game composes into, if it has one) is
labelled when you give its address; everything else by 4K page.

Usage:
    python tools/blitprobe.py --state NAME [--keys D] [--warm 32] [--frames 4]
                              [--shadow 0xC000]

--state   a machine state saved by boot.py --save
--keys    keys held throughout (names as keyprobe.py prints them)
--warm    frames to run before watching, so the keys have taken effect
--frames  frames to watch (one main-loop pass is the useful unit)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                             # noqa: E402
from harness import Harness                                   # noqa: E402
from keyprobe import KEYS, keymask, KEYMAP, press             # noqa: E402
from filmstrip import run_frames                              # noqa: E402


def region(a, shadow=None):
    if 0x4000 <= a < 0x5800:
        return 'REAL_BMP'
    if 0x5800 <= a < 0x5B00:
        return 'REAL_ATTR'
    if shadow is not None:
        if shadow <= a < shadow + 0x1800:
            return 'SHDW_BMP'
        if shadow + 0x1800 <= a < shadow + 0x1B00:
            return 'SHDW_ATTR'
    return f'{a >> 12:X}xxx'


def main():
    args = sys.argv[1:]
    if '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    state = None
    keys = []
    warm = 32
    frames = 4
    shadow = None
    while args:
        if args[0] == '--state':
            state = args[1]; del args[:2]
        elif args[0] == '--keys':
            keys = [k for k in args[1].split(',') if k]; del args[:2]
        elif args[0] == '--warm':
            warm = int(args[1]); del args[:2]
        elif args[0] == '--frames':
            frames = int(args[1]); del args[:2]
        elif args[0] == '--shadow':
            shadow = int(args[1], 0); del args[:2]
        else:
            del args[:1]
    if state is None:
        sys.exit('give --state NAME: a machine state saved by boot.py --save')

    h = Harness()
    h.load_state_file(portconfig.state_path(state))
    for k in keys:
        press(h.ports, k)
    run_frames(h, warm)
    h.memobj.watch(0x4000, 0x10000)
    run_frames(h, frames)
    h.memobj.unwatch()
    log = h.memobj.log
    hist = {}
    for pc, a, v in log:
        k = (pc, region(a, shadow))
        hist[k] = hist.get(k, 0) + 1
    print(f'{len(log)} writes above $4000 in {frames} frame(s) (keys={keys or "none"})')
    for (pc, r), n in sorted(hist.items(), key=lambda kv: -kv[1])[:45]:
        print(f'  ${pc:04X}  {r:<10} {n}')


if __name__ == '__main__':
    main()
