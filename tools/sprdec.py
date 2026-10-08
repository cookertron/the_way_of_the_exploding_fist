#!/usr/bin/env python3
"""
sprdec.py -- the sprite decoder $8803, transliterated with its T-states, and
checked call by call against the harness (manual 5.1, 7.2; D3).

The model walks the same rows, takes the same branches and charges each
instruction its uncontended T (code at $8803-$8AE8, scratch $8AE9-$8B1C,
tables $B500-$B9FF and the back buffer $F730 are all above $8000).  It is
the reading of $8803 in executable form: the JS decoder ports it, and the
fixture it freezes is the JS gate's oracle.

  --capture  run driven play; at every entry to $8803 save the machine, run
             the call alone (interrupts off) to its return at $C304, record
             HL, DE, every byte it wrote (stack excepted) and its T, restore,
             and carry on.  Each call is replayed through the model at once;
             distinct calls go to the fixture with the bytes the model read.
             Last line: T in play against uncontended over EVERY call, as
             play weights them -- the decoder's contention factor (D4).
  --check    replay the fixture through the model in a blank 64K: bytes
             written and T must both agree, case by case.
  --paths    with --check: tally the row paths (raw/packed, recolour, mirror,
             shift 2/4/6, single/edges, empty) the fixture covers.

Usage:
    python tools/sprdec.py --capture --state s1 [--frames 600] [--keys D+W]
                           [--out build/sprdec_cases.json] [--append]
    python tools/sprdec.py --check [--paths] [--fixture build/sprdec_cases.json]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Harness, SP, T                                 # noqa: E402
from probeutil import parse_target, boot_target, source_label, TARGET_HELP  # noqa: E402
import stamp as stamps                                             # noqa: E402

ENTRY, RET = 0x8803, 0xC304
SCRATCH = range(0x8AE9, 0x8B1D)
TABLES = range(0xB500, 0xBA00)
FIXTURE = 'build/sprdec_cases.json'
RH, RL, RD, RE = 6, 7, 4, 5          # skoolkit register indices (checked below)


def ldir_t(n):
    return 21 * (n or 0x10000) - 5


def djnz_t(k, body):
    return k * (body + 13) - 5


def ldir(m, s, d, n):
    for _ in range(n or 0x10000):
        m[d] = m[s]
        s, d = (s + 1) & 0xFFFF, (d + 1) & 0xFFFF
    return s, d


def put16(m, a, v):
    m[a], m[a + 1] = v & 0xFF, (v >> 8) & 0xFF


def get16(m, a):
    return m[a] | m[a + 1] << 8


def decode(m, hl, de, paths=None):
    """Run $8803 on memory m (anything indexable by address); return T."""
    def tally(k):
        if paths is not None:
            paths[k] = paths.get(k, 0) + 1
    F = m[0xC40E]
    t = 13 + 7 + 10
    if F & 0xFE:
        m[0x8B0A] = 1; t += 7 + 13 + 10
    else:
        m[0x8B0A] = 0; t += 4 + 13
    m[0x8AF3] = 0; t += 7 + 13
    w = m[hl]
    m[0x8B1C] = w; m[0x8B1B] = w; t += 7 + 13 + 13 + 4 + 13 + 4 + 10
    if m[0x8B0A]:
        m[0x8B1C] = (w + 1) & 0xFF; t += 13 + 4 + 13
    hl = (hl + 1) & 0xFFFF; t += 6
    while True:
        # $8833 row top
        m[0x8AF3] = m[0x8AF3] ^ 1; t += 13 + 7 + 13
        m[0x8AFF] = 0; m[0x8AFE] = 0; t += 4 + 13 + 13
        t += 7 + 4 + 10
        if m[hl] == 0:
            return t + 10
        put16(m, 0x8B16, de + m[0xC408]); t += 72
        hd = m[hl]; t += 7 + 4 + 10
        if not hd & 0x80:                          # $8858 raw row: w bytes
            tally('raw')
            w = m[0x8B1B]
            put16(m, 0x8B14, hl + w)
            m[0x8AE9] = w | 0x80
            ldir(m, hl, 0x8AEA, w)
            hl = 0x8AE9
            t += 13 + 4 + 7 + 11 + 11 + 16 + 10 + 11 + 10 + 7 + 7 + 6 + ldir_t(w) + 30
        else:                                      # $8875 packed row
            tally('packed')
            put16(m, 0x8B14, hl + (hd & 7) + 1)
            t += 4 + 7 + 4 + 4 + 7 + 11 + 11 + 16 + 10
        # $8882 recolour by row parity, tables $B8/$B9 via $8AD1
        t += 13 + 4 + 10
        if m[0xC407]:
            tally('recolour')
            a = m[hl]; m[0x8AF4] = a; n = a & 7
            tab = 0xB800 if m[0x8AF3] else 0xB900
            for i in range(n):
                m[0x8AF5 + i] = m[tab + m[hl + 1 + i]]
            t += 11 + 7 + 10 + 7 + 6 + 6 + 7 + 4 + 4 + 10 + 20
            if n:
                t += djnz_t(n, 7 + 17 + 97 + 7 + 6 + 6)
            hl = 0x8AF4
        # $88A5 mirror: skip re-measured from the right, bytes reversed by $B7
        t += 13 + 8 + 10
        if F & 1:
            tally('mirror')
            hd = m[hl]; n = hd & 7; s = (hd >> 3) & 7
            a = (((m[0x8B1B] - s - n) & 0xFF) << 3) & 0xFF
            t += 128
            if a:
                a |= 0x40; t += 7
            m[0x8B0B] = a | 0x80 | n
            for i in range(n):
                m[0x8B0B + n - i] = m[0xB700 + m[hl + 1 + i]]
            t += 42 + 78 + (djnz_t(n, 65) if n else 0) + 20
            hl = 0x8B0B
        # $88F7 shift: bit 1 two pixels, bit 2 four (RRD), bit 3 six (left 2)
        t += 13 + 8 + 10
        sh = 0
        if F & 2:
            sh = 2
        else:
            t += 13 + 8 + 10
            if F & 4:
                sh = 4
            else:
                t += 13 + 8 + 10
                if F & 8:
                    sh = 6
        if sh:
            tally(f'shift{sh}')
            hd = m[hl]; m[0x8B01] = hd; n = hd & 7; src = (hl + 1) & 0xFFFF
            t += 7 + 11 + 10 + 7 + 10 + 6 + 7 + 10
            if n:
                m[0x8B00] = n
                first = m[src]
                k = n + 1
                if sh == 6:
                    m[0x8B02] = 0
                    t += 13 + 11 + 10 + 4 + 7 + 11 + 4 + 7 + 6 + 7 + 7 + 10
                    if first < 0x40:
                        m[0x8AFE] = 1; t += 20
                    ldir(m, src, 0x8B03, n)
                    t += 4 + 4 + 10 + ldir_t(n) + 10 + 10 + 13 + 4 + 4 + 4 + 4 + 4 + 10
                    t += 11 + 13 + 4 + 7 + 11 + 10 + 11 + 11 + 4
                    for _ in range(2):
                        c = 0
                        for a in range(0x8B02 + n, 0x8B01, -1):
                            v = m[a]; m[a] = (v << 1 | c) & 0xFF; c = v >> 7
                    t += 2 * djnz_t(k, 24) + 10 + 4 + 4 + 10 + 7 + 4 + 10
                else:
                    t += 13 + 11 + 10 + 4 + 7 + 7 + 7 + 10
                    if first < (4 if sh == 2 else 0x10):
                        m[0x8AFE] = 1; t += 20
                    ldir(m, src, 0x8B02, n)
                    m[0x8B02 + n] = 0
                    t += 11 + 4 + 4 + 10 + ldir_t(n) + 10 + 4 + 7 + 10
                    if sh == 2:
                        for _ in range(2):
                            c = 0
                            for a in range(0x8B02, 0x8B02 + k):
                                v = m[a]; m[a] = v >> 1 | c << 7; c = v & 1
                        t += 47 + 11 + 2 * djnz_t(k, 24) + 10 + 4 + 4
                    else:
                        acc = 0
                        for a in range(0x8B02, 0x8B02 + k):
                            v = m[a]; m[a] = (acc & 0xF) << 4 | v >> 4; acc = v & 0xF
                        t += 13 + 4 + 4 + 4 + djnz_t(k, 24)
                    t += 6 + 7 + 4 + 10
                if m[0x8B02 + n] == 0:
                    m[0x8AFF] = 1; t += 20
            t += 20
            hl = 0x8B01
        # $8A30 plot: skip, then first byte masked by $B5, middle copied,
        # last masked by $B6; a single byte takes both masks ($8AA5)
        hd = m[hl]; t += 13 + 4 + 7 + 4 + 4 + 10
        if hd & 0x40:
            de = (de + ((hd >> 3) & 7)) & 0xFFFF; t += 89
        n = hd & 7; t += 25
        if n == 0:
            tally('empty')
            hl, de = get16(m, 0x8B14), get16(m, 0x8B16); t += 46
            continue
        b = n; t += 31
        if m[0x8B0A]:
            b += 1; t += 4
        hl = (hl + 1) & 0xFFFF; b -= 1; t += 37
        if m[0x8AFF]:
            b -= 1; t += 4
        t += 27
        if m[0x8AFE]:
            de = (de + 1) & 0xFFFF; hl = (hl + 1) & 0xFFFF; b -= 1; t += 16
        b &= 0xFF; t += 18
        if b == 0:
            tally('single')
            v = m[hl]
            m[de] = m[de] & (m[0xB500 + v] | m[0xB600 + v]) | v
            t += 121
        else:
            tally('edges')
            v = m[hl]
            m[de] = m[de] & m[0xB500 + v] | v
            hl, de = (hl + 1) & 0xFFFF, (de + 1) & 0xFFFF
            b -= 1; t += 96
            if b:
                hl, de = ldir(m, hl, de, b); t += 11 + ldir_t(b)
            v = m[hl]
            m[de] = m[de] & m[0xB600 + v] | v
            t += 70
        hl, de = get16(m, 0x8B14), get16(m, 0x8B16); t += 46


class Logged:
    """Memory that records the bytes read before any write to them (the
    call's inputs) and every address written."""
    def __init__(self, data):
        self.m = bytearray(data)
        self.reads = {}
        self.written = set()

    def __getitem__(self, a):
        if a not in self.written and a not in self.reads:
            self.reads[a] = self.m[a]
        return self.m[a]

    def __setitem__(self, a, v):
        self.written.add(a)
        self.m[a] = v


def runs(cells):
    """{addr: byte} -> [[addr, "hexbytes"], ...], one entry per contiguous run."""
    out = []
    for a in sorted(cells):
        if out and out[-1][0] + len(out[-1][1]) // 2 == a:
            out[-1][1] += f'{cells[a]:02x}'
        else:
            out.append([a, f'{cells[a]:02x}'])
    return out


def unruns(rs):
    return {a + i: b for a, h in rs for i, b in enumerate(bytes.fromhex(h))}


def case_key(hl, cells):
    """One case per sprite and flag set: the bytes under DE change only the
    masked edge bytes, and the T does not depend on them."""
    return (hl, cells.get(0xC40E), cells.get(0xC407), cells.get(0xC408))


def capture(args):
    t = parse_target(args)
    frames, keys, out, append = 600, [], FIXTURE, False
    while args:
        a = args[0]
        if a == '--frames':
            frames = int(args[1], 0); del args[:2]
        elif a == '--keys':
            keys = args[1].split('+'); del args[:2]
        elif a == '--out':
            out = args[1]; del args[:2]
        elif a == '--append':
            append = True; del args[:1]
        else:
            sys.exit(f'sprdec: unknown argument {a}  (target: {TARGET_HELP})')
    from keyprobe import press
    h = boot_target(t, 'sprdec')
    flat = Harness(deck=False, contended=False)
    if not h.contended or flat.contended:
        sys.exit('sprdec: needs the contended harness for play and an uncontended twin for T')
    r, m = h.regs, h.memobj.m
    for k in keys:
        press(h.ports, k)
    fx = {'tables': None, 'cases': []}
    if append and os.path.exists(out):
        fx = json.load(open(out))
    seen = {case_key(c['hl'], unruns(c['in'])) for c in fx['cases']}
    calls = bad = new = 0
    sum_t = sum_tc = 0                             # every call, weighted as play calls it
    end = r[T] + frames * h.frame_duration
    while r[T] < end:
        reason, _ = h.run_until([ENTRY], limit=200_000)
        if reason != 'target':
            continue
        st = h.save_state()
        pre, sp, t0 = bytes(m), r[SP], r[T]
        hl, de = r[RH] << 8 | r[RL], r[RD] << 8 | r[RE]
        reason, _ = h.run_until([RET], limit=2_000_000, interrupts=False)
        if reason != 'target':
            sys.exit(f'sprdec: call at T={t0} never returned to ${RET:04X}')
        cont_t = r[T] - t0
        stack = range(sp - 64, sp + 2)
        real = {a: m[a] for a in range(0x4000, 0x10000) if m[a] != pre[a] and a not in stack}
        post = bytes(m)
        flat.load_state(st)                        # the same call, uncontended
        flat.run_until([RET], limit=2_000_000, interrupts=False)
        real_t = flat.regs[T] - t0
        sum_t += real_t; sum_tc += cont_t
        h.load_state(st)
        for k in keys:
            press(h.ports, k)
        h.run_until([RET], limit=2_000_000)        # the real call, interrupts on
        calls += 1
        lm = Logged(pre)
        mt = decode(lm, hl, de)
        model = {a: lm.m[a] for a in lm.written if lm.m[a] != pre[a]}
        if any(lm.m[a] != post[a] for a in lm.written):
            model['rewritten'] = -1                # a write the model made that the call did not
        if model != real or mt != real_t:
            bad += 1
            if bad <= 5:
                diff = sorted(set(model.items()) ^ set(real.items()))[:8]
                print(f'*** call {calls}: HL=${hl:04X} DE=${de:04X} T model {mt} real {real_t}; '
                      f'differing writes {[(hex(a), v) for a, v in diff]}')
            continue
        tables = pre[TABLES.start:TABLES.stop].hex()
        if fx['tables'] is None:
            fx['tables'] = tables
        elif fx['tables'] != tables:
            sys.exit('sprdec: the tables at $B500-$B9FF changed between calls -- they are not constant')
        ins = {a: v for a, v in lm.reads.items() if a not in TABLES and a not in SCRATCH}
        key = case_key(hl, ins)
        if key in seen:
            continue
        seen.add(key)
        new += 1
        fx['cases'].append({
            'hl': hl, 'de': de, 'in': runs(ins),
            'out': runs({a: post[a] for a in lm.written if a not in SCRATCH}),
            't': real_t, 'tc': cont_t})
    print(f'sprdec: {source_label(t)}, {frames} frames: {calls} calls, {bad} disagree with the model, '
          f'{new} new distinct cases ({len(fx["cases"])} in {out})')
    if sum_t:
        print(f'sprdec: contention over all {calls} calls: {sum_tc} T in play against {sum_t} uncontended, '
              f'factor {sum_tc / sum_t:.5f}')
    if bad:
        sys.exit(1)
    fx['about'] = ('Purpose: frozen oracle for the sprite decoder $8803 -- one call per sprite and flag set: HL, DE, the bytes it read as [addr, hex] runs '
                   '(in), every byte it wrote outside its scratch (out), its uncontended T (t) and its T in play (tc). '
                   'Read by: python tools/sprdec.py --check, and the JS decoder gate.')
    stamps.step(fx, 'append' if append else 'capture')    # --check replays the model, not the machine: it does not stamp
    with open(out, 'w') as f:
        json.dump(fx, f, separators=(',', ':'))


def check(args):
    fixture, want_paths = FIXTURE, False
    while args:
        if args[0] == '--fixture':
            fixture = args[1]; del args[:2]
        elif args[0] == '--paths':
            want_paths = True; del args[:1]
        else:
            sys.exit(f'sprdec: unknown argument {args[0]}')
    fx = json.load(open(fixture))
    tables = bytes.fromhex(fx['tables'])
    paths, bad = {}, 0
    for i, c in enumerate(fx['cases']):
        m = bytearray(0x10000)
        m[TABLES.start:TABLES.stop] = tables
        ins = unruns(c['in'])
        for a, v in ins.items():
            m[a] = v
        lm = Logged(m)
        t = decode(lm, c['hl'], c['de'], paths)
        out = {a: lm.m[a] for a in lm.written if a not in SCRATCH}
        unread = [a for a in lm.reads if a not in TABLES and a not in ins]
        want = unruns(c['out'])
        if out != want or t != c['t'] or unread:
            bad += 1
            if bad <= 5:
                print(f'*** case {i}: T model {t} fixture {c["t"]}; writes agree: {out == want}')
    ts = [c['t'] for c in fx['cases']]
    print(f'sprdec: {len(fx["cases"])} cases, {bad} disagree; T {min(ts)}-{max(ts)}')
    if want_paths:
        print('row paths: ' + ', '.join(f'{k} {v}' for k, v in sorted(paths.items())))
    sys.exit(1 if bad else 0)


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    if args[0] == '--capture':
        capture(args[1:])
    elif args[0] == '--check':
        check(args[1:])
    else:
        sys.exit('sprdec: --capture or --check (see --help)')


if __name__ == '__main__':
    main()
