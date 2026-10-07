#!/usr/bin/env python3
"""branches.py -- which outcomes of each conditional branch a fixture's cases took.

A callio fixture (callio.py --capture) keeps per case the set of PCs the
real code executed ("sig").  A port gated on those cases is only proven on
the paths they reached, so each routine's gate also asks that the cases
reach every branch (the "reach every branch" rows in test/kit.test.js).
This lists every conditional instruction in the executed set -- JR cc,
JP cc, CALL cc, RET cc, DJNZ -- decoded from the image with z80dis, and for
each of its two outcomes whether some case took it:

  fall   a case executed the instruction and the one after it
         (for CALL cc: the one after it, without the target);
  taken  a case executed the instruction and the target
         (RET cc: the instruction but not the one after it).

The PC set is per case, not a trace, so an outcome is "taken" when the
evidence is consistent with it; a target also reached some other way can
look taken.  Read the PCs it marks MISSING off adis before writing a case
for them (callio.py --derive).

  --js     print the PCs to put in a gate's list: every reached target and
           fall-through, as JS hex literals, then each RET cc taken as a
           [pc, next] pair (a case with pc and not next).

Usage:
    python tools/branches.py --fixture build/callio_97cb.json [--lo 0x97CB --hi 0xAB67] [--js]
"""
import argparse
import json
import os
import sys

import z80dis.z80 as z

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portconfig                                        # noqa: E402


def pcsets(fixture):
    out = []
    for c in fixture['cases']:
        s = c['sig']
        out.append({int(s[j:j + 4], 16) for j in range(0, len(s), 4)})
    return out


def conditionals(mem, pcs):
    """(pc, len, text, kind, target) for every conditional in pcs."""
    res = []
    for pc in sorted(pcs):
        d = z.decode(mem[pc:pc + 4], pc)
        text = z.decoded2str(d).lower()
        words = text.split(None, 1)
        if not words:
            continue
        op = words[0]
        args = words[1].split(',') if len(words) > 1 else []
        if op == 'djnz':
            kind = 'jump'
        elif op in ('jr', 'jp', 'call') and len(args) == 2:
            kind = 'call' if op == 'call' else 'jump'
        elif op == 'ret' and args:
            kind = 'ret'
        else:
            continue
        tgt = None
        if kind != 'ret':
            tgt = int(args[-1].strip().lstrip('$').replace('0x', ''), 16)
        res.append((pc, d.len, text, kind, tgt))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--fixture', required=True)
    ap.add_argument('--image')
    ap.add_argument('--lo', type=lambda s: int(s, 0), default=0)
    ap.add_argument('--hi', type=lambda s: int(s, 0), default=0xFFFF)
    ap.add_argument('--js', action='store_true')
    a = ap.parse_args()
    img = a.image or portconfig.path(portconfig.get('z80', 'image'))
    with open(img, 'rb') as f:
        mem = f.read()
    with open(a.fixture) as f:
        sets = pcsets(json.load(f))
    union = set().union(*sets)
    conds = conditionals(mem, {p for p in union if a.lo <= p <= a.hi})
    pcs, pairs, missing = set(), [], 0
    for pc, ln, text, kind, tgt in conds:
        nxt = pc + ln
        here = [s for s in sets if pc in s]
        if kind == 'call':
            fall = any(nxt in s and tgt not in s for s in here)
        else:
            fall = any(nxt in s for s in here)
        if kind == 'ret':
            taken = any(nxt not in s for s in here)
        else:
            taken = any(tgt in s for s in here)
        flag = '' if fall and taken else '  MISSING ' + ' '.join(
            w for w, ok in (('fall', fall), ('taken', taken)) if not ok)
        missing += not (fall and taken)
        if not a.js:
            print(f'{pc:04X}  {text:<20} fall {"y" if fall else "-"}  taken {"y" if taken else "-"}'
                  f'  ({len(here)} cases){flag}')
        if fall:
            pcs.add(nxt)
        if taken and kind == 'ret':
            pairs.append((pc, nxt))
        elif taken:
            pcs.add(tgt)
    if a.js:
        print('[' + ', '.join(f'0x{p:04X}' for p in sorted(pcs)) + ']')
        print('[' + ', '.join(f'[0x{p:04X}, 0x{q:04X}]' for p, q in pairs) + ']')
    print(f'{len(conds)} conditionals, {missing} with an outcome no case took', file=sys.stderr)


if __name__ == '__main__':
    main()
