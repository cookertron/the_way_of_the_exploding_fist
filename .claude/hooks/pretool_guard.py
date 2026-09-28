#!/usr/bin/env python3
"""
PreToolUse hook (matcher "Read|Bash"): two guards that replace remembering
(manual 12.8; docs/TRAPS-MAP.md, mechanism `hook`).

1. The manual and the traps are read by ID, never whole.  Together they are
   well over 100,000 tokens, and they are the first thing a compaction
   discards.  A Read of docs/PORTING-ZX-TO-JS.txt or docs/TRAPS.md with no
   limit, or a limit above MAX_LINES, is refused, as is cat, less, more, nl,
   tac or bat of either with no pipe; the refusal says how to read by ID.
   tools/manual.py, grep, sed -n ranges, head and tail all pass.  Anything
   frozen under docs/archive/ is guarded the same way (manual 12.11).
2. Source files are written with the Write or Edit tool, never through a
   shell heredoc.  Bubble Bobble lost fifteen edits to shell escaping before
   that became a rule (TRAPS #149, #168).  A cat or tee heredoc into a .py,
   .js, .ts, .json or .html file is refused; running a script from a heredoc
   (python - << EOF) is not.

A refusal is a deliberate JSON decision.  Anything else -- including a crash
in this script -- lets the call through: it exits 0 every time.  This is a
guard rail, not a security boundary.
"""
import json
import re
import sys

MAX_LINES = 200
GUARDED = {
    'PORTING-ZX-TO-JS.txt': 'python tools/manual.py ID [ID ...], for example C9 6.11 Q13',
    'TRAPS.md': 'python tools/manual.py T<number>, for example T146',
}
WHOLE_FILE = re.compile(r'(^|[\s;&(])(cat|less|more|nl|tac|bat)(\s|$)')
HEREDOC_WRITE = re.compile(r'\b(cat|tee)\b[^;&|\n]*<<')
CODE_TARGET = re.compile(
    r'(?:>>?|\btee\s+(?:-a\s+)?)\s*["\']?[^\s"\';&|>]*\.(?:py|js|mjs|cjs|ts|json|html)\b')


def refuse(reason):
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': reason}}))


ARCHIVE = 'docs/archive/'
ARCHIVE_REASON = (
    'docs/archive/ holds frozen history, read by search and line range, never whole '
    '(manual 12.11): grep -n TERM docs/archive/FILE, then a Read with an offset and a '
    'limit of at most %d lines around the match.' % MAX_LINES)


def read_reason(name):
    return ('%s is read by ID, not whole (manual 0.7 and 12.8). Use %s; '
            'python tools/manual.py --grep TERM names the entries and traps that '
            'mention a term, and --index lists IDs. A Read with an offset and a '
            'limit of at most %d lines is also allowed.' % (name, GUARDED[name], MAX_LINES))


HEREDOC_REASON = (
    'Write source files with the Write or Edit tool, not a shell heredoc: shell '
    'escaping silently changed fifteen edits in Bubble Bobble (TRAPS #149, #168). '
    'For generated source, have a script write a temporary file, check it '
    '(python -m py_compile, node --check), then move it into place.')


def main():
    data = json.load(sys.stdin)
    tool = data.get('tool_name')
    args = data.get('tool_input') or {}
    if tool == 'Read':
        path = str(args.get('file_path', '')).replace('\\', '/')
        name = path.split('/')[-1]
        if '/' + ARCHIVE in '/' + path.lstrip('./') or path.startswith(ARCHIVE):
            try:
                limit = int(args.get('limit'))
            except (TypeError, ValueError):
                limit = None
            if limit is None or limit > MAX_LINES:
                refuse(ARCHIVE_REASON)
            return
        if name in GUARDED:
            try:
                limit = int(args.get('limit'))
            except (TypeError, ValueError):
                limit = None
            if limit is None or limit > MAX_LINES:
                refuse(read_reason(name))
    elif tool == 'Bash':
        cmd = str(args.get('command', ''))
        if HEREDOC_WRITE.search(cmd) and CODE_TARGET.search(cmd):
            refuse(HEREDOC_REASON)
            return
        if 'manual.py' in cmd or '|' in cmd or not WHOLE_FILE.search(cmd):
            return
        if ARCHIVE in cmd:
            refuse(ARCHIVE_REASON)
            return
        for name in GUARDED:
            if name in cmd:
                refuse(read_reason(name))
                return


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
