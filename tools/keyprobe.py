#!/usr/bin/env python3
"""
keyprobe.py -- find which key does something, by pressing each of the 40 in
turn and watching for an escape from a wait loop or a change in memory.

The usual trick (manual 8.1 -- single-step to the first port read with low byte
$FE and read the bit tested) does NOT discriminate in every game: in the case
study one routine scanned ALL EIGHT half-rows unconditionally into a table
every pass, so every half-row was read on every frame and the consumers tested
bits of the table instead.  So we probe behaviourally, from ONE boot,
restoring state per key.

Also the home of the keyboard map every driving tool imports: KEYS (the 40
(name, select, bit) triples), keymask(), KEYMAP, press(), and the key-script
format shared by boot.py and battery.py:

    "40:,60:SPACE,60:D+Z"    hold nothing 40 frames, SPACE 60, D and Z 60

Usage:
    python tools/keyprobe.py [--warm N | --state NAME] [--hold N] [--vars LO HI]

--warm N      boot from the entry point and run N instructions first (default
              400000); --state NAME resumes a state saved by boot.py instead
--hold N      instructions to run with each key held (default 150000)
--vars LO HI  the memory window diffed per key (default $5B00-$FFFF; narrow it
              to the game's variables once you know where they are)
"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                # noqa: E402
from harness import Harness, PC, T, IFF, TAPE_CALL_PC            # noqa: E402

HALFROWS = [
    (0xFE, ['CAPS', 'Z', 'X', 'C', 'V']),
    (0xFD, ['A', 'S', 'D', 'F', 'G']),
    (0xFB, ['Q', 'W', 'E', 'R', 'T']),
    (0xF7, ['1', '2', '3', '4', '5']),
    (0xEF, ['0', '9', '8', '7', '6']),
    (0xDF, ['P', 'O', 'I', 'U', 'Y']),
    (0xBF, ['ENTER', 'L', 'K', 'J', 'H']),
    (0x7F, ['SPACE', 'SYM', 'M', 'N', 'B']),
]

KEYS = [(name, sel, bit) for sel, names in HALFROWS
        for bit, name in enumerate(names)]


def keymask(bit):
    return 0xFF & ~(1 << bit)


KEYMAP = {name: (sel, bit) for name, sel, bit in KEYS}


def press(ports, name):
    """Hold a key by name on a harness.Ports: the game's own mask, verbatim."""
    sel, bit = KEYMAP[name.upper()]
    ports.press(sel, keymask(bit))


def parse_script(text):
    """'40:,60:SPACE,60:D+Z' -> [(40, []), (60, ['SPACE']), (60, ['D', 'Z'])]"""
    out = []
    for seg in text.split(','):
        seg = seg.strip()
        if not seg:
            continue
        frames, _, keys = seg.partition(':')
        names = [k.strip().upper() for k in keys.split('+') if k.strip()]
        for k in names:
            if k not in KEYMAP:
                sys.exit(f'unknown key {k!r}; names are ' + ' '.join(n for n, _, _ in KEYS))
        out.append((int(frames), names))
    return out


def drive(h, script):
    """Run a key script: release, hold the segment's keys, advance its frames."""
    for frames, keys in script:
        h.ports.release_all()
        for k in keys:
            press(h.ports, k)
        h.run_frames(frames)


def run(h, n, interrupts=True):
    sim = h.sim
    regs = sim.registers
    ops = sim.opcodes
    mem = sim.memory
    fd, ia = h.frame_duration, h.int_active
    seen = set()
    for _ in range(n):
        pc = regs[PC]
        seen.add(pc)
        if h.deck is not None and pc == TAPE_CALL_PC:
            h._tape()
            continue
        ops[mem[pc]]()
        if interrupts and regs[IFF] and regs[T] % fd < ia:
            sim.accept_interrupt(regs, mem, pc)
    return seen


def main():
    args = sys.argv[1:]
    if '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    warm = 400_000
    hold = 150_000
    lo, hi = 0x5B00, 0x10000
    state = None
    while args:
        if args[0] == '--warm':
            warm = int(args[1], 0); del args[:2]
        elif args[0] == '--hold':
            hold = int(args[1], 0); del args[:2]
        elif args[0] == '--vars':
            lo = int(args[1], 0); hi = int(args[2], 0); del args[:3]
        elif args[0] == '--state':
            state = args[1]; del args[:2]
        else:
            del args[:1]

    h = Harness()
    if state:
        h.load_state_file(portconfig.state_path(state))
        print(f'resumed {state}; PC=${h.pc():04X}')
    else:
        h.profile(warm)
        print(f'booted {warm} instructions; PC=${h.pc():04X}')
    state = h.save_state()

    snap0 = h.snapshot(lo, hi)
    baseline = run(h, hold)
    snapb = h.snapshot(lo, hi)
    idle = {i + lo for i in range(hi - lo) if snapb[i] != snap0[i]}
    print(f'baseline: PC=${h.pc():04X}, {len(baseline)} distinct PCs, '
          f'{len(idle)} vars change while idle')

    for name, sel, bit in KEYS:
        h.load_state(state)
        h.ports.press(sel, keymask(bit))
        seen = run(h, hold)
        new = sorted(seen - baseline)
        snap = h.snapshot(lo, hi)
        changed = [i + lo for i in range(hi - lo)
                   if snap[i] != snap0[i] and (i + lo) not in idle]
        note = ''
        if new:
            note += f'  NEW PCs {len(new)}: ' + ' '.join(f'${a:04X}' for a in new[:5])
        if changed:
            note += '  vars: ' + ' '.join(f'${a:04X}' for a in changed[:8])
        print(f'{name:>6} (${sel:02X}.{bit}): PC=${h.pc():04X}{note}')


if __name__ == '__main__':
    main()
