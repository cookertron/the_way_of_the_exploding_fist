#!/usr/bin/env python3
"""
selftest.py -- prove the kit's tools work with NO tape and NO manifest values.

Everything here is synthetic: a TZX built in memory (a BASIC loader whose
RANDOMIZE USR carries the 5-byte binary form, plus a 256-byte CODE block), code
poked into a ROM-only harness, tiny images for the walker, the byte-grep, the
disassembler and the renderers.  It exercises the parts a port relies on before
it has anything real to feed them, so a broken environment (no SkoolKit ROM,
the wrong z80dis, no PIL) shows up here and not three phases later.

Usage:  python tools/selftest.py [-v]        (-v prints tracebacks)
Exit status is non-zero if any check fails.
"""
import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

VERBOSE = '-v' in sys.argv
RESULTS = []


def mod(name):
    return importlib.import_module(name)


def check(name, fn):
    try:
        fn()
    except Exception as e:                      # noqa: BLE001
        RESULTS.append((name, False))
        print(f'FAIL  {name}: {e!r}')
        if VERBOSE:
            traceback.print_exc()
        return
    RESULTS.append((name, True))
    print(f'ok    {name}')


def eq(got, want, what=''):
    if got != want:
        raise AssertionError(f'{what}: got {got!r}, want {want!r}')


# ---------------------------------------------------------------------------
# a synthetic tape: text block, BASIC header+data, CODE header+data, pause
# ---------------------------------------------------------------------------
USR = 32768
CODE = bytes((i * 7 + 3) & 0xFF for i in range(256))


def le16(v):
    return bytes([v & 0xFF, (v >> 8) & 0xFF])


def rom_block(flag, body):
    data = bytes([flag]) + bytes(body)
    x = 0
    for b in data:
        x ^= b
    return data + bytes([x])


def header(htype, name, length, p1, p2):
    return rom_block(0x00, bytes([htype]) + name.encode('latin-1')[:10].ljust(10)
                     + le16(length) + le16(p1) + le16(p2))


def std_block(data, pause=1000):
    return bytes([0x10]) + le16(pause) + le16(len(data)) + data


def num5(n):
    """The 5-byte small-integer form the ROM stores behind a literal."""
    return bytes([0x0E, 0x00, 0x00, n & 0xFF, (n >> 8) & 0xFF, 0x00])


def basic_line(number, body):
    return bytes([number >> 8, number & 0xFF]) + le16(len(body)) + body


# 10 RANDOMIZE USR 32768
PROG = basic_line(10, bytes([0xF9, 0xC0]) + b'32768' + num5(USR) + b'\r')


def make_tzx():
    return (b'ZXTape!\x1a' + bytes([1, 20])
            + bytes([0x30, 8]) + b'selftest'                                  # 0 text
            + std_block(header(0, 'loader', len(PROG), 10, len(PROG)))       # 1 BASIC header
            + std_block(rom_block(0xFF, PROG))                                # 2 BASIC data
            + std_block(header(3, 'code', len(CODE), USR, 32768))            # 3 CODE header
            + std_block(rom_block(0xFF, CODE))                                # 4 CODE data
            + bytes([0x20]) + le16(0))                                        # 5 stop


@contextlib.contextmanager
def tzx_file():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'selftest.tzx')
        open(p, 'wb').write(make_tzx())
        yield p


# ---------------------------------------------------------------------------
# phase 1: tzx.py / basic.py
# ---------------------------------------------------------------------------
def t_tzx_parse():
    tzx = mod('tzx')
    (maj, mino), blocks = tzx.parse_bytes(make_tzx())
    eq((maj, mino), (1, 20), 'version')
    eq([b.id for b in blocks], [0x30, 0x10, 0x10, 0x10, 0x10, 0x20], 'block ids')
    eq([b.index for b in blocks], list(range(6)), 'indices')
    eq([b.checksum_ok for b in blocks if b.data is not None], [True] * 4, 'checksums')
    h0 = tzx.decode_header(blocks[1].data)
    eq((h0['type'], h0['name'], h0['length'], h0['autostart_line']),
       (0, 'loader    ', len(PROG), 10), 'BASIC header')
    h1 = tzx.decode_header(blocks[3].data)
    eq((h1['type'], h1['load_address'], h1['length']), (3, USR, 256), 'CODE header')
    eq(bytes(blocks[2].data[1:-1]), PROG, 'BASIC body')
    eq(bytes(blocks[4].data[1:-1]), CODE, 'CODE body')
    eq(len(blocks[4].data) - 2, h1['length'], 'body length vs header')
    eq(blocks[0].info['text'], 'selftest', 'text block')
    eq(blocks[5].info['pause_ms'], 0, 'stop block')


def t_tzx_file_and_report():
    tzx = mod('tzx')
    with tzx_file() as p:
        _, blocks = tzx.parse(p)
        eq(len(blocks), 6, 'blocks via file')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tzx.report(p)
        text = out.getvalue()
        assert 'No checksum or length problems.' in text, text
        assert 'HEADER: BASIC program' in text and 'HEADER: Code' in text, text
        assert 'MATCH' in text and 'MISMATCH' not in text, text


def t_tzx_bad_checksum():
    tzx = mod('tzx')
    raw = bytearray(make_tzx())
    i = raw.find(CODE[:8])
    raw[i + 3] ^= 0x01
    _, blocks = tzx.parse_bytes(bytes(raw))
    eq(blocks[4].checksum_ok, False, 'flipped byte detected')
    eq(blocks[2].checksum_ok, True, 'other block still fine')


def t_tzx_unhandled_stops():
    tzx = mod('tzx')
    raw = make_tzx()[:10] + bytes([0x16, 0, 0, 0, 0])      # a deprecated C64 block
    try:
        tzx.parse_bytes(raw)
    except tzx.TzxError as e:
        assert 'UNHANDLED BLOCK ID 0x16' in str(e), e
        return
    raise AssertionError('parser skipped an unhandled block instead of stopping')


