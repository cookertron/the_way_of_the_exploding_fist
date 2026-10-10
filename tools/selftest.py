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
    seen = []                                                   # on_read: sample.py --reads presses keys per read

    def on_read(port):
        seen.append(port & 0xFF)
        h.ports.release_all()
        if len(seen) == 4:
            kp.press(h.ports, 'z')
    h.ports.on_read = on_read
    h.regs[H.PC] = 0x8100
    h.run_until(end)
    h.ports.on_read = None
    eq(seen, [0xFE, 0x1F, 0xFF, 0xFE], 'on_read called before each read, in order')
    eq(h.peek(0x9000, 4), bytes([0xFF, 0x00, 0xFF, 0xFD]), 'a key pressed in on_read is seen by that read alone')


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
    shipped = adis.load_syms(os.path.join(HERE, 'symbols.json'))
    assert all(isinstance(k, int) and 0 <= k <= 0xFFFF and isinstance(v, str) and v
               for k, v in shipped.items()), 'shipped symbols.json: int keys, non-empty names'


def t_refcheck_parse():
    rc = mod('refcheck')
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 't.skool')
        open(p, 'w').write(
            '; Move The Player\n;\n; Used by the routine at #R$8000.\n'
            '@label=Move_Player\nc$8000 LD A,1 ; {Load one\n $8002 RET ; }\n\n'
            '; Routine at 8003\n@label=Bare\nc$8003 NOP\n'
            '@label=Inner\n $8004 RET ; returns\n')
        entries, labels = rc.parse(p)
        eq(labels, {0x8000: 'Move_Player', 0x8003: 'Bare', 0x8004: 'Inner'}, 'labels')
        eq(entries, [('c', 0x8000, 'Move The Player', 2, 1),
                     ('c', 0x8003, 'Routine at 8003', 2, 1)], 'entries, titles, comment counts')
        assert rc.DEFAULT_TITLE.match(entries[1][2]) and not rc.DEFAULT_TITLE.match(entries[0][2])
        q = os.path.join(d, 'symbols.json')
        json.dump({'0x8000': 'ours'}, open(q, 'w'))
        rc.import_symbols(p, q, 0x8000, 0x8004)
        eq(json.load(open(q)), {'0x8000': 'ours', '0x8003': 'Bare'}, 'our names kept, range honoured')


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
    hb = H.Harness(snapshot=False, deck=False)
    eq((hb.peek(0x8000), hb.pc()), (bytes([0]), 0), 'snapshot=False: blank RAM, no manifest fallback')


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

    def variant(stub_addr, buf, s2):
        """Build and check one tape shape: the stub at stub_addr reading blocks
        into buf, stage 2 entered at s2 (the two shapes seen: $CD00/$FE00/$FA00
        on twelve tapes, $DA00/$6D00/$FC00 on Empire)."""
        pg = stub_addr >> 8
        stub = bytearray((i * 13 + 7) & 0xFF for i in range(512))
        stub[0x1E:0x25] = b'\x3a' + le16(buf) + b'\xfe\x64\x20\xf6'    # LD A,(buf) / CP $64 / JR NZ
        K = bytes((i * 5 + 1) & 0xFF for i in range(256))
        keypage = bytes(K[i] ^ stub[i] ^ stub[256 + i] for i in range(256))
        stage2 = bytearray((i * 3) & 0xFF for i in range(256))
        stage2[0x30:0x39] = b'\x21' + le16(buf + 1) + b'\x01\x00\x01\x3e\x21\xae'   # LD HL,buf+1 / LD BC,$100 / LD A,$21 / XOR (HL)
        payload = bytes(range(256))

        def enc(page):
            return bytes(page[i] ^ K[i] for i in range(256))

        drv_code = (b'\x21\x00\xcf\x11\x00\x40\x01\x00\x01\xed\xb0'       # after group 1: LDIR $CF00->$4000 $100
                    + b'\x3e\x65\x32\x00\x5b\xcd' + le16(s2)             # gid $65 -> CALL stage 2: group 2
                    + b'\x21\x00\xd0\x11\x00\x80\x01\x00\x01\xed\xb0'    # after group 2: LDIR $D000->$8000 $100
                    + b'\x21\xff\xd0\x11\xff\xd1\x01\x00\x01\xed\xb8'    # LDDR: $D000-$D0FF -> $D100-$D1FF
                    + b'\x21\x00\x40\x11\x01\x40\x01\xff\x00\xed\xb0'    # a fill: LDIR $4000->$4001 $FF
                    + b'\x31\x00\x60\xc3\x34\x12')                        # LD SP,$6000 / JP $1234
        drv = bytearray(256)
        drv[0:8] = bytes([0xDD, 0xE5, 0xCD, 0x6E, pg, 0xCD, 0x2A, pg + 1])   # PUSH IX / CALL stub-read / CALL stub-checksum
        drv[0x40:0x40 + len(drv_code)] = drv_code
        drv_tape = bytes(drv[:0x40]) + bytes(drv[0x40 + i] ^ K[i] for i in range(0xC0))
        params = bytearray(drv)                 # the last block mirrors the driver page, parameters patched in:
        params[0xE6:0xE8] = le16(0xC900)        # buffer image gid at 0, data at 1.. -> (buf+$E7) = data[$E6]
        params[0xE8:0xEA] = le16(0xCF00)
        params[0xEB] = 0xD1
        # the stage-2 page is the one carrying the copy loop; put it in the region at s2 when s2 is
        # inside it, else at $CF00 (the tool only needs "in the region")
        s2_in_region = 0xCF00 <= s2 < 0xD100
        region_pages = {0xCF00: stage2 if not s2_in_region or s2 == 0xCF00 else payload,
                        0xD000: payload if not s2_in_region or s2 == 0xCF00 else stage2}
        tzxbytes = (b'ZXTape!\x1a' + bytes([1, 20])
                    + std_block(header(3, 'stub', 512, stub_addr, 32768)) + std_block(rom_block(0xFF, stub))
                    + bl(0x64, 0, 0xC900, keypage) + bl(0x64, 1, 0xCF00, enc(region_pages[0xCF00]))
                    + bl(0x64, 2, 0xD000, enc(region_pages[0xD000])) + bl(0x64, 3, 0x5B00, drv_tape)
                    + bl(0x64, 4, buf + 0x109, params)
                    + bl(0x65, 0, 0x9000, bytes(x ^ 0x21 for x in payload))
                    + turbo(rom_block(0xFF, bytes(100))))                  # truncated: skipped, not a crash
        tag = f'[stub ${stub_addr:04X} buf ${buf:04X}] '
        with tempfile.TemporaryDirectory() as d:
            tp = os.path.join(d, 'bl2.tzx')
            open(tp, 'wb').write(tzxbytes)
            notes = []
            blocks, got_stub = B.read_tape(tp, 256, notes)
            eq(len(blocks), 6, tag + 'blocks (the short one skipped)')
            eq(len(notes), 1, tag + 'the short block is noted')
            eq((bytes(got_stub), got_stub.addr), (bytes(stub), stub_addr), tag + 'the stub and its load address')
            eq(B.stub_params(got_stub), dict(first_group=0x64, buf=buf), tag + "first group and buffer from the stub's CP")
            model, why = B.driver_model(blocks, got_stub, 0x64, buf)
            eq(why, None, tag + 'driver model')
            eq((model['keypage'], model['region'], model['driver']['dest'], model['stub_page']),
               (0xC900, (0xCF00, 0xD100), 0x5B00, pg), tag + 'driver parameters from the buffer image')
            eq(model['key'], K, tag + 'K = key page XOR the two stub pages')
            img, loaded = bytearray(0x10000), bytearray(0x10000)
            for b in blocks[:5]:
                B.place(img, loaded, b['dest'], b['data'])
            B.apply_driver(img, model)
            eq(bytes(img[0xC900:0xCA00]), K, tag + 'key page decrypted in place')
            eq(bytes(img[0x5B40:0x5B40 + len(drv_code)]), drv_code, tag + 'driver page decrypted from $40')
            key, at = B.stage2_xor_key(img, model['region'], buf)
            eq((key, at & 0xFF00), (0x21, s2 if s2_in_region else 0xCF00), tag + 'later-group key and stage-2 page read from stage 2')
            drv = B.read_driver(img, model, s2)
            eq([(c['op'], c['src'], c['dst'], c['len'], c['after_group'], c['fill']) for c in drv['copies']],
               [('LDIR', 0xCF00, 0x4000, 0x100, 1, False), ('LDIR', 0xD000, 0x8000, 0x100, 2, False),
                ('LDDR', 0xD000, 0xD100, 0x100, 2, False), ('LDIR', 0x4000, 0x4001, 0xFF, 2, True)],
               tag + 'driver copies from the z80dis walk')
            eq(drv['handover'], (0x5B40 + len(drv_code) - 3, 0x1234), tag + 'hand-over JP')
            eq(drv['sps'], [(0x5B40 + len(drv_code) - 6, 0x6000)], tag + 'LD SP')
            B.apply_copies(img, loaded, drv['copies'], 1)
            eq(bytes(img[0x4000:0x4100]), bytes(region_pages[0xCF00]), tag + 'copy after group 1 applied')
            B.place(img, loaded, 0x9000, B.unscramble(blocks[5], 0x64, True, 0x21))
            eq(bytes(img[0x9000:0x9100]), payload, tag + 'later group de-XORed with the constant')
            B.apply_copies(img, loaded, drv['copies'], 2)
            eq(bytes(img[0x8000:0x8100]), bytes(region_pages[0xD000]), tag + 'LDIR after group 2 applied')
            eq(bytes(img[0xD100:0xD200]), bytes(region_pages[0xD000]), tag + 'LDDR after group 2 applied')
            eq(img[0x4001], region_pages[0xCF00][1], tag + 'the fill was skipped')

    variant(0xCD00, 0xFE00, 0xCF00)      # the common shape (stage 2 modelled at $CF00 for the tiny region)
    variant(0xDA00, 0x6D00, 0xD000)      # Empire's shape: stub at $DA00, buffer $6D00, stage 2 in the second page

