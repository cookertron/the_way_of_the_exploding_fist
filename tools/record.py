#!/usr/bin/env python3
"""
record.py -- write the project's records, each to its one home (manual 12.11).

Every kind of record has exactly one home, and this is how they are written,
so nothing is filed somewhere it will not be found again:

  NEXT.md                  where things stand: the unit, its step, the queue
  ledger/<ADDR>.toml       current truth about one routine
  ledger/topics/<N>.toml   current truth about a system spanning routines
  docs/DECISIONS.md        project-level decisions, numbered D1, D2, ...
  the commit message       what happened -- draft it with "record.py draft"

Fields arrive as "key: value" lines on stdin, through a QUOTED heredoc, so the
shell never touches a "$" or an apostrophe (TRAPS #149, #168):

  python tools/record.py new B34C <<'EOF'
  name: MovePlayerToEndOfPlatform
  EOF

  python tools/record.py fact B34C <<'EOF'
  kind: insn
  at: $B351
  says: RET Z after AND 7 -- no check at all on cell-aligned x
  by: python tools/adis.py 0xB351 3
  EOF

Commands:
  new ADDR | new NAME --topic    create a ledger file (name:; a topic also routines:)
  fact ADDR       kind: says: by: [at:]  -- negative kinds (never, absent,
                  unread, unused, unreachable) also need window: and n:
  refute ADDR     says: by:
  open ADDR       ask: tried: settle:
  close ADDR N    answer open question N; optional kind: says: by: become a fact
  link ADDR       oracle: fixture: port: manual: entry:  (lists space-separated;
                  every link is checked before it is written)
  next            unit: step: [then:] [blocked:] [notes:]  -- overwrites NEXT.md
  decide          title: text:  -- appends the next D-number to docs/DECISIONS.md
  draft           print a commit message draft for the unit being committed

Write addresses without the "$" on the command line (B34C, not $B34C: the
shell eats it); inside the heredoc, write them however reads best.  Every
value is one line: detail that needs more belongs in the commit message.
python tools/status.py --check validates everything this tool writes, and
anything edited by hand.
"""
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEDGER = os.path.join(ROOT, 'ledger')
TOPICS = os.path.join(LEDGER, 'topics')
NEXT = os.path.join(ROOT, 'NEXT.md')
DECISIONS = os.path.join(ROOT, 'docs', 'DECISIONS.md')

# The budgets (manual 12.11).  Tune them here; status.py reads them from here.
BUDGET = {
    'next_lines': 20,          # NEXT.md
    'ledger_lines': 80,        # one ledger file
    'decision_lines': 12,      # one DECISIONS.md entry
    'trap_lines': 20,          # one new TRAPS.md entry (below the budget marker)
    'commit_body_lines': 15,   # the body of the unit's commit message
    'claude_md_lines': 200,    # CLAUDE.md, re-read after every compaction
    'value_chars': 240,        # any one field
}
NEGATIVE = {'never', 'absent', 'unread', 'unused', 'unreachable'}
TOP_ORDER = ('name', 'entries', 'routines', 'oracle', 'fixtures', 'port', 'manual')
LIST_KEYS = {'entries', 'routines', 'fixtures', 'manual'}
TABLES = ('fact', 'refuted', 'open')


class RecordError(Exception):
    pass


# ---------------------------------------------------------------------------
# addresses and paths
# ---------------------------------------------------------------------------
def norm_addr(text):
    """'B34C', '$b34c', '0xB34C' -> '$B34C'; None if it is not an address."""
    m = re.fullmatch(r'(?:\$|0x|0X|&)?([0-9A-Fa-f]{1,4})', text.strip())
    return '$%04X' % int(m.group(1), 16) if m else None


def ledger_path(ident, topic=False):
    if topic:
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', ident):
            raise RecordError('a topic name is lower-case letters, digits and dashes: %r' % ident)
        return os.path.join(TOPICS, ident + '.toml')
    addr = norm_addr(ident)
    if not addr:
        raise RecordError('not an address: %r (write B34C, $B34C or 0xB34C)' % ident)
    return os.path.join(LEDGER, addr[1:] + '.toml')


