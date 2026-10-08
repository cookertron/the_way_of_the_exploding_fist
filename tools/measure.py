#!/usr/bin/env python3
"""
measure.py -- the one measurement entry point every oracle calls (manual
6.11).  G11 lists six ways a measurement of a routine lies; each is a
default here, so the careless measurement is the one you cannot write:

  (a) ARM, THEN SNAPSHOT.  The sentinels are pushed and the registers set
      before the baseline is taken; the probe's own pushes are never the
      routine's writes (TRAPS #146).
  (b) POISON.  Every run is made twice.  The first logs every write; the
      second fills exactly the bytes the first wrote (where the routine
      actually writes, TRAPS #182 -- a computed target included) with a value
      the routine did not write there, and checks the diff against the
      poison equals the write log (TRAPS #102, #172).  A second run that
      takes another path or writes elsewhere is reported: the routine read
      a byte it writes.  hold= keeps bytes out of the poison (a terminator,
      TRAPS #189); poison=False says the measurement does without.
  (c) NAMED WINDOWS.  Writes are grouped by window from one shared table
      (WINDOWS, plus the per-run "stack" and "sentinels"), reported as
      contiguous runs (TRAPS #152).  exclude= takes window NAMES only and
      the report still counts what each exclusion dropped (TRAPS #147).
      lint() rejects raw address comparisons in an oracle script.
  (d) BRANCH COVERAGE.  Every conditional JR/JP/CALL/RET and DJNZ executed
      is recorded taken, fallen through, or both, over the whole sweep;
      one-way branches are flagged, and so is every conditional the static
      walk from the entry (walk.py) finds that no run executed.  Input
      flags are swept like any input: flags_in=("C",) runs each case with
      carry clear and set.
  (e) STOP_AT.  A run reaching one of these PCs ends there, observed, not
      run (a cutscene).  A stop no run reached is reported (TRAPS #144).
  (f) EVERY WRITE WITH ITS PC, always (TRAPS #153).  NOT SEEN: a write
      below $4000.  SkoolKit's simulator drops it before memory is touched
      (simulator.py: "if addr > 0x3FFF"), so the log cannot hold it; a
      computed target that lands in ROM (TRAPS #182) shows only as a write
      the extent is missing.

Interrupts are off by default (a routine called in isolation); a routine
spinning on an ISR counter passes interrupts=True.  fixture() stamps its
output (manual 12.3) with the branch record.  The machine state is saved
before the sweep and restored after every run and at the end (TRAPS #59).

    import measure
    h = probeutil.boot_target('s1') ...
    m = measure.measure(h, 0x9C6F, [{'regs': {'A': 3}}, {'poke': {0x9CA5: 1}}],
                        stop_at=(0x9CA0,))
    print(m.text())
    json.dump(m.fixture(), open('build/x.json', 'w'))

A sweep case is a dict: regs (harness.call()'s names, 'F' among them),
poke ({addr: value}, set before arming: an input), label (free text).

    python tools/measure.py --lint FILE ...   the window lint on oracle scripts
"""
import re
import sys

import harness as H
import walk as walkmod

# --- the shared window table (G11c) ---------------------------------------
# [lo, hi) by name.  A port adds its own named windows through windows=;
# names are unique and an exclusion that names nothing is refused.
WINDOWS = {
    'rom':     (0x0000, 0x4000),
    'display': (0x4000, 0x5800),
    'attrs':   (0x5800, 0x5B00),
    'ram':     (0x5B00, 0x10000),
}
STACK_DEPTH = 128          # the call's own frames: SP at entry - 128 .. SP

FLAG_BITS = {'S': 0x80, 'Z': 0x40, 'H': 0x10, 'P': 0x04, 'V': 0x04, 'N': 0x02, 'C': 0x01}

