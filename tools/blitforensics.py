#!/usr/bin/env python3
"""
blitforensics.py -- measure ONE sprite blit from ground truth (manual phase
5.1/5.2), WITHOUT reading the blitter by hand and WITHOUT assuming the sprite's
size, byte order, or whether it is masked.

Method: a TWO-BACKGROUND DIFFERENTIAL.  Hook a per-sprite draw routine, then run
the same call twice from an identical saved state --

  * once over an all-$00 target region -> each written byte is the sprite DATA
    (for a masked blit  screen = (screen AND mask) OR data,  and 0 AND mask = 0,
     so the result is exactly `data`; for an opaque blit it is the sprite too);
  * once over an all-$FF target region -> the result is (mask OR data).

Diff the two write logs:
  * a byte identical over both backgrounds is OPAQUE (independent of what was
    under it); a byte that differs is MASKED;
  * data     = the over-$00 byte;
  * the bits that DIFFER (over-$FF XOR over-$00) are the transparent, non-ink
    pixels.  So a pixel is INK where data=1, TRANSPARENT where the diff=1, and
    BLACK otherwise -- the full sprite, recovered.

Because it never inspects opcodes -- only compares outputs -- it works for
POP/stack blitters, LDI copiers and masked AND-OR, OR-only or plain opaque
blitters alike.  An XOR blitter (screen ^= data) is DETECTED (over-$FF ==
over-$00 XOR $FF) and its data recovered, but a transparency mask is not
observable this way -- it is flagged, not guessed.  A call that writes only
background (every byte $00 over $00 and $FF over $FF) is EMPTY: masked-empty
and XOR-of-nothing are indistinguishable, so no mode is claimed.  The bounding
box of the written addresses gives WxH; the write order gives the draw order.

THE BOUND.  One call is bracketed by the return address on the stack at
--entry, so the stack top there must be the return of the CALL that led to it
(directly, or via JP/JR inside the CALLed routine), i.e. hook BEFORE the routine
pushes anything.  The tool checks that a CALL/RST instruction precedes the word
at (SP) and refuses otherwise (a fall-through entry, a JP from the main loop,
or a hook placed after a PUSH give a stack top that is NOT a return address,
and the measurement would silently run on into the game).  The check is a
plausibility test, not proof: pass --ret 0xADDR to name the bound yourself.
If the call does not reach the bound within --steps the result is reported as
NOT one call and the tool exits 3.

Hook the routine that composes ONE sprite, NOT the full-frame routine that
first restores the background from a shadow -- that would overwrite the fill
and make every sprite look opaque (the tool warns when a result looks like
that).  Attribute writes inside the target are counted, not decoded.

--target LO HI names the region filled and watched.  Its first $1800 bytes are
taken to be a bitmap in ULA display layout with base LO (so the default
0x4000 0x5B00 is the real screen, and 0xC000 0xDB00 a same-layout back
buffer), the next $300 its attributes.  A linear or otherwise laid-out buffer
is outside the tool's geometry: sizes and grids would be wrong for it.

Usage:
  python tools/blitforensics.py --state NAME --entry 0xADDR
        [--target 0x4000 0x5B00]   region filled + watched (default display+attrs)
        [--skip N]                 measure the (N+1)-th hit of --entry (default 0)
        [--ret 0xADDR]             the return address bounding the call (else (SP))
        [--src SP|HL|IX|IY|DE|BC]  also dump the source bytes at that register @entry
        [--src-len 64]             how many source bytes to dump (default 64)
        [--steps 200000]           per-call step cap
        [--out build/blit]         PNG + JSON output prefix
Exit: 0 measured; 2 nothing written in the target; 3 the bound is not a return
address / the call never returned to it.
"""
import os
import sys
import json
import base64

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                   # noqa: E402
import harness as H                                                # noqa: E402
from harness import Harness                                        # noqa: E402
import screen as scr                                               # noqa: E402

