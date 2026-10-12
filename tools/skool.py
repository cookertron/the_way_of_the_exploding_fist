#!/usr/bin/env python3
"""skool.py -- the annotated disassembly as a SkoolKit skool file and HTML,
built from the records: symbols, ledgers and (optionally) a third-party
control file for the block layout (manual 12.11, P3).

Pipeline, every product under OUT (default build/skool/, gitignored: it
embeds the game's bytes, house rule 7):

  1. image   build/image.bin with the game's start-up relocation applied
             (LDIR $6000-$80FF -> $5F00 at $9C43, as refcheck.py)
  2. ctl     the reference's control file (--ref CTL) with its old macro
             syntax brought up to the installed SkoolKit (#DEFINE0, #CALL:),
             plus one new code entry at each ledger routine that does not
             start an entry there already (split out of the reference's)
             -- or, without --ref, a minimal ctl: one code entry per ledger
             routine and per symbol the static walk reaches, bytes elsewhere
  3. skool   sna2skool over the image, then our records laid on top:
             - every symbols.json name as an @label (ours win; a reference
               label displaced or duplicated is reported)
             - each ledger's name, port function, oracle, fixtures, manual
               IDs and facts as description paragraphs of its entry, each
               topic's name on the entries of its routines
             - each fact with an "at" as a comment on that instruction
               (inside a {...} comment group it goes before the group)
             - $XXXX in our text linked (#R) where the skool has that line
  4. html    skool2html into OUT/html (the reference's HtmlWriter class and
             ref files when --ref is given and they import; else plain)

Prints what was placed and what could not be: a label or a fact "at" an
address that is not the start of a skool line is UNPLACED, and --strict
makes any unplaced record exit 1.

Usage:
    python tools/skool.py [--ref ../ref_wayoftheexplodingfist/sources/wotef.ctl]
                          [--out build/skool] [--no-html] [--strict]
    python tools/skool.py --ref CTL --entry 0x9745     show one entry's skool
"""
import argparse
import io
import json
import os
import re
import sys
import contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import portconfig  # noqa: E402
import record as R  # noqa: E402

RELOC = (0x6000, 0x5F00, 0x2100)          # src, dst, len: start-up LDIR at $9C43
LINE = re.compile(r'^([bcgistuw* ])\$([0-9A-F]{4}) (.*)$')
ENTRY = re.compile(r'^([bcgistuw]) \$([0-9A-Fa-f]{4})\b')
LABEL_OK = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def hexaddr(s):
    return int(str(s).lstrip('$').replace('0x', ''), 16) if str(s).startswith('$') else int(str(s), 0)


# ---------------------------------------------------------------- records

def ledgers():
    """-> (routines, topics): ledger dicts with 'rel' added."""
    routines, topics = [], []
    for folder, out in ((R.LEDGER, routines), (R.TOPICS, topics)):
        if not os.path.isdir(folder):
            continue
        for fn in sorted(os.listdir(folder)):
            if fn.endswith('.toml'):
                p = os.path.join(folder, fn)
                d = R.parse(open(p, encoding='utf-8').read())
                d['rel'] = os.path.relpath(p, R.ROOT).replace(os.sep, '/')
                out.append(d)
    return routines, topics


def symbols():
    p = portconfig.path(portconfig.get('z80', 'symbols'))
    if not p or not os.path.exists(p):
        return {}
    return {int(k, 0): v for k, v in json.load(open(p)).items()}


# ---------------------------------------------------------------- step 1, 2

def image_bytes(path):
    img = bytearray(open(path, 'rb').read())
    s, d, n = RELOC
    img[d:d + n] = img[s:s + n]
    return img


def match_paren(text, i):
    """index just past the bracket group opening at text[i] == '('."""
    depth = 0
    for j in range(i, len(text)):
        if text[j] == '(':
            depth += 1
        elif text[j] == ')':
            depth -= 1
            if depth == 0:
                return j + 1
    return len(text)