def t_basic():
    basic = mod('basic')
    lines, consumed = basic.detokenise(PROG)
    eq(lines, [(10, 'RANDOMIZE USR 32768<=32768>')], 'listing')
    eq(consumed, len(PROG), 'consumed')
    eq(basic.usr_targets(PROG), [(10, USR)], 'USR targets')
    eq(basic.float5(bytes([0, 0, 0, 0x80, 0])), 32768, 'small int')
    eq(basic.float5(bytes([0, 0xFF, 0xFF, 0xFF, 0])), -1, 'negative small int')
    eq(basic.float5(bytes([0x80, 0, 0, 0, 0])), 0.5, 'FP 0.5')
    eq(basic.float5(bytes([0x81, 0, 0, 0, 0])), 1.0, 'FP 1.0')
    # the digits lie, the binary form is what runs
    lying = basic_line(20, bytes([0xF9, 0xC0]) + b'32768' + num5(23778) + b'\r')
    eq(basic.usr_targets(lying), [(20, 23778)], 'binary form wins')


# ---------------------------------------------------------------------------
# phase 2: mkloader.py / mkimage.py
# ---------------------------------------------------------------------------
def t_mkloader():
    mkloader = mod('mkloader')
    tzx = mod('tzx')
    eq(mkloader.PROG - mkloader.CHANS, 21, 'CHANS is the 21-byte stock block')
    eq(mkloader.PROG, 0x5CCB, 'PROG on a stock 48K')
    _, blocks = tzx.parse_bytes(make_tzx())
    idx, basic = mkloader.find_basic(blocks)
    eq((idx, basic), (2, PROG), 'BASIC block found via its header')
    mem = mkloader.build_loader_image(basic, copies=[(0x5CCB, 0xFF00, len(PROG))])
    eq(len(mem), 0x10000, 'image size')
    eq(bytes(mem[0x5CCB:0x5CCB + len(PROG)]), PROG, 'BASIC at PROG')
    eq((mem[0x5CCB], mem[0x5CCC]), (0, 10), 'first line number, big-endian, at PROG')
    eq(mem[0x5CCA], 0, 'nothing below PROG')
    eq(bytes(mem[0xFF00:0xFF00 + len(PROG)]), PROG, 'hand-performed relocation')


def t_mkimage_auto():
    mkimage = mod('mkimage')
    with tzx_file() as p:
        mem, lines = mkimage.build_image(p)                 # blocks: follow the headers
    eq(len(mem), 0x10000, 'image size')
    eq(bytes(mem[0x5CCB:0x5CCB + len(PROG)]), PROG, 'BASIC at PROG')
    eq(bytes(mem[USR:USR + 256]), CODE, 'CODE at its header address')
    eq(len(lines), 2, 'two placements reported')
    assert lines[1].startswith('block #4'), lines


def t_mkimage_explicit():
    mkimage = mod('mkimage')
    tzx = mod('tzx')
    _, blocks = tzx.parse_bytes(make_tzx())
    spec = [{'dest': 0x5CCB, 'flag': 0xFF},                  # first unused $FF block = BASIC
            {'dest': 0x9000, 'len': 256, 'block': 4}]        # by TZX index
    mem, lines = mkimage.place(blocks, spec, copies=[(0x9000, 0xA000, 16)])
    eq(bytes(mem[0x5CCB:0x5CCB + len(PROG)]), PROG, 'flag match took the BASIC block')
    eq(bytes(mem[0x9000:0x9100]), CODE, 'index match placed CODE')
    eq(bytes(mem[0xA000:0xA010]), CODE[:16], 'copy applied after placement')
    eq(len(lines), 3, 'placements + copy reported')
    mem, lines = mkimage.place(blocks, spec, upto=1)
    eq(bytes(mem[0x9000:0x9100]), bytes(256), '--upto leaves later blocks out')
    assert any('not placed' in l for l in lines), lines
    for bad in ([{'dest': 0x9000, 'len': 255, 'block': 4}],
                [{'dest': 0x9000, 'block': 9}],
                [{'dest': 0xFFF0, 'block': 4}]):
        try:
            mkimage.place(blocks, bad)
        except mkimage.ImageError:
            continue
        raise AssertionError(f'{bad} accepted')


# ---------------------------------------------------------------------------
# phase 6: screen.py
# ---------------------------------------------------------------------------
def t_screen_addr():
    screen = mod('screen')
    for x, y, want in [(0, 0, 0x4000), (8, 0, 0x4001), (255, 0, 0x401F),
                       (0, 1, 0x4100), (0, 7, 0x4700), (0, 8, 0x4020),
                       (0, 63, 0x47E0), (16, 63, 0x47E2), (0, 64, 0x4800),
                       (0, 191, 0x57E0), (255, 191, 0x57FF)]:
        eq(screen.scr_addr(x, y), want, f'scr_addr({x},{y})')
    for x, y, want in [(0, 0, 0x5800), (8, 8, 0x5821), (255, 191, 0x5AFF)]:
        eq(screen.attr_addr(x, y), want, f'attr_addr({x},{y})')
    every = {screen.scr_addr(x, y) for y in range(192) for x in range(0, 256, 8)}
    eq(every, set(range(0x4000, 0x5800)), 'display file is a bijection onto $4000-$57FF')