BMP_LEN, ATTR_LEN = 0x1800, 0x300
COND_CALL = {0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}


class BoundError(Exception):
    """The word at (SP) is not a return address for --entry, or the call never returned."""


def run_call(h, ret, lo, hi, fill, steps):
    """Fill [lo,hi) with `fill`, run the current call to its return address with
    interrupts off, and return {addr: last value written} within [lo,hi) + order."""
    m = h.memobj
    m.m[lo:hi] = bytes([fill]) * (hi - lo)
    m.watch(lo, hi)
    reason, n = h.run_until((ret,), limit=steps, interrupts=False)
    log = m.log
    m.unwatch()
    writes, order = {}, []
    for pc, a, v in log:
        if lo <= a < hi:
            if a not in writes:
                order.append(a)
            writes[a] = v
    return writes, order, reason, n


def reg_at(h, name):
    return {'SP': h.sim.registers[H.SP], 'HL': h.hl(), 'DE': h.de(), 'BC': h.bc(),
            'IX': h.ix(), 'IY': h.iy()}[name]


def call_before(h, ret):
    """Is the word `ret` the return address of SOME CALL/RST (the instruction
    before it is CALL nn / CALL cc,nn / RST p)?  Returns that instruction's
    address, or None.  The call's target need not be --entry: a routine is often
    CALLed at one address and reaches the blit by JP/JR inside itself (Bubble
    Bobble: CALL $A447 ... JR C,$A600), and the stack top is still its return."""
    b3 = h.peek(ret - 3, 3)
    if b3[0] == 0xCD or b3[0] in COND_CALL:
        return ret - 3
    if h.peek(ret - 1)[0] & 0xC7 == 0xC7:                                   # RST p
        return ret - 1
    return None