def find_ledger(ident):
    """An existing ledger file for an address or a topic name."""
    addr = norm_addr(ident)
    if addr:
        p = ledger_path(addr)
        if os.path.isfile(p):
            return p
    if re.fullmatch(r'[a-z0-9][a-z0-9-]*', ident):
        p = ledger_path(ident, topic=True)
        if os.path.isfile(p):
            return p
    raise RecordError('no ledger entry for %r; create it with: python tools/record.py new %s'
                      % (ident, ident.lstrip('$')))


# ---------------------------------------------------------------------------
# the ledger's TOML subset: one-line strings and integers, arrays of strings,
# [[fact]] / [[refuted]] / [[open]] tables, comments.  Parsed the same way on
# every Python 3, so a file that passes here passes everywhere.
# ---------------------------------------------------------------------------
def _scan_value(s, i):
    """Parse one value starting at s[i]; return (value, next index)."""
    while i < len(s) and s[i] in ' \t':
        i += 1
    if i >= len(s):
        raise RecordError('a value is missing')
    c = s[i]
    if c == '"':
        out, i = [], i + 1
        while i < len(s):
            ch = s[i]
            if ch == '\\':
                nxt = s[i + 1:i + 2]
                out.append({'n': '\n', 't': '\t', '"': '"', '\\': '\\'}.get(nxt, nxt))
                i += 2
                continue
            if ch == '"':
                return ''.join(out), i + 1
            out.append(ch)
            i += 1
        raise RecordError('a string is not closed')
    if c == "'":
        j = s.find("'", i + 1)
        if j < 0:
            raise RecordError('a string is not closed')
        return s[i + 1:j], j + 1
    if c == '[':
        items, i = [], i + 1
        while True:
            while i < len(s) and s[i] in ' \t\n,':
                i += 1
            if i < len(s) and s[i] == '#':
                i = s.find('\n', i)
                i = len(s) if i < 0 else i
                continue
            if i >= len(s):
                raise RecordError('an array is not closed')
            if s[i] == ']':
                return items, i + 1
            v, i = _scan_value(s, i)
            if not isinstance(v, str):
                raise RecordError('arrays hold strings only')
            items.append(v)
    m = re.match(r'-?\d+|true|false', s[i:])
    if m:
        t = m.group(0)
        return (True if t == 'true' else False if t == 'false' else int(t)), i + len(t)
    raise RecordError('unrecognised value: %r' % s[i:i + 30].split('\n')[0])


def parse(text):
    data, current = {}, None
    s, i, line = text.replace('\r\n', '\n'), 0, 1
    while i < len(s):
        j = s.find('\n', i)
        j = len(s) if j < 0 else j
        raw = s[i:j].strip()
        try:
            if not raw or raw.startswith('#'):
                i = j + 1
            elif raw.startswith('[['):
                m = re.fullmatch(r'\[\[\s*([a-z]+)\s*\]\]\s*(#.*)?', raw)
                if not m or m.group(1) not in TABLES:
                    raise RecordError('tables are [[fact]], [[refuted]] or [[open]]')
                current = {}
                data.setdefault(m.group(1), []).append(current)
                i = j + 1
            else:
                m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*=', s[i:])
                if not m:
                    raise RecordError('expected key = value')
                value, k = _scan_value(s, i + m.end())
                rest = s[k:s.find('\n', k) if s.find('\n', k) >= 0 else len(s)].strip()
                if rest and not rest.startswith('#'):
                    raise RecordError('unexpected text after a value: %r' % rest[:30])
                target = current if current is not None else data
                if m.group(1) in target:
                    raise RecordError('%s is set twice' % m.group(1))
                target[m.group(1)] = value
                line += s[i:k].count('\n')
                j = s.find('\n', k)
                j = len(s) if j < 0 else j
                i = j + 1
                line += 1
                continue
        except RecordError as e:
            raise RecordError('line %d: %s' % (line, e))
        line += 1
    return data


