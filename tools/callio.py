#!/usr/bin/env python3
"""
callio.py -- what ONE routine reads and writes, measured over driven play.

Before a routine is ported, its interface is recorded (manual 5.1, 12.2):
the bytes it takes as inputs and the bytes it changes.  Reading that off the
disassembly misses the indexed reads (a table at HL+D) and the writes behind
a callee.  This brackets one CALL site and its return over driven play and
runs every call once more in an UNCONTENDED twin over a logging memory, as
rendfx.py does for $BF13:

  inputs   bytes read before the call wrote them -- instruction and operand
           fetches and the call's own stack frames
           (SP at entry - 128 .. SP + 1) excepted;
  outputs  every byte written outside the stack frames, with how many
           distinct values each took;
  code     the PCs executed, as runs -- the routine's extent including the
           callees it reached, and the paths that driven play never took
           (compare with adis).

Per address it reports in how many calls it was touched and the first PC
that touched it, so a run of the table points back at the instruction.  An
input that is also an output is a state variable the routine carries.

Fetches are the current instruction's own bytes, [PC, PC + length) with
the length decoded by z80dis -- not dataread.py's [PC, PC+3] window, which
drops DEC (HL) at $9CA3 reading Time at $9CA5.  The self-check line prints
how many reads were fetches.

  --capture  freeze the calls as a fixture, the rendfx.py shape for any
             call: per case the site (the CALL itself), SP and registers at
             entry, the inputs as [addr, hex] runs, the outputs, the
             registers at the return, the uncontended T and the PC set; one
             case per distinct (site, PC set), at most --per of each.
             --call may be given more than once (one routine, two sites).
             Fetched bytes must equal the target image at every call; the
             fixture keeps their addresses only (tape-derived, rule 7).
             ROM bytes read as data ($0000-$3FFF) are kept the same way, as
             addresses ("rom") -- D5: no ROM byte is committed.  --blind LO-HI
             (repeatable) keeps the outputs in that range as addresses only
             ("blind"), for writes that copy ROM bytes (a glyph on screen);
             the ranges are stored in the fixture and --check honours them.
  --check    replay every case in a blank 64K holding only the target's
             bytes at those addresses and the inputs: every byte written,
             every register at the return and the T must agree, and no
             byte outside them may be read.  Port reads are served from
             the case's log in order (the twin logs them from the keys held
             in the capture); R is set from the case and checked at the
             return, so a routine reading LD A,R replays exactly.
  --poke ADDR=VAL[,...]  (capture) set data bytes in the machine before play
             -- a mode or a control set no saved state holds (2P, Kempston);
             each case records them as "poked".  Never ROM, never a byte the
             fixture already fetched as code.  The oracle is still the
             machine code; the start is constructed, so say so.
  --kempston MASK  (capture) hold these Kempston bits (active high) all run.
  --derive   a path driven play never reached: replay case N over the
             target image with some of the bytes it read changed (--set),
             and append what the real code then did as a new case, marked
             "derived" with its parent and the bytes set.  The oracle is
             still the machine code; the input is constructed, so say so
             wherever the case is counted.  --r VAL replays it with R at
             the CALL set to VAL instead (the AI's draws, Q18).  --port
             I=VAL[,...] answers the parent's I-th logged port read (from 0)
             with VAL: a key or Kempston value on a path driven play already
             took, which --capture drops as a repeat PC set.  The derived
             case must read the same ports in the same order, or stop
             early (a key that ends the routine): it keeps the reads made.

Usage:
    python tools/callio.py --state NAME --call SITE RET [--frames 1500] [--keys D+W]
                           [--only in|out|code] [--gap N]
    python tools/callio.py --state s1 --call 0x9745 0x9748
    python tools/callio.py --capture --state s1 --call 0x9763 0x9766 --call 0x976C 0x976F
                           [--frames 1500] [--keys D+W] [--per 2] --out build/callio_97bb.json [--append]
    python tools/callio.py --capture --state s1 --call 0x9745 0x9748 --blind 0x4000-0x57FF
                           --out build/callio_9c6f.json
    python tools/callio.py --check --state s1 --fixture build/callio_97bb.json
    python tools/callio.py --derive --state s1 --fixture build/callio_97bb.json --case 12 --set 0xAA44=0x12
    python tools/callio.py --derive --state s1 --fixture build/callio_97cb.json --case 3 --r 0x15
"""
import json
import os
import statistics
import sys