def t_stackscan():
    """The slot-based shadow stack on a program whose every stack event is
    known: two balanced CALLs, a POP that discards a frame, a RET into a
    pushed address (fake return), a reset LD SP that buries a frame under new
    frames, and a blitter-style LD SP switch-and-restore that must NOT count
    as a discard; then the ROM ISR as frames (HALT loop, IM 1)."""
    H, h = fresh()
    S = mod('stackscan')
    h.poke(0x8000, 0xCD, 0x20, 0x80,        # 8000 CALL 8020            frame A -> balanced
           0xCD, 0x30, 0x80,                # 8003 CALL 8030            frame B -> balanced via 8037
           0x21, 0x40, 0x80, 0xE5, 0xC9)    # 8006 LD HL,8040 / PUSH HL / RET   fake return at 800A
    h.poke(0x8020, 0xC9)                    # 8020 RET
    h.poke(0x8030, 0xCD, 0x36, 0x80,        # 8030 CALL 8036            frame C
           0x18, 0xFE, 0x00,                # 8033 JR $   (never reached); 8035 NOP
           0xE1,                            # 8036 POP HL               discards frame C
           0xC9)                            # 8037 RET                  consumes B's slot -> 8006
    h.poke(0x8040, 0x31, 0x00, 0xFE,        # 8040 LD SP,$FE00          no live frame: cuts nothing
           0xCD, 0x50, 0x80,                # 8043 CALL 8050            frame D at slot $FDFE
           0x18, 0xFE)                      # 8046 JR $   (never reached)
    h.poke(0x8050, 0x31, 0x00, 0xFF,        # 8050 LD SP,$FF00          D cut (pending)
           0xCD, 0x60, 0x80,                # 8053 CALL 8060            frame E buries D -> D discarded by 8050
           0xE5, 0xC1,                      # 8056 PUSH HL / POP BC     data, balanced, no frame
           0xCD, 0x70, 0x80,                # 8058 CALL 8070            frame F
           0x18, 0xFE)                      # 805B JR $   (never reached: F returns elsewhere)
    h.poke(0x8060, 0xED, 0x73, 0x00, 0x81,  # 8060 LD ($8100),SP
           0x31, 0xF0, 0xFF,                # 8064 LD SP,$FFF0          E cut (pending): a data switch
           0xC1,                            # 8067 POP BC               reads data, not a frame
           0xED, 0x7B, 0x00, 0x81,          # 8068 LD SP,($8100)        restore: E revives
           0xC9)                            # 806C RET                  E balanced
    h.poke(0x8070, 0x21, 0x80, 0x80,        # 8070 LD HL,8080
           0xE3,                            # 8073 EX (SP),HL           F's slot now holds 8080
           0xC9)                            # 8074 RET                  consumes F's slot, lands 8080 -> REWRITE
    h.poke(0x8080, 0x18, 0xFE)              # 8080 JR $
    h.regs[H.PC] = 0x8000
    h.regs[H.SP] = 0xFF00
    s = S.scan(h, 2, None)
    # (ODD -- SP raised by an instruction outside RET/POP/INC SP/LD SP -- has no Z80 witness: the
    #  simulator steps an undocumented DD/FD prefix on its own, so a prefixed POP is a plain POP.
    #  ODD is a model-integrity canary, not something a program can trip.)
    eq((s['created'], s['balanced'], s['rewritten'], s['odd'], s['open'], sum(s['unresolved'].values())),
       (6, 3, 1, 0, 0, 0), 'frames / balanced / rewritten / odd / open / unresolved')
    eq(s['discards'], {(0x8036, 0x8036, 0x8033): 1, (0x8050, 0x8050, 0x8046): 1},
       'discards: C by the POP at 8036, D by the LD SP reset at 8050')
    eq(s['fakes'], {0x800A: 1}, 'the RET into a pushed address')
    eq(s['rewrites'], {0x8074: 1}, 'the EX (SP),HL rewrite')
    eq(h.regs[H.PC], 0x8080, 'the program reached its final loop')
    # a frame live before the scan is INHERITED; a push over that same slot makes the next RET fake
    H, h = fresh()
    h.poke(0xFEFE, 0x90, 0x80)              # the start's stack: one return word -> 8090
    h.poke(0x8000, 0xC9)                    # 8000 RET                  inherited
    h.poke(0x8090, 0x21, 0xA0, 0x80,        # 8090 LD HL,80A0
           0xE5, 0xC9)                      # 8093 PUSH HL / RET        same slot, pushed over -> fake at 8094
    h.poke(0x80A0, 0x18, 0xFE)              # 80A0 JR $
    h.regs[H.PC] = 0x8000
    h.regs[H.SP] = 0xFEFE
    s = S.scan(h, 1, None)
    eq((s['inherited'], s['fakes'], h.regs[H.PC]), ({0x8000: 1}, {0x8094: 1}, 0x80A0),
       'inherited RET at 8000; the pushed-over slot is a fake at 8094')
    H, h = fresh()                          # the same word PUSHED back over an unconsumed start slot
    h.poke(0xFEFE, 0x90, 0x80)
    h.poke(0x8000, 0x33, 0x33,              # 8000 INC SP x2            steps over the start's word
           0x21, 0x90, 0x80, 0xE5, 0xC9)    # 8002 LD HL,8090 / PUSH HL / RET   equal word, but pushed: fake
    h.poke(0x8090, 0x18, 0xFE)
    h.regs[H.PC] = 0x8000
    h.regs[H.SP] = 0xFEFE
    s = S.scan(h, 1, None, marks=(0x8002, 0x8090, 0x9000))
    eq((s['inherited'], s['fakes']), ({}, {0x8006: 1}), 'a push retires the start word: fake at 8006')
    eq(s['marked'], {0x8002: [0], 0x8090: [0]}, 'marks: one visit each at frame 0, the unrun PC absent')
    # interrupts are frames: a HALT loop under IM 1 with the ROM ISR
    H, h = fresh()
    h.poke(0x8000, 0x76, 0x18, 0xFD)        # HALT / JR $-1
    h.regs[H.PC] = 0x8000
    h.regs[H.SP] = 0xFF00
    h.regs[H.IM] = 1
    h.regs[H.IFF] = 1
    s = S.scan(h, 4, None)
    eq(s['created'] > 8 and s['balanced'] + s['open'] == s['created'] and s['open'] <= 1, True,
       f'ISR frames balanced (one may be open when the scan ends inside the ISR): {s}')
    eq((sum(s['discards'].values()), sum(s['fakes'].values()), s['odd']), (0, 0, 0), 'no discards/fakes/odd in the ROM ISR')



