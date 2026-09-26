#!/usr/bin/env python3
"""
manual.py -- read the kit's documents by ID, never end to end, and find the
tool for a job.

The manual (docs/PORTING-ZX-TO-JS.txt) and the traps (docs/TRAPS.md) are
together well over 100,000 tokens, and a compaction throws both away, along
with tools/README.md; a session reads the entries it needs, by ID, and asks
for the tool it needs by what it does (manual 0.7, 12.8).

Usage:
  python tools/manual.py C9 6.11 Q13        manual entries by ID
  python tools/manual.py T146 T63           traps by number, each with its map row
  python tools/manual.py --index [PREFIX]   manual IDs, lines, titles (--index T: traps)
  python tools/manual.py --whole N          a top-level manual section, subsections too
  python tools/manual.py --grep TERM        manual entries, traps and tools that mention TERM
  python tools/manual.py --map [WHAT]       the trap-to-check map: totals, or the rows
                                            for one mechanism or state (gate, READ, ...)
  python tools/manual.py --tools [TERM]     the tools in tools/README.md, or those whose
                                            name, purpose, usage or phase mention TERM

Manual IDs: catalogue entries (A1..G14, B2b), diagnostics (Q1..Q19), rungs
(R0..R9), phases (P9 or "PHASE 9") and numbered sections (0.8, 6.11, 12).
Trap IDs: T146 or #146.  Each document is found through $ZX_MANUAL, $ZX_TRAPS
or $ZX_TRAPMAP if set, else in docs/ under the repository root (the parent of
this script's directory), else in the working directory or any directory
above it, directly or under docs/.  The tools index is the tables in
tools/README.md, beside this script.
"""
import os
import re
import sys

MANUAL, TRAPS, TRAPMAP = 'PORTING-ZX-TO-JS.txt', 'TRAPS.md', 'TRAPS-MAP.md'
# The same pattern as the grep command in manual section 0.7.
INDEX = re.compile(r'^([A-G][0-9]+b? |Q[0-9]+ |R[0-9] |PHASE |[0-9]+\.[0-9]* )')
TOP = re.compile(r'^[0-9]+\. ')
TRAP = re.compile(r'^(\d+)\. \*\*')
MAPROW = re.compile(r'^\| (\d+) \| (.*) \| `([a-z]+)` \| ([A-Z]+) \|$')
TOOLROW = re.compile(r'^\| `([A-Za-z0-9_./-]+\.py)` \| (.*?) \| (.*?) \| (.*?) \|$')
STATES = ('KIT', 'BB', 'BUILD', 'READ')
GREP_MAX = 40


def find_doc(name, env, required=True):
    path = os.environ.get(env)
    if path and os.path.isfile(path):
        return path
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for cand in (os.path.join(root, 'docs', name), os.path.join(root, name)):
        if os.path.isfile(cand):
            return cand
    d = os.getcwd()
    while True:
        for cand in (os.path.join(d, 'docs', name), os.path.join(d, name)):
            if os.path.isfile(cand):
                return cand
        parent = os.path.dirname(d)
        if parent == d:
            if required:
                sys.exit('manual.py: cannot find %s (set %s to its path)' % (name, env))
            return None
        d = parent