def _q(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return '[' + ', '.join(_q(x) for x in v) + ']'
    return '"' + str(v).replace('\\', '\\\\').replace('"', '\\"') + '"'


def dump(data, header):
    out = [header, '']
    for k in TOP_ORDER:
        if k in data and data[k] not in (None, [], ''):
            out.append('%-8s = %s' % (k, _q(data[k])))
    for k in sorted(data):
        if k not in TOP_ORDER and k not in TABLES:
            out.append('%-8s = %s' % (k, _q(data[k])))
    for t in TABLES:
        for row in data.get(t, []):
            out += ['', '[[%s]]' % t]
            out += ['%-6s = %s' % (k, _q(v)) for k, v in row.items()]
    return '\n'.join(out) + '\n'


def header_for(path, data):
    if os.path.dirname(path) == TOPICS:
        return ('# ledger/topics/%s -- current truth about "%s", a system spanning\n'
                '# routines (manual 12.11).  Written with tools/record.py; history is in git.'
                % (os.path.basename(path), data.get('name', '?')))
    return ('# ledger/%s -- current truth about %s (manual 12.2, 12.11).\n'
            '# Written with tools/record.py; history is in git.'
            % (os.path.basename(path), data.get('name', '?')))


def load(path):
    with open(path, encoding='utf-8') as f:
        return parse(f.read())


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = dump(data, header_for(path, data))
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    n = text.count('\n')
    if n > BUDGET['ledger_lines']:
        print('note: %s is %d lines (budget %d): roll it up at the end of the unit (manual 12.11)'
              % (os.path.relpath(path, ROOT), n, BUDGET['ledger_lines']))


# ---------------------------------------------------------------------------
# what a link may point at (shared with status.py)
# ---------------------------------------------------------------------------
def port_assets():
    try:
        with open(os.path.join(ROOT, 'port.json'), encoding='utf-8') as f:
            return {a.get('key'): a for a in json.load(f).get('assets', []) if a.get('key')}
    except (OSError, ValueError):
        return {}


def source_text(folder, exts):
    parts = []
    d = os.path.join(ROOT, folder)
    for dirpath, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in ('node_modules', '__pycache__')]
        for fn in files:
            if fn.endswith(exts):
                try:
                    with open(os.path.join(dirpath, fn), encoding='utf-8', errors='replace') as f:
                        parts.append(f.read())
                except OSError:
                    pass
    return '\n'.join(parts)


def port_defined(name, web_text):
    pat = r'(\bfunction\s+%s\s*\()|(\b%s\s*[:=]\s*(async\s+)?(function\b|\())|(^\s*(async\s+)?%s\s*\([^)]*\)\s*\{)'
    n = re.escape(name)
    return re.search(pat % (n, n, n), web_text, re.M) is not None


def known_ids():
    """Manual IDs and trap numbers, via manual.py's own loaders."""
    sys.path.insert(0, HERE)
    import manual  # noqa: E402
    ids = set()
    try:
        ids |= set(manual.load_manual()[2])
    except SystemExit:
        pass
    try:
        ids |= {'T%d' % n for n in manual.load_traps(required=False)[2]}
    except SystemExit:
        pass
    return ids, manual


def canonical_id(i):
    """'c9' -> 'C9', '#146' or 't146' -> 'T146', 'phase 9' -> 'P9'."""
    sys.path.insert(0, HERE)
    import manual  # noqa: E402
    kind, key = manual.normalise(i)
    return 'T%d' % key if kind == 'T' else key


def link_problems(data, assets=None, web_text=None, ids=None):
    """Broken links in one ledger entry, as a list of strings."""
    assets = port_assets() if assets is None else assets
    web_text = source_text('web', ('.js', '.html')) if web_text is None else web_text
    probs = []
    oracle = data.get('oracle')
    if oracle and not os.path.isfile(os.path.join(ROOT, oracle)):
        probs.append('oracle %s does not exist' % oracle)
    for key in data.get('fixtures', []):
        if key not in assets:
            probs.append('fixture %r is not registered in port.json assets' % key)
    port = data.get('port')
    if port and not port_defined(port, web_text):
        probs.append('port function %r is not defined in web/' % port)
    if data.get('manual'):
        if ids is None:
            ids = known_ids()[0]
        for i in data['manual']:
            if canonical_id(i) not in ids:
                probs.append('manual/trap ID %r is unknown' % i)
    return probs