def t_blitforensics():
    """The two-background differential on blitters whose sprite is KNOWN because
    we poked it: masked AND-OR, opaque copy, XOR -- mode, WxH, origin, data,
    over-$FF and the grid cell for cell.  Then the guards: a fall-through entry
    (no CALL before the stack top) and a call that never returns are refused,
    a same-layout back-buffer is measured through --target LO, a sprite clipped
    into the attributes counts them instead of crashing, an all-transparent
    sprite is EMPTY (masked-empty and XOR-of-nothing are indistinguishable)."""
    B = mod('blitforensics')
    DATA = [0x3C, 0x42, 0x81, 0xA5, 0xA5, 0x81, 0x42, 0x3C]
    MASK = [0xC3, 0x81, 0x00, 0x18, 0x3C, 0x00, 0x81, 0xC3]        # 1 = transparent
    MASKED = [0x1A, 0xA6, 0x23, 0xB6, 0x23, 0x12, 0x14, 0x10, 0xF7, 0xC9]   # LD A,(DE)/AND (HL)/INC HL/OR (HL)/INC HL/LD (DE),A/INC D/DJNZ/RET
    OPAQUE = [0x7E, 0x12, 0x23, 0x14, 0x10, 0xFA, 0xC9]                     # LD A,(HL)/LD (DE),A/INC HL/INC D/DJNZ/RET
    XOR = [0x1A, 0xAE, 0x12, 0x23, 0x14, 0x10, 0xF9, 0xC9]                  # LD A,(DE)/XOR (HL)/LD (DE),A/INC HL/INC D/DJNZ/RET
    DOWN = [0x7E, 0x12, 0x23, 0x14, 0x7A, 0xE6, 0x07, 0x20, 0x0A, 0x7B, 0xC6, 0x20, 0x5F,
            0x38, 0x04, 0x7A, 0xD6, 0x08, 0x57, 0x10, 0xEB, 0xC9]           # opaque, one pixel row down with the ULA carry
    pairs = [b for m, d in zip(MASK, DATA) for b in (m, d)]

    def run(routine, src, b=8, de=0x4820, call=True, entry=0x8000, bg=None, garbage=0x1234, **kw):
        H, h = fresh()
        h.poke(0x8000, *routine)
        h.poke(0xA000, *src)
        if bg is not None:                              # something under the sprite
            for i in range(b):
                h.poke(de + (i << 8), bg)
        h.poke(0x9000, *([0xCD, 0x00, 0x80] if call else [0xC3, 0x00, 0x80]), 0x18, 0xFE)   # CALL/JP $8000; JR $
        if not call:
            h.poke(0xFF00, garbage & 0xFF, garbage >> 8)  # garbage on the stack top
        r = h.sim.registers
        r[H.PC], r[H.SP], r[H.B], r[H.IFF] = 0x9000, 0xFF00, b, 0
        r[H.H], r[H.L], r[H.D], r[H.E] = 0xA0, 0x00, de >> 8, de & 0xFF
        eq(h.run_until((entry,), limit=100, interrupts=False)[0], 'target', 'reach the entry')
        return B.measure(h, entry, **kw)

    def grid(mode, data, mask=None):
        rows = []
        for i, d in enumerate(data):
            m = mask[i] if mask else 0
            rows.append(''.join('I' if d >> b & 1 else
                                ('.' if m >> b & 1 else 'K') if mode == 'MASKED' else
                                'K' if mode == 'OPAQUE' else '.' for b in range(7, -1, -1)))
        return rows

    rep = run(MASKED, pairs)
    eq((rep['mode'], rep['w'], rep['h'], rep['origin'], rep['return']), ('MASKED', 8, 8, [0, 72], '$9003'), 'masked: shape')
    eq(list(rep['data_over_00'].values()), DATA, 'masked: data == over-$00')
    eq(list(rep['over_FF'].values()), [m | d for m, d in zip(MASK, DATA)], 'masked: over-$FF == mask OR data')
    eq(rep['grid'], grid('MASKED', DATA, MASK), 'masked: grid, transparent exactly where mask=1 & data=0')
    eq(run(MASKED, pairs, bg=0x55)['model_mismatch'], 0, 'masked over a real background: model holds')
    rep = run(OPAQUE, DATA)
    eq((rep['mode'], rep['transparent_px']), ('OPAQUE', 0), 'opaque: mode, no transparency')
    eq((list(rep['data_over_00'].values()), list(rep['over_FF'].values())), (DATA, DATA), 'opaque: both backgrounds give the data')
    eq(rep['grid'], grid('OPAQUE', DATA), 'opaque: grid')
    rep = run(XOR, DATA)
    eq(rep['mode'], 'XOR', 'xor: detected')
    eq((list(rep['data_over_00'].values()), list(rep['over_FF'].values())), (DATA, [d ^ 0xFF for d in DATA]), 'xor: data, ~data')
    eq(rep['grid'], grid('XOR', DATA), 'xor: grid claims no mask')
    eq(run(XOR, DATA, bg=0x55)['model_mismatch'], 0, 'xor over a real background: model holds')
    eq(run(OPAQUE, DATA, bg=0x55)['model_mismatch'], 0, 'opaque over a real background: model holds')
    INVERT = [0x1A, 0x2F, 0xA6, 0x12, 0x23, 0x14, 0x10, 0xF8, 0xC9]       # LD A,(DE)/CPL/AND (HL)/LD (DE),A ...: data AND NOT bg, outside the family
    rep = run(INVERT, DATA, bg=0x55)
    eq((rep['mode'], rep['model_mismatch'] > 0), ('MASKED', True), 'a routine outside the family is reported as a model mismatch')
    # guards
    try:
        run(MASKED, pairs, call=False)
        raise AssertionError('fall-through entry with a garbage stack top was accepted')
    except B.BoundError as e:
        eq('no CALL/RST precedes' in str(e), True, f'fall-through refused: {e}')
    try:
        run(MASKED, pairs, call=False, garbage=0x0000)   # a stack top nothing can precede (Gauntlet's JP-entered blitters)
        raise AssertionError('stack top $0000 was accepted')
    except B.BoundError as e:
        eq('no CALL/RST precedes' in str(e), True, f'$0000 stack top refused, not a crash: {e}')
    try:
        run(MASKED, pairs, ret=0x9010, steps=2000)
        raise AssertionError('a call that never reaches its bound was accepted')
    except B.BoundError as e:
        eq('did not return' in str(e), True, f'never-returned refused: {e}')
    rep = run(MASKED, pairs, de=0xD820, lo=0xD000, hi=0xEB00)
    eq((rep['mode'], rep['origin'], rep['grid']), ('MASKED', [0, 72], grid('MASKED', DATA, MASK)), 'back-buffer at $D000 via lo')
    eq(run(MASKED, pairs, de=0xD820)['bmp_bytes'], 0, 'back-buffer blit invisible on the display target')
    rep = run(DOWN, DATA + DATA[::-1], b=16, de=0x50E0)
    eq((rep['w'], rep['h'], rep['origin'], rep['attr_bytes']), (8, 8, [0, 184], 3), 'clipped at the bottom: 8 rows + 3 attrs')
    rep = run(DOWN, DATA + DATA[::-1], b=16)
    eq((rep['w'], rep['h'], rep['row_major']), (8, 16, True), 'two cells tall')
    eq(run(MASKED, [b for m, d in zip([0xFF] * 8, [0] * 8) for b in (m, d)])['mode'], 'EMPTY', 'all-transparent: EMPTY')


