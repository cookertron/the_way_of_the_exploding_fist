#!/usr/bin/env python3
"""
stackscan.py -- Q19, the DYNAMIC stack-imbalance scan (manual 8, Q19; family C1).

In 8-bit games the stack is a control-flow device: a routine that POPs extra
return addresses before its RET -- or resets SP outright -- "abandons" its
callers.  That is how "the player dies", "level complete" and "abandon this
update" are signalled, and it reads as dead code.  The manual calls this the
one scan that finds rules you did not know existed.

Method: a SHADOW CALL STACK kept BY STACK SLOT, not by nesting.
  - a CALL / conditional CALL / RST / accepted INTERRUPT creates a frame
    (callee, return address, slot = the SP that holds the return word);
  - after every instruction, any frame whose slot now lies below SP is gone,
    and the instruction that removed it is named:
      BALANCED   its own RET consumed its slot and landed on its return address
      DISCARD    a POP / INC SP removed it, or a RET went through a lower slot
                 -- the C1 idiom: the killing PC, its instruction, the victim's
                 callee and return address, and the count are reported
      REWRITE    its own RET consumed its slot but landed elsewhere (EX (SP),HL
                 or a store into the slot)
  - LD SP,* is ambiguous: a death handler resets the stack (Chuckie Egg 2:
    LD SP,$FFF0 / JP), but a blitter also parks SP in its data and restores it
    (Bubble Bobble: LD SP,HL at $A489, manual 3.10).  So frames an LD SP cuts
    are held PENDING: if SP comes back down to them they are live again and
    return normally; if a new frame is pushed while they are pending, the
    stack has been rebuilt over them and they are DISCARDED by that LD SP;
    if the scan ends first they are reported as cut and unresolved;
  - a RET that consumes a slot with NO frame is a FAKE RETURN: the game pushed
    an address and RET into it (RET-as-jump, PUSH-dispatch, inline parameters);
  - SP rising under an instruction this scan does not know is ODD.

SELF-CHECK.  frames == balanced + rewritten + discarded + open is bookkeeping
and holds by construction.  The checks that CAN fail are ODD == 0 (every SP
rise was a RET, POP, INC SP or LD SP this scan saw) and that a balanced return
consumed exactly its own slot; the exit status is non-zero on ODD > 0.  Fake
returns, rewrites and discards are reported, never failed: they are idioms to
go and read.

Interrupts are frames too (IM 1: $0038; IM 2: the vector selected by the bus
byte $FF), whenever they are accepted -- after a RET or a POP included -- so
an ISR's RET is balanced, not "unknown".  Verified against Bubble Bobble
(round 1: 0 discards, the RET-as-jump dispatch at $93E8 etc. as fake returns,
the blitter's LD SP,HL restored and balanced), Chuckie Egg 2 (a fall death:
exactly the 2 frames its own notes record, cut by LD SP,$FFF0 at $8A84, plus
its inline-parameter POP HL / INC SP idioms) and Chuckie Egg (see the probe
test report).

Usage (measure a LIVE state; a raw snapshot needs --arm/--warm to reach code):
    python tools/stackscan.py --state NAME  [--frames N] [--script "60:8,60:5"] [--top N]
    python tools/stackscan.py --snapshot G.z80 --arm --warm 400  [--frames N]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from harness import PC, SP, I, IM                                   # noqa: E402
from keyprobe import parse_script, press                           # noqa: E402
from probeutil import parse_target, boot_target, source_label, TARGET_HELP  # noqa: E402

try:
    import z80dis.z80 as z80
except ImportError:
    z80 = None

CALLS = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
RSTS = {0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF}
RETS = {0xC9, 0xC0, 0xC8, 0xD0, 0xD8, 0xE0, 0xE8, 0xF0, 0xF8}
POPS = {0xC1, 0xD1, 0xE1, 0xF1}
T = 25


def name_of(m, pc):
    """The instruction at pc, for the report."""
    if z80 is None:
        return ' '.join(f'{m[(pc + i) & 0xFFFF]:02X}' for i in range(3))
    try:
        return z80.decoded2str(z80.decode(bytes(m[(pc + i) & 0xFFFF] for i in range(4)), pc))
    except Exception:                       # noqa: BLE001
        return f'{m[pc]:02X} ?'


def isr_address(m, r):
    """Where an accepted interrupt goes: $0038, or the IM 2 vector for bus byte $FF."""
    if r[IM] == 2:
        v = (r[I] << 8) | 0xFF
        return m[v] | (m[(v + 1) & 0xFFFF] << 8)
    return 0x0038


def is_ld_sp(op, op2):
    return op in (0x31, 0xF9) or (op in (0xDD, 0xFD) and op2 == 0xF9) or (op == 0xED and op2 == 0x7B)


def sp_rise_known(op, op2):
    """Instructions that legitimately raise SP: RET*, POP*, INC SP, LD SP,*."""
    return (op in RETS or op in POPS or op == 0x33 or is_ld_sp(op, op2)
            or (op in (0xDD, 0xFD) and op2 == 0xE1)
            or (op == 0xED and op2 in (0x4D, 0x45)))


def below(slot, sp):
    """True when the word at `slot` lies below the stack pointer sp (mod 64K)."""
    return ((slot - sp) & 0xFFFF) >= 0x8000


def scan(h, frames, script):
    m = h.memobj.m
    r = h.regs
    shadow = []                 # live frames in push order: [callee, ret, slot]; newest last, lowest slot
    pending = []                # frames an LD SP cut, with the PC that cut them: [callee, ret, slot, kill_pc]
    created = balanced = rewritten = odd = 0
    discards = {}               # (kill_pc, victim_callee, victim_ret) -> count
    fakes = {}                  # ret_pc -> count
    rewrites = {}               # ret_pc -> count
    odds = {}                   # pc -> count
    names = {}                  # pc -> the instruction AS EXECUTED (loaders self-modify; decode at event time)
    fd = h.frame_duration
    t_end = r[T] + frames * fd
    segs = list(script) if script else [(frames, [])]
    seg_i = 0
    if script:
        for k in segs[0][1]:
            press(h.ports, k)

    def kill_pending(reason_pc=None):
        """A new frame was pushed: every pending frame is buried."""
        for callee, ret, slot, kpc in pending:
            key = (kpc, callee, ret)
            discards[key] = discards.get(key, 0) + 1
        pending.clear()

    while r[T] < t_end:
        pc, sp = r[PC], r[SP]
        op = m[pc]
        op2 = m[(pc + 1) & 0xFFFF]
        is_call = op in CALLS or op in RSTS
        is_ret = op in RETS or (op == 0xED and op2 in (0x4D, 0x45))
        isr = isr_address(m, r)
        if pc not in names and (is_ret or op in POPS or op == 0x33 or is_ld_sp(op, op2)
                                or (op in (0xDD, 0xFD) and op2 == 0xE1)):
            names[pc] = name_of(m, pc)
        h.step(1, interrupts=True)
        npc, nsp = r[PC], r[SP]
        # -- an accepted interrupt after this instruction?  Then the word at nsp is the PC the
        #    instruction itself reached; undo that push to classify the instruction on its own.
        int_frame = None
        if npc == isr:
            word = m[nsp] | (m[(nsp + 1) & 0xFFFF] << 8)
            plain_call = (is_call and ((sp - nsp) & 0xFFFF) == 2
                          and word == ((pc + (1 if op in RSTS else 3)) & 0xFFFF))
            if not plain_call:                      # (RST $38 under IM 1 is a call, not an interrupt)
                int_frame = [isr, word, nsp]
                npc, nsp = word, (nsp + 2) & 0xFFFF
        diff = (nsp - sp) & 0xFFFF
        if diff == 0:
            pass
        elif diff >= 0x8000:                                     # SP fell: something was pushed
            depth = 0x10000 - diff
            slot = (sp - 2) & 0xFFFF
            if is_call and depth >= 2:
                next_seq = (pc + (1 if op in RSTS else 3)) & 0xFFFF
                callee = (op & 0x38) if op in RSTS else (m[(pc + 1) & 0xFFFF] | (m[(pc + 2) & 0xFFFF] << 8))
                word = m[slot] | (m[(slot + 1) & 0xFFFF] << 8)
                if word == next_seq and npc == callee:          # the CALL was taken
                    if pending:
                        kill_pending()
                    shadow.append([callee, next_seq, slot])
                    created += 1
            if pending:                                          # SP came back down: cut frames revive
                revived = [f for f in pending if not below(f[2], nsp)]
                if revived:
                    pending[:] = [f for f in pending if below(f[2], nsp)]
                    for callee, ret, slot, kpc in sorted(revived, key=lambda f: -f[2]):
                        shadow.append([callee, ret, slot])
        else:                                                    # SP rose: frames below it are gone
            owned = False
            cut = is_ld_sp(op, op2)
            while shadow and below(shadow[-1][2], nsp):
                callee, ret, slot = shadow.pop()
                if is_ret and slot == sp:
                    owned = True
                    if npc == ret:
                        balanced += 1
                    else:
                        rewritten += 1
                        rewrites[pc] = rewrites.get(pc, 0) + 1
                elif cut:
                    pending.append([callee, ret, slot, pc])
                else:
                    key = (pc, callee, ret)
                    discards[key] = discards.get(key, 0) + 1
            if is_ret and not owned:
                fakes[pc] = fakes.get(pc, 0) + 1
            if not sp_rise_known(op, op2):
                odd += 1
                odds[pc] = odds.get(pc, 0) + 1
                names.setdefault(pc, name_of(m, pc))
        if int_frame is not None:
            if pending:
                kill_pending()
            shadow.append(int_frame)
            created += 1
        if script and seg_i < len(segs) - 1 and r[T] >= (t_end - sum(s[0] for s in segs[seg_i + 1:]) * fd):
            seg_i += 1
            h.ports.release_all()
            for k in segs[seg_i][1]:
                press(h.ports, k)
    unresolved = {}
    for callee, ret, slot, kpc in pending:
        unresolved[(kpc, callee, ret)] = unresolved.get((kpc, callee, ret), 0) + 1
    return dict(created=created, balanced=balanced, rewritten=rewritten, odd=odd,
                discards=discards, fakes=fakes, rewrites=rewrites, odds=odds,
                open=len(shadow), unresolved=unresolved, m=m, names=names)


def report(s, top_n=25):
    """Print the scan; return True when the falsifiable checks hold (ODD == 0)."""
    m = s['m']
    names = s.get('names', {})

    def name_of(m, pc):                      # the instruction as it was when it executed
        return names.get(pc) or globals()['name_of'](m, pc)
    n_disc = sum(s['discards'].values())
    n_fake = sum(s['fakes'].values())
    n_unres = sum(s['unresolved'].values())
    print(f"frames {s['created']} (CALL/RST/interrupt)  balanced {s['balanced']}  rewritten {s['rewritten']}  "
          f"discarded {n_disc} at {len(s['discards'])} sites  fake returns {n_fake} at {len(s['fakes'])} sites  "
          f"ODD {s['odd']}  open at end {s['open']}" + (f"  cut by LD SP, unresolved {n_unres}" if n_unres else ''))
    accounted = s['balanced'] + s['rewritten'] + n_disc + s['open'] + n_unres
    print(f"closure: {s['balanced']} balanced + {s['rewritten']} rewritten + {n_disc} discarded + {s['open']} open"
          + (f" + {n_unres} cut" if n_unres else '')
          + f" = {accounted} vs {s['created']} frames  {'OK' if accounted == s['created'] else '*** MISMATCH ***'} (bookkeeping)")
    ok = s['odd'] == 0
    print('self-check: ' + ('ODD 0 -- every SP rise was a RET, POP, INC SP or LD SP this scan saw: OK' if ok else
                            f"*** {s['odd']} ODD SP rises at {len(s['odds'])} PCs: an idiom this scan does not model ***"))
    print('\nDISCARDS (a frame removed by something other than its own RET) -- read each one (C1):')
    print('  kill PC   instruction            victim callee -> return   count')
    for (kpc, callee, ret), n in sorted(s['discards'].items(), key=lambda kv: -kv[1])[:top_n]:
        print(f'  ${kpc:04X}     {name_of(m, kpc):20s}   ${callee:04X} -> ${ret:04X}          x{n}')
    if not s['discards']:
        print('  (none in this run -- script the death / level-complete events to expose them)')
    if s['unresolved']:
        print('\nCUT BY LD SP, unresolved when the scan ended (a reset, or a switch not yet restored):')
        for (kpc, callee, ret), n in sorted(s['unresolved'].items(), key=lambda kv: -kv[1])[:top_n]:
            print(f'  ${kpc:04X}     {name_of(m, kpc):20s}   ${callee:04X} -> ${ret:04X}          x{n}')
    rom_fakes = {k: v for k, v in s['fakes'].items() if k < 0x4000}
    game_fakes = {k: v for k, v in s['fakes'].items() if k >= 0x4000}
    if game_fakes:
        print('\nFAKE RETURNS (RET into a pushed address: RET-as-jump, PUSH-dispatch, inline parameters):')
        for rpc, n in sorted(game_fakes.items(), key=lambda kv: -kv[1])[:top_n]:
            print(f'  ${rpc:04X}  {name_of(m, rpc):12s} x{n}')
    if rom_fakes:
        print(f"\nROM idioms, not the game's: {sum(rom_fakes.values())} fake returns at {len(rom_fakes)} ROM sites "
              "(the calculator's inline literals, BEEP): "
              + ' '.join(f'${k:04X}x{v}' for k, v in sorted(rom_fakes.items(), key=lambda kv: -kv[1])[:8]))
    if s['rewrites']:
        print('\nREWRITTEN returns (own slot consumed, landed elsewhere):')
        for rpc, n in sorted(s['rewrites'].items(), key=lambda kv: -kv[1])[:top_n]:
            print(f'  ${rpc:04X}  x{n}')
    if s['odds']:
        print('\nODD SP rises (not a RET/POP/INC SP/LD SP):')
        for opc, n in sorted(s['odds'].items(), key=lambda kv: -kv[1])[:top_n]:
            print(f'  ${opc:04X}  {name_of(m, opc):20s} x{n}')
    return ok


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    t = parse_target(args)
    script = None
    frames, top_n = 120, 25
    while args:
        if args[0] == '--frames':
            frames = int(args[1], 0); del args[:2]
        elif args[0] == '--script':
            script = parse_script(args[1]); del args[:2]
        elif args[0] == '--top':
            top_n = int(args[1], 0); del args[:2]
        else:
            sys.exit(f'stackscan: unknown argument {args[0]}  (target: {TARGET_HELP})')
    h = boot_target(t, 'stackscan')
    if script:
        frames = sum(s[0] for s in script)
    print(f'stackscan: {frames} frames from {source_label(t)}'
          + (f' with script {script}' if script else ''))
    ok = report(scan(h, frames, script), top_n)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
