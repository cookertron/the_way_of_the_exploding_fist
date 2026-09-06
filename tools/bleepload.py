#!/usr/bin/env python3
"""
bleepload.py -- decode a Firebird BLEEPLOAD tape: the block framing, the
loader's own decryption of group 1, the later groups' XOR key read from the
stage-2 loader, and a diff of the rebuilt image against the simulated-load
snapshot with every mismatching page attributed.

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
every surviving difference is then a loader transform you must NAME.  This
tool rebuilds the image, applies the transforms that belong to BLEEPLOAD
ITSELF (below), reads the game-specific ones out of the loader's own code and
prints them, and attributes each mismatching page of the diff to one of them.

SCOPE, STATED HONESTLY.  Verified against THIRTEEN titles on fourteen tapes
(loader REM dates 9/86 to 7/89; Firebird, Electric Dreams and Ariolasoft
releases): Bubble Bobble, Hybrid, I,Ball, Intensity, Ninja Scooter Simulator,
Parabola, Samurai Warrior, The King's Keep, Back to the Future, Empire, Jaws
(48K side and 128K side), Kenny Dalglish Soccer Manager, Starfox -- each
rebuilt from its tape bytes and diffed against a tap2sna snapshot taken at
the loader's hand-over JP (tools/simload.py --start; --no-finish-tape when
the game starts before the tape's trailing tone ends).  What held on all:
  - the framing below, DATA_LEN 256, first group $64 (the stub's own CP
    immediate), block numbers 0,1,2,... within a group.  Three stage-1 stub
    revisions exist (9/86; 3/87-7/89; Bubble Bobble's, which also saves
    BANKM) and they differ only in bookkeeping, never in the framing.  A
    stub is assembled for ONE buffer address -- $FE00 on thirteen tapes,
    $6D00 on Empire, whose stub also loads at $DA00 instead of $CD00 -- and
    this tool reads the buffer and the stub's load address off the tape;
  - group 1 is LDIR'd verbatim by the stub; then the group-1 DRIVER page
    decrypts group 1's payload (loading screen, a 4K block, the stage-2
    loader; $CF00-$FBFF on thirteen, $DC00-$FDFF on Empire) with a 256-byte
    key page K.  The key page arrives in group 1 at the address held in the
    loader buffer at offset $E7 and is itself XORed with the stub's two pages
    (the driver POPs the stub's return address to find them); the driver's
    own bytes $40-$FF are XORed with K[0..$BF]; the region (buffer+$E9)..page
    (buffer+$EC) with K[offset & $FF].  APPLIED here (--raw shows the tape
    bytes instead);
  - later groups are XORed before their copy with a key that is an IMMEDIATE
    in the stage-2 loader: LD A,(buffer+$103), the destination high byte, on
    eleven tapes; LD A,n, a constant, on three (Parabola $21, The King's
    Keep $16, Empire $37).  READ from the decrypted stage 2 (--xor-key auto,
    the default), whose entry is the page that loop sits in ($FA00 on
    thirteen, $FC00 on Empire); the tool prints the address and what it read.
What stays GAME-SPECIFIC is the driver's own copies after each group --
loading screen to $4000, the 4K block to $5E00..$7000, group 3 staged in the
display file and moved to $FA00 (or run from there: Kenny Dalglish jumps to
$4700), Parabola's 20K shift down by $1000, Ninja Scooter's $9C00-byte LDDR
up by $500, Back to the Future's $A000-byte LDDR up by $100, Empire's $500
move and $8800-byte LDDR up by $900 -- the CALLs into game code some drivers
make (Jaws 128K after its first later group, Back to the Future before its
shift: a bank switch or a copy in there is invisible here) -- and the
hand-over JP.  Those are READ from the decrypted driver page (a linear z80dis
walk: LD HL/DE/BC immediates + LDIR/LDDR, CALL stage-2 as the group boundary,
other CALLs, LD SP, the JP) and PRINTED; --apply-copies applies the copies
in code order at their group boundaries (a fill -- an LDIR whose destination
overlaps its source by one -- is skipped: it needs the register value the
code put there).  The diff attributes every mismatching page to one of: a
driver copy target, the display file, the loader buffer, the key or driver
page, the group-1 payload, the stack -- or UNATTRIBUTED, which is the
finding -- and, for the later-group blocks that later groups or copies
overwrote, searches the snapshot (all eight banks of a 128K one) for where
they went.  What a game does after the JP is the port's to name.

Bleepload turbo block, inside each TZX 0x11 block, after flag $FF:
    [gid][data * DATA_LEN][block#][dest lo][dest hi][tail ... ][XOR checksum]
  gid    groups blocks that load together: $64 = group 1 on every tape seen;
         later ids vary per title ($65/$66, $34/$35, $52, $5C/$5D, $16/$17,
         $3E/$3F, $36/$37, $51..$54) and are only ever compared with the id
         the driver hands to stage 2
  block# counts up within a group (a reload check)
  dest   where the DATA_LEN data bytes are copied: group 1 verbatim by the
         stub, later groups XORed with the key above by stage 2
  tail   [skip][end page][continuation][...][JP][length byte]: group-1 tails
         JP back into the stub; stage 2 reads the end page ($FF05) and the
         continuation address ($FF06) of each block

Usage:
    python tools/bleepload.py [--tape FILE] [--out build/image_tape.bin]
                              [--snapshot FILE] [--data-len N]
                              [--first-group ID] [--xor-key auto|hi|none|N]
                              [--raw] [--apply-copies]
                              [--no-xor-later-groups]     (= --xor-key none)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                   # noqa: E402
import tzx as tzxmod                                                # noqa: E402

try:
    import z80dis.z80 as z80
except ImportError:                     # the driver walk then reports "not read"
    z80 = None

DEFAULT_FIRST_GROUP = 0x64
STAGE2 = 0xFA00             # stage-2 entry (CALL in the driver = "load the next group") when not measured
BUF = 0xFE00                # the loader buffer (gid, 256 data, block#, dest, tail) when not measured


class Stub(bytes):
    """The 512-byte stage-1 stub, with the address its CODE header loads it at
    (.addr): $CD00 on every tape seen but one (Empire: $DA00)."""
    def __new__(cls, data, addr):
        s = super().__new__(cls, data)
        s.addr = addr
        return s


# ---------------------------------------------------------------------------
# the tape
# ---------------------------------------------------------------------------
def read_tape(tape, data_len=256, notes=None):
    """Every TZX turbo (0x11) block parsed as a Bleepload block -- a list of
    dicts {index, gid, data, blk, dest, tail, checksum_ok} -- and the stage-1
    stub (the 512-byte ROM-loaded CODE block, a Stub) or None.  A turbo block
    too short for the framing is skipped and noted in `notes`."""
    _, tblocks = tzxmod.parse(tape)
    out, stub = [], None
    want_code, code_addr = False, None
    for b in tblocks:
        if b.data is None:
            continue
        if b.id == 0x10:
            hdr = tzxmod.decode_header(b.data)
            if hdr is not None:
                want_code = hdr['type'] == 3 and hdr['length'] == 512
                code_addr = hdr.get('load_address')
            elif want_code and len(b.data) == 514:
                stub = Stub(b.data[1:-1], code_addr)
                want_code = False
            else:
                want_code = False
            continue
        if b.id != 0x11:
            continue
        d = b.data
        need = data_len + 6                # flag, gid, data, block#, dest lo/hi, checksum
        if len(d) < need:
            if notes is not None:
                notes.append(f'block #{b.index}: {len(d)} bytes, shorter than a Bleepload block '
                             f'with DATA_LEN {data_len} ({need} minimum) -- skipped')
            continue
        out.append(dict(index=b.index, gid=d[1], data=bytes(d[2:2 + data_len]),
                        blk=d[2 + data_len], dest=d[3 + data_len] | (d[4 + data_len] << 8),
                        tail=bytes(d[5 + data_len:-1]), checksum_ok=b.checksum_ok))
    return out, stub


def decode(tape, data_len=256):
    """The blocks alone (the original API)."""
    return read_tape(tape, data_len)[0]


def unscramble(block, first_group=DEFAULT_FIRST_GROUP, xor_later=True, xor_key='hi'):
    """A block's data as the loader copies it: the first group verbatim, later
    groups XORed with the destination high byte ('hi') or a constant."""
    data = block['data']
    if not xor_later or xor_key == 'none' or block['gid'] == first_group:
        return data
    k = (block['dest'] >> 8) if xor_key == 'hi' else int(xor_key) & 0xFF
    return bytes(x ^ k for x in data)


def place(img, loaded, dest, data):
    n = min(len(data), 0x10000 - dest)        # a block at $FF0x wraps into ROM: those bytes are dropped
    img[dest:dest + n] = data[:n]
    loaded[dest:dest + n] = b'\x01' * n


def build_naive(blocks, first_group=DEFAULT_FIRST_GROUP, xor_later=True, xor_key='hi'):
    """A 64K image with each block's data at its header destination, later
    groups de-XORed; no driver decryption, no copies.  (image, loaded mask)."""
    img, loaded = bytearray(0x10000), bytearray(0x10000)
    for b in blocks:
        place(img, loaded, b['dest'], unscramble(b, first_group, xor_later, xor_key))
    return img, loaded


# ---------------------------------------------------------------------------
# what the loader itself does, read from the tape bytes
# ---------------------------------------------------------------------------
def stub_params(stub):
    """What the stage-1 stub was assembled for -- the group id it accepts and
    the buffer it reads blocks into -- from its LD A,(buf) / CP n / JR NZ.
    None when the pattern is not there."""
    if not stub:
        return None
    m = re.search(rb'\x3a(..)\xfe(.)\x20', bytes(stub), re.S)
    if not m:
        return None
    return dict(first_group=m.group(2)[0], buf=m.group(1)[0] | (m.group(1)[1] << 8))


def stub_first_group(stub):
    """The group id the stage-1 stub accepts (see stub_params)."""
    p = stub_params(stub)
    return p['first_group'] if p else None


def driver_model(blocks, stub, first_group=DEFAULT_FIRST_GROUP, buf=BUF):
    """The group-1 driver's decryption, read from the tape.  Returns (model,
    None) or (None, why).  model: keypage, key (the 256 bytes K), region
    (lo, hi), driver (the block carrying the driver page, or None), last (the
    last group-1 block: its buffer image carries the parameters), buf, and
    stub_page (the page the stub loads at: the key to the key page)."""
    g1 = [b for b in blocks if b['gid'] == first_group]
    if len(g1) < 3:
        return None, f'fewer than 3 blocks in group ${first_group:02X}'
    if stub is None or len(stub) != 512:
        return None, 'no 512-byte ROM-loaded CODE block (the stage-1 stub) on the tape'
    stub_addr = getattr(stub, 'addr', None) or 0xCD00
    if stub_addr & 0xFF:
        return None, f'the stub loads at ${stub_addr:04X}, not a page boundary'
    page = stub_addr >> 8
    last = g1[-1]
    bimg = (bytes([last['gid']]) + last['data']              # the buffer as the last block leaves it
            + bytes([last['blk'], last['dest'] & 0xFF, last['dest'] >> 8]) + last['tail'])
    if len(bimg) < 0xED:
        return None, 'the last group-1 block is too short to carry the driver parameters'
    keypage = bimg[0xE7] | (bimg[0xE8] << 8)
    region = (bimg[0xE9] | (bimg[0xEA] << 8), bimg[0xEC] << 8)
    by_dest = {b['dest']: b for b in g1}
    if keypage & 0xFF or keypage not in by_dest:
        return None, f'($FEE7) = ${keypage:04X} is not a page-aligned group-1 block destination'
    if not (0x4000 <= region[0] < region[1] <= 0x10000):
        return None, f'($FEE9)..($FEEC) = ${region[0]:04X}..${region[1]:04X} is not a RAM range'
    key = bytes(by_dest[keypage]['data'][i] ^ stub[i] ^ stub[256 + i] for i in range(256))
    driver = None
    for b in g1[:-1]:      # PUSH IX / CALL stub-read / CALL stub-checksum, in clear; the last
        d = b['data']      # block mirrors this page with the parameters patched in, so skip it
        if (d[:2] == b'\xdd\xe5' and d[2] == 0xCD and d[4] == page and d[5] == 0xCD
                and d[7] in (page, page + 1)):
            driver = b
            break
    return dict(keypage=keypage, key=key, region=region, driver=driver, last=last,
                buf=buf, stub_page=page), None


def apply_driver(img, model):
    """What the driver does to group 1 before anything else is loaded."""
    K, (lo, hi) = model['key'], model['region']
    img[model['keypage']:model['keypage'] + 256] = K
    for a in range(lo, hi):
        img[a] ^= K[(a - lo) & 0xFF]
    if model['driver'] is not None:
        d = model['driver']['dest']
        for i in range(0xC0):
            img[d + 0x40 + i] ^= K[i]


def stage2_xor_key(img, region, buf=BUF):
    """The later-group XOR key, read from the decrypted stage-2 loader's copy
    loop: LD HL,buf+1 / LD BC,$100 / (LD A,(buf+$103) | LD A,n) / XOR (HL).
    Returns ('hi' or the constant, address of the key instruction), or
    (None, None) when the loop is not there.  The stage-2 entry is the page
    the loop sits in (address & $FF00)."""
    lo, hi = region
    seg = bytes(img[lo:hi])
    b1, dh = buf + 1, buf + 0x103
    head = bytes([0x21, b1 & 0xFF, b1 >> 8, 0x01, 0x00, 0x01])
    hi_key = bytes([0x3A, dh & 0xFF, dh >> 8, 0xAE])
    i = seg.find(head)
    while i >= 0:
        j = i + 6
        if seg[j:j + 4] == hi_key:
            return 'hi', lo + j
        if seg[j:j + 1] == b'\x3e' and seg[j + 2:j + 3] == b'\xae':
            return seg[j + 1], lo + j
        i = seg.find(head, i + 1)
    return None, None


def read_driver(img, model, stage2=STAGE2):
    """A linear z80dis walk of the decrypted driver page: its copies (LD
    HL/DE/BC immediates followed by LDIR/LDDR), the CALL stage-2 group
    boundaries, LD SP, and the JPs (the first JP after the last CALL stage-2
    is the hand-over).  None when there is no driver page or no z80dis."""
    if model['driver'] is None or z80 is None:
        return None
    base = model['driver']['dest']
    code = bytes(img[base:base + 0x100]) + bytes(4)
    regs, copies, calls, sps, jps, others = {}, [], [], [], [], []
    pc, group = 0, 1
    R, OT, OP = z80.REG, z80.OPER_TYPE, z80.OP
    while pc < 0x100:
        d = z80.decode(code[pc:pc + 4], base + pc)
        if not d.len:
            break
        ops = d.operands
        if d.op == OP.LD and len(ops) == 2 and ops[0][0] == OT.REG and ops[1][0] == OT.IMM:
            regs[ops[0][1]] = ops[1][1]
            if ops[0][1] == R.SP:
                sps.append((base + pc, ops[1][1]))
        elif d.op == OP.EX and len(ops) == 2 and (ops[0][1], ops[1][1]) == (R.DE, R.HL):
            regs[R.DE], regs[R.HL] = regs.get(R.HL), regs.get(R.DE)
        elif d.op in (OP.LDIR, OP.LDDR):
            hl, de, bc = regs.get(R.HL), regs.get(R.DE), regs.get(R.BC)
            if None not in (hl, de, bc) and bc:
                if d.op == OP.LDIR:
                    src, dst = hl, de
                    regs[R.HL], regs[R.DE] = (hl + bc) & 0xFFFF, (de + bc) & 0xFFFF
                else:                                   # LDDR copies [HL-BC+1..HL] -> [DE-BC+1..DE]
                    src, dst = (hl - bc + 1) & 0xFFFF, (de - bc + 1) & 0xFFFF
                    regs[R.HL], regs[R.DE] = (hl - bc) & 0xFFFF, (de - bc) & 0xFFFF
                copies.append(dict(at=base + pc, op='LDIR' if d.op == OP.LDIR else 'LDDR',
                                   src=src, dst=dst, len=bc, after_group=group,
                                   fill=(dst == src + 1) if d.op == OP.LDIR else (dst == src - 1)))
            regs[R.BC] = 0
        elif d.op == OP.CALL and ops and ops[-1][0] == OT.ADDR:
            if ops[-1][1] == stage2:
                calls.append(base + pc)
                group += 1
            elif ops[-1][1] >= 0x4000 and (ops[-1][1] >> 8) not in (model['stub_page'], model['stub_page'] + 1):
                others.append((base + pc, ops[-1][1], group))   # game code the driver runs: not read here
        elif d.op == OP.JP and len(ops) == 1 and ops[0][0] == OT.ADDR:
            jps.append((base + pc, ops[0][1], group))
            if calls and code[pc + 3:pc + 7] == b'\0\0\0\0':   # the page's zero padding follows
                break
        pc += d.len
    handover = next(((a, t) for a, t, g in jps if g == group and calls), None)
    return dict(base=base, copies=copies, calls=calls, others=others, sps=sps, jps=jps,
                groups=group, handover=handover)


def find_blocks(blocks, first_group, xor_key, img, windows):
    """For every later-group block the image no longer holds at its
    destination (a later group or a copy landed on it), search the snapshot's
    windows -- (name, 16K bytes) pairs: the three 48K thirds, or the eight
    128K banks -- page by page for its 256 bytes.  Those blocks are the R3
    coverage the destination diff cannot give.  {gid: [(dest, [(name, off)])]}"""
    out = {}
    for b in blocks:
        if b['gid'] == first_group:
            continue
        data = unscramble(b, first_group, True, xor_key)
        d = b['dest']
        if bytes(img[d:d + 256]) == data:
            continue
        hits = [(name, off) for name, mem in windows
                for off in range(0, len(mem) - 255, 0x100) if mem[off:off + 256] == data]
        out.setdefault(b['gid'], []).append((d, hits))
    return out


def apply_copies(img, loaded, copies, after_group):
    """The driver's copies for one group boundary, in code order, byte by byte
    in the direction the instruction works (so overlaps behave as on the Z80).
    Fills are skipped.  Returns the copies applied."""
    done = []
    for c in copies:
        if c['after_group'] != after_group or c['fill']:
            continue
        src, dst, n = c['src'], c['dst'], c['len']
        order = range(n) if c['op'] == 'LDIR' else range(n - 1, -1, -1)
        for i in order:
            s, t = (src + i) & 0xFFFF, (dst + i) & 0xFFFF
            img[t] = img[s]
            loaded[t] = loaded[s]
        done.append(c)
    return done


def attribute(page, model, copies, applied, raw, sp=None):
    """Why a page of the rebuilt image may legitimately differ from the snapshot."""
    if 0x4000 <= page < 0x5B00:
        return 'display file: transient (loading screen, "Loading" text, group-3 staging)'
    if sp is not None and page in ((sp - 1) & 0xFF00, (sp - 0x80) & 0xFF00):
        return f"the stack below SP=${sp:04X} at hand-over (the driver's own CALLs and pushes)"
    buf = (model['buf'] if model else BUF) & 0xFF00
    if buf <= page < buf + 0x200:
        return (f'loader buffer ${buf:04X}-${buf + 0x1FF:04X}: the last group-1 block lands over it; '
                'rewritten at run time')
    for c in copies or ():
        if c['dst'] < page + 0x100 and page < c['dst'] + c['len']:
            what = f"{c['op']} ${c['src']:04X}->${c['dst']:04X} ${c['len']:04X} after group {c['after_group']}"
            if c['fill']:
                return f"target of the driver's fill {what} (not applied: needs the register value)"
            return f"target of the driver's copy {what}" + ('' if applied else ' (not applied; --apply-copies)')
    if model is not None:
        if page == model['keypage']:
            return 'key page: decrypted in place by the driver' + (' (--raw)' if raw else '')
        if model['driver'] is not None and page == model['driver']['dest']:
            return ('driver page: its first bytes are rewritten with the next group id and text '
                    'position at run time' + (', and --raw skipped its decryption' if raw else ''))
        lo, hi = model['region']
        if lo <= page < hi:
            return ('group-1 payload: ' + ('encrypted on tape and --raw skipped the decryption' if raw
                    else 'stage-2 loader parameters rewritten at run time'))
    return 'UNATTRIBUTED'


# ---------------------------------------------------------------------------
def main():
    args = sys.argv[1:]
    if '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    tape = snap = None
    out = portconfig.path('build/image_tape.bin')
    data_len, first_group, xor_key = 256, None, 'auto'
    raw = apply = False
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
        elif a == '--xor-key':
            v = args[1].lower(); del args[:2]
            xor_key = v if v in ('auto', 'hi', 'none') else int(v, 0) & 0xFF
        elif a == '--no-xor-later-groups':
            xor_key = 'none'; del args[:1]
        elif a == '--raw':
            raw = True; del args[:1]
        elif a == '--apply-copies':
            apply = True; del args[:1]
        else:
            sys.exit(f'bleepload: unknown argument {a}')
    if data_len <= 0:
        sys.exit('bleepload: --data-len must be positive')
    if tape is None:
        tape = portconfig.path(portconfig.get('tape', 'path'))
        if tape is None:
            portconfig.need('tape', 'path', what='the Bleepload tape')
    if not os.path.exists(tape):
        sys.exit(f'bleepload: tape not found: {tape}')

    notes = []
    try:
        blocks, stub = read_tape(tape, data_len, notes)
    except (tzxmod.TzxError, OSError) as e:
        sys.exit(f'bleepload: {e}')
    for n in notes:
        print('  NOTE', n)

    # -- the groups and their sequencing ------------------------------------
    order = []
    groups = {}
    for b in blocks:
        if b['gid'] not in groups:
            order.append(b['gid'])
        groups.setdefault(b['gid'], []).append(b)
    print(f'{len(blocks)} turbo blocks in {len(groups)} groups: ' +
          ', '.join(f'${g:02X}={len(v)}' for g, v in sorted(groups.items())))
    bad = 0
    for gid, gblocks in sorted(groups.items()):
        for i, b in enumerate(gblocks):
            if b['blk'] != i:
                print(f"  NOTE block #{b['index']}: group ${gid:02X} number {b['blk']} != expected {i} "
                      f"(a variant, or not a Bleepload block -- check --data-len)")
                bad += 1
                break
    if groups and bad == len(groups):
        print('  NOTE no group sequences 0,1,2,...: not a Bleepload tape as this tool knows it, '
              'or --data-len is wrong -- the image below is NOT to be trusted')
    if not blocks:
        print('  no turbo blocks: nothing to rebuild')

    # -- the first group and the buffer: measured from the stub ---------------
    sp = stub_params(stub)
    measured = sp['first_group'] if sp else None
    buf = sp['buf'] if sp else BUF
    how = f"the stub's LD A,(${buf:04X}) / CP immediate"
    if measured is None:
        measured = blocks[0]['gid'] if blocks else DEFAULT_FIRST_GROUP
        how = "the first turbo block's gid (no stub CP found)" if blocks else 'the default'
    if first_group is None:
        first_group = measured
    elif first_group != measured:
        print(f'  NOTE --first-group ${first_group:02X} but {how} says ${measured:02X}; using yours')
    print(f'first group ${first_group:02X} ({how}); stub: '
          + (f'{len(stub)} bytes at ${stub.addr:04X}, buffer ${buf:04X}'
             + ('' if sp else ' (assumed)') if stub else 'not found'))

    # -- the driver's decryption of group 1 -----------------------------------
    model, why = driver_model(blocks, stub, first_group, buf) if blocks else (None, 'no blocks')
    img, loaded = bytearray(0x10000), bytearray(0x10000)
    for b in groups.get(first_group, ()):
        place(img, loaded, b['dest'], b['data'])
    if model is None:
        print(f'group-1 driver: not modelled ({why}); group 1 is left as the tape bytes')
    else:
        lo, hi = model['region']
        dblk = model['driver']
        kblk = [b for b in groups[first_group] if b['dest'] == model['keypage']][0]
        pg = model['stub_page']
        print(f"group-1 driver: key page ${model['keypage']:04X} (block #{kblk['index']}) "
              f"XOR stub ${pg:02X}00/${pg + 1:02X}00 -> K = {model['key'][:6].hex()}...; "
              f"decrypts ${lo:04X}-${hi - 1:04X}"
              + (f" and its own page ${dblk['dest']:04X}+$40 (block #{dblk['index']})" if dblk else
                 '; driver page not identified (no PUSH IX / CALL stub head)')
              + ('  [NOT applied: --raw]' if raw else '  [applied]'))
        if not raw:
            apply_driver(img, model)
    # -- the later groups' XOR key and the stage-2 entry, read from stage 2 ----
    stage2 = STAGE2
    found, at = stage2_xor_key(img, model['region'], buf) if (model and not raw) else (None, None)
    if found is not None:
        stage2 = at & 0xFF00
    if xor_key == 'auto':
        if found is None:
            xor_key = 'hi'
            print('later groups: stage-2 copy loop not found' + (' (--raw)' if raw else '')
                  + ' -- ASSUMING the destination high byte as the XOR key (--xor-key to override)')
        else:
            xor_key = found
            print(f'later groups: stage 2 (entry ${stage2:04X}) at ${at:04X} does '
                  + (f'LD A,(${buf + 0x103:04X}) -> XOR key = destination high byte' if found == 'hi'
                     else f'LD A,${found:02X} -> XOR key = constant ${found:02X}'))
    else:
        print('later groups: XOR key ' + ('none' if xor_key == 'none' else
                                         'destination high byte' if xor_key == 'hi' else f'${xor_key:02X}')
              + ' (from the command line)'
              + (f'; stage-2 entry ${stage2:04X} read from its copy loop at ${at:04X}' if found is not None
                 else f'; stage-2 entry assumed ${stage2:04X}'))
    # -- the driver's copies and hand-over ------------------------------------
    drv = read_driver(img, model, stage2) if (model and not raw) else None
    copies = drv['copies'] if drv else []
    if drv:
        print(f"driver page ${drv['base']:04X}: {len(drv['calls'])} CALL ${stage2:04X} (later groups), "
              f"{len(copies)} copies" + ('' if apply else ' (printed, not applied; --apply-copies)'))
        for c in copies:
            print(f"  after group {c['after_group']}: {c['op']} ${c['src']:04X}->${c['dst']:04X} "
                  f"${c['len']:04X} at ${c['at']:04X}" + ('  (a fill: skipped)' if c['fill'] else ''))
        for a, t, g in drv['others']:
            print(f'  after group {g}: CALL ${t:04X} at ${a:04X}  (game code the driver runs: not read; '
                  'a bank switch or a copy there is invisible here)')
        if drv['handover']:
            sp = [v for a, v in drv['sps'] if a < drv['handover'][0]]
            print(f"  hand-over: JP ${drv['handover'][1]:04X} at ${drv['handover'][0]:04X}"
                  + (f' (LD SP,${sp[-1]:04X})' if sp else ''))
        else:
            print('  hand-over JP: not found in the walk')
    elif model is not None and not raw:
        print('driver page: not read' + ('' if z80 else ' (z80dis not installed)'))

    # -- build, in the loader's order: group 1 + driver, then each later group + copies
    if apply:
        apply_copies(img, loaded, copies, 1)
    for gi, gid in enumerate(order, 1):
        if gid == first_group:
            continue
        for b in groups[gid]:
            place(img, loaded, b['dest'], unscramble(b, first_group, True, xor_key))
        if apply:
            apply_copies(img, loaded, copies, gi)

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
    print(f'wrote {out} (block data at header destinations'
          + (', group 1 decrypted as the driver does' if model and not raw else '')
          + (', driver copies applied' if apply and copies else '') + ')')

    # -- the diff -------------------------------------------------------------
    if not snap:
        return
    if not os.path.exists(snap):
        print(f'\nsnapshot not found: {snap} -- no diff')
        return
    from skoolkit.snapshot import Snapshot
    s = Snapshot.get(snap)
    ram = s.ram(-1)
    if len(ram) != 0xC000:
        page = s.out7ffd & 7
        windows = [(f'bank {k}', bytes(ram[k * 0x4000:(k + 1) * 0x4000])) for k in range(8)]
        bases = {}                              # a bank has no fixed address
        ram = s.ram(page)
        print(f'\n(128K snapshot: comparing against banks 5/2/{page}, the 48K view as paged at the snapshot)')
    else:
        windows = [(f'${b:04X}', bytes(ram[b - 0x4000:b])) for b in (0x4000, 0x8000, 0xC000)]
        bases = {name: int(name[1:], 16) for name, _ in windows}      # ram[0] is $4000
    compared = mism = 0
    bad_pages = {}
    for a in range(0x4000, 0x10000):
        if not loaded[a]:
            continue
        compared += 1
        if img[a] != ram[a - 0x4000]:
            mism += 1
            bad_pages[a & 0xFF00] = bad_pages.get(a & 0xFF00, 0) + 1
    unattributed = 0
    lines = []
    for p in sorted(bad_pages):
        why = attribute(p, model, copies, apply, raw, s.sp)
        if why == 'UNATTRIBUTED':
            unattributed += bad_pages[p]
        lines.append(f'  ${p:04X}: {bad_pages[p]:3d} bytes differ -- {why}')
    print(f'\nvs {os.path.basename(snap)}: bytes compared {compared} / mismatching {mism} '
          f'in {len(bad_pages)} pages / unattributed {unattributed}')
    for l in lines:
        print(l)
    if unattributed:
        print('  UNATTRIBUTED bytes are the finding: a transform this tool does not know '
              '(name it in your port, or it is a variant).')
    lost = find_blocks(blocks, first_group, xor_key, img, windows)
    for gid, lst in sorted(lost.items()):
        from collections import Counter
        # a 48K window has an address, so the hit is "dest shifted by N"; a bank has an offset
        c = Counter((w if w not in bases else '48K', (bases.get(w, 0) + off - d) & 0xFFFF)
                    for d, h in lst for w, off in h)
        located = sum(1 for d, h in lst if h)
        line = (f'group ${gid:02X}: {len(lst)} blocks no longer at their destination in the image '
                f'(later groups or copies landed on them); {located} found in the snapshot')
        if c:
            (w, delta), n = c.most_common(1)[0]
            sign, mag = ('+', delta) if delta < 0x8000 else ('-', 0x10000 - delta)
            line += (f', {n} of them at dest{sign}${mag:04X}' if w == '48K'
                     else f', {n} of them in {w} at offset dest{sign}${mag:04X}')
        print(line + ('' if located else ' -- NOT verified anywhere (R3 gap, or transformed)'))


if __name__ == '__main__':
    main()