def entry_problems(data, topic):
    """Structural problems in one ledger entry (not links)."""
    probs = []
    if not data.get('name'):
        probs.append('no name')
    key = 'routines' if topic else 'entries'
    vals = data.get(key)
    if not isinstance(vals, list) or not vals:
        probs.append('no %s list' % key)
    else:
        bad = [v for v in vals if norm_addr(v) != v]
        if bad:
            probs.append('%s must be written like "$B34C": %s' % (key, ' '.join(bad)))
    for i, f in enumerate(data.get('fact', []), 1):
        for need in ('kind', 'says', 'by'):
            if not f.get(need):
                probs.append('fact %d has no %s' % (i, need))
        if f.get('kind') in NEGATIVE and (not f.get('window') or not isinstance(f.get('n'), int)):
            probs.append('fact %d is a negative claim (%s): it needs window and n (TRAPS #48)'
                         % (i, f.get('kind')))
    for i, r in enumerate(data.get('refuted', []), 1):
        for need in ('says', 'by'):
            if not r.get(need):
                probs.append('refuted claim %d has no %s' % (i, need))
    for i, o in enumerate(data.get('open', []), 1):
        for need in ('ask', 'tried', 'settle'):
            if not o.get(need):
                probs.append('open question %d has no %s' % (i, need))
    return probs


