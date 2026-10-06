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

--coverage prints the honest coverage statement P3 asks for instead: entries
by type, labels, routines titled vs carrying SkoolKit's default title
("Routine at XXXX"), and instruction lines that carry a comment -- with
every untitled entry named.

--symbols OUT imports the reference's @label names (within --lo/--hi) into
a symbols file in adis.py's format.  Names already in OUT are kept: our own
readings win.  The labels are R1 evidence (manual R1): a name to look under,
never a finding.

Usage:
    python tools/refcheck.py SKOOL [--image build/image.bin] [--lo 0x5F00]
                             [--hi 0x10000] [--no-reloc]
    python tools/refcheck.py SKOOL --coverage
    python tools/refcheck.py SKOOL --symbols tools/symbols.json
The reference lives OUTSIDE the repository (it embeds the game's bytes).
"""
import argparse
import json
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


ENTRY = re.compile(r'^([bcgistuw])\$([0-9A-Fa-f]{4}) ')
DEFAULT_TITLE = re.compile(r'^(Routine|Data block|Message|Unused|Game status buffer entry)'
                           r'( at [0-9A-Fa-f]{4})?$|^$')


def parse(skool):
    """-> (entries, labels).  entries: [(type, addr, title, insns, commented)]
    for every entry; labels: {addr: name} from @label directives."""
    entries, labels = [], {}
    head, label, cur = [], None, None
    for line in open(skool, encoding='utf-8'):
        line = line.rstrip('\r\n')
        if not line.strip():
            head, cur = [], None
            continue
        if line.startswith('@label='):
            label = line[7:].strip()
            continue
        if line.startswith('@'):
            continue
        if line.startswith(';'):
            if cur is None:
                head.append(line[1:].strip())
            continue
        m = LINE.match(line)
        if not m:
            continue
        adr = int(m.group(2), 16)
        if label:
            labels[adr] = label
            label = None
        e = ENTRY.match(line)
        if e and cur is None:
            title = ' '.join(head[:head.index('')] if '' in head else head)
            cur = [e.group(1), adr, title, 0, 0]
            entries.append(cur)
        if cur is not None:
            cur[3] += 1
            c = line.split(';', 1)[1].strip() if ';' in line else ''
            if c.strip('{} '):
                cur[4] += 1
    return [tuple(x) for x in entries], labels


def coverage(skool):
    entries, labels = parse(skool)
    kinds = {}
    for t, *_ in entries:
        kinds[t] = kinds.get(t, 0) + 1
    print('entries: ' + ', '.join('%s=%d' % kv for kv in sorted(kinds.items()))
          + '  (b bytes, c code, g game status, i ignored, s space, t text, u unused, w words)')
    print('labels: %d' % len(labels))
    code = [x for x in entries if x[0] == 'c']
    bare = [x for x in code if DEFAULT_TITLE.match(x[2])]
    print('routines: %d, titled %d, default/empty title %d' % (len(code), len(code) - len(bare), len(bare)))
    ins = sum(x[3] for x in code)
    com = sum(x[4] for x in code)
    print('code lines: %d, commented %d (%d%%)' % (ins, com, 100 * com // max(ins, 1)))
    print('per routine (addr, lines, commented, title):')
    for t, adr, title, n, c in code:
        print('  $%04X %5d %5d %3d%%  %s%s' % (adr, n, c, 100 * c // max(n, 1),
              '[DEFAULT] ' if DEFAULT_TITLE.match(title) else '', title[:70]))
    return 0


def import_symbols(skool, out, lo, hi):
    _, labels = parse(skool)
    d = json.load(open(out)) if os.path.exists(out) else {}
    have = {int(k, 0) for k in d}
    added = 0
    for adr, name in sorted(labels.items()):
        if lo <= adr < hi and adr not in have:
            d['0x%04X' % adr] = name
            added += 1
    json.dump(d, open(out, 'w'), indent=1, sort_keys=True)
    print('symbols: %d labels in reference, %d in range, %d added, %d kept from %s'
          % (len(labels), sum(lo <= a < hi for a in labels), added, len(have), out))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('skool')
    ap.add_argument('--image', default=None)
    ap.add_argument('--lo', type=lambda s: int(s, 0), default=0x5F00)
    ap.add_argument('--hi', type=lambda s: int(s, 0), default=0x10000)
    ap.add_argument('--no-reloc', action='store_true')
    ap.add_argument('--coverage', action='store_true')
    ap.add_argument('--symbols', metavar='OUT')
    a = ap.parse_args()
    if a.coverage:
        return coverage(a.skool)
    if a.symbols:
        return import_symbols(a.skool, a.symbols, a.lo, a.hi)

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
