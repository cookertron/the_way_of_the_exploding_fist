#!/usr/bin/env python3
"""
status.py -- where the project stands, derived from its records, never typed
(manual 5.4, 12.4, 12.11).

  python tools/status.py --brief     the orientation the session hook prints at
                                     every start and after every compaction
  python tools/status.py B34C        everything known about one routine (or a
                                     topic name): ledger, links, evidence, IDs
  python tools/status.py --check     consistency.  Exit 1 on anything that
                                     breaks awareness -- an unregistered record,
                                     a broken link, a malformed ledger file;
                                     warnings for budgets and loose ends
  python tools/status.py --index     every record, by home, one line each

Evidence is what exists now: MEASURED (the routine's fixtures are registered
and present), PORTED (its port function is defined in web/), GATED (every one
of its fixtures is read by a test).  Freshness comes from the stamps (manual
12.3, tools/stamp.py): a fixture is FRESH while every file that produced it
hashes the same, STALE once one does not, UNSTAMPED if written before stamps;
its gate is fresh while the last green full suite ran a page built from it
as it is now.  --brief counts them and names the first stale few.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import record as R  # noqa: E402
import stamp as ST  # noqa: E402

ROOT = R.ROOT
HOMES = {'README.md', 'CLAUDE.md', 'NEXT.md', 'docs/PORTING-ZX-TO-JS.txt', 'docs/TRAPS.md',
         'docs/TRAPS-MAP.md', 'docs/DECISIONS.md', 'tools/README.md'}
NOT_RECORDS = ('docs/archive/', '.claude/', 'scratch/', 'test/', 'web/', 'build/', 'node_modules/')
RECORD_EXTS = ('.md', '.txt', '.toml')
TRAP_MARKER = '<!-- budget:'
BRIEF_CAP = 2800


def git(*args):
    try:
        r = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def read(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# gather everything once
# ---------------------------------------------------------------------------
def gather():
    ctx = {'ledger': [], 'assets': R.port_assets(),
           'web': R.source_text('web', ('.js', '.html')),
           'tests': R.source_text('test', ('.js',)),
           'next': read('NEXT.md'), 'decisions': read('docs/DECISIONS.md')}
    try:
        ctx['port'] = json.loads(read('port.json') or '{}')
    except ValueError:
        ctx['port'] = {}
    for folder, topic in ((R.LEDGER, False), (R.TOPICS, True)):
        if not os.path.isdir(folder):
            continue
        for fn in sorted(os.listdir(folder)):
            p = os.path.join(folder, fn)
            if not os.path.isfile(p):
                continue
            item = {'path': p, 'rel': os.path.relpath(p, ROOT).replace(os.sep, '/'),
                    'topic': topic, 'data': None, 'error': None, 'lines': 0}
            try:
                with open(p, encoding='utf-8') as f:
                    text = f.read()
                item['lines'] = text.count('\n')
                item['data'] = R.parse(text) if fn.endswith('.toml') else None
                if not fn.endswith('.toml'):
                    item['error'] = 'ledger/ holds only <ADDR>.toml and topics/<name>.toml files'
            except (OSError, R.RecordError) as e:
                item['error'] = str(e)
            ctx['ledger'].append(item)
    return ctx


def addresses(ctx):
    """Every address some ledger entry covers."""
    out = set()
    for it in ctx['ledger']:
        d = it['data'] or {}
        out |= set(d.get('entries', [])) | set(d.get('routines', []))
    return out


def evidence(data, ctx):
    fx = data.get('fixtures', [])
    measured = bool(fx) and all(k in ctx['assets'] and os.path.isfile(
        os.path.join(ROOT, ctx['assets'][k].get('file', ''))) for k in fx)
    ported = bool(data.get('port')) and R.port_defined(data['port'], ctx['web'])
    gated = bool(fx) and all(re.search(r'\b%s\b' % re.escape(k), ctx['tests']) for k in fx)
    return {'measured': measured, 'ported': ported, 'gated': gated}


def fresh(key, ctx):
    """(fixture state, gate state, reasons) for one asset key, cached."""
    cache = ctx.setdefault('fresh', {})
    if key not in cache:
        path = ctx['assets'].get(key, {}).get('file', '')
        st, why = ST.freshness(path)
        g, gwhy = ST.gate_freshness(key, path)
        cache[key] = (st, g, why + gwhy)
    return cache[key]


def freshness_lines(ctx, keys):
    """The brief's freshness summary over these asset keys."""
    states = {k: fresh(k, ctx) for k in keys}
    count = lambda i, *v: sum(1 for s in states.values() if s[i] in v)
    out = ['Stamps (manual 12.3): fixtures %d fresh, %d stale, %d unstamped; gates %d fresh, %d not'
           % (count(0, 'fresh'), count(0, 'stale', 'unreadable'), count(0, 'unstamped', 'missing'),
              count(1, 'fresh'), count(1, 'stale', 'none'))]
    stale = [(k, s) for k, s in states.items() if s[0] != 'fresh' or s[1] != 'fresh']
    stale.sort(key=lambda ks: ks[1][0] != 'stale')        # stale fixtures first: they are the re-run list
    for k, s in stale[:3]:
        out.append('  %s %s: %s' % (s[0] if s[0] != 'fresh' else 'gate ' + s[1], k, s[2][0] if s[2] else s[0]))
    if len(stale) > 3:
        out.append('  ... %d more: python tools/stamp.py' % (len(stale) - 3))
    return out