def modernise(text, notes):
    """Old SkoolKit macro syntax -> the installed version's."""
    n = [0, 0]

    def define(m):
        n[0] += 1
        return '#DEF(#%s %s)' % (m.group(1), m.group(2))
    text = re.sub(r'#DEFINE0\(([A-Z]+),(#[^)]*)\)', define, text)

    def udgarray(m):
        n[2] += 1
        return '#UDGARRAY%s(%s)(%s)' % m.groups()
    n.append(0)
    text = re.sub(r'#UDGARRAY([^;\s]*);(\S*)\(([\w-]+)\)', udgarray, text)
    out, i = [], 0
    while True:
        j = text.find('#CALL:', i)
        if j < 0:
            break
        k = text.find('(', j)
        end = match_paren(text, k)
        out.append(text[i:j] + '#CALL(' + text[j + 6:end] + ')')
        n[1] += 1
        i = end
    out.append(text[i:])
    notes.append('ctl: %d #DEFINE0, %d #CALL: and %d #UDGARRAY;spec rewritten for SkoolKit 10' % (n[0], n[1], n[2]))
    return ''.join(out)


def split_ctl(text, starts, names, notes):
    """Add a code entry at each ledger routine not already an entry start,
    inside a reference code entry."""
    lines = text.splitlines()
    blocks = []                                   # (addr, type, line index)
    for i, ln in enumerate(lines):
        m = ENTRY.match(ln)
        if m:
            blocks.append((int(m.group(2), 16), m.group(1), i))
    have = {a for a, _, _ in blocks}
    inserts, split = [], []
    for a in sorted(starts):
        if a in have:
            continue
        prev = [b for b in blocks if b[0] < a]
        if not prev or prev[-1][1] != 'c':
            notes.append('ctl: ledger routine $%04X lies in a %s entry, not split'
                         % (a, prev[-1][1] if prev else 'no'))
            continue
        # after the containing entry's sub-blocks that start before a
        nxt = [b for b in blocks if b[0] > a]
        hi = nxt[0][2] if nxt else len(lines)
        at = hi
        for i in range(prev[-1][2] + 1, hi):
            m = re.match(r'^[ BCDINRSTW@] \$([0-9A-Fa-f]{4})', lines[i])
            if m and int(m.group(1), 16) >= a:
                at = i
                break
        inserts.append((at, ['', 'c $%04X %s' % (a, names.get(a, 'Routine at $%04X' % a))]))
        split.append(a)
    for at, new in sorted(inserts, reverse=True):
        lines[at:at] = new
    notes.append('ctl: %d ledger routines split out of reference entries: %s'
                 % (len(split), ' '.join('$%04X' % a for a in split) or '-'))
    return '\n'.join(lines) + '\n'


def minimal_ctl(img, starts, syms, names):
    """No reference: code from the static walk (a lower bound, walk.py) out of
    the ledger routines, the entry point and every symbol; bytes elsewhere."""
    import walk
    roots = set(starts) | set(syms)
    entry = portconfig.get('tape', 'entry')
    if entry is not None:
        roots.add(hexaddr(entry))
    seen, covered, calls, _ = walk.walk(img, sorted(roots))
    heads = {a for a in roots | set(calls) if a in seen}
    out, prev = ['b $5F00 Data'], False
    for a in range(0x5F00, 0x10000):
        code = a in covered
        if a in heads:
            out.append('c $%04X %s' % (a, names.get(a) or syms.get(a) or 'Routine at $%04X' % a))
        elif code and not prev:
            out.append('c $%04X Routine at $%04X' % (a, a))
        elif prev and not code:
            out.append('b $%04X Data block at $%04X' % (a, a))
        prev = code
    return '\n'.join(out) + '\n'


def run_skoolkit(mod, argv, stdout=None):
    buf = io.StringIO()
    with contextlib.redirect_stdout(stdout or buf), contextlib.redirect_stderr(io.StringIO()):
        mod.main(argv)
    return buf.getvalue()


# ---------------------------------------------------------------- step 3

def esc(text, lines_at):
    """Our text safe in a skool comment: no macros, braces or HTML, addresses linked."""
    text = text.replace('#', '#CHR35').replace('{', '(').replace('}', ')')
    text = text.replace('&', '#CHR38').replace('<', '#CHR60').replace('>', '#CHR62')

    def link(m):
        a = int(m.group(1), 16)
        return '#R$%04X($%04X)' % (a, a) if a in lines_at else m.group(0)
    return re.sub(r'(?<![#R])\$([0-9A-Fa-f]{4})\b', link, text)