# ---------------------------------------------------------------------------
# the session machinery (manual 12.8): tools/manual.py, the trap-to-check map
# and the .claude hooks.  These read the kit's real docs/, which hold no tape
# data, and run each script the way Claude Code does: JSON on stdin.
# ---------------------------------------------------------------------------
REPO = os.path.dirname(HERE)


def t_callio_up():
    C = mod('callio')
    from harness import Simulator, SP, PC
    def go(code, ret):
        mem = bytearray(0x10000)
        mem[0x8000:0x8000 + len(code)] = code
        mem[0x9000:0x9002] = bytes([0x10, 0x80])        # the caller's return at the entry SP: $8010
        lm = C.Logged(bytes(mem), C.frame(0x9000))
        regs = list(Simulator(bytearray(0x10000)).registers)
        regs[PC], regs[SP] = 0x8000, 0x9000
        C.run_alone(lm, regs, ret)
        return lm, C.up_io(mem, 0x9000, lm)
    # RET to $8010, then PUSH HL twice: the exit SP is below the entry, yet $9000 was popped
    lm, up = go(bytes([0xC9] + [0] * 15 + [0xE5, 0xE5]), 0x8012)
    eq(lm.exit[SP] < 0x9000, True, 'exit SP below the entry')
    eq(up, {'up': '1080'}, 'a RET past the entry SP records up whatever the exit SP')
    eq(sorted(lm.popped), [0x9000, 0x9001], 'the popped bytes')
    # LD SP,$A000 is no pop: nothing above the entry SP is recorded
    lm, up = go(bytes([0x31, 0x00, 0xA0, 0x00]), 0x8003)
    eq((up, lm.popped), ({}, set()), 'LD SP is not a pop')


def t_measure():
    H, h = fresh()
    ME = mod('measure')
    h.poke(0x8000, 0x38, 0x05,            # JR C,$8007        (carry in)
           0x21, 0x00, 0x90,              # LD HL,$9000
           0x36, 0x00,                    # LD (HL),0         a write of the value already there
           0x3A, 0x00, 0x91,              # LD A,($9100)
           0xB7,                          # OR A
           0xC8,                          # RET Z
           0x32, 0x01, 0x91,              # LD ($9101),A
           0xCD, 0x20, 0x80,              # CALL $8020
           0xC9)                          # RET
    h.poke(0x8020, 0x32, 0x00, 0x00,      # LD ($0000),A      an attempted ROM write
           0xC3, 0x30, 0x80)              # JP $8030          the stop
    h.poke(0x8030, 0xC9)
    before = h.save_state()
    m = ME.measure(h, 0x8000, [{}, {'poke': {0x9100: 7}}], stop_at=(0x8030, 0x8040))
    eq(h.save_state(), before, 'the harness is left as found')
    eq(len(m.runs), 4, 'two cases x carry clear/set')
    r0 = m.runs[0]
    eq((r0.flags, r0.exit), ({'C': 0}, ('ret', 0)), 'run 0: carry clear, RET Z')
    eq(r0.writes, [(0x8005, 0x9000, 0)], 'the unchanged-value write is logged with its PC (G11b, f)')
    eq(r0.changed, set(), 'and the diff alone saw nothing')
    eq(r0.poison['diverged'], None, 'the poisoned twin agrees')
    eq(r0.poison['fill'], 1, 'poisoned where it wrote: one byte')
    eq(r0.poison['unlogged'], set(), 'diff against the poison equals the log')
    r1 = m.runs[1]
    eq(r1.exit, ('ret', 0), 'run 1: carry set skips the store')
    eq(r1.writes, [], 'no writes, not even the armed sentinels (G11a)')
    r2 = m.runs[2]
    eq(r2.exit, ('stop', 0x8030), 'run 2 stops at $8030, observed not run (G11e)')
    eq(sorted((r2.window_of(a), a) for _, a, _ in r2.writes),
       [('ram', 0x9000), ('ram', 0x9101), ('stack', r2.sp - 2), ('stack', r2.sp - 1)],
       'writes by window, the CALL frame as stack; the ROM attempt is not seen (G11c, f)')
    eq(m.branches(), {0x8000: 'both', 0x800B: 'both'}, 'carry swept: both branches both ways (G11d)')
    eq(m.stops_unreached(), [0x8040], 'an unreached stop is named (TRAPS #144)')
    txt = m.text()
    assert 'stop_at $8040: no run reached it' in txt, txt
    m1 = ME.measure(h, 0x8000, [{}], flags_in=())
    eq(m1.branches(), {0x8000: 'never taken', 0x800B: 'taken only'}, 'one-way branches flagged')
    assert any('branch $8000: never taken' in p for p in m1.problems())
    mx = ME.measure(h, 0x8000, [{'poke': {0x9100: 7}}], stop_at=(0x8030,), exclude=('stack',), flags_in=())
    assert 'stack     excluded: 2 writes to 2 bytes' in mx.text(), mx.text()
    for bad in ((0x5800,), ('screen',)):
        try:
            ME.measure(h, 0x8000, exclude=bad)
        except ValueError:
            pass
        else:
            raise AssertionError('exclude=%r accepted' % (bad,))
    mw = ME.measure(h, 0x8000, [{'poke': {0x9100: 7}}], flags_in=(), stop_at=(0x8030,),
                    windows={'vars': (0x9100, 0x9110)})
    eq(mw.runs[0].window_of(0x9101), 'vars', "a port's window wins over 'ram'")
    # a routine that reads what it writes: the poisoned twin says so
    h.poke(0x8050, 0x21, 0x00, 0x90, 0x34, 0xC9)        # LD HL,$9000; INC (HL); RET
    mr = ME.measure(h, 0x8050, flags_in=())
    eq(mr.runs[0].poison['diverged'], 'wrote other values', 'INC (HL) under poison')
    # DJNZ $ in one fast step still counts as both ways
    h.poke(0x8060, 0x06, 0x05, 0x10, 0xFE, 0xC9)        # LD B,5; DJNZ $; RET
    eq(ME.measure(h, 0x8060, flags_in=()).branches(), {0x8062: 'both'}, 'fast DJNZ')
    fx = m.fixture(argv=['selftest'])
    eq(fx['_stamp']['branches'], {'$8000': 'both', '$800B': 'both'}, 'the stamp carries the branches')
    d = tempfile.mkdtemp()
    p = os.path.join(d, 'oracle.py')
    with open(p, 'w') as f:
        f.write('ok = [a for a in x if lo <= a < hi]\nif ad < 0x5800:\n    pass\n# ad < 0x5800 in a comment\n')
    eq([n for n, _ in ME.lint(p)], [2], 'the lint names the raw comparison only (G11c)')



