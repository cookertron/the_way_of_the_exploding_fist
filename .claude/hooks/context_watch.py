#!/usr/bin/env python3
"""
PostToolUse hook: tell Claude when the context passes the handover mark.

Opus models are not told how full their context is (Sonnet and Haiku are),
so without this a long unit runs on until automatic compaction lands wherever
the window happens to fill (manual 12.8, 12.11).  After each tool call this
reads the latest token usage from the session transcript -- input, cache
reads and cache writes of the most recent response -- and, the first time
the total passes ZX_HANDOVER_TOKENS (default 150,000) and again at each
further ZX_HANDOVER_STEP (default 50,000), adds one short note to Claude's
context: hand over at the next clean point.

Tune both in the "env" block of .claude/settings.json.  The note is written
as a statement of fact.  A failure here never blocks: it always exits 0.
"""
import json
import os
import re
import sys
import tempfile

TAIL = 512 * 1024          # read only the end of a long transcript


def latest_tokens(path):
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - TAIL))
            lines = f.read().decode('utf-8', errors='replace').splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        usage = (obj.get('message') or {}).get('usage') if isinstance(obj, dict) else None
        if isinstance(usage, dict):
            return sum(int(usage.get(k) or 0) for k in
                       ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
    return None


def main():
    data = json.load(sys.stdin)
    tokens = latest_tokens(data.get('transcript_path') or '')
    if not tokens:
        return
    mark = int(os.environ.get('ZX_HANDOVER_TOKENS') or 150000)
    step = max(1, int(os.environ.get('ZX_HANDOVER_STEP') or 50000))
    level = 0 if tokens < mark else 1 + (tokens - mark) // step
    sid = re.sub(r'[^A-Za-z0-9_-]', '', str(data.get('session_id') or 'session'))[:64]
    state = os.path.join(tempfile.gettempdir(), 'zx-context-watch-%s.json' % sid)
    try:
        with open(state) as f:
            last = int(json.load(f).get('level', 0))
    except (OSError, ValueError):
        last = 0
    if level != last:                     # remember falls too: after a compaction it can rise again
        try:
            with open(state, 'w') as f:
                json.dump({'level': level}, f)
        except OSError:
            pass
    if level > last:
        note = ('Context check: this conversation now carries about {:,} tokens, past the '
                "kit's handover mark of {:,}.  The kit's handover at the next clean point is: "
                'finish the current step, record anything unsettled in the ledger '
                '(python tools/record.py), update NEXT.md (python tools/record.py next), '
                'commit, and tell the user a /clear is safe (CLAUDE.md, session routine).'
                ).format(tokens, mark)
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PostToolUse',
                                                 'additionalContext': note}}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