def measure(h, entry, lo=0x4000, hi=0x5B00, steps=200000, ret=None):
    """PC is at `entry` (just reached).  Run the call over both backgrounds and
    return the report dict (mode, w, h, grid rows of I/K/'.', data ...).  Raises
    BoundError when the bound is unusable; when nothing was written inside the
    target's bitmap the dict has bmp_bytes 0 (attr_bytes/other_bytes still count)."""
    sp = h.sim.registers[H.SP]
    if ret is None:
        ret = h.peek16(sp)
        caller = call_before(h, ret)
        if caller is None:
            raise BoundError(f'the word at (SP=${sp:04X}) is ${ret:04X}, and no CALL/RST precedes '
                             f'it: ${entry:04X} is reached by fall-through/JP from code that was '
                             f'not CALLed, or is hooked after a PUSH.  Hook an entry whose stack '
                             f'top is a return address, or pass --ret 0xADDR')
    saved = h.save_state()
    w0, order, r0, n0 = run_call(h, ret, lo, hi, 0x00, steps)
    h.load_state(saved)
    w1, _, r1, n1 = run_call(h, ret, lo, hi, 0xFF, steps)
    h.load_state(saved)
    if r0 != 'target' or r1 != 'target':
        raise BoundError(f'the call did not return to ${ret:04X} within {steps} steps '
                         f'({r0}/{r1}); the writes are NOT one call.  Raise --steps, or the '
                         f'bound is wrong (--ret)')

    bmp_hi = min(hi, lo + BMP_LEN)
    attr_hi = min(hi, lo + BMP_LEN + ATTR_LEN)
    touched = set(w0) | set(w1)
    bmp = sorted(a for a in touched if lo <= a < bmp_hi)
    attr = sorted(a for a in touched if bmp_hi <= a < attr_hi)
    other = sorted(a for a in touched if a >= attr_hi)
    if not bmp:
        return {'bmp_bytes': 0, 'attr_bytes': len(attr), 'other_bytes': len(other)}

    coords = {a: scr.bmp_coords(a, base=lo) for a in bmp}
    cols = sorted({x for x, y in coords.values()})
    ys = sorted({y for x, y in coords.values()})
    x0, y0 = cols[0], ys[0]
    wpx = (cols[-1] - cols[0]) + 8
    hpx = (ys[-1] - ys[0]) + 1
    # classify from the two backgrounds, per written byte, then overall:
    #   empty  : every byte is background over both ($00 over $00, $FF over $FF)
    #   opaque : identical over $00 and $FF   (output independent of background)
    #   xor    : over-$FF == over-$00 XOR $FF (screen ^= data; a mask is NOT recoverable)
    #   masked : otherwise                    (screen = (screen AND mask) OR data)
    d0 = {a: w0.get(a, 0x00) for a in bmp}
    d1 = {a: w1.get(a, 0xFF) for a in bmp}
    empty = all(d0[a] == 0x00 and d1[a] == 0xFF for a in bmp)
    opq = all(d0[a] == d1[a] for a in bmp)
    xor = all((d0[a] ^ d1[a]) == 0xFF for a in bmp)
    mode = 'EMPTY' if empty else 'OPAQUE' if opq else 'XOR' if xor else 'MASKED'

    # recover the sprite grid.  data = over-$00; for a masked blit the bits that
    # DIFFER between the two backgrounds are the transparent (background-showing) ones.
    grid = [['.'] * wpx for _ in range(hpx)]
    for a in bmp:
        x, y = coords[a]
        diff = d0[a] ^ d1[a]
        for b in range(8):
            bit = 0x80 >> b
            gx, gy = (x - x0) + b, (y - y0)
            if d0[a] & bit:
                grid[gy][gx] = 'I'                              # ink (sprite pixel)
            elif mode == 'OPAQUE':
                grid[gy][gx] = 'K'                              # opaque black, no transparency
            elif mode in ('XOR', 'EMPTY'):
                grid[gy][gx] = '.'                              # XOR leaves non-data pixels as bg
            else:
                grid[gy][gx] = '.' if (diff & bit) else 'K'     # masked: transparent vs black
    rows = [''.join(r) for r in grid]
    transparent = sum(c == '.' for r in rows for c in r)
    bmp_order = [a for a in order if a in coords]
    order_rowmajor = bmp_order == sorted(bmp_order, key=lambda a: coords[a][::-1])
    return {
        'entry': f'${entry:04X}', 'return': f'${ret:04X}', 'steps': [n0, n1],
        'target': [f'${lo:04X}', f'${hi:04X}'],
        'w': wpx, 'h': hpx, 'chars': [wpx // 8, (hpx + 7) // 8], 'mode': mode,
        'bmp_bytes': len(bmp), 'attr_bytes': len(attr), 'other_bytes': len(other),
        'origin': [x0, y0], 'transparent_px': transparent,
        'solid_warning': transparent == 0 and (wpx * hpx) >= 64 and mode == 'OPAQUE',
        'row_major': order_rowmajor,
        'grid': rows,
        'data_over_00': {f'{a:04X}': d0[a] for a in bmp},
        'over_FF': {f'{a:04X}': d1[a] for a in bmp},
        'draw_order': [list(coords[a]) for a in bmp_order[:64]],
    }


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    state = entry = None
    lo, hi = 0x4000, 0x5B00
    skip = 0
    ret = None
    src = None
    src_len = 64
    steps = 200000
    out = portconfig.path('build/blit')
    while args:
        a = args[0]
        if a == '--state': state = args[1]; del args[:2]
        elif a == '--entry': entry = int(args[1], 0); del args[:2]
        elif a == '--target': lo, hi = int(args[1], 0), int(args[2], 0); del args[:3]
        elif a == '--skip': skip = int(args[1], 0); del args[:2]
        elif a == '--ret': ret = int(args[1], 0); del args[:2]
        elif a == '--src': src = args[1].upper(); del args[:2]
        elif a == '--src-len': src_len = int(args[1], 0); del args[:2]
        elif a == '--steps': steps = int(args[1], 0); del args[:2]
        elif a == '--out': out = args[1]; del args[:2]
        else: sys.exit(f'blitforensics: unknown argument {a}')
    if state is None or entry is None:
        sys.exit('blitforensics: --state and --entry are required')
    if not (0x4000 <= lo < hi <= 0x10000):
        sys.exit(f'blitforensics: --target must lie in RAM, LO < HI (got ${lo:04X} ${hi:04X})')

    h = Harness(deck=False)
    h.load_state_file(portconfig.state_path(state))

    # reach the wanted hit of the entry
    for k in range(skip + 1):
        reason, _ = h.run_until((entry,), limit=4_000_000, interrupts=True)
        if reason != 'target':
            sys.exit(f'blitforensics: entry ${entry:04X} not reached (hit {k}/{skip}; {reason})')
        if k < skip:
            h.step(1)
    src_ptr = reg_at(h, src) if src else None
    src_bytes = bytes(h.peek(src_ptr, src_len)) if src else b''

    try:
        rep = measure(h, entry, lo, hi, steps, ret)
    except BoundError as e:
        print(f'blitforensics: {e}')
        sys.exit(3)
    if rep['bmp_bytes'] == 0:
        print(f'no bitmap writes in [{lo:04X},{hi:04X}); wrong entry, or it draws to a '
              f'shadow/back-buffer -- try --target at that buffer. attrs touched: '
              f'{rep["attr_bytes"]}, other bytes in target: {rep["other_bytes"]}')
        sys.exit(2)

    mode, wpx, hpx = rep['mode'], rep['w'], rep['h']
    print(f'blit @${entry:04X} (skip {skip}) -> return {rep["return"]}   [{state}]')
    print(f'  sprite {wpx}x{hpx} px  ({wpx // 8}x{(hpx + 7) // 8} chars, {rep["bmp_bytes"]} bitmap bytes'
          f'{", " + str(rep["attr_bytes"]) + " attr bytes" if rep["attr_bytes"] else ""}'
          f'{", " + str(rep["other_bytes"]) + " bytes beyond the attrs" if rep["other_bytes"] else ""})')
    print(f'  {mode}   draw order: {"row-major top-down" if rep["row_major"] else "custom"}')
    if mode == 'XOR':
        print('  (XOR blitter: data recovered from the $00 background; a transparency mask '
              'is not observable by this method.)')
    if mode == 'EMPTY':
        print('  ! every written byte is background over both fills: nothing drawn.  A '
              'masked blit of an empty sprite and an XOR of nothing look the same; no mode '
              'is claimed -- try another --skip.')
    if rep['solid_warning']:
        print('  ! fully solid with zero transparency -- may be a background-restore or an '
              'opaque tile, not a masked sprite; confirm --entry is the per-sprite blit.')
    for row in rep['grid']:
        print('  ' + ''.join('#' if c == 'I' else '.' if c == 'K' else ' ' for c in row))

    # PNG
    from PIL import Image
    img = Image.new('RGBA', (wpx, hpx), (0, 0, 0, 0))
    p = img.load()
    for y in range(hpx):
        for x in range(wpx):
            c = rep['grid'][y][x]
            p[x, y] = (255, 255, 255, 255) if c == 'I' else (0, 0, 0, 255) if c == 'K' else (0, 0, 0, 0)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.resize((wpx * 4, hpx * 4), Image.NEAREST).save(out + '.png')

    report = {'state': state, 'skip': skip, **rep}
    if src:
        report['src_reg'] = src
        report['src_ptr'] = f'${src_ptr:04X}'
        report['src_bytes'] = base64.b64encode(src_bytes).decode()
        print(f'  source {src}=${src_ptr:04X}: {src_bytes.hex()}')
    json.dump(report, open(out + '.json', 'w'), indent=1)
    print(f'  -> {out}.png + {out}.json')


if __name__ == '__main__':
    main()