def run_py(script, stdin='', env=None, cwd=None):
    import subprocess
    e = dict(os.environ)
    e.update(env or {})
    r = subprocess.run([sys.executable] + script, input=stdin, capture_output=True,
                       text=True, cwd=cwd or REPO, env=e, timeout=60)
    return r.returncode, r.stdout, r.stderr


def t_manual_ids():
    tool = os.path.join(HERE, 'manual.py')
    code, out, _ = run_py([tool, 'c9', 'T146', 'PHASE', '9'])
    eq(code, 0, 'exit status')
    for want in ('== C9 ', 'THE LOOP IS WHERE THE DISPLACEMENT SAYS', '== T146 ', 'map: ', '== P9 '):
        if want not in out:
            raise AssertionError(f'{want!r} missing from the output')
    eq(run_py([tool, 'Z99'])[0], 1, 'unknown ID exits 1')
    eq(run_py([tool, 'T9999'])[0], 1, 'unknown trap exits 1')
    lines = run_py([tool, '--index'])[1].splitlines()
    if len(lines) < 160:
        raise AssertionError(f'index has {len(lines)} entries, want >= 160')
    out = run_py([tool, '--grep', 'straddle'])[1]
    if 'G11' not in out or 'T143' not in out:
        raise AssertionError('--grep must search the manual and the traps')
    out = run_py([tool, '--grep', 'blit'])[1]
    if 'blitforensics.py' not in out or not out.split()[0].endswith('.py'):
        raise AssertionError('--grep must search the tools tables, and list tools first')
    out = run_py([tool, '--tools', 'stack'])[1]
    if 'stackscan.py' not in out or 'python tools/stackscan.py' not in out:
        raise AssertionError('--tools must find a tool with its usage')


def t_tools_registry():
    import re
    readme = open(os.path.join(HERE, 'README.md'), encoding='utf-8').read()
    rows = re.findall(r'^\| `([A-Za-z0-9_./-]+\.py)` \|', readme, re.M)
    scripts = sorted(f for f in os.listdir(HERE) if f.endswith('.py'))
    eq(len(rows), len(set(rows)), 'each tool listed once')
    missing = [s for s in scripts if s not in rows]
    extra = sorted(set(rows) - set(scripts))
    eq((missing, extra), ([], []), 'scripts without a row in tools/README.md, rows without a script')


def t_traps_map():
    import re
    traps = open(os.path.join(REPO, 'docs', 'TRAPS.md'), encoding='utf-8').read()
    nums = [int(n) for n in re.findall(r'^(\d+)\. \*\*', traps, re.M)]
    rows = mod('manual').load_map()
    eq(len(nums), len(set(nums)), 'each trap number used once')
    missing = sorted(set(nums) - set(rows))
    extra = sorted(set(rows) - set(nums))
    eq((missing, extra), ([], []), 'traps without a map row, map rows without a trap')
    bad = [n for n, (_, mech, state) in rows.items() if state not in ('KIT', 'BB', 'BUILD', 'READ')
           or (state == 'READ') != (mech in ('manual', 'game'))]
    eq(bad, [], 'rows whose state and mechanism disagree')


def t_hooks():
    hooks = os.path.join(REPO, '.claude', 'hooks')
    guard = os.path.join(hooks, 'pretool_guard.py')
    manual = os.path.join(REPO, 'docs', 'PORTING-ZX-TO-JS.txt')

    def decision(payload):
        code, out, _ = run_py([guard], json.dumps(payload))
        eq(code, 0, 'the guard always exits 0')
        return json.loads(out)['hookSpecificOutput']['permissionDecision'] if out.strip() else 'allow'

    def bash(cmd):
        return decision({'tool_name': 'Bash', 'tool_input': {'command': cmd}})

    eq(decision({'tool_name': 'Read', 'tool_input': {'file_path': manual}}), 'deny', 'whole manual')
    eq(decision({'tool_name': 'Read', 'tool_input': {'file_path': manual, 'offset': 90, 'limit': 150}}),
       'allow', 'a ranged read')
    eq(decision({'tool_name': 'Read', 'tool_input': {'file_path': '/p/docs/TRAPS.md', 'limit': 900}}),
       'deny', 'traps, limit too large')
    eq(bash('cd /p && cat docs/TRAPS.md'), 'deny', 'cat of the traps')
    eq(bash('cat docs/TRAPS.md | grep -n straddle'), 'allow', 'a filtered read')
    eq(bash('python tools/manual.py T146'), 'allow', 'manual.py')
    eq(bash("cat > tools/x.py << 'EOF'\nprint(1)\nEOF"), 'deny', 'a heredoc into a .py file')
    eq(bash("python - << 'EOF'\nprint(1)\nEOF"), 'allow', 'a script run from a heredoc')
    eq(run_py([guard], 'not json'), (0, '', ''), 'garbage in: silent pass')
    eq(decision({'tool_name': 'Read', 'tool_input': {'file_path': '/p/docs/archive/LOG.md'}}),
       'deny', 'a whole archived file')
    eq(decision({'tool_name': 'Read', 'tool_input': {'file_path': '/p/docs/archive/LOG.md',
                                                     'offset': 10, 'limit': 100}}),
       'allow', 'an archive read by line range')

    stop = os.path.join(hooks, 'stop_check.py')
    with tempfile.TemporaryDirectory() as d:
        env = {'CLAUDE_PROJECT_DIR': d}
        eq(run_py([stop], '{}', env, d)[0], 0, 'no status.py: never blocks')
        os.makedirs(os.path.join(d, 'tools'))
        with open(os.path.join(d, 'tools', 'status.py'), 'w') as f:
            f.write('import sys\nprint("fixture named by no ledger entry")\nsys.exit(1)\n')
        code, _, err = run_py([stop], '{"stop_hook_active": false}', env, d)
        eq(code, 2, 'a failing --check blocks')
        if 'fixture named by no ledger entry' not in err:
            raise AssertionError('the block must carry the check output')
        eq(run_py([stop], '{"stop_hook_active": true}', env, d)[0], 0, 'blocks at most once per turn')

        code, out, _ = run_py([os.path.join(hooks, 'session_context.py')], '{"source": "compact"}', env, d)
        eq(code, 0, 'session hook exit status')
        if 'source: compact' not in out or 'tools/manual.py' not in out or len(out) >= 10000:
            raise AssertionError('session context must name its source and manual.py, under the cap')
        if 'Tools in tools/' not in out or ' status' not in out:
            raise AssertionError("session context must list the scripts in the project's tools/")

    out = run_py([os.path.join(hooks, 'subagent_context.py')], '{}')[1]
    spec = json.loads(out)['hookSpecificOutput']
    eq(spec['hookEventName'], 'SubagentStart', 'sub-agent hook event')
    if 'tools/manual.py' not in spec['additionalContext']:
        raise AssertionError('sub-agent context must name manual.py')

    settings = json.load(open(os.path.join(REPO, '.claude', 'settings.json')))
    for event, groups in settings['hooks'].items():
        for g in groups:
            for h in g['hooks']:
                script = h['command'].split('/.claude/hooks/')[1]
                if not os.path.isfile(os.path.join(hooks, script)):
                    raise AssertionError(f'{event} runs a script that does not exist: {script}')