def label(it):
    d = it['data'] or {}
    if it['topic']:
        return 'topic %s' % os.path.basename(it['path'])[:-5]
    return (d.get('entries') or ['?'])[0]


# ---------------------------------------------------------------------------
# the check
# ---------------------------------------------------------------------------
def record_files():
    listed = git('ls-files', '-z', '--cached', '--others', '--exclude-standard')
    if listed is not None:
        return [p for p in listed.split('\0') if p]
    out = []
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'build', 'scratch', '__pycache__')]
        out += [os.path.relpath(os.path.join(dirpath, f), ROOT).replace(os.sep, '/') for f in files]
    return out


def purpose_header(rel):
    head = (read(rel) or '').splitlines()[:6]
    text = '\n'.join(head).lower()
    return 'purpose:' in text and 'read by:' in text


def entry_spans(text, pattern):
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines) if re.match(pattern, l)]
    spans = []
    for k, i in enumerate(starts):
        j = starts[k + 1] if k + 1 < len(starts) else len(lines)
        while j > i + 1 and not lines[j - 1].strip():
            j -= 1
        spans.append((lines[i], j - i))
    return spans


def check(ctx):
    block, warn = [], []
    ids = None
    for it in ctx['ledger']:
        if it['error']:
            block.append('%s: %s' % (it['rel'], it['error']))
            continue
        d = it['data']
        probs = R.entry_problems(d, it['topic'])
        if not it['topic']:
            want = '$' + os.path.basename(it['path'])[:-5].upper()
            if want not in d.get('entries', []):
                probs.append('its file name says %s but its entries do not include it' % want)
        if d.get('manual') and ids is None:
            ids = R.known_ids()[0]
        probs += R.link_problems(d, ctx['assets'], ctx['web'], ids)
        block += ['%s: %s' % (it['rel'], p) for p in probs]
        if it['lines'] > R.BUDGET['ledger_lines']:
            warn.append('%s is %d lines (budget %d): roll it up (manual 12.11)'
                        % (it['rel'], it['lines'], R.BUDGET['ledger_lines']))

    for rel in record_files():
        if not rel.endswith(RECORD_EXTS):
            continue
        if rel in HOMES or rel.startswith(NOT_RECORDS) or rel.startswith('ledger/'):
            continue
        if not purpose_header(rel):
            block.append('%s is not a record home and has no "Purpose:" / "Read by:" header in '
                         'its first lines: give it a home, add the header, or delete it' % rel)

    nxt = ctx['next']
    if nxt is None:
        warn.append('NEXT.md is missing: nothing records where things stand '
                    '(python tools/record.py next)')
    else:
        n = nxt.count('\n')
        if n > R.BUDGET['next_lines']:
            warn.append('NEXT.md is %d lines (budget %d)' % (n, R.BUDGET['next_lines']))
        for key in ('Unit', 'Step'):
            if not re.search(r'^%s:\s*\S' % key, nxt, re.M):
                warn.append('NEXT.md has no %s: line' % key)
        m = re.search(r'^Unit:.*?(?:\$|0x)([0-9A-Fa-f]{4})\b', nxt, re.M)
        if m and '$' + m.group(1).upper() not in addresses(ctx):
            warn.append("NEXT.md's unit $%s has no ledger entry (python tools/record.py new %s)"
                        % (m.group(1).upper(), m.group(1).upper()))

    dec = ctx['decisions']
    if dec is not None:
        nums = [int(x) for x in re.findall(r'^D(\d+)\. ', dec, re.M)]
        if len(nums) != len(set(nums)):
            block.append('docs/DECISIONS.md numbers a decision twice')
        for head, n in entry_spans(dec, r'D\d+\. '):
            if n > R.BUDGET['decision_lines']:
                warn.append('docs/DECISIONS.md %s is %d lines (budget %d)'
                            % (head.split('.')[0], n, R.BUDGET['decision_lines']))

    traps = read('docs/TRAPS.md') or ''
    if TRAP_MARKER in traps:
        tail = traps[traps.index(TRAP_MARKER):]
        for head, n in entry_spans(tail, r'\d+\. \*\*'):
            if n > R.BUDGET['trap_lines']:
                warn.append('TRAPS #%s is %d lines (budget %d for new entries)'
                            % (head.split('.')[0], n, R.BUDGET['trap_lines']))

    claude = read('CLAUDE.md')
    if claude and claude.count('\n') > R.BUDGET['claude_md_lines']:
        warn.append('CLAUDE.md is %d lines (budget %d): it is re-read after every compaction'
                    % (claude.count('\n'), R.BUDGET['claude_md_lines']))

    body = git('log', '-1', '--format=%b')
    if body:
        n = len(body.rstrip('\n').splitlines())
        if n > R.BUDGET['commit_body_lines']:
            warn.append('the last commit message body is %d lines (budget %d)'
                        % (n, R.BUDGET['commit_body_lines']))

    src = ctx['tests'] + ctx['web']
    for key, a in ctx['assets'].items():
        stem = key.rstrip('0123456789')            # a numbered family read by name: `live_dan${n}`
        if not (re.search(r'\b%s\b' % re.escape(key), src)
                or (stem != key and re.search(r'\b%s\$\{' % re.escape(stem), src))):
            warn.append('asset %r is read by nothing in test/ or web/ (TRAPS #116)' % key)

    have = addresses(ctx)
    for addr in sorted(set(m.upper() for m in re.findall(r'@z80\s+\$([0-9A-Fa-f]{4})', ctx['web']))):
        if '$' + addr not in have:
            warn.append('web/ tags @z80 $%s but no ledger entry covers it' % addr)

    # the provenance record (manual P15), once one has been written
    if read('docs/PROVENANCE.md') is not None:
        import provenance as PV
        text, probs = PV.generate()
        warn += ['provenance: ' + p for p in probs]
        if read(PV.OUT) != text:
            warn.append('%s is stale: python tools/provenance.py' % PV.OUT)

    # the mutation battery (manual 6.12): is a full run due?
    mlast = read('build/mutants/last.json')
    if mlast:
        try:
            rev = json.loads(mlast).get('full_rev')
            dirty = json.loads(mlast).get('full_dirty') or []
        except ValueError:
            rev, dirty = None, []
        if not rev:
            warn.append('no full mutation run on record: python tools/mutants.py --background')
        else:
            moved = [f for f in ('test/rig.js', 'tools/build.py', 'tools/mutants.py', 'tools/mutants.js')
                     if git('diff', '--quiet', rev, '--', f) is None or f in dirty]
            if moved:
                warn.append('a full mutation run is due: %s changed since the last one '
                            '(python tools/mutants.py --background)' % ', '.join(moved))

    # the roster manifest (manual 12.6): every saved state a row, computed
    rcfg = (ctx['port'].get('roster') or {}) if isinstance(ctx.get('port'), dict) else {}
    rfile = rcfg.get('file', 'build/roster.json')
    sdir = os.path.join(ROOT, ((ctx.get('port') or {}).get('z80') or {}).get('states') or 'build')
    pkls = sorted(f[:-4] for f in os.listdir(sdir) if f.endswith('.pkl')) if os.path.isdir(sdir) else []
    if pkls:
        st, why = ST.freshness(rfile)
        if st in ('missing', 'unreadable'):
            warn.append('no roster manifest for %d saved states: python tools/roster.py (manual 12.6)'
                        % len(pkls))
        else:
            if st != 'fresh':
                warn.append('the roster is %s (%s): python tools/roster.py' % (st, why[0] if why else st))
            have = set(((ST.load(rfile) or {}).get('states') or {}))
            new = [n for n in pkls if n not in have]
            if new:
                warn.append('saved states not in the roster: %s (python tools/roster.py)' % ', '.join(new))

    scratch = os.path.join(ROOT, 'scratch')
    last = git('log', '-1', '--format=%ct')
    if os.path.isdir(scratch) and last and last.strip().isdigit():
        for dirpath, dirs, files in os.walk(scratch):
            if dirpath == scratch and 'mutants' in dirs:
                dirs.remove('mutants')      # the runner's worker trees: rebuilt by every run
            for fn in files:
                p = os.path.join(dirpath, fn)
                if os.path.getmtime(p) < int(last.strip()):
                    warn.append('%s survived the last commit: promote it to a home or delete it'
                                % os.path.relpath(p, ROOT).replace(os.sep, '/'))
    return block, warn


