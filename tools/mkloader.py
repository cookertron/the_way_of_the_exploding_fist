#!/usr/bin/env python3
"""
mkloader.py -- build a scratch 64K image containing only the BASIC block, laid
out exactly as the ROM loader leaves it, plus any self-relocation the loader
stub performs, done by hand, so the stub can be disassembled at its running
address.

Phase 2 step 1.  Facts asserted here (each with the evidence):

  - PROG = $5CCB on a stock 48K with the standard 21-byte channel information
    block at CHANS = $5CB6.  The block is LOADed by the ROM at PROG, so a
    BASIC block's first byte lands at $5CCB (the high byte of its first line
    number) whatever the header says.
  - The listing basic.py prints is what the loader DOES, but the address the
    interpreter acts on is the 5-byte binary form behind each number, not the
    digits.  In the case study the line printed as RANDOMIZE USR 32768 and the
    binary form was 23778 = $5CE2 -- the first byte of the REM that followed,
    i.e. machine code smuggled into the program text.
  - A stub commonly copies itself somewhere safe and jumps there (case study:
    DI / LD HL,$5CF1 / LD DE,$FF00 / LD BC,$0100 / LDIR / JP $FF00).  Give
    that move as --copy SRC DST LEN (or tape.copies in port.json) and the
    relocated stub sits in this image at its running address.

Usage:
    python tools/mkloader.py [--tape F] [--block N] [--prog ADDR]
                             [--copy SRC DST LEN]... [--out F]

Defaults: tape.path from port.json; the BASIC block is the first data block
that follows a type-0 header (or --block N, a TZX block index as tzx.py
prints it); tape.copies; the output is loader_image.bin beside z80.image.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                        # noqa: E402
import tzx as tzxmod                                     # noqa: E402

CHANS = 0x5CB6         # stock 48K channel information block, 21 bytes
PROG = 0x5CCB          # = CHANS + 21: where the BASIC program starts


def find_basic(blocks):
    """(tzx index, payload) of the first data block following a BASIC header."""
    pending = None
    for b in blocks:
        if b.data is None or len(b.data) < 2:
            continue
        hdr = tzxmod.decode_header(b.data)
        if hdr is not None:
            pending = hdr
            continue
        if pending is not None and pending['type'] == 0:
            return b.index, bytes(b.data[1:-1])
        pending = None
    return None, None


def build_loader_image(basic, prog=PROG, copies=()):
    """A blank 64K with the BASIC block at PROG and the copies performed."""
    if prog + len(basic) > 0x10000:
        raise ValueError(f'BASIC block of {len(basic)} bytes at ${prog:04X} runs past $FFFF')
    mem = bytearray(0x10000)
    mem[prog:prog + len(basic)] = basic
    for src, dst, ln in copies:
        if src + ln > 0x10000 or dst + ln > 0x10000:
            raise ValueError(f'copy ${src:04X}->${dst:04X} x{ln} runs past $FFFF')
        mem[dst:dst + ln] = mem[src:src + ln]
    return mem


def main():
    args = sys.argv[1:]
    if '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    tape = out = block = None
    prog = portconfig.num(portconfig.get('tape', 'prog'), 'tape.prog') or PROG
    copies = list(portconfig.copies_spec())
    explicit = []
    while args:
        if args[0] == '--tape':
            tape = args[1]; del args[:2]
        elif args[0] == '--block':
            block = int(args[1], 0); del args[:2]
        elif args[0] == '--prog':
            prog = int(args[1], 0); del args[:2]
        elif args[0] == '--copy':
            explicit.append((int(args[1], 0), int(args[2], 0), int(args[3], 0))); del args[:4]
        elif args[0] == '--out':
            out = args[1]; del args[:2]
        else:
            del args[:1]
    if explicit:
        copies = explicit
    tape = tape or portconfig.path(portconfig.need('tape', 'path', what='the tape holding the BASIC loader'))
    if not os.path.exists(tape):
        sys.exit(f'tape not found: {tape}')
    _, blocks = tzxmod.parse(tape)
    if block is not None:
        found = [b for b in blocks if b.index == block and b.data is not None and len(b.data) >= 2]
        if not found:
            sys.exit(f'no data block #{block} on {tape}')
        idx, basic = block, bytes(found[0].data[1:-1])
    else:
        idx, basic = find_basic(blocks)
        if basic is None:
            sys.exit(f'no BASIC block (type-0 header + data) on {tape}; give --block N')
    if out is None:
        out = os.path.join(os.path.dirname(portconfig.path(portconfig.get('z80', 'image'))),
                           'loader_image.bin')
    mem = build_loader_image(basic, prog, copies)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    open(out, 'wb').write(mem)
    print(f'BASIC block #{idx}: {len(basic)} bytes at ${prog:04X}..${prog + len(basic) - 1:04X}')
    for src, dst, ln in copies:
        print(f'copied: ${src:04X}+{ln} -> ${dst:04X}')
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