def make_port(d):
    """A throwaway port with one oracle, one fixture, one tagged function and
    one test that reads the fixture -- enough for record.py and status.py."""
    import shutil
    import subprocess
    for rel in ('tools/record.py', 'tools/status.py', 'tools/manual.py', 'tools/stamp.py',
                'docs/PORTING-ZX-TO-JS.txt', 'docs/TRAPS.md', 'docs/TRAPS-MAP.md'):
        os.makedirs(os.path.join(d, os.path.dirname(rel)), exist_ok=True)
        shutil.copy(os.path.join(REPO, rel), os.path.join(d, rel))
    files = {
        'port.json': json.dumps({'name': 'demo', 'assets': [
            {'key': 'edgejump', 'file': 'build/edgejump_fixture.json', 'note': 'test'}]}),
        'build/edgejump_fixture.json': '{"rows": []}\n',
        'tools/sim_edge.py': '"""oracle for $B34C (selftest)"""\n',
        'web/game.js': '// @z80 $B34C\nfunction movePlayer(s) {\n  return s;\n}\n',
        'test/game.test.js': "check('edge: A.edgejump rows', 1, 1);\n",
        'docs/DECISIONS.md': '# Decisions\n\nPurpose: selftest\nRead by: selftest\n',
    }
    for rel, text in files.items():
        os.makedirs(os.path.join(d, os.path.dirname(rel)) or d, exist_ok=True)
        with open(os.path.join(d, rel), 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    try:
        for args in (['init', '-q'], ['add', '-A'],
                     ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'base']):
            subprocess.run(['git', *args], cwd=d, capture_output=True, check=True)
        return True
    except Exception:
        return False                              # no git: skip the git-derived parts


def rec(d, *args, stdin=''):
    return run_py([os.path.join(d, 'tools', 'record.py'), *args], stdin, cwd=d)


def stat(d, *args):
    return run_py([os.path.join(d, 'tools', 'status.py'), *args], cwd=d)


def t_records():
    with tempfile.TemporaryDirectory() as d:
        has_git = make_port(d)
        eq(rec(d, 'new', 'B34C', stdin='name: MovePlayer\n')[0], 0, 'new')
        code, _, _ = rec(d, 'fact', 'B34C', stdin="kind: insn\nat: $B351\nsays: RET Z -- $8D22's caller\nby: adis\n")
        eq(code, 0, 'fact with $ and an apostrophe')
        code, _, err = rec(d, 'fact', 'B34C', stdin='kind: never\nsays: no writes\nby: sim\n')
        if code != 1 or '#48' not in err:
            raise AssertionError('a negative claim without window and n must be refused')
        eq(rec(d, 'fact', 'B34C', stdin='kind: never\nsays: no writes\nby: sim\nwindow: 12 jumps\nn: 12\n')[0],
           0, 'a negative claim with window and n')
        eq(rec(d, 'open', 'B34C', stdin='ask: ladder?\ntried: sweep\nsettle: ladder sweep\n')[0], 0, 'open')
        eq(rec(d, 'link', 'B34C', stdin='fixture: nosuch\n')[0], 1, 'an unregistered fixture is refused')
        eq(rec(d, 'link', 'B34C', stdin='port: nosuch\n')[0], 1, 'an undefined port function is refused')
        eq(rec(d, 'link', 'B34C', stdin='oracle: tools/sim_edge.py\nfixture: edgejump\nport: movePlayer\n'
                                        'manual: c9 #141\n')[0], 0, 'real links')
        eq(rec(d, 'close', 'B34C', '1', stdin='kind: measured\nsays: ladder tops support\nby: sim\n')[0],
           0, 'close an open question as a fact')
        sys.path.insert(0, os.path.join(d, 'tools'))
        try:
            import importlib
            R = importlib.import_module('record')
            data = R.load(os.path.join(d, 'ledger', 'B34C.toml'))
        finally:
            sys.path.pop(0)
            sys.modules.pop('record', None)
            sys.modules.pop('manual', None)
        eq((len(data['fact']), 'open' in data, data['manual']), (3, False, ['C9', 'T141']),
           'the ledger file round-trips')
        eq(data['fact'][0]['says'], "RET Z -- $8D22's caller", 'text survives the heredoc untouched')
        eq(rec(d, 'next', stdin='unit: $B34C gate next\nstep: write the gate\n')[0], 0, 'next')
        eq(rec(d, 'decide', stdin='title: No ROM glyphs\ntext: substitute cells\n')[0], 0, 'decide')
        with open(os.path.join(d, 'test', 'game.test.js'), 'a') as f:
            f.write("checkTrue('edge: second row', true);\n")
        if has_git:
            out = rec(d, 'draft')[1]
            if '1 check rows added' not in out or 'B34C +3 facts' not in out or not out.startswith('$B34C'):
                raise AssertionError('draft must derive the gate rows and ledger deltas: ' + out[:200])


def t_status():
    with tempfile.TemporaryDirectory() as d:
        has_git = make_port(d)
        rec(d, 'new', 'B34C', stdin='name: MovePlayer\n')
        rec(d, 'link', 'B34C', stdin='fixture: edgejump\nport: movePlayer\n')
        rec(d, 'next', stdin='unit: $B34C gate next\nstep: write the gate\n')
        code, out, _ = stat(d, '--check')
        eq(code, 0, 'a clean port passes: ' + out)
        out = stat(d, '--brief')[1]
        for want in ('1 routines', '1 measured, 1 ported, 1 gated', 'Unit $B34C MovePlayer'):
            if want not in out:
                raise AssertionError('--brief is missing %r' % want)
        if 'evidence: measured, ported, gated' not in stat(d, 'b34c')[1]:
            raise AssertionError('the per-routine view must show its evidence')
        planted = {'notes.md': 'orphan\n'}
        for rel, text in planted.items():
            with open(os.path.join(d, rel), 'w') as f:
                f.write(text)
        code, out, _ = stat(d, '--check')
        if code != 1 or 'notes.md is not a record home' not in out:
            raise AssertionError('an unregistered record must block: ' + out)
        with open(os.path.join(d, 'notes.md'), 'w') as f:
            f.write('Purpose: selftest\nRead by: selftest\n')
        eq(stat(d, '--check')[0], 0, 'a record with a Purpose/Read by header is registered')
        with open(os.path.join(d, 'web', 'game.js'), 'w') as f:
            f.write('function renamed() {}\n')
        code, out, _ = stat(d, '--check')
        if code != 1 or "port function 'movePlayer'" not in out:
            raise AssertionError('a broken link must block: ' + out)
        with open(os.path.join(d, 'NEXT.md'), 'a') as f:
            f.write('x\n' * 20)
        if 'NEXT.md is' not in stat(d, '--check')[1]:
            raise AssertionError('an oversized NEXT.md must warn')


