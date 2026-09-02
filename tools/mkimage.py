#!/usr/bin/env python3
"""
mkimage.py -- build the post-loader 64K memory image directly (manual 6.1).

We ASSERT the loader's postcondition rather than running the loader: each
data block goes where the loader would put it, then the loader's own
post-load moves are performed by hand.  The postcondition is recovered in
phase 2 by reading the loader (the BASIC listing via basic.py, then the
machine-code stub via adis.py) and written into port.json:

    tape.blocks   [] or "auto"  follow the ROM headers: a BASIC block goes to
                                PROG, a CODE block to its header's address
                                (a stock, unprotected tape needs nothing more)
                  a list        one entry per block, for a custom loader:
                                  {"dest": "0x8600", "len": "0x5210", "flag": "0x80"}
                                matched by tape flag byte (the first unused
                                block with that flag, in tape order), or
                                  {"dest": "0x8400", "len": "0x7777", "block": 6}
                                matched by TZX block index as tzx.py prints it
    tape.copies   the loader's own LDIRs after loading -- typically a stub
                  relocating itself:  {"src": "0x5CF1", "dst": "0xFF00", "len": "0x100"}

`len` is the loader's own count (its DE).  A payload of a different size is
an ERROR, not a warning: it means the block table is wrong.

In the case study three custom-flag blocks loaded to $8600, $73DA and $8400,
and the third overwrote the first entirely, so the first was a transient
stage: loaded, one routine inside it called, then gone.  Anything such a
stage leaves behind must lie OUTSIDE the later blocks, and that is what
--upto is for: place only the first N blocks and look at that image.

Usage:
    python tools/mkimage.py [--tape F] [--out F] [--upto N]

Defaults: tape.path -> z80.image, both from port.json.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                        # noqa: E402
import tzx as tzxmod                                     # noqa: E402

PROG = 0x5CCB          # where the ROM LOADs a BASIC program on a stock 48K


class ImageError(Exception):
    pass


def data_blocks(blocks):
    """(tzx index, flag, payload) for every ROM-format data block, in order."""
    return [(b.index, b.data[0], bytes(b.data[1:-1])) for b in blocks
            if b.data is not None and len(b.data) >= 2]


def headers_spec(blocks, prog=PROG):
    """The placement a stock ROM loader performs: each header names where the
    block after it goes.  Headerless blocks are REPORTED, never guessed."""
    spec = []
    notes = []
    pending = None
    for b in blocks:
        if b.data is None or len(b.data) < 2:
            continue
        hdr = tzxmod.decode_header(b.data)
        if hdr is not None:
            pending = hdr
            continue
        if pending is None:
            notes.append(f'block #{b.index}: headerless (flag ${b.data[0]:02X}, '
                         f'{len(b.data) - 2} bytes) -- NOT placed; describe it in tape.blocks')
            continue
        if pending['type'] == 0:
            spec.append({'dest': prog, 'len': pending['length'], 'block': b.index, 'flag': None})
        elif pending['type'] == 3:
            spec.append({'dest': pending['load_address'], 'len': pending['length'],
                         'block': b.index, 'flag': None})
        else:
            notes.append(f'block #{b.index}: {pending["type_name"]} {pending["name"]!r} -- not placed')
        pending = None
    return spec, notes


def place(blocks, spec='auto', copies=(), prog=PROG, upto=None):
    """A blank 64K with the blocks at their destinations and the copies done.
    Returns (mem, lines): one printable line per placement -- the exit gate."""
    mem = bytearray(0x10000)
    lines = []
    if not spec or spec == 'auto':
        spec, notes = headers_spec(blocks, prog)
        lines += notes
    by_index = {}
    by_flag = {}
    for idx, flag, payload in data_blocks(blocks):
        by_index[idx] = (flag, payload)
        by_flag.setdefault(flag, []).append((idx, payload))
    for n, e in enumerate(spec):
        if upto is not None and n >= upto:
            lines.append(f'--upto {upto}: {len(spec) - upto} later block(s) not placed')
            break
        if e.get('block') is not None:
            idx = e['block']
            if idx not in by_index:
                raise ImageError(f'tape.blocks[{n}]: no data block #{idx} on the tape')
            flag, payload = by_index[idx]
        else:
            flag = e['flag']
            if not by_flag.get(flag):
                raise ImageError(f'tape.blocks[{n}]: no (more) blocks with flag ${flag:02X} on the tape')
            idx, payload = by_flag[flag].pop(0)
        dest = e['dest']
        ln = e.get('len')
        if ln is None:
            ln = len(payload)
        elif len(payload) != ln:
            raise ImageError(f'block #{idx} (flag ${flag:02X}): payload {len(payload)} bytes != '
                             f'tape.blocks[{n}].len ${ln:04X} -- the block table is wrong')
        if dest + ln > 0x10000:
            raise ImageError(f'block #{idx}: ${dest:04X}+{ln} runs past $FFFF')
        mem[dest:dest + ln] = payload
        lines.append(f'block #{idx} (flag ${flag:02X}): ${dest:04X}..${dest + ln - 1:04X}  ({ln} bytes)')
    for src, dst, ln in copies:
        if src + ln > 0x10000 or dst + ln > 0x10000:
            raise ImageError(f'copy ${src:04X}->${dst:04X} x{ln} runs past $FFFF')
        mem[dst:dst + ln] = mem[src:src + ln]
        lines.append(f'copy: ${src:04X}+{ln} -> ${dst:04X}..${dst + ln - 1:04X}')
    return mem, lines


def build_image(tape_path, spec='auto', copies=(), prog=PROG, upto=None):
    """Parse the tape and place it.  Returns (mem, lines) as place() does."""
    _, blocks = tzxmod.parse(tape_path)
    return place(blocks, spec, copies, prog, upto)


def main():
    args = sys.argv[1:]
    if '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    tape = out = upto = None
    while args:
        if args[0] == '--tape':
            tape = args[1]; del args[:2]
        elif args[0] == '--out':
            out = args[1]; del args[:2]
        elif args[0] == '--upto':
            upto = int(args[1], 0); del args[:2]
        else:
            del args[:1]
    tape = tape or portconfig.path(portconfig.need('tape', 'path', what='the tape to build the image from'))
    if not os.path.exists(tape):
        sys.exit(f'tape not found: {tape}')
    out = out or portconfig.path(portconfig.get('z80', 'image'))
    prog = portconfig.num(portconfig.get('tape', 'prog'), 'tape.prog') or PROG
    try:
        mem, lines = build_image(tape, portconfig.blocks_spec(), portconfig.copies_spec(), prog, upto)
    except ImageError as e:
        sys.exit(f'mkimage: {e}')
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    open(out, 'wb').write(mem)
    for l in lines:
        print(l)
    entry = portconfig.num(portconfig.get('tape', 'entry'), 'tape.entry')
    print(f'entry ${entry:04X}' if entry is not None else 'entry: not set (port.json tape.entry)')
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