class Skool:
    """The skool as entries of lines, addressable by instruction address."""

    def __init__(self, text):
        self.entries = [e.split('\n') for e in text.strip('\n').split('\n\n')]
        self.at = {}                              # addr -> (entry idx, line idx)
        self.starts = {}
        for ei, e in enumerate(self.entries):
            first = True
            for li, ln in enumerate(e):
                m = LINE.match(ln)
                if m:
                    a = int(m.group(2), 16)
                    self.at[a] = (ei, li)
                    if first and m.group(1) != ' ':
                        self.starts[a] = ei
                        first = False

    def text(self):
        return '\n\n'.join('\n'.join(e) for e in self.entries) + '\n'

    def labels(self):
        out = {}
        for e in self.entries:
            for li, ln in enumerate(e):
                if ln.startswith('@label='):
                    for ln2 in e[li + 1:]:
                        m = LINE.match(ln2)
                        if m:
                            out[int(m.group(2), 16)] = ln[7:]
                            break
        return out

    def _reindex(self, ei):
        for li, ln in enumerate(self.entries[ei]):
            m = LINE.match(ln)
            if m:
                self.at[int(m.group(2), 16)] = (ei, li)

    def set_label(self, a, name):
        ei, li = self.at[a]
        e = self.entries[ei]
        k = li
        while k > 0 and e[k - 1].startswith('@'):
            k -= 1
            if e[k].startswith('@label='):
                old = e[k][7:]
                e[k] = '@label=' + name
                return old
        e.insert(li, '@label=' + name)
        self._reindex(ei)
        return None

    def drop_label(self, a):
        ei, li = self.at[a]
        e = self.entries[ei]
        k = li
        while k > 0 and e[k - 1].startswith('@'):
            k -= 1
            if e[k].startswith('@label='):
                del e[k]
                self._reindex(ei)
                return

    def describe(self, a, paras):
        """Append paragraphs to the description of the entry starting at a."""
        ei = self.starts[a]
        e = self.entries[ei]
        first = next(i for i, ln in enumerate(e) if LINE.match(ln) or ln.startswith('@label='))
        hdr = [i for i in range(first) if e[i].startswith(';')]
        if not hdr:
            k = next((i for i, ln in enumerate(e) if not ln.startswith('@')), 0)
            e[k:k] = ['; Routine at $%04X' % a, ';'] + self._paras(paras)
            self._reindex(ei)
            return
        lo, hi = hdr[0], hdr[-1] + 1
        sect, cur = [], []
        for ln in e[lo:hi]:
            if ln.strip() == ';':
                sect.append(cur)
                cur = []
            else:
                cur.append(ln)
        sect.append(cur)
        ours = self._paras(paras)
        if len(sect) == 1:
            sect.append(ours)
        elif [ln.strip() for ln in sect[1]] == ['; .']:
            sect[1] = ours
        else:
            sect[1] = sect[1] + ['; .'] + ours
        new = []
        for i, s in enumerate(sect):
            new += (([';'] if i else []) + s)
        e[lo:hi] = new
        self._reindex(ei)

    @staticmethod
    def _paras(paras):
        out = []
        for i, p in enumerate(paras):
            if i:
                out.append('; .')
            out.append('; ' + p)
        return out

    def midblock(self, a, paras):
        """A mid-block comment above the instruction at a."""
        ei, li = self.at[a]
        e = self.entries[ei]
        k = li
        while k > 0 and e[k - 1].startswith('@'):
            k -= 1
        e[k:k] = self._paras(paras)
        self._reindex(ei)

    def group_start(self, a):
        """The first instruction of the {...} comment group holding a, or a."""
        ei, li = self.at[a]
        e = self.entries[ei]
        depth, start = 0, None
        for ln in e[:li + 1]:
            m = LINE.match(ln)
            c = ln.split(';', 1)[1].strip() if ';' in ln else ''
            if m and depth == 0:
                start = int(m.group(2), 16)
            depth += len(c) - len(c.lstrip('{'))
            depth -= len(c) - len(c.rstrip('}'))
            depth = max(depth, 0)
        return start if start is not None else a

    def comment(self, a, text):
        """Append to the instruction comment at a; -> where it went."""
        g = self.group_start(a)
        ei, li = self.at[a]
        e = self.entries[ei]
        last = li
        while last + 1 < len(e) and e[last + 1].lstrip().startswith(';') and e[last + 1].startswith(' '):
            last += 1
        own = ''.join(ln.split(';', 1)[1] for ln in e[li:last + 1] if ';' in ln).strip()
        grouped = g != a or own.startswith('{')
        if grouped:
            note = ['$%04X: %s' % (a, text)] if g != a else [text]
            if g in self.starts:          # above the first line would join the header
                self.describe(g, note)
                return 'description'
            self.midblock(g, note)
            return 'midblock'
        ln = e[last]
        if ';' in ln:
            body = ln.split(';', 1)[1].rstrip()
            e[last] = ln.split(';', 1)[0] + ';' + (body + ' -- ' if body.strip() else ' ') + text
        else:
            e[last] = ln.rstrip().ljust(19) + ' ; ' + text
        return 'comment'