def make_mutport(d):
    """A synthetic port for the mutation runner: the kit's own page with a tiny
    engine included, a three-block suite, and six cases that between them reach
    every verdict path (manual 6.12)."""
    import io
    import shutil
    import subprocess
    port = json.load(io.open(os.path.join(REPO, 'port.json'), encoding='utf-8'))
    assets = [a['file'] for a in port.get('assets', [])          # every asset the build needs
              if os.path.exists(os.path.join(REPO, a['file']))]
    for rel in ['tools/build.py', 'tools/stamp.py', 'tools/mutants.py', 'tools/mutants.js', 'test/rig.js',
                'web/platform.js'] + assets:
        os.makedirs(os.path.join(d, os.path.dirname(rel)), exist_ok=True)
        shutil.copy(os.path.join(REPO, rel), os.path.join(d, rel))
    shutil.copytree(os.path.join(REPO, 'tools', 'vendor'), os.path.join(d, 'tools', 'vendor'))
    tpl = io.open(os.path.join(REPO, 'web', 'template.html'), encoding='utf-8').read()
    marker = '/*#include platform.js*/'
    assert marker in tpl, 'the template lost its platform include marker'
    port['out'] = 'web/demo.html'
    port['includes'] = {'platform.js': 'web/platform.js', 'game.js': 'web/game.js'}
    port['mutants'] = {'cases': 'test/mutants.json', 'suite': 'test/demo.test.js'}
    files = {
        'web/template.html': tpl.replace(marker, marker + '\n/*#include game.js*/'),
        'port.json': json.dumps(port, indent=1),
        'web/game.js': ('const DEMO_K = 7;\n'
                        'globalThis.__DEMO = {\n'
                        '  add(a, b) { return a + b; },\n'
                        '  twice(x) { return x * 2; },\n'
                        '  unused(x) { return x - 1; },\n'
                        '  k() { return DEMO_K; },\n'
                        '};\n'),
        'test/demo.test.js': ("'use strict';\nconst rig = require('./rig');\nconst { check } = rig;\n"
                              "const { sandbox } = rig.loadBuilt();\nconst D = sandbox.__DEMO;\n"
                              "{ check('add', D.add(2, 3), 5); }\n"
                              "{ check('twice', D.twice(4), 8); }\n"
                              "{ check('k', D.k(), 7); }\n"
                              "rig.done();\n"),
        'test/mutants.json': json.dumps([
            {'file': 'game.js', 'label': 'add subtracts', 'old': 'return a + b;', 'new': 'return a - b;'},
            {'file': 'game.js', 'label': 'twice triples', 'old': 'return x * 2;', 'new': 'return x * 3;'},
            {'file': 'game.js', 'label': 'unused is never called', 'old': 'return x - 1;', 'new': 'return x - 2;'},
            {'file': 'game.js', 'label': 'the constant', 'old': 'const DEMO_K = 7;', 'new': 'const DEMO_K = 8;'},
            {'file': 'game.js', 'label': 'a dead anchor', 'old': 'return a * b;', 'new': 'return a / b;'},
            {'file': 'demo.test.js', 'label': 'the test expects 6',
             'old': "check('add', D.add(2, 3), 5);", 'new': "check('add', D.add(2, 3), 6);"},
        ], indent=1),
    }
    for rel, text in files.items():
        with open(os.path.join(d, rel), 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    try:
        for args in (['init', '-q'], ['add', '-A'],
                     ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'base']):
            subprocess.run(['git', *args], cwd=d, capture_output=True, check=True)
        return True
    except Exception:
        return False


def t_mutants():
    import io
    import subprocess
    with tempfile.TemporaryDirectory() as d:
        has_git = make_mutport(d)
        pristine = io.open(os.path.join(d, 'web', 'game.js'), encoding='utf-8').read()
        r = subprocess.run([sys.executable, 'tools/mutants.py', '--jobs', '1'], cwd=d,
                           capture_output=True, text=True, timeout=600)
        eq(r.returncode, 1, 'a survivor and a dead anchor make the run red: ' + r.stdout[-300:])
        state = json.load(io.open(os.path.join(d, 'build', 'mutants', 'last.json'), encoding='utf-8'))
        got = {k: v['verdict'] for k, v in state['cases'].items()}
        eq(got, {'add subtracts': 'KILLED', 'twice triples': 'KILLED', 'unused is never called': 'SURVIVED',
                 'the constant': 'KILLED', 'a dead anchor': 'ANCHOR', 'the test expects 6': 'KILLED'},
           'verdicts on the synthetic port')
        for k in ('add subtracts', 'twice triples', 'the constant'):
            if not state['cases'][k]['killer_sha']:
                raise AssertionError('no killing block recorded for %r' % k)
        if 'LISTED 6' not in io.open(os.path.join(d, 'build', 'mutants', 'summary.txt'), encoding='utf-8').read():
            raise AssertionError('the one-line summary is missing or wrong')
        eq(io.open(os.path.join(d, 'web', 'game.js'), encoding='utf-8').read(), pristine,
           'the real tree is never written')
        if has_git:
            cases = json.load(io.open(os.path.join(d, 'test', 'mutants.json'), encoding='utf-8'))
            cases.append({'file': 'game.js', 'label': 'twice quadruples',
                          'old': 'return x * 2;', 'new': 'return x * 4;'})
            with open(os.path.join(d, 'test', 'mutants.json'), 'w', encoding='utf-8') as f:
                json.dump(cases, f)
            r = subprocess.run([sys.executable, 'tools/mutants.py', '--jobs', '1', '--affected'], cwd=d,
                               capture_output=True, text=True, timeout=600)
            if 'affected: 3 cases (1 new, 0 anchor lines, 0 killing block, 1 dead anchor, 1 red)' not in r.stdout:
                raise AssertionError('--affected must pick the new case and keep the red ones: '
                                     + r.stdout[-400:])
            if 'LISTED 3  KILLED 1' not in r.stdout:
                raise AssertionError('the new case must be killed: ' + r.stdout[-300:])
        if not has_git:
            return
        # manual 6.12 step 4: every killed verdict is stamped, and an edit stales
        # only the verdicts whose blocks executed the edited function
        state = json.load(io.open(os.path.join(d, 'build', 'mutants', 'last.json'), encoding='utf-8'))
        for k, v in state['cases'].items():
            if (v['verdict'] == 'KILLED') != bool(v.get('stamp')):
                raise AssertionError('a stamp on every killed verdict and on nothing else: %r %r' % (k, v))
        game = os.path.join(d, 'web', 'game.js')
        io.open(game, 'w', encoding='utf-8', newline='\n').write(
            pristine.replace('k() { return DEMO_K; },', 'k() { const v = DEMO_K; return v; },'))
        r = subprocess.run([sys.executable, 'tools/mutants.py', '--jobs', '1', '--affected', '--list'], cwd=d,
                           capture_output=True, text=True, timeout=600)
        listed = sorted(l.strip() for l in r.stdout.splitlines() if l.startswith('  ') and 'block' not in l)
        eq(listed, ['a dead anchor', 'the constant', 'unused is never called'],
           'editing k() stales the one verdict killed in the block that runs it, and the red ones: ' + r.stdout[-300:])
        if '1 stamp code' not in r.stdout:
            raise AssertionError('the reason must name the executed code: ' + r.stdout[-300:])
        io.open(game, 'w', encoding='utf-8', newline='\n').write(pristine)
        # manual 6.12 step 6: whole kill sets, then the cases that add nothing
        cases = json.load(io.open(os.path.join(d, 'test', 'mutants.json'), encoding='utf-8'))
        cases.append({'file': 'game.js', 'label': 'add adds one', 'old': 'return a + b;', 'new': 'return a + b + 1;'})
        with open(os.path.join(d, 'test', 'mutants.json'), 'w', encoding='utf-8') as f:
            json.dump(cases, f)
        r = subprocess.run([sys.executable, 'tools/mutants.py', '--jobs', '1', '--all-rows'], cwd=d,
                           capture_output=True, text=True, timeout=600)
        r = subprocess.run([sys.executable, 'tools/mutants.py', '--prune', '--write'], cwd=d,
                           capture_output=True, text=True, timeout=600)
        if '6 cases with whole kill sets: 3 add nothing, 3 kept' not in r.stdout:
            raise AssertionError('--prune on the synthetic port: ' + r.stdout[-400:])
        cases = json.load(io.open(os.path.join(d, 'test', 'mutants.json'), encoding='utf-8'))
        eq(sorted(c['label'] for c in cases if c.get('withdrawn')), ['add adds one', 'the test expects 6', 'twice quadruples'],
           'the later of two cases with the same kill set is withdrawn, with its reason')
        r = subprocess.run([sys.executable, 'tools/mutants.py', '--jobs', '1', '--list'], cwd=d,
                           capture_output=True, text=True, timeout=600)
        if '3 withdrawn cases not run' not in r.stdout or '5 cases would run' not in r.stdout:
            raise AssertionError('withdrawn cases are not run: ' + r.stdout[-300:])