def t_screen_render():
    screen = mod('screen')
    mem = bytearray(0x10000)
    mem[screen.scr_addr(0, 0)] = 0x80
    mem[screen.attr_addr(0, 0)] = 0x47                      # BRIGHT, ink 7, paper 0
    mem[screen.scr_addr(8, 0)] = 0xFF
    mem[screen.attr_addr(8, 0)] = 0x02                      # ink 2 (dim), paper 0
    mem[screen.attr_addr(0, 8)] = 0x87                      # FLASH, ink 7, paper 0; no pixels
    img = screen.render(mem)
    px = img.load()
    eq(img.size, (256, 192), 'size')
    eq(px[0, 0], (255, 255, 255), 'bright ink pixel')
    eq(px[1, 0], (0, 0, 0), 'paper pixel')
    eq(px[8, 0], (0xD7, 0, 0), 'dim red')
    eq(px[0, 8], (0, 0, 0), 'flash cell, phase 0 shows paper')
    px2 = screen.render(mem, flash_phase=1).load()
    eq(px2[0, 8], (0xD7, 0xD7, 0xD7), 'flash cell, phase 1 swaps')
    at = screen.render_attrs(mem)
    eq(at.size, (32, 24), 'attr sheet size')
    eq(at.load()[0, 0], (255, 255, 255), 'attr sheet shows ink')


# ---------------------------------------------------------------------------
# phase 7: harness.py, ROM only
# ---------------------------------------------------------------------------
def fresh():
    """ROM only, blank RAM, PC=0 -- independent of whatever port.json says."""
    H = mod('harness')
    return H, H.Harness(image=False, deck=False, entry=0)


def t_harness_rom():
    H, h = fresh()
    eq(h.peek(0, 3), b'\xF3\xAF\x11', 'real 48K ROM starts DI; XOR A; LD DE,...')
    eq(h.pc(), 0, 'entry honoured')
    eq(h.regs[H.SP], 0xFFFF, 'default SP')
    h.mem[0x0000] = 0x00
    eq(h.memobj.rom_writes, 1, 'ROM write counted')
    eq(h.peek(0), b'\xF3', 'ROM write ignored')
    assert h.deck is None and h.tape_call_pc is None


def t_harness_run():
    H, h = fresh()
    h.poke(0x8000, 0x3E, 0x07,            # LD A,7        7T
           0xD3, 0xFE,                    # OUT ($FE),A  11T
           0x06, 0x03,                    # LD B,3        7T
           0x10, 0xFE,                    # DJNZ $       13T,13T,8T
           0x76)                          # HALT
    h.regs[H.PC] = 0x8000
    h.ports.record_writes = True
    h.step(2)
    eq(h.regs[H.A], 7, 'A after LD')
    eq(h.tstates(), 18, 'T after LD + OUT')
    eq(len(h.ports.writes), 1, 'one port write')
    eq((h.ports.writes[0][1] & 0xFF, h.ports.writes[0][2]), (0xFE, 7), 'OUT ($FE),7 seen')
    reason, n = h.run_until(0x8008)
    eq(reason, 'target', 'reached HALT')
    eq(h.regs[H.B], 0, 'DJNZ ran down')
    eq(h.tstates(), 59, 'T-states exact through the DJNZ loop')
    eq(h.pc(), 0x8008, 'stopped ON the target, not past it')


def t_harness_ports():
    H, h = fresh()
    kp = mod('keyprobe')
    prog = [0x01, 0xFE, 0xFE, 0xED, 0x78, 0x32, 0x00, 0x90,    # LD BC,$FEFE; IN A,(C); LD ($9000),A
            0xDB, 0x1F, 0x32, 0x01, 0x90,                      # IN A,($1F);  LD ($9001),A
            0x01, 0xFF, 0x7F, 0xED, 0x78, 0x32, 0x02, 0x90,    # LD BC,$7FFF; IN A,(C); LD ($9002),A
            0x01, 0xFE, 0x00, 0xED, 0x78, 0x32, 0x03, 0x90,    # LD BC,$00FE; IN A,(C); LD ($9003),A
            0x00]
    h.poke(0x8100, *prog)
    end = 0x8100 + len(prog) - 1
    kp.press(h.ports, 'z')                                      # CAPS..V half-row, bit 1
    h.ports.kempston = 0x10                                     # fire
    h.regs[H.PC] = 0x8100
    eq(h.run_until(end)[0], 'target', 'ran')
    eq(h.peek(0x9000, 4), bytes([0xFD, 0x10, 0xFF, 0xFD]),
       'half-row with Z, Kempston fire, unattached $FF, B=0 selects all rows')
    assert 0xFEFE in h.ports.reads and 0x7FFF in h.ports.reads, h.ports.reads
    h.ports.release_all()
    h.regs[H.PC] = 0x8100
    h.run_until(end)
    eq(h.peek(0x9000, 4), bytes([0xFF, 0x00, 0xFF, 0xFF]), 'everything released')


def t_harness_watch():
    H, h = fresh()
    h.poke(0x8200, 0x21, 0x00, 0x91,       # LD HL,$9100
           0x36, 0x55,                     # LD (HL),$55
           0x3E, 0x66,                     # LD A,$66
           0x32, 0x50, 0x91,               # LD ($9150),A
           0x32, 0x00, 0x92,               # LD ($9200),A   outside the window
           0x00)
    h.regs[H.PC] = 0x8200
    h.memobj.watch(0x9100, 0x9200)
    h.run_until(0x820D)
    h.memobj.unwatch()
    eq(h.memobj.log, [(0x8203, 0x9100, 0x55), (0x8207, 0x9150, 0x66)], 'write log (PC, addr, value)')
    eq(h.peek(0x9200), b'\x66', 'unwatched write still lands')