# ---------------------------------------------------------------------------
# views
# ---------------------------------------------------------------------------
def id_titles(idlist):
    try:
        manual = R.known_ids()[1]
        m = manual.load_manual()
        t = manual.load_traps(required=False)
    except SystemExit:
        return idlist
    out = []
    for raw in idlist:
        key = R.canonical_id(raw)
        if key.startswith('T') and key[1:].isdigit() and int(key[1:]) in t[2]:
            out.append('%s %s' % (key, manual.trap_title(t[1], t[2][int(key[1:])])[:48]))
        elif key in m[2]:
            out.append('%s %s' % (key, manual.manual_title(m[1][m[2][key][0]])[:48]))
        else:
            out.append(key)
    return out


def brief(ctx):
    items = [it for it in ctx['ledger'] if it['data'] is not None]
    routines = [it for it in items if not it['topic']]
    ev = [evidence(it['data'], ctx) for it in routines]
    opens = sum(len(it['data'].get('open', [])) for it in items)
    decisions = len(re.findall(r'^D\d+\. ', ctx['decisions'] or '', re.M))
    out = ['Records: %d routines, %d topics, %d decisions; evidence: %d measured, %d ported, '
           '%d gated; %d open questions'
           % (len(routines), len(items) - len(routines), decisions,
              sum(e['measured'] for e in ev), sum(e['ported'] for e in ev),
              sum(e['gated'] for e in ev), opens)]
    nxt = ctx['next']
    if nxt:
        out.append('NEXT.md:')
        out += ['  ' + l for l in nxt.splitlines() if re.match(r'^[A-Z][a-z]+:', l)]
        m = re.search(r'^Unit:.*?(?:\$|0x)([0-9A-Fa-f]{4})\b', nxt, re.M)
        if m:
            addr = '$' + m.group(1).upper()
            for it in items:
                d = it['data']
                if addr in d.get('entries', []) + d.get('routines', []):
                    e = evidence(d, ctx)
                    got = ', '.join(k if v else 'not ' + k for k, v in e.items())
                    out.append('Unit %s %s: %d facts, %d refuted, %d open; %s'
                               % (addr, d.get('name', '?'), len(d.get('fact', [])),
                                  len(d.get('refuted', [])), len(d.get('open', [])), got))
                    for k, o in enumerate(d.get('open', [])[:3], 1):
                        out.append('  open %d: %s' % (k, o.get('ask', '')))
                    if d.get('manual'):
                        out.append('  read: python tools/manual.py ' + ' '.join(d['manual']))
                    break
    keys = sorted({k for it in routines for k in it['data'].get('fixtures', []) if k in ctx['assets']})
    out += freshness_lines(ctx, keys)
    block, warn = check(ctx)
    out.append('Check: %d blocking, %d warnings%s' % (
        len(block), len(warn), ' -- python tools/status.py --check' if block or warn else ''))
    out += ['  BLOCK ' + b for b in block[:4]] + ['  warn  ' + w for w in warn[:4 if block else 6]]
    text = '\n'.join(out)
    return text if len(text) <= BRIEF_CAP else text[:BRIEF_CAP - 40] + '\n  ... (python tools/status.py --check)'


