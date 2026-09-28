#!/usr/bin/env python3
"""
SessionStart hook: put the project's state back into Claude's context.

It runs for every SessionStart source -- startup, resume, clear, compact and
fork -- so this is how the status returns after a compaction (manual 12.8).
Plain text on stdout is added to Claude's context.  The text is written as
statements of fact, kept under the 10,000-character cap on hook output, and
nothing here can block anything: the script always exits 0.

What it prints:
  - how the manual and the traps are read (the rule every compaction would
    otherwise take with it);
  - tools/status.py --brief, once status.py exists (manual 12.4);
  - the uncommitted changes, which ARE the unit in progress -- derived from
    git rather than remembered -- and the last few commits;
  - the manual IDs and trap numbers named by the "manual = [...]" line of any
    ledger entry among those changes (manual 12.2), so the session re-reads
    exactly those.
"""
import json
import os
import re
import subprocess
import sys

CAP = 9000                      # hook output is capped at 10,000 characters
ROOT = os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd()
MAX_CHANGED = 15


def run(args, timeout):
    try:
        r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except Exception as exc:    # no git, a timeout, anything at all
        return None, '(%s did not run: %s)' % (args[0], exc)


def changed_path(porcelain_line):
    path = porcelain_line[3:].strip()
    if ' -> ' in path:          # a rename: keep the new name
        path = path.split(' -> ', 1)[1]
    return path.strip('"')


def manual_ids(paths):
    ids = []
    for path in paths:
        if not (path.startswith('ledger/') and path.endswith('.toml')):
            continue
        try:
            with open(os.path.join(ROOT, path), encoding='utf-8') as f:
                text = f.read()
        except OSError:
            continue
        m = re.search(r'^\s*manual\s*=\s*\[([^\]]*)\]', text, re.M)
        if m:
            for i in re.findall(r'"([^"]+)"', m.group(1)):
                if i not in ids:
                    ids.append(i)
    return ids


def main():
    try:
        source = json.load(sys.stdin).get('source', 'unknown')
    except Exception:
        source = 'unknown'
    out = [
        'Session context (source: %s), printed by '
        '.claude/hooks/session_context.py.' % source,
        'The manual (docs/PORTING-ZX-TO-JS.txt) and the traps (docs/TRAPS.md) '
        'are read by ID with python tools/manual.py: IDs such as C9 or 6.11, '
        'traps such as T146; --index lists IDs, --grep TERM names what mentions '
        'a term, and --map shows which traps each mechanism must prevent. '
        'Whole-file reads of either document are refused by a hook.',
    ]

    # The tool names are the cue that survives compaction; the details are a
    # query away.  Read from the directory, so a port's own scripts appear too.
    try:
        names = sorted(f[:-3] for f in os.listdir(os.path.join(ROOT, 'tools'))
                       if f.endswith('.py'))
    except OSError:
        names = []
    if names:
        listed = ' '.join(names)
        if len(listed) > 1500:
            listed = listed[:1500].rsplit(' ', 1)[0] + ' ...'
        out.append('Tools in tools/ -- python tools/manual.py --tools TERM gives '
                   "each one's purpose and usage, and a tool's --help the rest; read "
                   'it before extending a tool or writing a new one: ' + listed)

    status = os.path.join(ROOT, 'tools', 'status.py')
    status_text = ''
    if os.path.isfile(status):
        code, text = run([sys.executable, status, '--brief'], timeout=30)
        status_text = text.strip()
        out.append('Project status (tools/status.py --brief):')
        out.append(status_text or '(no output)')
    else:
        out.append('tools/status.py does not exist yet. It is PLANNED and is '
                   'the first tool to build (manual 12.10). Until it exists, '
                   "the project's state is what ledger/ and the git log show.")

    # -uall lists new files one by one; otherwise a new ledger/ is one line
    code, text = run(['git', 'status', '--porcelain', '--untracked-files=all'],
                     timeout=15)
    if code == 0:
        changed = [l for l in text.splitlines() if l.strip()]
        if changed:
            out.append('Uncommitted changes -- the unit in progress '
                       '(%d files):' % len(changed))
            out.extend('  ' + l for l in changed[:MAX_CHANGED])
            if len(changed) > MAX_CHANGED:
                out.append('  ... and %d more' % (len(changed) - MAX_CHANGED))
            ids = manual_ids([changed_path(l) for l in changed])
            if ids and not all(i in status_text for i in ids):   # else the status said it
                out.append('Manual entries and traps named by the ledger entries '
                           'in progress: %s (python tools/manual.py %s)'
                           % (' '.join(ids), ' '.join(ids)))
        else:
            out.append('The working tree is clean: no unit is in progress.')
        code, text = run(['git', 'log', '-3', '--format=%h %s'], timeout=15)
        if code == 0 and text.strip():
            out.append('Last commits:')
            out.extend('  ' + l for l in text.strip().splitlines())

    text = '\n'.join(out)
    if len(text) > CAP:
        text = text[:CAP - 60] + '\n... (cut to stay under the hook output cap)'
    print(text)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