import z80dis.z80 as z

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Simulator, SP, PC, T, R                         # noqa: E402
from keyprobe import press                                         # noqa: E402
from probeutil import parse_target, boot_target, source_label, TARGET_HELP  # noqa: E402
from sprdec import runs as hexruns, unruns                         # noqa: E402

FLAT = {'fast_djnz': False, 'fast_ldir': False}


class Logged:
    """Memory that logs data reads before any write, and every write,
    against the twin's registers; ROM writes are dropped as on the machine."""
    def __init__(self, data, stack):
        self.m = bytearray(data)
        self.regs = None
        self.stack = stack
        self.reads = {}            # addr -> first PC that read it before any write
        self.writes = {}           # addr -> first PC that wrote it
        self.fetches = 0
        self.fetched = set()       # addresses fetched as instruction bytes
        self.exit = None           # registers at the return
        self.lens = {}             # (pc, first 4 bytes) -> instruction length

    def __len__(self):
        return 0x10000

    def __getitem__(self, a):
        pc = self.regs[PC]
        if pc <= a < pc + 4 and a < pc + self.length(pc):
            self.fetches += 1
            self.fetched.add(a)
        elif a not in self.writes and a not in self.reads and a not in self.stack:
            self.reads[a] = pc
        return self.m[a]

    def length(self, pc):
        key = bytes(self.m[pc:pc + 4])
        n = self.lens.get((pc, key))
        if n is None:
            n = self.lens[pc, key] = z.decode(key, pc).len
        return n

    def __setitem__(self, a, v):
        if a >= 0x4000:
            if a not in self.writes and a not in self.stack:
                self.writes[a] = self.regs[PC]
            self.m[a] = v

    def __iter__(self):
        return iter(self.m)


class PortLog:
    """The twin's ports.  Live: answer from the harness's Ports (the keys held
    for the whole capture) and log each read; replay: serve a case's logged
    reads in order, and count any read that does not match the log."""
    def __init__(self, live=None, logged=None):
        self.live, self.logged, self.log, self.bad = live, logged, [], 0

    def read_port(self, registers, port):
        if self.logged is None:
            v = self.live.read_port(registers, port) if self.live else 0xFF
        else:
            i = len(self.log)
            if i < len(self.logged) and self.logged[i][0] == port:
                v = self.logged[i][1]
            else:
                self.bad += 1; v = 0xFF
        self.log.append([port, v])
        return v

    def write_port(self, registers, port, value, offset=0):
        pass

    def left(self):
        return len(self.logged) - len(self.log) if self.logged is not None else 0


def run_alone(mem, regs, ret, limit=20_000_000, ports=None):
    sim = Simulator(mem, config=FLAT)
    if ports is not None:
        sim.set_tracer(ports)
    sim.registers[:] = regs
    r, ops, t0 = sim.registers, sim.opcodes, regs[T]
    mem.regs = r
    pcs = set()
    for _ in range(limit):
        pc = r[PC]
        if pc == ret:
            mem.exit = list(r)
            return r[T] - t0, pcs
        pcs.add(pc)
        ops[mem.m[pc]]()
    sys.exit(f'callio: call never returned to ${ret:04X}')


REGS = [i for i in range(24) if i not in (SP, 13, R)]   # 13 unused; R is kept apart, in r / rx


def frame(sp):
    """The call's own stack frames: never inputs or outputs."""
    return {a & 0xFFFF for a in range(sp - 128, sp + 2)}


def runs(addrs):
    out, lo, prev = [], None, None
    for a in sorted(addrs):
        if lo is None:
            lo = prev = a
        elif a == prev + 1:
            prev = a
        else:
            out.append((lo, prev)); lo = prev = a
    if lo is not None:
        out.append((lo, prev))
    return out