def view(ident, ctx):
    try:
        path = R.find_ledger(ident)
    except R.RecordError as e:
        return None, str(e)
    it = next(i for i in ctx['ledger'] if os.path.samefile(i['path'], path))
    if it['error']:
        return None, '%s: %s' % (it['rel'], it['error'])
    d = it['data']
    out = ['== %s %s  (%s, %d lines) ==' % (label(it), d.get('name', '?'), it['rel'], it['lines'])]
    key = 'routines' if it['topic'] else 'entries'
    out.append('%-9s %s' % (key + ':', ' '.join(d.get(key, []))))
    if d.get('oracle'):
        out.append('oracle:   %s' % d['oracle'])
    if d.get('fixtures'):
        out.append('fixtures: %s' % ' '.join(d['fixtures']))
        for k in d['fixtures']:
            if k in ctx['assets']:
                st, g, why = fresh(k, ctx)
                out.append('  %s: %s, gate %s%s' % (k, st, g, ('; ' + why[0]) if why else ''))
    if d.get('port'):
        out.append('port:     %s' % d['port'])
    e = evidence(d, ctx)
    out.append('evidence: %s' % ', '.join(k if v else 'not ' + k for k, v in e.items()))
    if d.get('manual'):
        out.append('read:     ' + '; '.join(id_titles(d['manual'])))
    for table, fmt in (('fact', lambda r: '%s%s: %s  [%s]%s' % (
            r.get('kind'), (' ' + r['at']) if r.get('at') else '', r.get('says'), r.get('by'),
            ('  (window: %s; n=%s)' % (r.get('window'), r.get('n'))) if r.get('window') else '')),
            ('refuted', lambda r: '%s  [%s]' % (r.get('says'), r.get('by'))),
            ('open', lambda r: '%s | tried: %s | settles it: %s' % (r.get('ask'), r.get('tried'), r.get('settle')))):
        rows = d.get(table, [])
        if rows:
            out.append('%s:' % table)
            out += ['  %d. %s' % (k, fmt(r)) for k, r in enumerate(rows, 1)]
    probs = R.entry_problems(d, it['topic']) + R.link_problems(d, ctx['assets'], ctx['web'])
    out.append('problems: %s' % ('none' if not probs else '; '.join(probs)))
    addr = (d.get(key) or [''])[0]
    log = git('log', '-5', '--format=%h %s', '--grep', addr.lstrip('$'), '--regexp-ignore-case') if addr else None
    if log and log.strip():
        out.append('commits:')
        out += ['  ' + l for l in log.strip().splitlines()]
    return '\n'.join(out), None