# conditional opcodes -> instruction length (walk.py decodes the same set)
COND = {0x10: 2, 0x20: 2, 0x28: 2, 0x30: 2, 0x38: 2}
COND.update({op: 3 for op in (0xC2, 0xCA, 0xD2, 0xDA, 0xE2, 0xEA, 0xF2, 0xFA)})   # JP cc
COND.update({op: 3 for op in (0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC)})   # CALL cc
COND.update({op: 1 for op in (0xC0, 0xC8, 0xD0, 0xD8, 0xE0, 0xE8, 0xF0, 0xF8)})   # RET cc


def runs(addrs):
    """Sorted addresses -> [(lo, hi_inclusive)] contiguous runs."""
    out = []
    for a in sorted(addrs):
        if out and a == out[-1][1] + 1:
            out[-1][1] = a
        else:
            out.append([a, a])
    return [tuple(r) for r in out]


def fmt_runs(rs):
    return ' '.join('$%04X' % lo if lo == hi else '$%04X-$%04X' % (lo, hi) for lo, hi in rs)


class Run:
    """One execution: a sweep case under one flag setting, poisoned or not."""

    def __init__(self, case, flags):
        self.case, self.flags = case, flags
        self.exit = None          # ('ret', sentinel index) | ('stop', pc) | ('limit', None)
        self.t = 0
        self.steps = 0
        self.writes = []          # (pc, addr, value), every write in order
        self.changed = set()      # addresses whose byte differs from the armed baseline
        self.sp = None            # SP after arming
        self.branches = {}        # pc -> set of 'taken' / 'fell'
        self.pcs = set()
        self.windows = {}         # name -> [lo, hi)
        self.poison = None        # dict for the poisoned twin, see _poisoned

    def written(self):
        return {a for _, a, _ in self.writes}

    def window_of(self, a):
        for name in ('sentinels', 'stack'):
            lo, hi = self.windows[name]
            if lo <= a < hi:
                return name
        for name, (lo, hi) in self.windows.items():         # a port's windows come first
            if name not in ('sentinels', 'stack') and lo <= a < hi:
                return name
        return 'other'

    def label(self):
        lab = self.case.get('label') or ', '.join(
            '%s=%s' % (k, (hex(v) if isinstance(v, int) else v)) for k, v in
            list((self.case.get('regs') or {}).items()) +
            [('$%04X' % a, v) for a, v in (self.case.get('poke') or {}).items()])
        if self.flags:
            lab += (' ' if lab else '') + ' '.join('%s=%d' % kv for kv in self.flags.items())
        return lab or '(base)'