# ---------------------------------------------------------------------------
# fields on stdin
# ---------------------------------------------------------------------------
def read_fields(allowed, required=()):
    if sys.stdin.isatty():
        raise RecordError('fields go on stdin as "key: value" lines, through a quoted heredoc '
                          "(<<'EOF'); see python tools/record.py --help")
    fields = {}
    for n, raw in enumerate(sys.stdin.read().splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        m = re.match(r'\s*([a-z_]+)\s*:\s?(.*)$', raw)
        if not m:
            raise RecordError('stdin line %d is not "key: value": %r' % (n, raw[:60]))
        k, v = m.group(1), m.group(2).strip()
        if k not in allowed:
            raise RecordError('unknown field %r here; allowed: %s' % (k, ', '.join(allowed)))
        if k in fields:
            raise RecordError('field %r given twice: every value is one line' % k)
        if len(v) > BUDGET['value_chars']:
            raise RecordError('%s is %d characters (budget %d): say less, and put detail in the '
                              'commit message' % (k, len(v), BUDGET['value_chars']))
        fields[k] = v
    missing = [k for k in required if not fields.get(k)]
    if missing:
        raise RecordError('missing field(s): %s' % ', '.join(missing))
    return fields


def fact_row(fields):
    row = {'kind': fields['kind']}
    if not re.fullmatch(r'[a-z_]+', row['kind']):
        raise RecordError('kind is one lower-case word, e.g. insn, writes, never: %r' % row['kind'])
    if fields.get('at'):
        at = norm_addr(fields['at'])
        if not at:
            raise RecordError('at: is an address: %r' % fields['at'])
        row['at'] = at
    row['says'], row['by'] = fields['says'], fields['by']
    if row['kind'] in NEGATIVE:
        if not fields.get('window') or not fields.get('n'):
            raise RecordError('a negative claim (%s) needs window: (what was watched) and n: '
                              '(how many), or it cannot be checked (TRAPS #32, #48)' % row['kind'])
    if fields.get('window'):
        row['window'] = fields['window']
    if fields.get('n'):
        try:
            row['n'] = int(fields['n'].replace(',', ''))
        except ValueError:
            raise RecordError('n: is a whole number: %r' % fields['n'])
    return row


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_new(args):
    if not args:
        raise RecordError('new needs an address, or a topic name with --topic')
    topic = '--topic' in args
    ident = [a for a in args if a != '--topic'][0]
    path = ledger_path(ident, topic)
    if os.path.exists(path):
        raise RecordError('%s already exists' % os.path.relpath(path, ROOT))
    if topic:
        f = read_fields(('name', 'routines'), ('name', 'routines'))
        routines = [norm_addr(x) for x in f['routines'].split()]
        if None in routines:
            raise RecordError('routines: is a list of addresses')
        data = {'name': f['name'], 'routines': routines}
    else:
        f = read_fields(('name',), ('name',))
        data = {'name': f['name'], 'entries': [norm_addr(ident)]}
    save(path, data)
    print('created %s' % os.path.relpath(path, ROOT))


def _append(args, table, allowed, required, build):
    if not args:
        raise RecordError('%s needs an address or a topic name' % table)
    path = find_ledger(args[0])
    data = load(path)
    row = build(read_fields(allowed, required))
    data.setdefault(table, []).append(row)
    save(path, data)
    print('%s: %s %d recorded' % (os.path.relpath(path, ROOT), table, len(data[table])))


def cmd_fact(args):
    _append(args, 'fact', ('kind', 'at', 'says', 'by', 'window', 'n'), ('kind', 'says', 'by'), fact_row)


def cmd_refute(args):
    _append(args, 'refuted', ('says', 'by'), ('says', 'by'), lambda f: {'says': f['says'], 'by': f['by']})


def cmd_open(args):
    _append(args, 'open', ('ask', 'tried', 'settle'), ('ask', 'tried', 'settle'),
            lambda f: {'ask': f['ask'], 'tried': f['tried'], 'settle': f['settle']})


def cmd_close(args):
    if len(args) < 2 or not args[1].isdigit():
        raise RecordError('close needs an address and the open question number: close B34C 1')
    path = find_ledger(args[0])
    data = load(path)
    opens, n = data.get('open', []), int(args[1])
    if not 1 <= n <= len(opens):
        raise RecordError('%s has %d open question(s)' % (os.path.relpath(path, ROOT), len(opens)))
    fields = read_fields(('kind', 'at', 'says', 'by', 'window', 'n'))
    del opens[n - 1]
    if not opens:
        data.pop('open', None)
    if fields:
        for need in ('kind', 'says', 'by'):
            if not fields.get(need):
                raise RecordError('an answer recorded as a fact needs kind, says and by')
        data.setdefault('fact', []).append(fact_row(fields))
    save(path, data)
    print('%s: open question %d closed%s' % (os.path.relpath(path, ROOT), n,
                                             ', answer recorded as a fact' if fields else ''))


def cmd_link(args):
    if not args:
        raise RecordError('link needs an address or a topic name')
    path = find_ledger(args[0])
    data = load(path)
    f = read_fields(('oracle', 'fixture', 'port', 'manual', 'entry'))
    if not f:
        raise RecordError('nothing to link')
    new = dict(data)
    if f.get('oracle'):
        new['oracle'] = f['oracle']
    if f.get('port'):
        new['port'] = f['port']
    for field, key in (('fixture', 'fixtures'), ('manual', 'manual')):
        for v in f.get(field, '').split():
            v = canonical_id(v) if field == 'manual' else v
            new.setdefault(key, [])
            if v not in new[key]:
                new[key] = new[key] + [v]
    for v in f.get('entry', '').split():
        a = norm_addr(v)
        if not a:
            raise RecordError('entry: is an address: %r' % v)
        key = 'routines' if os.path.dirname(path) == TOPICS else 'entries'
        if a not in new.get(key, []):
            new[key] = new.get(key, []) + [a]
    probs = link_problems({k: new[k] for k in ('oracle', 'fixtures', 'port', 'manual') if k in new})
    if probs:
        raise RecordError('not linked -- ' + '; '.join(probs))
    save(path, new)
    print('%s: links updated' % os.path.relpath(path, ROOT))


NEXT_FIELDS = ('unit', 'step', 'then', 'blocked', 'notes')


def cmd_next(args):
    f = read_fields(NEXT_FIELDS, ('unit', 'step'))
    lines = ['# NEXT -- where things stand',
             '<!-- Overwritten at every unit end by python tools/record.py next; '
             '%d lines at most (manual 12.11). -->' % BUDGET['next_lines'], '']
    for k in NEXT_FIELDS:
        lines.append('%s %s' % ((k.capitalize() + ':').ljust(9), f.get(k) or 'none'))
    with open(NEXT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    print('NEXT.md written (%d lines)' % len(lines))


def cmd_decide(args):
    f = read_fields(('title', 'text'), ('title', 'text'))
    try:
        with open(DECISIONS, encoding='utf-8') as fh:
            text = fh.read()
    except OSError:
        raise RecordError('docs/DECISIONS.md is missing')
    nums = [int(n) for n in re.findall(r'^D(\d+)\. ', text, re.M)]
    n = max(nums) + 1 if nums else 1
    entry = 'D%d. **%s** (%s).  %s' % (n, f['title'], datetime.date.today().isoformat(), f['text'])
    with open(DECISIONS, 'a', encoding='utf-8', newline='\n') as fh:
        fh.write(('' if text.endswith('\n\n') else '\n' if text.endswith('\n') else '\n\n') + entry + '\n')
    print('docs/DECISIONS.md: D%d recorded' % n)


def _git(*args):
    try:
        r = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else ''
    except Exception:
        return ''


def _counts(text):
    try:
        d = parse(text)
    except RecordError:
        return None
    return tuple(len(d.get(t, [])) for t in TABLES)


def cmd_draft(args):
    """A commit message draft for the unit being committed: the mechanical
    lines derived from git, the judgment lines left for you (manual 12.11)."""
    staged = _git('diff', '--cached', '--name-only').split()
    names = staged or _git('diff', 'HEAD', '--name-only').split()
    names += [p for p in _git('ls-files', '--others', '--exclude-standard').split() if p not in names]
    diff = _git('diff', '--cached') if staged else _git('diff', 'HEAD')

    def field(text, key):
        m = re.search(r'^%s:\s*(.*)$' % key, text, re.M | re.I)
        return m.group(1).strip() if m else ''

    before = _git('show', 'HEAD:NEXT.md')
    try:
        with open(NEXT, encoding='utf-8') as fh:
            after = fh.read()
    except OSError:
        after = ''
    unit_text = field(before, 'Unit') or field(after, 'Unit') or ''
    m = re.search(r'(?:\$|0x)([0-9A-Fa-f]{4})\b', unit_text)
    unit = ('$' + m.group(1).upper()) if m else (unit_text.split(' -- ')[0][:30] or '<unit>')
    checks = len(re.findall(r'^\+(?!\+\+).*\bcheck(?:True)?\(', diff, re.M))
    areas = {}
    for p in names:
        top = p.split('/')[0]
        areas[top] = areas.get(top, 0) + 1
    ledger_lines = []
    for p in names:
        if p.startswith('ledger/') and p.endswith('.toml'):
            old = _counts(_git('show', 'HEAD:' + p)) or (0, 0, 0)
            try:
                with open(os.path.join(ROOT, p), encoding='utf-8') as fh:
                    new = _counts(fh.read())
            except OSError:
                new = (0, 0, 0)
            if new:
                ledger_lines.append('%s %+d facts %+d refuted %+d open' % (
                    p[7:-5], new[0] - old[0], new[1] - old[1], new[2] - old[2]))
    head_assets = set()
    try:
        head_assets = {a.get('key') for a in json.loads(_git('show', 'HEAD:port.json') or '{}').get('assets', [])}
    except ValueError:
        pass
    added_assets = sorted(set(port_assets()) - head_assets)
    print('%s: <what the unit achieved, one line>' % unit)
    print('')
    print('Measured: <what was measured, and on what>')
    print('Gates:    %d check rows added%s; suite <N/N>' % (
        checks, ('; fixtures added: ' + ' '.join(added_assets)) if added_assets else ''))
    print('Battery:  <cases added, killed/survived, or "not run">')
    print('Records:  %s' % ('; '.join(ledger_lines) if ledger_lines else 'no ledger change'))
    print('Files:    %s' % ', '.join('%s %d' % kv for kv in sorted(areas.items())))
    print('Surprise: <anything that contradicted an expectation, or "none">')
    print('Next:     %s' % (field(after, 'Unit') or '<from NEXT.md>'))
    print('')
    print('(%d body lines at most; details that need more belong in the ledger or TRAPS.)'
          % BUDGET['commit_body_lines'])


COMMANDS = {'new': cmd_new, 'fact': cmd_fact, 'refute': cmd_refute, 'open': cmd_open,
            'close': cmd_close, 'link': cmd_link, 'next': cmd_next, 'decide': cmd_decide,
            'draft': cmd_draft}


def main(argv):
    if not argv or argv[0] in ('-h', '--help') or argv[0] not in COMMANDS:
        print(__doc__.strip())
        return 0 if not argv or argv[0] in ('-h', '--help') else 2
    try:
        COMMANDS[argv[0]](argv[1:])
    except RecordError as e:
        sys.stderr.write('record.py %s: %s\n' % (argv[0], e))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