def index(ctx):
    out = ['NEXT.md  where things stand (python tools/record.py next)']
    for it in ctx['ledger']:
        d = it['data']
        if d is None:
            out.append('%s  UNREADABLE: %s' % (it['rel'], it['error']))
            continue
        e = evidence(d, ctx)
        tags = ' '.join(k for k, v in e.items() if v) or 'read'
        out.append('%s  %s %s [%s]' % (it['rel'], label(it), d.get('name', '?'), tags))
    for m in re.finditer(r'^(D\d+)\. \*\*(.+?)\*\*', ctx['decisions'] or '', re.M):
        out.append('docs/DECISIONS.md %s  %s' % (m.group(1), m.group(2)))
    out.append('docs/PORTING-ZX-TO-JS.txt  the method, by ID (python tools/manual.py --index)')
    out.append('docs/TRAPS.md  lessons, by number (python tools/manual.py T146)')
    out.append('docs/TRAPS-MAP.md  each trap and the mechanism that prevents it (--map)')
    for rel in sorted(record_files()):
        if rel.startswith('docs/archive/'):
            out.append('%s  archive: read by search or line range' % rel)
        elif rel.endswith(RECORD_EXTS) and rel not in HOMES and not rel.startswith(NOT_RECORDS + ('ledger/',)):
            head = next((l for l in (read(rel) or '').splitlines()[:6] if 'purpose:' in l.lower()), '')
            out.append('%s  %s' % (rel, head.strip()[:80] or 'NO PURPOSE HEADER'))
    return '\n'.join(out)


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__.strip())
        return 0
    ctx = gather()
    if argv[0] == '--brief':
        print(brief(ctx))
        return 0
    if argv[0] == '--index':
        print(index(ctx))
        return 0
    if argv[0] == '--check':
        block, warn = check(ctx)
        for b in block:
            print('BLOCK ' + b)
        for w in warn:
            print('warn  ' + w)
        print('status: %d blocking, %d warnings' % (len(block), len(warn)))
        return 1 if block else 0
    text, err = view(argv[0], ctx)
    if err:
        sys.stderr.write('status.py: %s\n' % err)
        return 1
    print(text)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