class Measurement:
    def __init__(self, routine, args):
        self.routine = routine
        self.args = args
        self.runs = []
        self.static = set()       # conditional PCs the walk from the entry found

    # -- the branch record (manual 12.3 "branches") -------------------------
    def branches(self):
        seen = {}
        for r in self.runs:
            for pc, outs in r.branches.items():
                seen.setdefault(pc, set()).update(outs)
        rec = {}
        for pc in sorted(set(seen) | self.static):
            o = seen.get(pc, set())
            rec[pc] = ('both' if len(o) == 2 else 'taken only' if 'taken' in o
                       else 'never taken' if 'fell' in o else 'never executed')
        return rec

    def one_way(self):
        return [pc for pc, v in self.branches().items() if v != 'both']

    def stops_unreached(self):
        hit = {r.exit[1] for r in self.runs if r.exit and r.exit[0] == 'stop'}
        return [s for s in self.args['stop_at'] if s not in hit]

    def problems(self):
        """Everything a reader must not miss, one line each."""
        out = []
        for i, r in enumerate(self.runs):
            if r.exit[0] == 'limit':
                out.append('run %d (%s): no exit within %d steps' % (i, r.label(), self.args['limit']))
            p = r.poison
            if p and p['diverged']:
                out.append('run %d (%s): the poisoned twin %s -- the routine reads bytes it writes'
                           % (i, r.label(), p['diverged']))
            if p and p['unlogged']:
                out.append('run %d (%s): changed but not in the write log: %s'
                           % (i, r.label(), fmt_runs(runs(p['unlogged']))))
        for s in self.stops_unreached():
            out.append('stop_at $%04X: no run reached it (a sweep that found nothing, TRAPS #144)' % s)
        for pc, v in self.branches().items():
            if v != 'both':
                out.append('branch $%04X: %s' % (pc, v))
        return out

    def text(self):
        a = self.args
        lines = ['measure $%04X: %d runs (%d cases x %d flag settings), poison %s, interrupts %s'
                 % (self.routine, len(self.runs), a['ncases'], a['nflags'],
                    'on' if a['poison'] else 'OFF', 'on' if a['interrupts'] else 'off')]
        for i, r in enumerate(self.runs):
            ex = ('ret %d' % r.exit[1] if r.exit[0] == 'ret' else
                  'stop $%04X' % r.exit[1] if r.exit[0] == 'stop' else 'LIMIT')
            lines.append('  run %d  %s: %s, %d T, %d writes' % (i, r.label(), ex, r.t, len(r.writes)))
            groups = {}
            for _, ad, _ in r.writes:
                groups.setdefault(r.window_of(ad), set()).add(ad)
            for name in sorted(groups):
                n = sum(1 for _, ad, _ in r.writes if r.window_of(ad) == name)
                if name in a['exclude']:
                    lines.append('      %-9s excluded: %d writes to %d bytes' % (name, n, len(groups[name])))
                else:
                    lines.append('      %-9s %d writes: %s' % (name, n, fmt_runs(runs(groups[name]))))
        br = self.branches()
        lines.append('  branches: %d conditionals, %d both ways' % (len(br), sum(v == 'both' for v in br.values())))
        for msg in self.problems():
            lines.append('  !! ' + msg)
        return '\n'.join(lines)

    def fixture(self, argv=None, by='capture'):
        """The frozen output, stamped (manual 12.3) with the branch record."""
        import stamp
        fx = {
            'about': 'Purpose: measure() of $%04X (manual 6.11) -- per run the case, exit, T and '
                     'every write as [pc, addr, value]. Read by: whatever gate cites it.' % self.routine,
            'routine': self.routine,
            'args': {k: v for k, v in self.args.items() if k not in ('ncases', 'nflags')},
            'runs': [{'case': {k: ({'%04x' % a: v for a, v in c.items()} if k == 'poke' else c)
                               for k, c in r.case.items()},
                      'flags': r.flags, 'exit': list(r.exit), 't': r.t,
                      'writes': [list(w) for w in r.writes],
                      'poison': ({'value': r.poison['value'], 'diverged': r.poison['diverged']}
                                 if r.poison else None)}
                     for r in self.runs],
        }
        stamp.step(fx, by, argv)
        fx['_stamp']['branches'] = {'$%04X' % pc: v for pc, v in self.branches().items()}
        return fx


def _flag_settings(flags_in):
    out = [{}]
    for f in flags_in:
        if f not in FLAG_BITS:
            raise ValueError('flags_in: %r is not a flag (S Z H P V N C)' % f)
        out = [dict(d, **{f: b}) for d in out for b in (0, 1)]
    return out