def t_harness_state():
    H, h = fresh()
    h.poke(0x9300, 0x11)
    h.regs[H.PC] = 0x8000
    s = h.save_state()
    h.poke(0x9300, 0x22)
    h.regs[H.PC] = 0x1234
    h.load_state(s)
    eq((h.peek(0x9300), h.pc()), (b'\x11', 0x8000), 'load_state is exact')
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'st.pkl')
        h.save_state_file(p)
        h.poke(0x9300, 0x33)
        h.load_state_file(p)
    eq(h.peek(0x9300), b'\x11', 'state file round trip')
    snap = h.snapshot(0x9000, 0x9400)
    h.poke(0x9300, 0x99)
    eq(h.diff(snap, 0x9000, 0x9400), [(0x9300, 0x11, 0x99)], 'diff finds the one change')


def t_harness_call():
    H, h = fresh()
    h.poke(0x8300, 0x3E, 0x42, 0xC9)                    # LD A,$42; RET
    h.poke(0x8310, 0xE1, 0xC9)                          # POP HL; RET  (discards one return)
    h.poke(0x8320, 0x18, 0xFE)                          # JR $
    h.poke(0x8330, 0x7C, 0xC9)                          # LD A,H; RET
    idx, t, n = h.call(0x8300)
    eq((idx, t, h.regs[H.A]), (0, 17, 0x42), 'normal return: sentinel 0, 7+10 T')
    eq(h.call(0x8310)[0], 1, 'one discarded return lands on sentinel 1')
    eq(h.call(0x8320, limit=500)[0], None, 'runaway routine reports None')
    h.call(0x8330, regs={'HL': 0x1234, 'A': 5})
    eq(h.regs[H.A], 0x12, 'register seeding by name')


def t_harness_find():
    H, h = fresh()
    h.poke(0x8000, 0x3E, 0x07, 0xD3, 0xFE)
    eq(h.find_bytes(bytes([0x3E, 0x07, 0xD3, 0xFE])), [0x8000], 'find_bytes')
    eq(h.find_bytes(bytes([0x3E, 0x07]), lo=0x8001), [], 'range respected')


def t_harness_image():
    H = mod('harness')
    img = bytearray(0x10000)
    img[0x8000] = 0xC9
    img[0x0000] = 0x00                                    # a bogus ROM area, must be ignored
    h = H.Harness(image=bytes(img), deck=False, entry=0x8000)
    eq((h.pc(), h.peek(0x8000), h.peek(0)), (0x8000, b'\xC9', b'\xF3'), 'image bytes + real ROM')
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'img.bin')
        open(p, 'wb').write(img)
        h = H.Harness(image=p, deck=False, entry=0x8000)
    eq(h.peek(0x8000), b'\xC9', 'image file')


def t_harness_interrupts():
    H, h = fresh()
    h.poke(0x8400, 0x76, 0xC3, 0x00, 0x84)                # HALT; JP $8400
    h.regs[H.PC] = 0x8400
    h.regs[H.IM] = 1
    h.regs[H.IFF] = 1
    h.regs[H.IYh], h.regs[H.IYl] = 0x5C, 0x3A            # IY as the ROM ISR expects
    for a in range(0x5C00, 0x5C08):
        h.poke(a, 0xFF)                                   # KSTATE free, as after NEW
    frames0 = h.peek16(0x5C78)
    h.step(3000)
    frames = h.peek16(0x5C78) - frames0
    assert frames >= 2, f'FRAMES advanced {frames}'
    assert h.halts_skipped > 0, 'fast HALT never engaged'
    # one interrupt at T=0, then one per frame boundary: N interrupts span N-1 frames
    assert h.tstates() >= (frames - 1) * H.FRAME_T, (h.tstates(), frames)
    assert h.tstates() < (frames + 1) * H.FRAME_T, (h.tstates(), frames)


def t_harness_contended():
    H = mod('harness')
    hc = H.Harness(image=False, deck=False, contended=True)
    hp = H.Harness(image=False, deck=False, contended=False)
    eq((hc.contended, hp.contended), (True, False), 'per-instance switch')
    eq(type(hp.sim).__name__, 'Simulator', 'plain class')
    eq(type(hc.sim).__name__, 'CMIOSimulator', 'contended class')
    for h in (hc, hp):
        h.poke(0x6000, *([0x00] * 128))                    # NOPs in contended RAM
    # top border: no contention, identical clocks
    for h in (hc, hp):
        h.regs[H.PC] = 0x6000
        h.regs[H.T] = 0
        h.step(100, interrupts=False)
    eq(hc.tstates(), hp.tstates(), 'no contention in the top border')
    # inside the display period: the contended machine is slower
    for h in (hc, hp):
        h.regs[H.PC] = 0x6000
        h.regs[H.T] = 14335 + 200
        h.step(100, interrupts=False)
    assert hc.tstates() > hp.tstates(), (hc.tstates(), hp.tstates())
    # and the module default follows the manifest / PORT_CONTENDED
    pc = mod('portconfig')
    eq(H.Harness(image=False, deck=False).contended, pc.contended(), 'module default')


def t_readwatch_swap():
    H, h = fresh()
    rw = mod('readwatch')
    h.poke(0x8500, 0x3A, 0x00, 0x92, 0x3A, 0x01, 0x92, 0xC3, 0x00, 0x85)   # LD A,($9200); LD A,($9201); JP
    h.regs[H.PC] = 0x8500
    rm = rw.ReadMem(h.memobj.m, h.sim, 0x9200, 0x9300)
    rw.watch(h, rm, frames=1)
    assert rm.by_addr[0x9200] > 100 and rm.by_addr[0x9201] > 100, dict(rm.by_addr)
    eq(set(rm.by_pc), {0x8500, 0x8503}, 'reads attributed to the reading PCs')
    eq(set(rm.by_addr), {0x9200, 0x9201}, 'only the window is counted')


