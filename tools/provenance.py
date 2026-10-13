#!/usr/bin/env python3
"""
provenance.py -- the provenance record (manual P15), generated from the
records rather than kept by hand: a hand-kept map drifts away from the code
it describes.

  python tools/provenance.py           write docs/PROVENANCE.md
  python tools/provenance.py --check   exit 1 if docs/PROVENANCE.md is not
                                       what the records generate now, or a
                                       ported routine has no @z80 tag
  python tools/provenance.py --print   the generated text on stdout

Its four parts and where each comes from:

  1. the routine map   ledger/<ADDR>.toml (name, port, fixtures) joined to
                       the engine's "// @z80 $ADDR -- what it does" tags in
                       web/ (manual 7.1), one on each port function, which
                       --check requires; evidence as status.py derives it
  2. the boundary      Fist.FLAGS as the page declares it, the kit.test.js
                       rows that enforce it (G.identity, the FLAGS check),
                       and the decisions citing manual 0.5: material the
                       port substitutes because it may not ship it
  3. the log           every open question closed in ledger/ history (git):
                       the question, the facts written in the same commit
                       as its answer, and the commit and command that
                       settled it; every [[refuted]] claim still on record;
                       every trap this port added to docs/TRAPS.md
  4. still open        [[open]] entries now, ledgers with no port function,
                       PROVISIONAL numbers in web/, and the substitutions

The log reads git history, so it changes only when a commit closes a
question; regenerate and commit it with the unit that does.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import record as R  # noqa: E402
import status as S  # noqa: E402

ROOT = R.ROOT
OUT = 'docs/PROVENANCE.md'
TEMPLATE = 'web/template.html'
GAME = 'Exploding Fist'                     # the port's name, as its traps attribute it


def cell(s):
    return ' '.join(str(s).split()).replace('|', '\\|')


def sentence(s, cap=140):
    s = ' '.join(s.split())
    m = re.search(r'(?<=[a-z0-9)\]])\.(\s|$)', s)
    if m:
        s = s[:m.start()]
    return s if len(s) <= cap else s[:cap - 3].rstrip() + '...'


def tags(web):
    """{ADDR: {line, fn, does}} for every '// @z80 $ADDR -- what it does' in
    the template: the line of the function the tag sits on, and its name."""
    lines = web.split('\n')
    out = {}
    for i, l in enumerate(lines):
        m = re.match(r'\s*//\s*@z80\s+\$([0-9A-Fa-f]{4})\b(?:\s*--\s*(.*))?', l)
        if not m:
            continue
        fn = re.match(r'\s*function\s*\*?\s*(\w+)', lines[i + 1]) if i + 1 < len(lines) else None
        out[m.group(1).upper()] = {'line': i + 2, 'fn': fn.group(1) if fn else None,
                                   'does': (m.group(2) or '').strip()}
    return out


def routine_map(ctx, tg, probs):
    rows = ['| address | name | what it does | port (%s) | fixtures | evidence |' % TEMPLATE,
            '|---|---|---|---|---|---|']
    for it in ctx['ledger']:
        d = it['data'] or {}
        if it['topic'] or not d:
            continue
        addr = os.path.basename(it['rel'])[:4].upper()
        port, t = d.get('port'), tg.get(addr)
        ev = S.evidence(d, ctx)
        if port and not t:
            probs.append('%s: port %s has no // @z80 $%s tag in %s' % (it['rel'], port, addr, TEMPLATE))
        if t and not t['does']:
            probs.append('the @z80 $%s tag says nothing after "--": what the routine does' % addr)
        if port and t and t['fn'] != port:
            probs.append('%s: port %s, but the @z80 $%s tag sits on %s' % (it['rel'], port, addr, t['fn']))
        where = '`%s` :%d' % (port, t['line']) if port and t else ('`%s`' % port if port else
                                                                    '-- (none: see part 4)')
        rows.append('| $%s | %s | %s | %s | %s | %s |' % (
            addr, cell(d.get('name', '')), cell(t['does'] if t else ''),
            where, cell(' '.join(d.get('fixtures', [])) or '--'),
            ' '.join(k for k in ('measured', 'ported', 'gated') if ev[k]) or 'read'))
    have = {os.path.basename(it['rel'])[:4].upper() for it in ctx['ledger'] if not it['topic']}
    for addr in sorted(set(tg) - have):
        probs.append('%s tags @z80 $%s but no ledger/%s.toml' % (TEMPLATE, addr, addr))
    return rows


def decisions(ctx, cite):
    out = []
    for m in re.finditer(r'^(D\d+)\. \*\*(.+?)\*\* \(([\d-]+)\)\.\s+(.*)$', ctx['decisions'] or '', re.M):
        if cite in m.group(2):
            out.append((m.group(1), m.group(2), m.group(4)))
    return out


def boundary(ctx):
    m = re.search(r'static FLAGS = Object\.freeze\((\{.*?\})\)', ctx['web'], re.S)
    flags = m.group(1).strip() if m else '(not found)'
    names = re.findall(r'^\s*check(?:True)?\(\s*[\'"`]((?:Fist\.FLAGS|G\.identity)[^\'"`]*)', ctx['tests'], re.M)
    lines = ['Added layer: `Fist.FLAGS = %s` in %s.  Every departure from the original '
             'is a named flag, off on the faithful path (house rule 5); %s.' % (
                 flags, TEMPLATE, 'none is declared, so the page is the original throughout'
                 if flags in ('{}', '{ }') else 'each one is listed above'),
             '',
             'Enforced by these rows of test/kit.test.js, run against the built page:', '']
    lines += ['- %s' % cell(n) for n in names] or ['- (none found: the boundary is NOT enforced)']
    lines += ['', 'Substituted, not added: material the original takes from the ROM, which '
              'the port may not ship (manual 0.5).  Timing and counts are kept; the content is ours:', '']
    lines += ['- **%s %s** -- %s' % (d, t, sentence(x, 400)) for d, t, x in decisions(ctx, 'manual 0.5')]
    return lines


def history():
    """[(commit, subject, file, asks, facts)] for every commit that removed an
    [[open]] entry from a ledger file, oldest first."""
    log = S.git('log', '-p', '--reverse', '--format=@@C %h %s', '--', 'ledger/') or ''
    out, cur, fname, blk = [], None, None, None
    rec = {}

    def flush():
        # an ask removed and re-added in the same diff was reworded, not closed
        same = {a[:50] for a in rec.get('added', [])}
        rec['asks'] = [a for a in rec.get('asks', []) if a[:50] not in same]
        if rec['asks']:
            out.append(dict(rec))
    for l in log.split('\n'):
        if l.startswith('@@C '):
            flush()
            h, _, subj = l[4:].partition(' ')
            cur, fname, blk = (h, subj), None, None
            rec = {}
            continue
        if l.startswith('+++ '):
            flush()
            fname = l[6:] if l.startswith('+++ b/') else None
            rec = {'commit': cur, 'file': fname, 'asks': [], 'added': [], 'facts': []}
            continue
        m = re.match(r'([+-])\[\[(\w+)\]\]', l)
        if m:
            blk = (m.group(1), m.group(2))
            if blk == ('+', 'fact'):
                rec.setdefault('facts', []).append({})
            continue
        m = re.match(r'([+-])(\w+)\s*=\s*"(.*)"\s*$', l)
        if not m or not rec:
            continue
        sign, key, val = m.groups()
        if sign == '-' and key == 'ask':
            rec['asks'].append(val.replace('\\"', '"'))
        elif sign == '+' and key == 'ask':
            rec['added'].append(val.replace('\\"', '"'))
        elif sign == '+' and blk == ('+', 'fact') and key in ('says', 'by') and rec['facts']:
            rec['facts'][-1][key] = val.replace('\\"', '"')
    flush()
    return out


def log_part(ctx):
    rows = ['| # | asked (what was assumed or not known) | what the machine said | caught by |',
            '|---|---|---|---|']
    n = 0
    for r in history():
        addr = os.path.basename(r['file'] or '?').replace('.toml', '')
        facts = [f for f in r['facts'] if f.get('says')]
        said = ' / '.join(sentence(f['says'], 220) for f in facts) or '(closed with no fact recorded)'
        by = '; '.join(sorted({f['by'].split(' ; ')[0] for f in facts if f.get('by')}))
        for a in r['asks']:
            n += 1
            rows.append('| %d | %s: %s | %s | %s (%s) |' % (
                n, addr, cell(sentence(a, 220)), cell(said), cell(sentence(by, 160) or '--'), r['commit'][0]))
    ref = []
    for it in ctx['ledger']:
        for x in (it['data'] or {}).get('refuted', []):
            ref.append('| %s: %s | %s |' % (os.path.basename(it['rel']).replace('.toml', ''),
                                             cell(x.get('says', '')), cell(x.get('by', ''))))
    traps = re.findall(r'^(\d+)\. \*\*(.+?)\*\*\s*\(%s' % GAME, R_traps(), re.M)
    lines = ['Every question the ledgers closed, oldest first: the "caught by" column is the '
             'command or gate that settled it, and the commit that recorded it.', ''] + rows
    lines += ['', 'Refuted claims still on record:', '',
              '| claim | refuted by |', '|---|---|'] + (ref or ['| (none) | |'])
    lines += ['', 'Lessons this port added to docs/TRAPS.md:', '']
    lines += ['- T%s %s' % (k, cell(t.capitalize() if t.isupper() else t)) for k, t in traps] or ['- (none)']
    return lines


def R_traps():
    return S.read('docs/TRAPS.md') or ''


def open_part(ctx):
    lines = []
    opens = [(os.path.basename(it['rel']).replace('.toml', ''), q)
             for it in ctx['ledger'] for q in (it['data'] or {}).get('open', [])]
    lines += ['Open questions in ledger/: %d.' % len(opens), '']
    lines += ['- %s: %s (settle: %s)' % (a, cell(q.get('ask', '')), cell(q.get('settle', ''))) for a, q in opens]
    unported = [(os.path.basename(it['rel'])[:4], it['data']) for it in ctx['ledger']
                if not it['topic'] and it['data'] and not it['data'].get('port')]
    if opens:
        lines.append('')
    lines += ['Routines read but with no port function of their own:', '']
    for a, d in unported:
        gated = [f for f in d.get('fact', []) if f.get('kind') == 'gated']
        lines.append('- $%s %s -- %s' % (a, d.get('name', ''), cell(sentence(gated[-1]['says'], 300))
                                          if gated else 'no gated fact: NOT covered'))
    if not unported:
        lines.append('- (none)')
    prov = [(n + 1, l.strip()) for n, l in enumerate((S.read(TEMPLATE) or '').split('\n')) if 'PROVISIONAL' in l]
    lines += ['', 'PROVISIONAL numbers in %s: %d.' % (TEMPLATE, len(prov)), '']
    lines += ['- :%d `%s`' % (n, cell(l)[:160]) for n, l in prov]
    lines += ['', 'Our own inventions -- the substitutions of part 2, which are ours and not the '
              'original\'s: %s.' % (', '.join(d for d, _, _ in decisions(ctx, 'manual 0.5')) or 'none')]
    return lines


def generate():
    ctx = S.gather()
    probs = []
    tg = tags(S.read(TEMPLATE) or '')
    body = ['# Provenance -- %s' % GAME, '',
            'Purpose: the provenance record (manual P15) -- routine map, faithful/added boundary,',
            'what the original proved wrong, what is still open.  GENERATED: do not edit.',
            'Read by: a reviewer; whoever ports the next game.  Rewritten with',
            'python tools/provenance.py; --check says whether it is current.', '',
            '## 1. The routine map', '',
            'Original address -> what it does -> the function that implements it, joined from',
            'ledger/<ADDR>.toml and the `// @z80 $ADDR -- what it does` tag on each function (manual 7.1).', '']
    body += routine_map(ctx, tg, probs)
    body += ['', '## 2. The faithful/added boundary', ''] + boundary(ctx)
    body += ['', '## 3. What the original proved wrong', ''] + log_part(ctx)
    body += ['', '## 4. What is still open', ''] + open_part(ctx)
    return '\n'.join(body) + '\n', probs


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--check', action='store_true')
    g.add_argument('--print', action='store_true')
    a = ap.parse_args(argv)
    text, probs = generate()
    for p in probs:
        print('provenance: ' + p, file=sys.stderr)
    path = os.path.join(ROOT, OUT)
    if a.print:
        sys.stdout.write(text)
    elif a.check:
        old = S.read(OUT)
        if old != text:
            print('provenance: %s is %s -- python tools/provenance.py' % (OUT, 'missing' if old is None else 'stale'))
            return 1
        print('provenance: %s current%s' % (OUT, '' if not probs else ', %d problem(s)' % len(probs)))
    else:
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print('provenance: wrote %s (%d lines)' % (OUT, text.count('\n')))
    return 1 if probs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
