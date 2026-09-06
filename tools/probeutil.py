#!/usr/bin/env python3
"""
probeutil.py -- shared "boot a target and settle it" for the analysis probes
(stackscan, chaincost, dataread, ...).

A probe measures a LIVE, running state, which can come from three places:
  --state NAME     a saved harness state (build/NAME.pkl) driven into play
  --snapshot FILE  a .z80/.szx/.sna straight off simload.py -- ANY game
  (default)        the port's manifest snapshot / tape image

A raw hand-over snapshot boots with interrupts DISABLED and often still in
the loader's tail, so a probe would read the loader, not the game.  Two knobs
reach running code without game-specific menu driving, for a robustness pass:
  --arm            set IFF=1 now (the game's own DI/EI/IM still apply)
  --warm N         run N video frames (interrupts armed) before measuring
For a real GAMEPLAY measurement you still drive the menus (a saved --state, or
--keys held); --arm/--warm only boot far enough to exercise the tool.

parse_target(args) consumes these options from the arg list in place; the rest
stay for the tool's own parser.  boot_target(t) returns a ready Harness.
"""
import sys

from harness import Harness, IFF                                    # noqa: E402
import portconfig                                                   # noqa: E402

TARGET_HELP = "[--state NAME | --snapshot FILE] [--arm] [--warm N]"


def parse_target(args):
    """Consume --state/--snapshot/--arm/--warm from `args` (in place)."""
    t = {'state': None, 'snapshot': None, 'arm': False, 'warm': 0}
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--state':
            t['state'] = args[i + 1]; del args[i:i + 2]
        elif a == '--snapshot':
            t['snapshot'] = args[i + 1]; del args[i:i + 2]
        elif a == '--arm':
            t['arm'] = True; del args[i:i + 1]
        elif a == '--warm':
            t['warm'] = int(args[i + 1], 0); del args[i:i + 2]
        else:
            i += 1
    return t


def boot_target(t, name='probe'):
    if t['state'] and t['snapshot']:
        sys.exit(f'{name}: use --state OR --snapshot, not both')
    if not (t['state'] or t['snapshot']) and portconfig.get('z80', 'snapshot') is None:
        sys.exit(f'{name}: need --state NAME or --snapshot FILE '
                 '(no z80.snapshot in the manifest to fall back to)')
    h = Harness(snapshot=t['snapshot'], deck=False) if t['snapshot'] else Harness(deck=False)
    if t['state']:
        h.load_state_file(portconfig.state_path(t['state']))
    if t['arm'] or t['warm']:
        h.regs[IFF] = 1                     # --warm needs interrupts to make progress
    if t['warm']:
        h.run_frames(t['warm'], interrupts=True)
    return h


def source_label(t):
    if t['snapshot']:
        return t['snapshot']
    if t['state']:
        return t['state']
    return 'manifest snapshot'