def read_lines(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read().splitlines()


def trailing_noise(line):
    """Rulers, family banners, the end banner and blanks close an entry."""
    s = line.strip()
    return (not s or (len(s) >= 40 and set(s) <= set('=-'))
            or s.startswith('FAMILY ') or s == 'END OF MANUAL')


def load_manual():
    path = find_doc(MANUAL, 'ZX_MANUAL')
    lines = read_lines(path)
    end = next((i for i, l in enumerate(lines) if l.strip() == 'END OF MANUAL'), len(lines))
    heads = [i for i, l in enumerate(lines[:end]) if INDEX.match(l)]
    spans, order = {}, []
    for n, i in enumerate(heads):
        j = heads[n + 1] if n + 1 < len(heads) else end
        while j > i + 1 and trailing_noise(lines[j - 1]):
            j -= 1
        m = re.match(r'^PHASE ([0-9]+)', lines[i])
        key = 'P' + m.group(1) if m else lines[i].split()[0].rstrip('.')
        if key not in spans:
            spans[key] = (i, j)
            order.append(key)
    return path, lines, spans, order, end


def manual_title(line):
    m = re.match(r'^PHASE [0-9]+\s*(?:--)?\s*(.*)$', line)
    if m:
        return m.group(1).strip()
    parts = line.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else ''


def load_traps(required=True):
    path = find_doc(TRAPS, 'ZX_TRAPS', required)
    if not path:
        return None, [], {}
    lines = read_lines(path)
    starts = [(i, int(m.group(1))) for i, l in enumerate(lines) for m in [TRAP.match(l)] if m]
    spans = {}
    for k, (i, n) in enumerate(starts):
        j = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        for s in range(i + 1, j):                 # a section heading ends an entry
            if lines[s].startswith('## '):
                j = s
                break
        while j > i + 1 and not lines[j - 1].strip():
            j -= 1
        spans[n] = (i, j)
    return path, lines, spans


def trap_title(lines, span):
    text = ' '.join(l.strip() for l in lines[span[0]:span[1]])
    m = re.match(r'^\d+\. \*\*(.+?)\*\*', text)
    return m.group(1) if m else text[:80]


def load_map():
    path = find_doc(TRAPMAP, 'ZX_TRAPMAP', required=False)
    rows = {}
    if path:
        for l in read_lines(path):
            m = MAPROW.match(l)
            if m:
                rows[int(m.group(1))] = (m.group(2).replace('\\|', '|'), m.group(3), m.group(4))
    return rows


def normalise(arg):
    a = arg.strip().rstrip('.')
    m = re.match(r'(?i)^(?:t|#)([0-9]+)$', a)
    if m:
        return ('T', int(m.group(1)))
    m = re.match(r'(?i)^(?:phase|p)\s*([0-9]+)$', a)
    if m:
        return ('M', 'P' + m.group(1))
    m = re.match(r'(?i)^([a-g])([0-9]+)(b?)$', a)
    if m:
        return ('M', m.group(1).upper() + m.group(2) + m.group(3).lower())
    m = re.match(r'(?i)^([qr])([0-9]+)$', a)
    if m:
        return ('M', m.group(1).upper() + m.group(2))
    return ('M', a)


def rel(path):
    try:
        return os.path.relpath(path)
    except ValueError:                            # another drive on Windows
        return path


def cmd_index(prefix):
    if prefix.upper().startswith('T'):
        path, lines, spans = load_traps()
        want = prefix[1:]
        for n in sorted(spans):
            if str(n).startswith(want):
                print('%5d  T%-4d %s' % (spans[n][0] + 1, n, trap_title(lines, spans[n])[:64]))
        return 0
    path, lines, spans, order, end = load_manual()
    p = normalise(prefix)[1] if prefix else ''
    for key in order:
        if not p or key.startswith(p):
            i = spans[key][0]
            print('%5d  %-5s %s' % (i + 1, key, manual_title(lines[i])[:66]))
    return 0


def cmd_whole(n):
    path, lines, spans, order, end = load_manual()
    key = normalise(n)[1]
    if key not in spans or not TOP.match(lines[spans[key][0]]):
        sys.exit('manual.py: --whole takes a top-level section number, e.g. 6 or 12')
    i = spans[key][0]
    j = next((k for k in range(i + 1, end) if TOP.match(lines[k])), end)
    while j > i + 1 and trailing_noise(lines[j - 1]):
        j -= 1
    print('(%d lines)' % (j - i))
    print('== %s  (%s lines %d-%d) ==' % (key, rel(path), i + 1, j))
    print('\n'.join(lines[i:j]))
    return 0


def load_tools():
    """Rows of every tool table in tools/README.md: (name, purpose, usage,
    phase, section).  The README is the single source; nothing is copied."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'README.md')
    if not os.path.isfile(path):
        sys.exit('manual.py: cannot find %s' % path)
    rows, section = [], ''
    for l in read_lines(path):
        if l.startswith('## '):
            section = l[3:].strip()
        m = TOOLROW.match(l)
        if m:
            clean = [c.replace('`', '').strip() for c in m.groups()]
            rows.append(tuple(clean) + (section,))
    return rows


def cmd_tools(term):
    rows = load_tools()
    needle = term.lower()
    picked = [r for r in rows if not needle or needle in ' '.join(r[:4]).lower()]
    if not picked:
        print('no tool mentions %r; python tools/manual.py --tools lists them all' % term)
        return 0
    for name, purpose, usage, phase, section in picked:
        tag = '' if section.startswith('Tools by phase') else '  (%s)' % section
        if needle:
            print('%s  [phase %s]%s\n    %s\n    %s' % (name, phase, tag, purpose, usage))
        else:
            print('%-17s %s%s' % (name, purpose[:58], tag))
    print('\npython tools/NAME.py --help gives full usage.  Read it before extending a '
          'tool or writing a new one (TRAPS #65, #170).')
    return 0


def cmd_grep(term):
    needle, hits = term.lower(), []
    path, lines, spans, order, end = load_manual()
    for key in order:
        i, j = spans[key]
        c = sum(l.lower().count(needle) for l in lines[i:j])
        if c:
            hits.append((key, c, manual_title(lines[i])))
    tpath, tlines, tspans = load_traps(required=False)
    for n in sorted(tspans):
        i, j = tspans[n]
        c = sum(l.lower().count(needle) for l in tlines[i:j])
        if c:
            hits.append(('T%d' % n, c, trap_title(tlines, tspans[n])))
    tools = [(name, ' '.join((name, purpose, usage, phase)).lower().count(needle), purpose)
             for name, purpose, usage, phase, section in load_tools()]
    hits = [t for t in tools if t[1]] + hits      # tools first: never cut off
    if not hits:
        print('no manual entry, trap or tool mentions %r' % term)
        return 0
    for key, c, title in hits[:GREP_MAX]:
        print('%-5s %3dx  %s' % (key, c, title[:62]))
    if len(hits) > GREP_MAX:
        print('... and %d more' % (len(hits) - GREP_MAX))
    return 0


def cmd_map(what):
    rows = load_map()
    if not rows:
        sys.exit('manual.py: cannot find %s (set ZX_TRAPMAP to its path)' % TRAPMAP)
    if not what:
        by_state, by_mech = {}, {}
        for rule, mech, state in rows.values():
            by_state[state] = by_state.get(state, 0) + 1
            by_mech.setdefault(mech, [0, 0])
            by_mech[mech][0] += 1
            by_mech[mech][1] += state == 'BUILD'
        print('%d traps: %s' % (len(rows), ', '.join(
            '%s %d' % (s, by_state.get(s, 0)) for s in STATES)))
        for mech, (total, todo) in sorted(by_mech.items(), key=lambda kv: -kv[1][0]):
            print('  %-9s %3d traps, %3d still to build' % (mech, total, todo))
        return 0
    w = what.upper() if what.upper() in STATES else what.lower()
    picked = [(n, r) for n, r in sorted(rows.items()) if w in (r[1], r[2])]
    if not picked:
        sys.exit('manual.py: no map rows for %r (a mechanism such as gate, or %s)'
                 % (what, '/'.join(STATES)))
    for n, (rule, mech, state) in picked:
        print('T%-4d %-8s %-5s %s' % (n, mech, state, rule))
    return 0


def cmd_ids(args):
    ids, k = [], 0
    while k < len(args):                          # "PHASE 9" may arrive as two words
        if args[k].upper() == 'PHASE' and k + 1 < len(args):
            ids.append('P' + args[k + 1])
            k += 2
        else:
            ids.append(args[k])
            k += 1
    manual = traps = rows = None
    status = 0
    for raw in ids:
        kind, key = normalise(raw)
        if kind == 'T':
            if traps is None:
                traps, rows = load_traps(), load_map()
            path, lines, spans = traps
            if key not in spans:
                sys.stderr.write('manual.py: no trap %s; TRAPS.md has 1..%d\n'
                                 % (raw, max(spans) if spans else 0))
                status = 1
                continue
            i, j = spans[key]
            print('== T%d  (%s lines %d-%d) ==' % (key, rel(path), i + 1, j))
            if key in rows:
                rule, mech, state = rows[key]
                print('map: %s  [%s, %s]' % (rule, mech, state))
            print('\n'.join(lines[i:j]))
            continue
        if manual is None:
            manual = load_manual()
        path, lines, spans, order, end = manual
        if key in spans:
            i, j = spans[key]
            print('== %s  (%s lines %d-%d) ==' % (key, rel(path), i + 1, j))
            print('\n'.join(lines[i:j]))
        else:
            near = [x for x in order if x.startswith(key[:1])][:12]
            sys.stderr.write('manual.py: no entry %r; IDs starting %r: %s\n'
                             % (raw, key[:1], ' '.join(near) or 'none'))
            status = 1
    return status


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__.strip())
        return 0
    if argv[0] == '--index':
        return cmd_index(argv[1] if len(argv) > 1 else '')
    if argv[0] == '--whole':
        if len(argv) < 2:
            sys.exit('manual.py: --whole needs a section number')
        return cmd_whole(argv[1])
    if argv[0] == '--grep':
        if len(argv) < 2:
            sys.exit('manual.py: --grep needs a term')
        return cmd_grep(' '.join(argv[1:]))
    if argv[0] == '--map':
        return cmd_map(argv[1] if len(argv) > 1 else '')
    if argv[0] == '--tools':
        return cmd_tools(' '.join(argv[1:]))
    return cmd_ids(argv)


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        # Output piped into head or similar: stop quietly, no traceback.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