# ---------------------------------------------------------------------------
# phases 3-4: walk.py / grepbytes.py / adis.py / strings.py / hexdump.py
# ---------------------------------------------------------------------------
def walk_image():
    mem = bytearray(0x10000)
    mem[0x8000:0x800B] = bytes([0x3E, 0x07, 0xD3, 0xFE, 0xCD, 0x00, 0x81, 0xD7, 0xC3, 0x00, 0x80])
    mem[0x800B] = 0xFF                                    # stray data byte, never reached
    mem[0x8100:0x8107] = bytes([0x06, 0x03, 0x10, 0xFE, 0xDB, 0xFE, 0xC9])
    mem[0x8200:0x8203] = bytes([0xED, 0x56, 0x76])       # IM 1; HALT
    return mem


def t_walk():
    walk = mod('walk')
    mem = walk_image()
    seen, covered, calls, jumps = walk.walk(mem, [0x8000, 0x8200])
    eq(seen, {0x8000, 0x8002, 0x8004, 0x8007, 0x8008, 0x8100, 0x8102, 0x8104, 0x8106, 0x8200, 0x8202},
       'instruction boundaries')
    eq(len(covered), 21, 'bytes covered')
    assert 0x800B not in covered, 'data byte wrongly covered'
    eq(calls, {0x8100: {0x8004}, 0x10: {0x8007}}, 'call graph incl. RST')
    eq(jumps, {0x8000: {0x8008}, 0x8102: {0x8102}}, 'jumps incl. DJNZ self-loop')
    eq(walk.regions(covered), [(0x8000, 0x800A), (0x8100, 0x8106), (0x8200, 0x8202)], 'regions')
    po, pi, rc, hl, ims = walk.inventory(mem, seen)
    eq(po, [(0x8002, 0xFE, 'OUT (n),A')], 'port writes')
    eq(pi, [(0x8104, 0xFE, 'IN A,(n)')], 'port reads')
    eq(rc, [(0x8007, 0x10)], 'transfers below $4000')
    eq(hl, [0x8202], 'HALTs')
    eq([a for a, _ in ims], [0x8200], 'IM instructions')


def t_grepbytes():
    gb = mod('grepbytes')
    mem = bytearray(0x10000)
    mem[0x8000:0x8005] = bytes([0x21, 0x00, 0x90, 0xD3, 0xFE])
    eq(gb.search(mem, bytes([0x21, 0x00, 0x90])), [0x8000], 'search')
    eq(gb.search(mem, bytes([0x00]), 0x8000, 0x8003), [0x8001], 'ranged search')
    eq(gb.confirm(mem, 0x8000), 2, 'instruction boundary confirmed')
    eq(gb.confirm(mem, 0x8001), None, 'operand byte is NOT a boundary')


def t_adis():
    adis = mod('adis')
    mem = walk_image()
    syms = adis.load_syms()
    eq(syms[0x0556], 'ROM_LD_BYTES', 'ROM symbols present')
    eq(adis.substitute('CALL 0x0556', syms), 'CALL ROM_LD_BYTES', 'substitution')
    syms[0x8100] = 'sub'
    out = io.StringIO()
    adis.disasm(mem, 0x8000, 5, syms=syms,
                regions=[{'start': 0x8000, 'end': 0x80FF, 'desc': 'main', 'kind': 'code'}], out=out)
    text = out.getvalue()
    assert 'CALL sub' in text, text
    assert '8000  3E 07' in text and 'RST' in text and '; ===== 8000-80FF  main (code)' in text, text
    out = io.StringIO()
    adis.disasm(mem, 0x8100, 1, syms=syms,
                regions=[{'start': 0x8100, 'end': 0x810F, 'desc': 'table', 'kind': 'data'}], out=out)
    assert 'sub:' in out.getvalue() and 'DEFB $06,$03' in out.getvalue(), out.getvalue()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'regions.json')
        json.dump([{'start': '0x8100', 'end': '$81FF', 'desc': 'x', 'kind': 'code'}], open(p, 'w'))
        r = adis.load_regions(p)
        eq((r[0]['start'], r[0]['end']), (0x8100, 0x81FF), 'hex strings in regions.json')
        q = os.path.join(d, 'symbols.json')
        adis.save_sym('main', 0x8000, q)
        eq(adis.load_syms(q)[0x8000], 'main', 'symbols.json round trip')
    eq(adis.load_regions(os.path.join(HERE, 'regions.json')), [], 'shipped regions.json is empty')
    assert 0x8000 not in adis.load_syms(os.path.join(HERE, 'symbols.json')), 'shipped symbols.json is empty'


def t_strings_hexdump():
    st = mod('strings')
    hd = mod('hexdump')
    mem = bytearray(0x10000)
    mem[0x9000:0x9005] = b'HELLO'
    mem[0x9010:0x9015] = b'WORL' + bytes([ord('D') | 0x80])
    eq(st.runs(mem, 0x8000, 0xA000, 5), [(0x9000, 'HELLO')], 'ascii runs')
    eq(st.runs_hi(mem, 0x8000, 0xA000, 5), [(0x9000, 'HELLO'), (0x9010, 'WORLD')], 'bit-7 runs')
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        hd.dump(b'ABC', base=0x8000)
    line = out.getvalue().rstrip('\n')
    assert line.startswith('8000  41 42 43') and line.endswith('|ABC|'), line


# ---------------------------------------------------------------------------
# phase 5: contact.py / speckle.py
# ---------------------------------------------------------------------------
def t_speckle():
    sp = mod('speckle')
    solid = sp.score(bytes([0xFF]) * 32, 0, 2, 16)
    eq((solid['density'], solid['iso'], solid['single_runs'], solid['speckle']), (1.0, 0, 0, 0.0), 'solid = art')
    board = sp.score(bytes([0x55, 0x55, 0xAA, 0xAA]) * 8, 0, 2, 16)
    eq((board['density'], board['iso'], board['single_runs'], board['speckle']), (0.5, 1.0, 1.0, 2.0), 'checkerboard = noise')
    eq(sp.score(bytes(32), 0, 2, 16), None, 'empty block')
    eq(sp.score(bytes(16), 0, 2, 16), None, 'short block')


