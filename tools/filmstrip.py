#!/usr/bin/env python3
"""
filmstrip.py -- render consecutive frames side by side and LOOK at them
(manual G7: "for anything visual, render a filmstrip of consecutive frames and
LOOK at it -- thirty lines of code that settles arguments histograms cannot").

Usage:
    python tools/filmstrip.py out.png --state NAME [--keys Z,D] [--frames 12]
                              [--every 6] [--cols 4]

The state is one saved by boot.py --save; the keys (named as keyprobe.py
prints them) are held for the whole strip.
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                           # noqa: E402
from harness import Harness                                 # noqa: E402
from keyprobe import KEYS, keymask, KEYMAP, press           # noqa: E402
import screen                                               # noqa: E402


def run_frames(h, n):
    """Advance n video frames (frames are the natural unit once a game is
    frame-synced; the case study HALTed twice per pass).  Harness.run_frames
    is the implementation; this name is kept for the tools that import it."""
    return h.run_frames(n)


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    out = args[0]
    del args[:1]
    state = None
    keys = []
    frames = 12
    every = 6
    cols = 4
    while args:
        if args[0] == '--state':
            state = args[1]; del args[:2]
        elif args[0] == '--keys':
            keys = [k for k in args[1].split(',') if k]; del args[:2]
        elif args[0] == '--frames':
            frames = int(args[1]); del args[:2]
        elif args[0] == '--every':
            every = int(args[1]); del args[:2]
        elif args[0] == '--cols':
            cols = int(args[1]); del args[:2]
        else:
            del args[:1]
    if state is None:
        sys.exit('give --state NAME: a machine state saved by boot.py --save')

    h = Harness()
    h.load_state_file(portconfig.state_path(state))
    for k in keys:
        name, _, _n = k.partition(':')
        press(h.ports, name)

    shots = []
    for i in range(frames):
        run_frames(h, every)
        shots.append(screen.render(h.memobj.m))
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * 258, rows * 194), (40, 40, 40))
    for i, im in enumerate(shots):
        sheet.paste(im, ((i % cols) * 258 + 1, (i // cols) * 194 + 1))
    sheet.save(out)
    print(f'wrote {out}  ({len(shots)} frames, {every} video frames apart, '
          f'keys={keys or "none"})')


if __name__ == '__main__':
    main()