def t_context_watch():
    hook = os.path.join(REPO, '.claude', 'hooks', 'context_watch.py')
    with tempfile.TemporaryDirectory() as d:
        tr = os.path.join(d, 't.jsonl')
        sid = 'selftest-%d' % os.getpid()

        def at(tokens):
            with open(tr, 'a') as f:
                f.write(json.dumps({'message': {'usage': {'input_tokens': 10,
                                    'cache_read_input_tokens': tokens - 10}}}) + '\n')
            code, out, _ = run_py([hook], json.dumps({'session_id': sid, 'transcript_path': tr}),
                                  {'ZX_HANDOVER_TOKENS': '1000', 'ZX_HANDOVER_STEP': '500'})
            eq(code, 0, 'the watch always exits 0')
            return 'additionalContext' in out

        eq([at(900), at(1100), at(1200), at(1600), at(300), at(1050)],
           [False, True, False, True, False, True],
           'notes once per crossing, again after the context shrinks and regrows')
        state = os.path.join(tempfile.gettempdir(), 'zx-context-watch-%s.json' % sid)
        if os.path.exists(state):
            os.remove(state)


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
    ('harness: keyboard, Kempston, unattached ports, on_read', t_harness_ports),
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
    ('refcheck: skool entries, titles, labels, symbol import', t_refcheck_parse),
    ('strings / hexdump', t_strings_hexdump),
    ('speckle: art vs noise', t_speckle),
    ('contact: both layouts', t_contact),
    ('keyprobe: export surface + press()', t_keyprobe_exports),
    ('portconfig: manifest, defaults, need()', t_portconfig),
    ('stackscan: slot-based frames, discards, fake return, LD SP reset vs switch, ISR', t_stackscan),
    ('blitforensics: two-background differential on known sprites + guards', t_blitforensics),
    ('callio: up recorded for any pop past the entry SP, not LD SP', t_callio_up),
    ('measure: arm then snapshot, poison twin, named windows, branches, stop_at, lint (6.11)', t_measure),
    ('manual: entries, traps, index, grep across both documents', t_manual_ids),
    ('tools: every script in tools/ has a row in tools/README.md', t_tools_registry),
    ('records: record.py writes each record to its home, refuses what it cannot check', t_records),
    ('status: orientation, per-routine view, check blocks orphans and broken links', t_status),
    ('hooks: the context watch notes each handover crossing once', t_context_watch),
    ('mutants: selection, killing block, survivor confirmed, dead anchor, test-file case, --affected, verdict stamps, --prune', t_mutants),
    ('traps: every trap has exactly one row in the trap-to-check map', t_traps_map),
    ('hooks: read and heredoc guards, stop check, session and sub-agent context', t_hooks),
]


def t_stamp():
    import json
    import shutil
    import tempfile
    st = mod('stamp')
    d = tempfile.mkdtemp(dir=st.ROOT, prefix='.stamptest')
    keep = (st.READ[:], st.GATE)
    try:
        inp, fxp, gate = (os.path.join(d, n) for n in ('state.pkl', 'fx.json', 'gate.json'))
        open(inp, 'wb').write(b'one')
        st.READ[:] = []
        st.note(inp)
        st.note(os.path.join('x', 'site-packages', 'skoolkit', '48.rom'))   # covered by pip:
        eq(st.READ, [st.rel(inp)], 'note keeps repo files, drops installed ones')
        fx = st.step({'cases': [1, 2]}, 'capture', argv=['t.py', '--capture'])
        json.dump(fx, open(fxp, 'w'))
        eq(st.freshness(fxp)[0], 'fresh', 'just written')
        open(inp, 'wb').write(b'two')
        state, why = st.freshness(fxp)
        eq((state, any(st.rel(inp) in w for w in why)), ('stale', True), 'a changed input names itself')
        open(inp, 'wb').write(b'one')
        fx['cases'].append(3)
        json.dump(fx, open(fxp, 'w'))
        state, why = st.freshness(fxp)
        eq((state, any('#97' in w for w in why)), ('stale', True), 'a hand edit')
        eq(len(st.step(fx, 'derive')['_stamp']['steps']), 2, 'derive appends a step')
        eq(len(st.step(fx, 'check')['_stamp']['steps']), 1, 'check vouches: one step')
        json.dump(fx, open(fxp, 'w'))
        eq(st.freshness(fxp)[0], 'fresh', 'restamped')
        eq(st.freshness(os.path.join(d, 'none.json'))[0], 'missing', 'absent')
        json.dump({'cases': []}, open(os.path.join(d, 'old.json'), 'w'))
        eq(st.freshness(os.path.join(d, 'old.json'))[0], 'unstamped', 'before stamps')
        # the gate chain: built.json's asset hash, the suite's files, the page
        page = os.path.join(d, 'page.html')
        open(page, 'w').write('page')
        built = {'out': st.rel(page), 'html': st.file_hash(page), 'files': {st.rel(inp): st.file_hash(inp)},
                 'assets': {'k': [st.rel(fxp), st.content_hash(fxp)]}}
        json.dump({'files': {}, 'built': built}, open(gate, 'w'))
        st.GATE = st.rel(gate)
        eq(st.gate_freshness('k', fxp)[0], 'fresh', 'gate as built')
        eq(st.gate_freshness('other', fxp)[0], 'stale', 'an asset the page never had')
        open(page, 'w').write('rebuilt')
        eq(st.gate_freshness('k', fxp)[0], 'stale', 'the page rebuilt since the suite')
        open(page, 'w').write('page')
        json.dump(st.step(dict(fx, cases=[9]), 'capture', argv=['t.py']), open(fxp, 'w'))
        eq(st.gate_freshness('k', fxp)[0], 'stale', 'the fixture recaptured since the build')
        st.GATE = os.path.join(d, 'nothing.json')
        eq(st.gate_freshness('k', fxp)[0], 'none', 'no green suite on record')
    finally:
        st.READ[:], st.GATE = keep
        shutil.rmtree(d, ignore_errors=True)


CHECKS.append(('stamp: fresh, stale on a changed input or a hand edit, steps, the gate chain', t_stamp))


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