def t_contact():
    ct = mod('contact')
    data = bytearray(32)
    data[0], data[1] = 0x80, 0x01                          # row 0: leftmost and rightmost pixel
    imgs = ct.cells_row_major(bytes(data), 2, 16)
    eq(len(imgs), 1, 'one cell')
    eq(imgs[0].size, (16, 16), 'cell size')
    px = imgs[0].load()
    eq((px[0, 0], px[15, 0], px[1, 0]), ((255, 255, 255), (255, 255, 255), (0, 0, 0)), 'row-major pixels')
    data = bytes([0xFF] * 8) + bytes(24)                   # cell-major: first 8x8 cell solid
    px = ct.cells_cell_major(data, 2, 16)[0].load()
    eq((px[7, 7], px[8, 0], px[0, 8]), ((255, 255, 255), (0, 0, 0), (0, 0, 0)), 'cell-major pixels')
    eq(ct.sheet(imgs, 4, 'row').size, (72, 28), 'sheet geometry')


# ---------------------------------------------------------------------------
# keyprobe.py exports and portconfig.py
# ---------------------------------------------------------------------------
def t_keyprobe_exports():
    kp = mod('keyprobe')
    eq(len(kp.KEYS), 40, '40 keys')
    eq(len({n for n, _, _ in kp.KEYS}), 40, 'unique names')
    eq(kp.KEYS[0], ('CAPS', 0xFE, 0), 'first key')
    eq(kp.KEYS[-1], ('B', 0x7F, 4), 'last key')
    eq((kp.keymask(0), kp.keymask(4)), (0xFE, 0xEF), 'keymask')
    eq(kp.KEYMAP['SPACE'], (0x7F, 0), 'KEYMAP')
    eq(kp.parse_script('40:,60:SPACE,60:d+z'), [(40, []), (60, ['SPACE']), (60, ['D', 'Z'])], 'script')
    H = mod('harness')
    p = H.Ports()
    kp.press(p, 'Q')
    eq(p.read_port(None, 0xFBFE), 0xFE, 'Q pressed reads bit 0 clear on $FB half-row')
    eq(p.read_port(None, 0xFDFE), 0xFF, 'other half-row untouched')


def t_portconfig():
    pc = mod('portconfig')
    eq(pc.num('0x8400'), 0x8400, 'hex string')
    eq(pc.num('$8400'), 0x8400, 'dollar string')
    eq(pc.num(33792), 33792, 'int')
    eq(pc.num(None), None, 'None passes')
    default_root = pc.root()
    try:
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'port.json')
            json.dump({'tape': {'path': 'tape/x.tzx', 'entry': '0x8400',
                                'blocks': [{'dest': '0x8600', 'len': '0x5210', 'flag': '0x80'},
                                           {'dest': 33792, 'block': 6}],
                                'copies': [{'src': '0x5CF1', 'dst': '0xFF00', 'len': '0x100'}]},
                       'z80': {'contended': False}}, open(p, 'w'))
            pc.reload(p)
            eq(pc.manifest_path(), p, 'manifest path')
            eq(pc.root(), d, 'root is the manifest directory')
            eq(pc.path('build/x.bin'), os.path.normpath(os.path.join(d, 'build/x.bin')), 'path()')
            eq(pc.num(pc.get('tape', 'entry')), 0x8400, 'entry')
            eq(pc.get('tape', 'prog'), '0x5CCB', 'default filled in beside given keys')
            eq(pc.blocks_spec(), [{'dest': 0x8600, 'len': 0x5210, 'flag': 0x80, 'block': None},
                                  {'dest': 0x8400, 'len': None, 'flag': None, 'block': 6}], 'blocks')
            eq(pc.copies_spec(), [(0x5CF1, 0xFF00, 0x100)], 'copies')
            eq(pc.contended(), False, 'manifest contention')
            os.environ['PORT_CONTENDED'] = '1'
            eq(pc.contended(), True, 'env overrides manifest')
            del os.environ['PORT_CONTENDED']
            eq(pc.state_path('foo'), os.path.join(pc.path('build'), 'foo.pkl'), 'state_path')
            eq(pc.state_path(p), p, 'existing path passes through')
            try:
                pc.need('tape', 'tape_call_pc', what='x')
            except SystemExit as e:
                assert 'tape.tape_call_pc' in str(e) and p in str(e), e
            else:
                raise AssertionError('need() did not fail on a null key')
            pc.reload(os.path.join(d, 'absent.json'))
            eq(pc.manifest_path(), None, 'absent manifest -> None')
            eq(pc.cfg()['tape']['entry'], None, 'defaults without a manifest')
            eq(pc.blocks_spec(), 'auto', 'no blocks -> auto')
    finally:
        pc.reload()
    eq(pc.root(), default_root, 'default manifest restored')


def t_harness_snapshot():
    H = mod('harness')
    from skoolkit.snapshot import write_snapshot
    with tempfile.TemporaryDirectory() as d:
        sp = os.path.join(d, 'snap.z80')
        ram = bytearray(0xC000)                      # $4000..$FFFF
        ram[0x8000 - 0x4000] = 0xC9                  # a RET at $8000
        write_snapshot(sp, bytes(ram), ('pc=32768', 'sp=32000', 'bc=4660'), ('im=2',))
        h = H.Harness(snapshot=sp, deck=False)
        eq(h.pc(), 0x8000, 'snapshot PC')
        eq(h.regs[H.SP], 32000, 'snapshot SP')
        eq(h.regs[H.IM], 2, 'snapshot IM')
        eq(h.peek(0x8000), bytes([0xC9]), 'snapshot RAM byte')
        eq(h.peek(0, 3), bytes([0xF3, 0xAF, 0x11]), 'real ROM under the snapshot')