def case_io(src, lm, blind):
    """The in/out fields of a case: ROM data reads and blind outputs as
    address runs only (D5, rule 7), everything else as [addr, hex] runs."""
    hide = lambda a: any(lo <= a <= hi for lo, hi in blind)
    io = {'in': hexruns({a: src[a] for a in lm.reads if a >= 0x4000}),
          'out': hexruns({a: lm.m[a] for a in lm.writes if not hide(a)})}
    rom = [a for a in lm.reads if a < 0x4000]
    hid = [a for a in lm.writes if hide(a)]
    if rom:
        io['rom'] = [[lo, hi] for lo, hi in runs(rom)]
    if hid:
        io['blind'] = [[lo, hi] for lo, hi in runs(hid)]
    return io


def addrs(rs):
    return {a for lo, hi in rs for a in range(lo, hi + 1)}


def table(title, touched, firstpc, extra=None, gap=None):
    """touched: addr -> calls; firstpc: addr -> PC.  Contiguous addresses
    that share a call count are one row; with gap, addresses within gap
    bytes of each other are one row whatever their counts (a table read at
    an index: the range of counts and the PCs that read it are shown)."""
    print(f'{title}: {len(touched)} bytes')
    rows, cur = [], None
    for a in sorted(touched):
        n = touched[a]
        if cur and (a <= cur[1] + gap if gap is not None else a == cur[1] + 1 and n == cur[2]):
            cur[1] = a
            cur[2], cur[3] = min(cur[2], n), max(cur[3], n)
            cur[4].setdefault(firstpc[a], None)
        else:
            cur = [a, a, n, n, {firstpc[a]: None}]; rows.append(cur)
    for lo, hi, n0, n1, pcs in rows:
        span = f'${lo:04X}' if lo == hi else f'${lo:04X}-${hi:04X}'
        calls = f'{n0}' if n0 == n1 else f'{n0}-{n1}'
        at = ' '.join(f'${pc:04X}' for pc in list(pcs)[:4]) + (' ...' if len(pcs) > 4 else '')
        more = f'  {extra(lo, hi)}' if extra else ''
        print(f'  {span:<13} {calls:>8} calls  first at {at}{more}')