def _execute(h, routine, run, stops, limit, interrupts, poison_fill=None):
    """Arm, snapshot, run.  Fills run in place.  poison_fill: {addr: value}
    written after arming and before the snapshot."""
    sim = h.sim
    regs = sim.registers
    mem = sim.memory
    opcodes = sim.opcodes
    m = h.memobj
    case = run.case
    for a, v in (case.get('poke') or {}).items():
        m.m[a] = v                         # an input, set before arming
    seed = dict(case.get('regs') or {})
    run.sp = _arm(h, routine, seed)
    for f, b in run.flags.items():
        regs[H.F] = (regs[H.F] | FLAG_BITS[f]) if b else (regs[H.F] & ~FLAG_BITS[f])
    sp = run.sp
    run.windows = dict(WINDOWS_ACTIVE)
    run.windows['sentinels'] = (sp, sp + 2 * len(h.SENTINELS))
    run.windows['stack'] = (sp - STACK_DEPTH, sp)
    if poison_fill:
        for a, v in poison_fill.items():
            m.m[a] = v
    base = bytes(m.m)                      # AFTER arming (G11a)
    sentinels = set(h.SENTINELS)
    fd, ia = h.frame_duration, h.int_active
    tcp = h.tape_call_pc if h.deck is not None else None
    t0 = regs[H.T]
    m.watch(0, 0x10000)
    n = 0
    try:
        while True:
            pc = regs[H.PC]
            if pc in sentinels:
                run.exit = ('ret', h.SENTINELS.index(pc))
                break
            if pc in stops:
                run.exit = ('stop', pc)
                break
            if n >= limit:
                run.exit = ('limit', None)
                break
            n += 1
            if pc == tcp:
                h._tape()
                continue
            op = mem[pc]
            if interrupts and op == 0x76 and regs[H.IFF]:
                h._fast_halt()
                continue
            run.pcs.add(pc)
            ln = COND.get(op)
            if ln:
                b = regs[H.B]
                opcodes[op]()
                taken = regs[H.PC] != (pc + ln) & 0xFFFF
                outs = run.branches.setdefault(pc, set())
                outs.add('taken' if taken else 'fell')
                if op == 0x10 and not taken and b != 1:
                    outs.add('taken')          # a DJNZ $ loop run in one step (fast_djnz)
            else:
                opcodes[op]()
            if interrupts and regs[H.IFF] and regs[H.T] % fd < ia:
                sim.accept_interrupt(regs, mem, pc)
    finally:
        m.unwatch()
    run.writes = list(m.log)
    m.log = []
    run.t = regs[H.T] - t0
    run.steps = n
    now = m.m
    run.changed = {a for a in range(0x10000) if now[a] != base[a]}


def _arm(h, addr, regs):
    """harness.call()'s arming half: the sentinels pushed, the registers
    seeded, PC set.  Returns SP after the pushes."""
    r = h.sim.registers
    sp = r[H.SP]
    for s in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = s & 0xFF
        h.memobj.m[(sp + 1) & 0xFFFF] = s >> 8
    r[H.SP] = sp
    for k, v in regs.items():
        if k in ('HL', 'DE', 'BC', 'IX', 'IY'):
            hi, lo = {'HL': (H.H, H.L), 'DE': (H.D, H.E), 'BC': (H.B, H.C),
                      'IX': (H.IXh, H.IXl), 'IY': (H.IYh, H.IYl)}[k]
            r[hi], r[lo] = v >> 8, v & 0xFF
        else:
            r[H.U.REGISTERS[k]] = v
    r[H.PC] = addr
    return sp


WINDOWS_ACTIVE = dict(WINDOWS)