def t_bleepload():
    B = mod('bleepload')

    def turbo(payload):
        hdr = (le16(2168) + le16(667) + le16(735) + le16(855) + le16(1710)
               + le16(20) + bytes([8]) + le16(50))
        ln = len(payload)
        return bytes([0x11]) + hdr + bytes([ln & 0xFF, (ln >> 8) & 0xFF, (ln >> 16) & 0xFF]) + payload

    def bl(gid, blk, dest, fill):
        body = bytes([gid]) + bytes([fill]) * 256 + bytes([blk, dest & 0xFF, dest >> 8]) + bytes([0xC9])
        return turbo(rom_block(0xFF, body))

    tzxbytes = (bytes([0x5A, 0x58, 0x54, 0x61, 0x70, 0x65, 0x21, 0x1A]) + bytes([1, 20])
                + bl(0x64, 0, 0x8000, 0xAA) + bl(0x64, 1, 0x8100, 0xBB)
                + bl(0x65, 0, 0x9000, 0x01))          # a later group: stored XORed by dest-hi ($90)
    with tempfile.TemporaryDirectory() as d:
        tp = os.path.join(d, 'bl.tzx')
        open(tp, 'wb').write(tzxbytes)
        blocks = B.decode(tp)
        eq(len(blocks), 3, 'bleepload block count')
        eq((blocks[0]['gid'], blocks[0]['blk'], blocks[0]['dest']), (0x64, 0, 0x8000), 'block framing')
        eq(blocks[1]['dest'], 0x8100, 'second block dest')
        img, loaded = B.build_naive(blocks)           # first_group $64, XOR later groups on
        eq(img[0x8000], 0xAA, 'group-1 data placed verbatim')
        eq(img[0x9000], 0x01 ^ 0x90, 'later-group data de-XORed by dest high byte')
        eq((loaded[0x8000], loaded[0x9000]), (1, 1), 'loaded-page mask set')


def t_bleepload_driver():
    """A synthetic tape carrying everything the driver model reads (the shape
    measured on eight Firebird tapes): the 512-byte stub with its CP $64, the
    key page XORed with the stub's two pages, a region encrypted with K that
    carries a stage-2 copy loop keyed on a CONSTANT, the driver page (clear
    head, K-encrypted tail: LDIR / CALL $FA00 / LDDR / a fill / LD SP / JP),
    the parameter block, a later group XORed with that constant -- and a
    truncated turbo block, which must be skipped, not crash."""
    B = mod('bleepload')

    def turbo(payload):
        hdr = (le16(2168) + le16(667) + le16(735) + le16(855) + le16(1710)
               + le16(20) + bytes([8]) + le16(50))
        ln = len(payload)
        return bytes([0x11]) + hdr + bytes([ln & 0xFF, (ln >> 8) & 0xFF, (ln >> 16) & 0xFF]) + payload

    def bl(gid, blk, dest, data):
        return turbo(rom_block(0xFF, bytes([gid]) + bytes(data) + bytes([blk, dest & 0xFF, dest >> 8, 0xC9])))

    stub = bytearray((i * 13 + 7) & 0xFF for i in range(512))
    stub[0x1E:0x23] = b'\x3a\x00\xfe\xfe\x64'                    # LD A,($FE00) / CP $64
    K = bytes((i * 5 + 1) & 0xFF for i in range(256))
    keypage = bytes(K[i] ^ stub[i] ^ stub[256 + i] for i in range(256))
    stage2 = bytearray((i * 3) & 0xFF for i in range(256))
    stage2[0x30:0x39] = b'\x21\x01\xfe\x01\x00\x01\x3e\x21\xae'  # LD HL,$FE01 / LD BC,$100 / LD A,$21 / XOR (HL)
    payload = bytes(range(256))

    def enc(page):
        return bytes(page[i] ^ K[i] for i in range(256))

    drv_code = (b'\x21\x00\xcf\x11\x00\x40\x01\x00\x01\xed\xb0'       # after group 1: LDIR $CF00->$4000 $100
                + b'\x3e\x65\x32\x00\x5b\xcd\x00\xfa'                # gid $65 -> CALL $FA00: group 2
                + b'\x21\x00\xd0\x11\x00\x80\x01\x00\x01\xed\xb0'    # after group 2: LDIR $D000->$8000 $100
                + b'\x21\xff\xd0\x11\xff\xd1\x01\x00\x01\xed\xb8'    # LDDR: $D000-$D0FF -> $D100-$D1FF
                + b'\x21\x00\x40\x11\x01\x40\x01\xff\x00\xed\xb0'    # a fill: LDIR $4000->$4001 $FF
                + b'\x31\x00\x60\xc3\x34\x12')                        # LD SP,$6000 / JP $1234
    drv = bytearray(256)
    drv[0:8] = b'\xdd\xe5\xcd\x6e\xcd\xcd\x2a\xce'                    # PUSH IX / CALL stub-read / CALL stub-checksum
    drv[0x40:0x40 + len(drv_code)] = drv_code
    drv_tape = bytes(drv[:0x40]) + bytes(drv[0x40 + i] ^ K[i] for i in range(0xC0))
    params = bytearray(256)                 # the buffer image: gid at 0, data at 1.. -> ($FEE7) = data[$E6]
    params[0xE6:0xE8] = le16(0xC900)
    params[0xE8:0xEA] = le16(0xCF00)
    params[0xEB] = 0xD1
    tzxbytes = (b'ZXTape!\x1a' + bytes([1, 20])
                + std_block(header(3, 'stub', 512, 0xCD00, 32768)) + std_block(rom_block(0xFF, stub))
                + bl(0x64, 0, 0xC900, keypage) + bl(0x64, 1, 0xCF00, enc(stage2))
                + bl(0x64, 2, 0xD000, enc(payload)) + bl(0x64, 3, 0x5B00, drv_tape)
                + bl(0x64, 4, 0xFF09, params) + bl(0x65, 0, 0x9000, bytes(x ^ 0x21 for x in payload))
                + turbo(rom_block(0xFF, bytes(100))))                  # truncated: skipped, not a crash
    with tempfile.TemporaryDirectory() as d:
        tp = os.path.join(d, 'bl2.tzx')
        open(tp, 'wb').write(tzxbytes)
        notes = []
        blocks, got_stub = B.read_tape(tp, 256, notes)
        eq(len(blocks), 6, 'blocks (the short one skipped)')
        eq(len(notes), 1, 'the short block is noted')
        eq(got_stub, bytes(stub), 'the stub is the 512-byte CODE block')
        eq(B.stub_first_group(got_stub), 0x64, "first group from the stub's CP")
        model, why = B.driver_model(blocks, got_stub, 0x64)
        eq(why, None, 'driver model')
        eq((model['keypage'], model['region'], model['driver']['dest']),
           (0xC900, (0xCF00, 0xD100), 0x5B00), 'driver parameters from the buffer image')
        eq(model['key'], K, 'K = key page XOR the two stub pages')
        img, loaded = bytearray(0x10000), bytearray(0x10000)
        for b in blocks[:5]:
            B.place(img, loaded, b['dest'], b['data'])
        B.apply_driver(img, model)
        eq(bytes(img[0xC900:0xCA00]), K, 'key page decrypted in place')
        eq(bytes(img[0xD000:0xD100]), payload, 'region decrypted with K')
        eq(bytes(img[0x5B40:0x5B40 + len(drv_code)]), drv_code, 'driver page decrypted from $40')
        eq(B.stage2_xor_key(img, model['region']), (0x21, 0xCF36), 'later-group key read from stage 2')
        drv = B.read_driver(img, model)
        eq([(c['op'], c['src'], c['dst'], c['len'], c['after_group'], c['fill']) for c in drv['copies']],
           [('LDIR', 0xCF00, 0x4000, 0x100, 1, False), ('LDIR', 0xD000, 0x8000, 0x100, 2, False),
            ('LDDR', 0xD000, 0xD100, 0x100, 2, False), ('LDIR', 0x4000, 0x4001, 0xFF, 2, True)],
           'driver copies from the z80dis walk')
        eq(drv['handover'], (0x5B40 + len(drv_code) - 3, 0x1234), 'hand-over JP')
        eq(drv['sps'], [(0x5B40 + len(drv_code) - 6, 0x6000)], 'LD SP')
        B.apply_copies(img, loaded, drv['copies'], 1)
        eq(bytes(img[0x4000:0x4100]), bytes(stage2), 'copy after group 1 applied')
        B.place(img, loaded, 0x9000, B.unscramble(blocks[5], 0x64, True, 0x21))
        eq(bytes(img[0x9000:0x9100]), payload, 'later group de-XORed with the constant')
        B.apply_copies(img, loaded, drv['copies'], 2)
        eq(bytes(img[0x8000:0x8100]), payload, 'LDIR after group 2 applied')
        eq(bytes(img[0xD100:0xD200]), payload, 'LDDR after group 2 applied')
        eq(img[0x4001], stage2[1], 'the fill was skipped')