def capture(args):
    t = parse_target(args)
    calls, frames, keys, per, out, append, blind = [], 1500, [], 2, None, False, []
    pokes, kemp = {}, 0
    while args:
        a = args[0]
        if a == '--call':
            calls.append((int(args[1], 0), int(args[2], 0))); del args[:3]
        elif a == '--frames':
            frames = int(args[1], 0); del args[:2]
        elif a == '--keys':
            keys = args[1].split('+'); del args[:2]
        elif a == '--per':
            per = int(args[1]); del args[:2]
        elif a == '--out':
            out = args[1]; del args[:2]
        elif a == '--append':
            append = True; del args[:1]
        elif a == '--blind':
            lo, hi = args[1].split('-'); blind.append([int(lo, 0), int(hi, 0)]); del args[:2]
        elif a == '--poke':
            for kv in args[1].split(','):
                pa, pv = kv.split('=')
                pokes[int(pa, 0)] = int(pv, 0)
            del args[:2]
        elif a == '--kempston':
            kemp = int(args[1], 0); del args[:2]
        else:
            sys.exit(f'callio: unknown argument {a}  (target: {TARGET_HELP})')
    if not calls or not out:
        sys.exit('callio: --capture needs --call SITE RET (one or more) and --out FILE')
    h = boot_target(t, 'callio')
    r, m = h.regs, h.memobj.m
    image = bytes(m)
    code_now = set()
    if append and os.path.exists(out):
        code_now = {a for lo, hi in json.load(open(out))['code'] for a in range(lo, hi + 1)}
    for pa, pv in pokes.items():
        if pa < 0x4000 or pa in code_now:
            sys.exit(f'callio: --poke ${pa:04X} is ROM or a byte the fixture fetched as code')
        m[pa] = pv
    for k in keys:
        press(h.ports, k)
    h.ports.kempston = kemp
    fx = {'calls': [[s, e] for s, e in calls], 'code': [], 'cases': []}
    if append and os.path.exists(out):
        fx = json.load(open(out))
    if append and fx.get('blind', []) != blind:
        sys.exit(f'callio: --blind must match the fixture {fx.get("blind", [])} to append')
    fx['blind'] = blind
    code = {a for lo, hi in fx['code'] for a in range(lo, hi + 1)}
    seen = {}
    for c in fx['cases']:
        seen[c['site'], c['sig']] = seen.get((c['site'], c['sig']), 0) + 1
    rets = dict(calls)
    n = new = 0
    end = r[T] + frames * h.frame_duration
    while r[T] < end:
        reason, _ = h.run_until(list(rets), limit=200_000)
        if reason != 'target':
            continue
        site, sp, regs_in, pre = r[PC], r[SP], list(r), bytes(m)
        lm = Logged(pre, frame(sp))
        pl = PortLog(live=h.ports)
        dt, pcs = run_alone(lm, regs_in, rets[site], ports=pl)
        h.run_until([rets[site]], limit=20_000_000)    # the real call, interrupts on
        n += 1
        drift = [a for a in lm.fetched | pcs if pre[a] != image[a]]
        if drift:
            sys.exit(f'callio: ${site:04X} fetched bytes that differ from the target image at '
                     + ' '.join(f'${a:04X}' for a in sorted(drift)[:6]))
        code |= lm.fetched | pcs
        sig = ''.join(f'{a:04x}' for a in sorted(pcs))
        if seen.get((site, sig), 0) >= per:
            continue
        seen[site, sig] = seen.get((site, sig), 0) + 1
        new += 1
        fx['cases'].append({'site': site, 'sp': sp, 'regs': [regs_in[i] for i in REGS],
                            **case_io(pre, lm, blind),
                            'exit': [lm.exit[i] for i in REGS], 'r': regs_in[R], 'rx': lm.exit[R],
                            **({'ports': pl.log} if pl.log else {}), 't': dt, 'sig': sig,
                            **({'poked': {f'{a:04x}': v for a, v in pokes.items()}} if pokes else {})})
    fx['code'] = [[lo, hi] for lo, hi in runs(code)]
    fx['regs'] = REGS
    fx['about'] = ('Purpose: frozen oracle for the routine called at ' + ', '.join(f'${s:04X}' for s, _ in calls)
                   + ' -- one case per distinct (site, PC set), at most a few each: SP and the registers '
                   '(SkoolKit indices in regs) at the CALL, the bytes read before written as [addr, hex] runs '
                   '(in; fetches and the call frame excepted), every byte written outside the frame (out), '
                   'the registers at the return (exit), R at the call and the return (r, rx), the port reads '
                   'in order as [port, value] (ports), the uncontended T (t); code lists the fetched '
                   'addresses, whose bytes come from the target, as do ROM data reads (rom, addresses '
                   'only, D5); outputs inside the blind ranges are addresses only (blind). Read by: python tools/callio.py --check, '
                   'and the JS gate of that routine.')
    with open(out, 'w') as f:
        json.dump(fx, f, separators=(',', ':'))
    print(f'callio: {source_label(t)}, {frames} frames: {n} calls, {new} new cases '
          f'({len(fx["cases"])} in {out}); code {len(code)} bytes in {len(fx["code"])} runs')


def check(args):
    t = parse_target(args)
    fixture = None
    while args:
        if args[0] == '--fixture':
            fixture = args[1]; del args[:2]
        else:
            sys.exit(f'callio: unknown argument {args[0]}')
    if not fixture:
        sys.exit('callio: --check needs --fixture FILE')
    h = boot_target(t, 'callio')                   # the code comes from the target, never the fixture
    src = h.memobj.m
    fx = json.load(open(fixture))
    rets = dict((s, e) for s, e in fx['calls'])
    bad = 0
    for i, c in enumerate(fx['cases']):
        mem = bytearray(0x10000)
        for lo, hi in fx['code']:
            mem[lo:hi + 1] = src[lo:hi + 1]
        ins = unruns(c['in'])
        for a, v in ins.items():
            mem[a] = v
        rom = addrs(c.get('rom', []))
        for a in rom:
            mem[a] = src[a]
        sp = c['sp']
        lm = Logged(bytes(mem), frame(sp))
        regs = list(h.regs)
        for k, v in zip(fx['regs'], c['regs']):
            regs[k] = v
        regs[PC], regs[SP], regs[T] = c['site'], sp, 0
        if 'r' in c:
            regs[R] = c['r']
        pl = PortLog(logged=c.get('ports', []))
        dt, _ = run_alone(lm, regs, rets[c['site']], ports=pl)
        portsok = not pl.bad and not pl.left() and ('rx' not in c or lm.exit[R] == c['rx'])
        hid = addrs(fx.get('blind', []))
        out = {a: lm.m[a] for a in lm.writes if a not in hid}
        seen = sorted(a for a in lm.writes if a in hid) == sorted(addrs(c.get('blind', [])))
        unread = sorted(a for a in lm.reads if a not in ins and a not in rom)
        ex = [lm.exit[k] for k in fx['regs']]
        if out != unruns(c['out']) or not seen or dt != c['t'] or unread or ex != c['exit'] or not portsok:
            bad += 1
            if bad <= 5:
                print(f'*** case {i} (${c["site"]:04X}): T replay {dt} fixture {c["t"]}; writes agree: '
                      f'{out == unruns(c["out"]) and seen}; exit registers agree: {ex == c["exit"]}; '
                      f'ports and R agree: {portsok}; '
                      f'unrecorded reads {[hex(a) for a in unread[:6]]}')
    ts = [c['t'] for c in fx['cases']]
    print(f'callio: {fixture}: {len(fx["cases"])} cases, {bad} disagree; T {min(ts)}-{max(ts)}')
    sys.exit(1 if bad else 0)