def measure(h, routine, sweep=({},), poison=True, exclude=(), stop_at=(),
            interrupts=False, flags_in=('C',), windows=None, hold=(),
            limit=2_000_000, static=True, poison_value=0x5A):
    """Measure `routine` over `sweep` on harness h (left as found).
    Returns a Measurement; .text() is the report, .problems() what must be
    read, .fixture() the stamped output."""
    global WINDOWS_ACTIVE
    table = {}
    for name, rng in (windows or {}).items():
        if name in WINDOWS or name in ('stack', 'sentinels', 'other'):
            raise ValueError('window %r is already named' % name)
        lo, hi = rng
        for other, (olo, ohi) in table.items():
            if lo < ohi and olo < hi:
                raise ValueError('windows %r and %r overlap' % (name, other))
        table[name] = (lo, hi)
    table.update(WINDOWS)
    names = set(table) | {'stack', 'sentinels', 'other'}
    for e in exclude:
        if not isinstance(e, str) or e not in names:
            raise ValueError('exclude takes window names only (G11c): %r is not one of %s'
                             % (e, ', '.join(sorted(names))))
    WINDOWS_ACTIVE = table
    sweep = list(sweep)
    settings = _flag_settings(flags_in)
    stops = set(stop_at)
    hold = set(hold)
    M = Measurement(routine, {
        'poison': bool(poison), 'exclude': list(exclude), 'stop_at': list(stop_at),
        'interrupts': bool(interrupts), 'flags_in': list(flags_in), 'limit': limit,
        'hold': sorted(hold), 'windows': {k: list(v) for k, v in table.items()},
        'ncases': len(sweep), 'nflags': len(settings)})
    saved = h.save_state()
    try:
        for case in sweep:
            for fl in settings:
                h.load_state(saved)
                r = Run(case, fl)
                _execute(h, routine, r, stops, limit, interrupts)
                if poison:
                    _poisoned(h, routine, r, saved, stops, limit, interrupts, hold, poison_value)
                M.runs.append(r)
        if static:
            seen = walkmod.walk(h.sim.memory, [routine])[0]
            M.static = {pc for pc in seen if pc >= 0x4000 and h.sim.memory[pc] in COND}
    finally:
        h.load_state(saved)
        WINDOWS_ACTIVE = dict(WINDOWS)
    return M


def _poisoned(h, routine, r, saved, stops, limit, interrupts, hold, value):
    """The twin run over a poisoned extent (G11b): every byte r wrote outside
    its own stack and sentinels and ROM, held bytes kept back."""
    target = {a for a in r.written() if a >= 0x4000 and a not in hold
              and r.window_of(a) not in ('stack', 'sentinels')}
    wrote = {}
    for _, a, v in r.writes:
        wrote.setdefault(a, set()).add(v)
    fill = {}
    for a in target:
        v = value
        while v in wrote[a]:
            v = (v + 0x33) & 0xFF
        fill[a] = v
    h.load_state(saved)
    t = Run(r.case, r.flags)
    _execute(h, routine, t, stops, limit, interrupts, poison_fill=fill)
    diverged = None
    if t.exit != r.exit or t.pcs != r.pcs or t.branches != r.branches:
        diverged = 'took another path'
    elif t.written() != r.written():
        diverged = 'wrote other bytes'
    elif t.writes != r.writes:
        diverged = 'wrote other values'
    unlogged = {a for a in t.changed if a not in t.written()
                and t.window_of(a) not in ('stack', 'sentinels')} - set(fill)
    # a poisoned byte must come back changed exactly where it was written
    unlogged |= {a for a in fill if a not in t.changed and not diverged}
    r.poison = {'value': value, 'fill': len(fill), 'diverged': diverged, 'unlogged': unlogged}
    h.load_state(saved)


# --- the lint (G11c) ---------------------------------------------------------
_RAW = re.compile(r'\b(?:ad|addr|address|a)\s*(?:<|>|<=|>=)\s*(?:0x[0-9A-Fa-f]{3,4}|\d{4,5})\b'
                  r'|(?:0x[0-9A-Fa-f]{3,4}|\d{4,5})\s*(?:<|>|<=|>=)\s*(?:ad|addr|address|a)\b')


def lint(path):
    """Raw address comparisons in an oracle script: [(line_no, text)]."""
    out = []
    with open(path, encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            code = line.split('#', 1)[0]
            if _RAW.search(code):
                out.append((i, line.rstrip()))
    return out


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__.strip())
        return 0
    if argv[0] == '--lint':
        bad = 0
        for p in argv[1:]:
            for n, text in lint(p):
                print('%s:%d: raw address comparison (G11c): name a window in measure.WINDOWS: %s'
                      % (p, n, text.strip()))
                bad += 1
        return 1 if bad else 0
    print('measure.py: a library (import measure); --lint FILE ... or --help', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