CHECKS = [
    ('tzx: parse synthetic tape', t_tzx_parse),
    ('tzx: file parse + report', t_tzx_file_and_report),
    ('tzx: bad checksum flagged', t_tzx_bad_checksum),
    ('tzx: unhandled block stops', t_tzx_unhandled_stops),
    ('bleepload: block framing + naive image', t_bleepload),
    ('bleepload: driver model, stage-2 key, copies', t_bleepload_driver),
    ('basic: detokenise / USR binary form', t_basic),
    ('mkloader: PROG/CHANS layout + relocation', t_mkloader),
    ('mkimage: follow the headers', t_mkimage_auto),
    ('mkimage: explicit block table, --upto, errors', t_mkimage_explicit),
    ('screen: display-file arithmetic', t_screen_addr),
    ('screen: render + attrs', t_screen_render),
    ('harness: real ROM, ROM writes ignored', t_harness_rom),
    ('harness: step / run_until / T-states / port write', t_harness_run),
    ('harness: keyboard, Kempston, unattached ports', t_harness_ports),
    ('harness: Mem.watch write log', t_harness_watch),
    ('harness: save/load state, snapshot/diff', t_harness_state),
    ('harness: call() with sentinels', t_harness_call),
    ('harness: find_bytes', t_harness_find),
    ('harness: image from bytes / file', t_harness_image),
    ('harness: snapshot boot (.z80 -> registers + RAM)', t_harness_snapshot),
    ('harness: interrupts + fast HALT via the ROM ISR', t_harness_interrupts),
    ('harness: contended variant constructs and costs', t_harness_contended),
    ('readwatch: memory swap counts reads', t_readwatch_swap),
    ('walk: boundaries, calls, jumps, inventory', t_walk),
    ('grepbytes: search + boundary confirmation', t_grepbytes),
    ('adis: symbols, regions, DEFB, empty config files', t_adis),
    ('strings / hexdump', t_strings_hexdump),
    ('speckle: art vs noise', t_speckle),
    ('contact: both layouts', t_contact),
    ('keyprobe: export surface + press()', t_keyprobe_exports),
    ('portconfig: manifest, defaults, need()', t_portconfig),
]


def main():
    if '-h' in sys.argv or '--help' in sys.argv:
        print(__doc__.strip()); sys.exit(0)
    for name, fn in CHECKS:
        check(name, fn)
    passed = sum(1 for _, ok in RESULTS if ok)
    print(f'\n{passed}/{len(RESULTS)} checks passed')
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == '__main__':
    main()