def fact_text(f):
    extra = ''
    if f.get('window'):
        extra = ' (window %s, N=%s)' % (f['window'], f.get('n', '?'))
    return '[%s] %s%s (by: %s)' % (f.get('kind', '?'), f.get('says', ''), extra, f.get('by', ''))


def overlay(sk, syms, routines, topics, notes):
    lines_at = set(sk.at)
    unplaced = []
    # labels
    ref = sk.labels()
    ours = {a: n for a, n in syms.items()}
    bad = [a for a, n in ours.items() if not LABEL_OK.match(n)]
    for a in bad:
        unplaced.append('label %s $%04X: not a valid SkoolKit label' % (ours.pop(a), a))
    names = set(ours.values())
    dropped = []
    for a, n in sorted(ref.items()):
        if n in names and ours.get(a) != n:
            sk.drop_label(a)
            if a not in ours:
                dropped.append('%s@$%04X' % (n, a))
    placed = displaced = 0
    disagree = []
    for a, n in sorted(ours.items()):
        if a not in sk.at:
            unplaced.append('label %s $%04X: no skool line starts there' % (n, a))
            continue
        sk.set_label(a, n)
        placed += 1
        old = ref.get(a)
        if old and old != n:
            displaced += 1
            disagree.append('$%04X %s (ref %s)' % (a, n, old))
    notes.append('labels: %d ours placed, %d replaced a different reference name, '
                 '%d reference labels dropped as duplicates of ours elsewhere'
                 % (placed, displaced, len(dropped)))
    for d in disagree:
        notes.append('  ours over ref: ' + d)
    for d in dropped:
        notes.append('  dropped ref duplicate: ' + d)
    # ledgers
    desc = mid = com = 0
    for d in routines:
        entries = [hexaddr(x) for x in d.get('entries', [])]
        if not entries:
            continue
        a = entries[0]
        head = '%s -- port %s; ledger %s; oracle %s; fixtures %s; manual %s' % (
            d.get('name', '?'), d.get('port') or '-', d['rel'], d.get('oracle') or '-',
            ', '.join(d.get('fixtures', [])) or '-', ', '.join(d.get('manual', [])) or '-')
        paras = [esc(head, lines_at)]
        for f in d.get('fact', []):
            if not f.get('at') or hexaddr(f['at']) == a:
                paras.append(esc(fact_text(f), lines_at))
        for f in d.get('refuted', []):
            paras.append(esc('[refuted] %s (by: %s)' % (f.get('says', ''), f.get('by', '')), lines_at))
        for f in d.get('open', []):
            paras.append(esc('[open] %s (tried: %s; settle: %s)'
                             % (f.get('ask', ''), f.get('tried', ''), f.get('settle', '')), lines_at))
        if a in sk.starts:
            sk.describe(a, paras)
            desc += 1
        elif a in sk.at:
            sk.midblock(a, paras)
            mid += 1
        else:
            unplaced.append('ledger %s $%04X: no skool line starts there' % (d['rel'], a))
        for f in d.get('fact', []):
            if not f.get('at') or hexaddr(f['at']) == a:
                continue
            fa = hexaddr(f['at'])
            if fa not in sk.at:
                unplaced.append('fact %s at $%04X: no skool line starts there' % (d['rel'], fa))
                continue
            sk.comment(fa, esc(fact_text(f), lines_at))
            com += 1
    tops = 0
    for t in topics:
        for x in t.get('routines', []):
            a = hexaddr(x)
            para = [esc('topic: %s (%s)' % (t.get('name', '?'), t['rel']), lines_at)]
            if a in sk.starts:
                sk.describe(a, para)
            elif a in sk.at:
                sk.midblock(a, para)
            else:
                unplaced.append('topic %s $%04X: no skool line starts there' % (t['rel'], a))
                continue
            tops += 1
        for f in t.get('fact', []):
            if f.get('at'):
                fa = hexaddr(f['at'])
                if fa in sk.at:
                    sk.comment(fa, esc(fact_text(f), lines_at))
                    com += 1
                else:
                    unplaced.append('fact %s at $%04X: no skool line starts there' % (t['rel'], fa))
    notes.append('ledgers: %d entry descriptions, %d mid-entry notes, %d instruction facts, '
                 '%d topic notes' % (desc, mid, com, tops))
    return unplaced


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ref', metavar='CTL', help='third-party control file for the block layout')
    ap.add_argument('--out', default='build/skool')
    ap.add_argument('--image', default=None)
    ap.add_argument('--no-html', action='store_true')
    ap.add_argument('--strict', action='store_true', help='exit 1 on any unplaced record')
    ap.add_argument('--entry', type=lambda s: int(s, 0), help='print the skool entry holding ADDR')
    a = ap.parse_args(argv)

    from skoolkit import sna2skool, skool2html
    out = portconfig.path(a.out)
    os.makedirs(out, exist_ok=True)
    notes = []
    routines, topics = ledgers()
    syms = symbols()
    starts = {hexaddr(d['entries'][0]) for d in routines if d.get('entries')}
    names = {hexaddr(d['entries'][0]): d.get('name', '') for d in routines if d.get('entries')}

    img = image_bytes(a.image or portconfig.path(portconfig.get('z80', 'image')))
    binp = os.path.join(out, 'fist.bin')
    open(binp, 'wb').write(img)
    if a.ref:
        ctl = modernise(open(a.ref, encoding='utf-8').read(), notes)
        ctl = split_ctl(ctl, starts, names, notes)
    else:
        ctl = minimal_ctl(img, starts, syms, names)
        notes.append('ctl: minimal, %d code entries' % ctl.count('\nc '))
    ctlp = os.path.join(out, 'fist.ctl')
    open(ctlp, 'w', encoding='utf-8').write(ctl)

    raw = run_skoolkit(sna2skool, ['-H', '-c', ctlp, '-o', '0', binp])
    sk = Skool(raw)
    unplaced = overlay(sk, syms, routines, topics, notes)
    skp = os.path.join(out, 'fist.skool')
    open(skp, 'w', encoding='utf-8').write(sk.text())

    if a.entry is not None:
        hit = [ei for ei, e in enumerate(sk.entries) if any(
            LINE.match(ln) and int(LINE.match(ln).group(2), 16) == a.entry for ln in e)]
        for ei in hit:
            print('\n'.join(sk.entries[ei]))
        return 0 if hit else 1

    for n in notes:
        print(n)
    for u in unplaced:
        print('UNPLACED ' + u)
    print('skool: %s (%d entries, %d lines)' % (os.path.relpath(skp), len(sk.entries),
                                                  sum(len(e) for e in sk.entries)))
    rc = 1 if (a.strict and unplaced) else 0
    if not a.no_html:
        args = ['-q', '-H', '-d', os.path.join(out, 'html'), '-c', 'Config/GameDir=fist',
                '-c', 'Paths/CodeFiles={address:04X}.html',
                '-c', 'Game/Game=The Way of the Exploding Fist (port annotations)']
        refs = []
        if a.ref:
            rdir = os.path.dirname(os.path.abspath(a.ref))
            base = os.path.splitext(os.path.basename(a.ref))[0]
            if os.path.exists(os.path.join(rdir, base + '.py')):
                args += ['-W', '%s:%s.WayOfTheExplodingFistHtmlWriter' % (rdir, base)]
            if os.path.exists(os.path.join(rdir, base + '.ref')):
                refs.append(os.path.join(rdir, base + '.ref'))
        try:
            run_skoolkit(skool2html, args + [skp] + refs)
            print('html: %s' % os.path.relpath(os.path.join(out, 'html', 'fist', 'index.html')))
        except Exception as e:                      # noqa: BLE001 -- name it, never hide it
            print('HTML FAILED: %s: %s' % (type(e).__name__, e))
            rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main())
