#!/usr/bin/env python3
"""
bleepload.py -- decode a Firebird BLEEPLOAD tape's block framing.

WHAT TO REACH FOR FIRST.  The general way to boot ANY protected or custom-loader
tape -- Bleepload, Speedlock, Alkatraz, and the rest -- is the SNAPSHOT ROUTE,
which needs no loader-specific code at all:

    python tools/simload.py                 # tap2sna runs the real loader -> .z80
    python tools/snapimport.py build/boot48.z80 --save boot

That is manual 6.1 / Q1, and it is what you should use.  You do NOT need this
tool to make a Bleepload game run.

WHAT THIS TOOL IS FOR.  The snapshot route loses R3 -- the byte-for-byte
cross-check of your image against the tape (manual phase 3 / 5.2, evidence
rung R3).  Bleepload blocks each carry their own destination address, so the
image can be rebuilt from the tape bytes alone and diffed against the snapshot;
every surviving difference is then a loader transform you must NAME.  This tool
does the framing half of that: it prints the block -> destination map and the
group structure, and writes a "naive" image (each block's 256 data bytes at its
header destination) to start the diff from.

SCOPE, STATED HONESTLY.  The framing below was recovered from, and verified
against, ONE tape (a Firebird 1987 release).  Bleepload has known variants that
differ in how block data is stored, so the header offsets are PARAMETERS with
that tape's values as defaults -- check them against your own tape's stage-1
stub (disassemble the loader that the BASIC RANDOMIZE USR jumps to).  And the
POST-LOAD TRANSFORMS a given game's loader performs -- relocations, in-place
decryption, staging one group in the display file and moving it later -- are
GAME-SPECIFIC and are deliberately NOT here.  Add them in your port (see that
port's own tools/bleepload.py for a worked example) so this stays reusable.

Bleepload turbo block, as seen (inside each TZX 0x11 block, after flag $FF):
    [gid][data * DATA_LEN][block#][dest lo][dest hi][tail ... ][XOR checksum]
  gid    groups blocks that load together ($64,$65,$66 = groups 1,2,3)
  block# counts up within a group (a reload check)
  dest   where the DATA_LEN data bytes are LDIR'd
  tail   code the loader JP (HL)s into -- the loader is distributed on the tape
Later groups may store the data XORed with the destination's high byte
(--xor-later-groups, on by default because the reference tape does it).

Usage:
    python tools/bleepload.py [--tape FILE] [--out build/image_tape.bin]
                              [--snapshot FILE] [--data-len N] [--first-group ID]
                              [--no-xor-later-groups]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                   # noqa: E402
import tzx as tzxmod                                                # noqa: E402


def decode(tape, data_len=256):
    """Every TZX turbo (0x11) block, parsed as a Bleepload block.  Returns a
    list of dicts {index, gid, data, blk, dest, tail}."""
    _, blocks = tzxmod.parse(tape)
    out = []
    for b in blocks:
        if b.id != 0x11 or b.data is None:
            continue
        d = b.data                       # flag byte at d[0], XOR checksum at d[-1]
        base = 1
        gid = d[base]
        data = bytes(d[base + 1:base + 1 + data_len])
        blk = d[base + 1 + data_len]
        dest = d[base + 2 + data_len] | (d[base + 3 + data_len] << 8)
        tail = bytes(d[base + 4 + data_len:-1])
        out.append(dict(index=b.index, gid=gid, data=data, blk=blk, dest=dest, tail=tail))
    return out


def build_naive(blocks, first_group=0x64, xor_later=True):
    """A 64K image with each block's data at its header destination.  Groups
    after `first_group` are de-XORed by the destination high byte if xor_later.
    Returns (image bytearray, loaded-page mask bytearray)."""
    img = bytearray(0x10000)
    loaded = bytearray(0x10000)
    for b in blocks:
        dest = b['dest']
        data = b['data']
        if xor_later and b['gid'] != first_group:
            data = bytes(x ^ (dest >> 8) for x in data)
        n = min(len(data), 0x10000 - dest)
        img[dest:dest + n] = data[:n]
        loaded[dest:dest + n] = b'\x01' * n
    return img, loaded


def main():
    args = sys.argv[1:]
    if '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    tape = snap = None
    out = portconfig.path('build/image_tape.bin')
    data_len = 256
    first_group = 0x64
    xor_later = True
    while args:
        a = args[0]
        if a == '--tape':
            tape = args[1]; del args[:2]
        elif a == '--out':
            out = args[1]; del args[:2]
        elif a == '--snapshot':
            snap = args[1]; del args[:2]
        elif a == '--data-len':
            data_len = int(args[1], 0); del args[:2]
        elif a == '--first-group':
            first_group = int(args[1], 0); del args[:2]
        elif a == '--no-xor-later-groups':
            xor_later = False; del args[:1]
        else:
            sys.exit(f'bleepload: unknown argument {a}')
    tape = tape or portconfig.path(portconfig.get('tape', 'path'))
    if tape is None or not os.path.exists(tape):
        portconfig.need('tape', 'path', what='the Bleepload tape')

    blocks = decode(tape, data_len)
    groups = {}
    for b in blocks:
        groups.setdefault(b['gid'], []).append(b)
    print(f'{len(blocks)} turbo blocks in {len(groups)} groups: ' +
          ', '.join(f'${g:02X}={len(v)}' for g, v in sorted(groups.items())))
    for gid, gblocks in sorted(groups.items()):
        for i, b in enumerate(gblocks):
            if b['blk'] != i:
                print(f"  NOTE block #{b['index']}: group ${gid:02X} number {b['blk']} != expected {i} "
                      f"(a variant, or not a Bleepload block -- check --data-len)")
                break

    img, loaded = build_naive(blocks, first_group, xor_later)
    runs = []
    for b in blocks:
        d = b['dest']
        if runs and runs[-1][0] == b['gid'] and runs[-1][2] + 0x100 == d:
            runs[-1][2] = d
        else:
            runs.append([b['gid'], d, d, b['index']])
    print('\nblock -> destination map:')
    for gid, lo, hi, idx in runs:
        print(f'  ${gid:02X}  ${lo:04X}..${hi + 0xFF:04X}  (from block #{idx})')

    pages = sum(1 for p in range(0, 0x10000, 0x100) if loaded[p])
    print(f'\npages carrying tape data: {pages}/256')
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    open(out, 'wb').write(img)
    print(f'wrote {out} (the NAIVE image: header destinations only, no game-specific '
          f'relocation/decryption -- add those in your port)')

    if snap and os.path.exists(snap):
        from skoolkit.snapshot import Snapshot
        s = Snapshot.get(snap)
        ram = s.ram(-1)
        if len(ram) != 0xC000:
            print('(snapshot is 128K; the naive diff below is 48K-only)')
            return
        compared = mism = 0
        for a in range(0x4000, 0x10000):
            if not loaded[a]:
                continue
            compared += 1
            mism += (img[a] != ram[a - 0x4000])
        print(f'\nvs {os.path.basename(snap)}: bytes compared {compared} / mismatching {mism}. '
              f'Each mismatch is a loader transform to name (relocation, decryption, staging) '
              f'or a variant; attribute them in your port, do not leave them unexplained (R3).')


if __name__ == '__main__':
    main()
