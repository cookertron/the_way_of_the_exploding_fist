#!/usr/bin/env python3
"""
refcheck.py -- phase 3 gate: verify a third-party SkoolKit disassembly
byte-for-byte against our own extraction (manual P3).

Each line of the reference skool file is assembled ALONE at the address it
states, with SkoolKit's assembler (no @ofix/@bfix applied: we compare what
it says the ORIGINAL bytes are), and compared with build/image.bin after
the game's own start-up relocation (LDIR $6000-$80FF -> $5F00 at $9C43;
ledger/topics/battery.toml).  skool2bin is not used: it relocates operands
when an entry assembles to another length, which misaligns a whole-binary
diff.

Prints the gate line "bytes compared N / mismatching M / skipped S", with
every mismatching range, unparsed line and skipped range NAMED:
  skipped  = addresses no skool line defines (i-entries, gaps)
  unparsed = skool lines the assembler cannot assemble

Usage:
    python tools/refcheck.py SKOOL [--image build/image.bin] [--lo 0x5F00]
                             [--hi 0x10000] [--no-reloc]
The reference lives OUTSIDE the repository (it embeds the game's bytes).
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import portconfig  # noqa: E402
from skoolkit.z80 import Assembler  # noqa: E402

LINE = re.compile(r'^([bcgistuw*@ ])\$([0-9A-Fa-f]{4}) (.*)$')


def ranges(addrs):
    out = []
    for a in addrs:
        if out and a == out[-1][1] + 1:
            out[-1][1] = a
        else:
            out.append([a, a])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('skool')
    ap.add_argument('--image', default=None)
    ap.add_argument('--lo', type=lambda s: int(s, 0), default=0x5F00)
    ap.add_argument('--hi', type=lambda s: int(s, 0), default=0x10000)
    ap.add_argument('--no-reloc', action='store_true')
    a = ap.parse_args()

    image = a.image or portconfig.path(portconfig.get('z80', 'image'))
    img = bytearray(open(image, 'rb').read())
    if not a.no_reloc:
        img[0x5F00:0x5F00 + 0x2100] = img[0x6000:0x6000 + 0x2100]

    asm = Assembler()
    compared, mism, unparsed, ignored = 0, [], [], 0
    seen = set()
    for n, line in enumerate(open(a.skool, encoding='utf-8'), 1):
        m = LINE.match(line.rstrip('\r\n'))
        if not m:
            continue
        kind, adr, rest = m.group(1), int(m.group(2), 16), m.group(3)
        if kind == 'i':
            ignored += 1
            continue
        op = rest.split(';')[0].strip()
        if not op or not (a.lo <= adr < a.hi):
            continue
        try:
            data = asm.assemble(op, adr)
        except Exception:
            data = None
        if not data:
            unparsed.append((n, adr, op))
            continue
        for i, b in enumerate(data):
            seen.add(adr + i)
            compared += 1
            if img[(adr + i) & 0xFFFF] != b:
                mism.append(adr + i)
    skipped = [x for x in range(a.lo, a.hi) if x not in seen]

    print('bytes compared %d / mismatching %d / skipped %d'
          % (compared, len(mism), len(skipped)))
    for s, e in ranges(mism)[:40]:
        print('  MISMATCH $%04X-$%04X' % (s, e))
    for n, adr, op in unparsed[:20]:
        print('  UNPARSED line %d $%04X %s' % (n, adr, op))
    print('  %d unparsed lines; %d i-entries (left undefined by the reference)'
          % (len(unparsed), ignored))
    for s, e in ranges(skipped)[:40]:
        print('  skipped  $%04X-$%04X  (%d bytes, no skool line defines them)'
              % (s, e, e - s + 1))
    return 1 if mism or unparsed else 0


if __name__ == '__main__':
    sys.exit(main())