def derive(args):
    t = parse_target(args)
    fixture, base, sets, rset, psets = None, None, {}, None, {}
    while args:
        if args[0] == '--fixture':
            fixture = args[1]; del args[:2]
        elif args[0] == '--case':
            base = int(args[1]); del args[:2]
        elif args[0] == '--set':
            for kv in args[1].split(','):
                a, v = kv.split('=')
                sets[int(a, 0)] = int(v, 0)
            del args[:2]
        elif args[0] == '--r':
            rset = int(args[1], 0); del args[:2]
        elif args[0] == '--port':
            for kv in args[1].split(','):
                i, v = kv.split('=')
                psets[int(i, 0)] = int(v, 0)
            del args[:2]
        else:
            sys.exit(f'callio: unknown argument {args[0]}')
    if not fixture or base is None or not (sets or psets or rset is not None):
        sys.exit('callio: --derive needs --fixture FILE --case N --set ADDR=VAL[,ADDR=VAL...]')
    h = boot_target(t, 'callio')
    fx = json.load(open(fixture))
    c = fx['cases'][base]
    ins = unruns(c['in'])
    missing = [a for a in sets if a not in ins]     # never a ROM byte: those are not inputs to set
    if missing:
        sys.exit('callio: --set may only change bytes the case read: not '
                 + ' '.join(f'${a:04X}' for a in missing))
    mem = bytearray(h.memobj.m)                    # the target, for code the case never fetched
    for a, v in {**ins, **sets}.items():
        mem[a] = v
    sp = c['sp']
    lm = Logged(bytes(mem), frame(sp))
    regs = list(h.regs)
    for k, v in zip(fx['regs'], c['regs']):
        regs[k] = v
    regs[PC], regs[SP], regs[T] = c['site'], sp, 0
    if 'r' in c:
        regs[R] = c['r']
    if rset is not None:
        if 'r' not in c:
            sys.exit('callio: --r needs a fixture that records R (r, rx)')
        regs[R] = rset
    ports = [list(p) for p in c.get('ports', [])]
    if any(not 0 <= i < len(ports) for i in psets):
        sys.exit(f'callio: --port indexes the parent\'s {len(ports)} logged reads')
    for i, v in psets.items():                     # the value the machine answers; the port stays
        ports[i][1] = v
    pl = PortLog(logged=ports)
    dt, pcs = run_alone(lm, regs, dict((s, e) for s, e in fx['calls'])[c['site']], ports=pl)
    if pl.bad:                                     # stopping early is fine: the case keeps its own log
        sys.exit('callio: the derived case reads the ports differently from its parent; derive another way')
    sig = ''.join(f'{a:04x}' for a in sorted(pcs))
    old = {a for s in (x['sig'] for x in fx['cases']) for a in (int(s[i:i + 4], 16) for i in range(0, len(s), 4))}
    code = {a for lo, hi in fx['code'] for a in range(lo, hi + 1)} | lm.fetched | pcs
    fx['code'] = [[lo, hi] for lo, hi in runs(code)]
    fx['cases'].append({'site': c['site'], 'sp': sp, 'regs': c['regs'],
                        **case_io(mem, lm, fx.get('blind', [])),
                        'exit': [lm.exit[k] for k in fx['regs']],
                        **({'r': regs[R], 'rx': lm.exit[R]} if 'r' in c else {}),
                        **({'ports': pl.log} if pl.log else {}), 't': dt, 'sig': sig,
                        'derived': {'from': base, 'set': {f'{a:04x}': v for a, v in sets.items()},
                                    **({'r': rset} if rset is not None else {}),
                                    **({'port': {str(i): v for i, v in psets.items()}} if psets else {})}})
    with open(fixture, 'w') as f:
        json.dump(fx, f, separators=(',', ':'))
    print(f'callio: case {len(fx["cases"]) - 1} derived from case {base}: T {dt}; PCs no case reached before: '
          + (' '.join(f'${a:04X}' for a, _ in runs(pcs - old)) if pcs - old else 'none'))


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    if args[0] == '--capture':
        return capture(args[1:])
    if args[0] == '--check':
        return check(args[1:])
    if args[0] == '--derive':
        return derive(args[1:])
    t = parse_target(args)
    site = ret = None
    frames, keys, only, gap = 1500, [], None, None
    while args:
        a = args[0]
        if a == '--call':
            site, ret = int(args[1], 0), int(args[2], 0); del args[:3]
        elif a == '--frames':
            frames = int(args[1], 0); del args[:2]
        elif a == '--keys':
            keys = args[1].split('+'); del args[:2]
        elif a == '--gap':
            gap = int(args[1], 0); del args[:2]
        elif a == '--only':
            only = args[1]; del args[:2]
        else:
            sys.exit(f'callio: unknown argument {a}  (target: {TARGET_HELP})')
    if site is None:
        sys.exit('callio: need --call SITE RET')
    h = boot_target(t, 'callio')
    r, m = h.regs, h.memobj.m
    for k in keys:
        press(h.ports, k)
    ins, outs, firstin, firstout, vals, code = {}, {}, {}, {}, {}, set()
    ts, calls, fetches = [], 0, 0
    end = r[T] + frames * h.frame_duration
    while r[T] < end:
        reason, _ = h.run_until([site], limit=200_000)
        if reason != 'target':
            continue
        sp = r[SP]
        lm = Logged(bytes(m), {a & 0xFFFF for a in range(sp - 128, sp + 2)})
        dt, pcs = run_alone(lm, list(r), ret, ports=PortLog(live=h.ports))
        h.run_until([ret], limit=20_000_000)           # the real call, interrupts on
        calls += 1
        ts.append(dt)
        fetches += lm.fetches
        code |= pcs
        for a, pc in lm.reads.items():
            ins[a] = ins.get(a, 0) + 1
            firstin.setdefault(a, pc)
        for a, pc in lm.writes.items():
            outs[a] = outs.get(a, 0) + 1
            firstout.setdefault(a, pc)
            vals.setdefault(a, set()).add(lm.m[a])
    if not calls:
        sys.exit(f'callio: ${site:04X} never reached in {frames} frames')
    print(f'callio: ${site:04X} -> ${ret:04X}, {source_label(t)}, {frames} frames'
          + (f', keys {"+".join(keys)}' if keys else '') + f': {calls} calls, '
          f'uncontended T min {min(ts)} median {int(statistics.median(ts))} max {max(ts)}')
    print(f'self-check: {fetches} reads dropped as fetches; {len(ins)} input and {len(outs)} output bytes kept')
    if only in (None, 'code'):
        print(f'code: {len(code)} PCs executed in ' + ' '.join(
            f'${lo:04X}' if lo == hi else f'${lo:04X}-${hi:04X}' for lo, hi in runs(code)))
    if only in (None, 'in'):
        table('inputs (read before written)', ins, firstin,
              lambda lo, hi: 'also written' if any(a in outs for a in range(lo, hi + 1)) else '', gap)
    if only in (None, 'out'):
        table('outputs (written)', outs, firstout,
              lambda lo, hi: 'values ' + '/'.join(str(len(vals[a])) if a in vals else '-'
                                                  for a in range(lo, min(hi, lo + 7) + 1))
              + ('...' if hi > lo + 7 else ''), gap)


if __name__ == '__main__':
    main()
