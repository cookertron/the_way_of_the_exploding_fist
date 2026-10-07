#!/usr/bin/env python3
"""
sfx.py -- the sound effect $B15A measured against the real ROM, its D6
substitutes built, and every effect frozen as a speaker-edge fixture
(manual phase 11, 3.7; D6).  GAME-SPECIFIC.

$B15A plays effect A (1-6) inline and blocking.  Effects 1,2,3,5,6 are
pulse trains whose half-periods are ROM bytes AND a mask (0 read as 1);
effect 4 takes its delays from the LFSR at $B153-$B155.  Manual 0.5 forbids
shipping the ROM or a transcription of it, so D6: each ROM segment is
replaced by a deterministic substitute with the real segment's byte count,
sum of half-periods and count of zero bytes -- the three numbers the T
depends on -- so the edge count and the total T are the real machine's.

  --measure  per segment: the real ROM's count, sum and zeros; then each
             effect called alone in an UNCONTENDED harness twice, over the
             real ROM and with the substitute poked into it: the T must
             agree exactly, or the substitute is wrong and nothing is
             written.  Also prints the contended T from s1.
  --capture  the fixture (default build/sfx_cases.json): the segments, the
             substitutes the JS reads (our own numbers, no ROM byte), and
             cases -- effect 0, Flag_Sound 0, each ROM effect over its
             substitute, and effect 4 from a chain of LFSR states carried
             call to call from s1 plus derived states that reach the
             BC = 0 wrap (65536 passes) -- each with its uncontended T, its
             M1 count mod 128 (m1: how far R advanced), the
             $FE writes as [T from entry, value], and $B150-$B159 after.

Usage:
    python tools/sfx.py --measure [--state s1]
    python tools/sfx.py --capture [--state s1] [--out build/sfx_cases.json]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Harness, rom48, R                               # noqa: E402

ENTRY = 0xB15A
FLAG_SOUND = 0xB2FA
LFSR = 0xB153
# (effect, [(DE, HL, mask), ...]) as loaded at $B179-$B229 (adis 0xB179 90)
SEGMENTS = {1: [(0x000A, 0x0400, 0x7F)],
            2: [(0x000A, 0x0300, 0x3F)],
            3: [(0x00C0, 0x0100, 0x3F)],
            5: [(0x00E0, 0x0120, 0xFF), (0x03C0, 0x0400, 0xFF)],
            6: [(0x0080, 0x0100, 0x3F)]}


def seg_reads(de, hl):
    """Addresses the $B25B/$B297 loop reads: two per pass until DE passes HL."""
    out = []
    while True:
        out += [de, de + 1]
        de += 2
        if de >= hl:
            return out


def real_stats(rom, de, hl, mask):
    vals = [rom[a] & mask for a in seg_reads(de, hl)]
    return len(vals), sum(max(v, 1) for v in vals), vals.count(0)


def substitute(n, s, z, mask, seed):
    """n bytes whose values AND mask have exactly z zeros and a sum of
    max(v,1) = s.  A fixed LCG, then +-1 steps cycling over the nonzero
    positions; the bits above the mask are random, as a ROM byte's are,
    so the mask is exercised."""
    x = seed

    def nxt():
        nonlocal x
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        return x >> 8
    vals = [1 + nxt() % mask for _ in range(n)]
    zeros = set()
    while len(zeros) < z:
        zeros.add(nxt() % n)
    for i in zeros:
        vals[i] = 0
    diff = s - sum(max(v, 1) for v in vals)
    live = [i for i in range(n) if i not in zeros]
    k = 0
    while diff:
        i = live[k % len(live)]
        if diff > 0 and vals[i] < mask:
            vals[i] += 1; diff -= 1
        elif diff < 0 and vals[i] > 1:
            vals[i] -= 1; diff += 1
        k += 1
    return [v | (nxt() & ~mask & 0xFF) for v in vals]


def build_subst():
    rom = rom48()
    out = {}
    for e, segs in SEGMENTS.items():
        out[e] = []
        for j, (de, hl, mask) in enumerate(segs):
            n, s, z = real_stats(rom, de, hl, mask)
            out[e].append({'de': de, 'hl': hl, 'mask': mask, 'n': n, 'sum': s, 'zeros': z,
                           'vals': substitute(n, s, z, mask, 0x5F1 + 16 * e + j)})
    return out


def poke_subst(h, e, subst):
    for seg in subst.get(e, []):
        for a, v in zip(seg_reads(seg['de'], seg['hl']), seg['vals']):
            h.memobj.m[a] = v


def run(h, a, flag=1, lfsr=None):
    """One call of $B15A alone; returns (T, [[dt, value]], bytes $B150-$B159)."""
    h.poke(FLAG_SOUND, flag)
    h.poke(0xB150, a)                               # the request, as play_pass passes it
    if lfsr is not None:
        h.poke(LFSR, *lfsr)
    h.ports.writes.clear()
    h.ports.record_writes = True
    t0, r0 = h.tstates(), h.sim.registers[R]
    ex, t, _ = h.call(ENTRY, {'A': a}, limit=400_000_000)
    m1 = (h.sim.registers[R] - r0) & 0x7F
    h.ports.record_writes = False
    if ex != 0:
        sys.exit(f'sfx: effect {a} did not return (exit {ex})')
    w = [[tt - t0, v] for tt, p, v in h.ports.writes if p & 0xFF == 0xFE]
    return t, w, h.peek(0xB150, 10).hex(), m1


def twin(state):
    h = Harness(deck=False, contended=False)
    if h.contended:
        sys.exit('sfx: the twin must be uncontended')
    h.load_state_file(f'build/{state}.pkl')
    return h


def measure(state):
    subst = build_subst()
    h = twin(state)
    base = h.save_state()
    hc = Harness(deck=False)
    hc.load_state_file(f'build/{state}.pkl')
    cbase = hc.save_state()
    bad = 0
    for e in range(1, 7):
        for seg in subst.get(e, []):
            print(f"fx{e} segment ${seg['de']:04X}-${seg['hl']:04X} mask ${seg['mask']:02X}: "
                  f"real n={seg['n']} sum={seg['sum']} zeros={seg['zeros']}")
        h.load_state(base)
        t_real, w_real, _, _ = run(h, e)
        h.load_state(base)
        poke_subst(h, e, subst)
        t_sub, w_sub, _, _ = run(h, e)
        hc.load_state(cbase)
        t_cont, _, _, _ = run(hc, e)
        ok = t_real == t_sub and len(w_real) == len(w_sub)
        bad += not ok
        print(f"fx{e}: T real ROM {t_real}, substitute {t_sub}, writes {len(w_real)}/{len(w_sub)}"
              f" {'agree' if ok else 'DISAGREE'}; contended (s1) {t_cont}")
    print(f"sfx --measure: {6 - bad}/6 effects keep the real T and edge count over the substitute")
    return bad == 0, subst


def capture(state, out):
    ok, subst = measure(state)
    if not ok:
        sys.exit('sfx: a substitute changes the T; nothing written')
    h = twin(state)
    base = h.save_state()
    rom = bytes(h.memobj.m[0:0x4000])
    cases = []

    def add(kind, a, flag=1, lfsr=None, sub=True):
        h.memobj.m[0:0x4000] = rom
        if sub:
            poke_subst(h, a, subst)
        h.poke(0xB150, a)
        lin = h.peek(LFSR, 3).hex() if lfsr is None else bytes(lfsr).hex()
        before = h.peek(0xB150, 10).hex()
        t, w, after, m1 = run(h, a, flag, lfsr)
        cases.append({'kind': kind, 'a': a, 'flag': flag, 'lfsr': lin, 'mem_in': before,
                      'mem_out': after, 't': t, 'm1': m1, 'writes': w})
        print(f"case {len(cases) - 1}: {kind} A={a} flag={flag} LFSR {lin} -> T {t}, {len(w)} writes")

    h.load_state(base)
    add('early', 0)
    add('early', 2, flag=0)
    for e in (1, 2, 3, 5, 6):
        h.load_state(base)
        add('substitute', e)
    h.load_state(base)
    for _ in range(8):                              # the LFSR carried call to call from s1
        add('play', 4)
    for st in ((0x00, 0x00, 0x80), (0x00, 0x01, 0x2A)):
        h.load_state(base)                          # first delay C = 0: BC wraps to 65536 passes
        add('derived', 4, lfsr=st)
    segs = {str(e): [{k: s[k] for k in ('de', 'hl', 'mask', 'n', 'sum', 'zeros', 'vals')} for s in v]
            for e, v in subst.items()}
    fx = {'note': 'python tools/sfx.py --capture: uncontended $B15A calls from build/' + state +
                  '.pkl; ROM effects over the D6 substitutes (no ROM byte kept)',
          'segments': segs, 'cases': cases}
    with open(out, 'w') as f:
        json.dump(fx, f, separators=(',', ':'))
    print(f'sfx --capture: {len(cases)} cases -> {out}')


def main():
    args = sys.argv[1:]
    state, out = 's1', 'build/sfx_cases.json'
    if '--state' in args:
        state = args[args.index('--state') + 1]
    if '--out' in args:
        out = args[args.index('--out') + 1]
    if '--measure' in args:
        sys.exit(0 if measure(state)[0] else 1)
    elif '--capture' in args:
        capture(state, out)
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
