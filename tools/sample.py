#!/usr/bin/env python3
"""
sample.py -- named bytes sampled at every visit to one PC, over driven play.

The harness half of a differential gate (house rule 2): one sampler at the
main-loop top, the same rows printed by the engine, diffed row for row.  Also
the quick way to confirm a reading of a routine against the simulator: name
the variables it reads and writes, sample them at the pass top, and watch
them change (or not) the way the disassembly says.

Each --var is NAME=ADDR (one byte) or NAME=ADDR:N (N bytes, hex).  Rows are
"pass name=value ..."; --changes prints only rows where some variable moved
(pass numbers still count every visit).  --keys holds keys as keyprobe does.

Usage:
    python tools/sample.py --state NAME --at PC --var NAME=ADDR [--var ...]
                           [--passes 1000] [--changes] [--keys D+W]
    python tools/sample.py --state s1 --at 0x9745 --var time=0x9CA5 --var cnt=0x9CA6 --changes
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from keyprobe import press                                         # noqa: E402
from probeutil import parse_target, boot_target, source_label, TARGET_HELP  # noqa: E402


def parse_var(s):
    name, _, where = s.partition('=')
    addr, _, n = where.partition(':')
    if not name or not addr:
        sys.exit(f'sample.py: --var wants NAME=ADDR[:N], got {s!r}')
    return name, int(addr, 0), int(n, 0) if n else 1


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    target = parse_target(args)
    at, passes, changes, keys, vars_ = None, 1000, False, None, []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--at':
            at = int(args[i + 1], 0); i += 2
        elif a == '--var':
            vars_.append(parse_var(args[i + 1])); i += 2
        elif a == '--passes':
            passes = int(args[i + 1], 0); i += 2
        elif a == '--changes':
            changes = True; i += 1
        elif a == '--keys':
            keys = args[i + 1]; i += 2
        else:
            sys.exit(f'sample.py: unknown argument {a!r}; {TARGET_HELP}')
    if at is None or not vars_:
        sys.exit('sample.py: need --at PC and at least one --var')
    h = boot_target(target, 'sample.py')
    for k in (keys.split('+') if keys else []):
        press(h.ports, k)
    print(f'# sample.py at ${at:04X} over {passes} passes, {source_label(target)}'
          + (f', keys {keys}' if keys else ''))
    m = h.memobj.m
    prev = None
    for p in range(passes):
        reason, _ = h.run_until(at, limit=50_000_000)
        if reason != 'target':
            print(f'# stopped at pass {p}: {reason}'); break
        row = tuple(bytes(m[a:a + n]).hex().upper() if n > 1 else f'{m[a]:02X}'
                    for _, a, n in vars_)
        if not changes or row != prev:
            print(p, ' '.join(f'{v[0]}={x}' for v, x in zip(vars_, row)))
        prev = row
        h.step(1)


if __name__ == '__main__':
    main()
