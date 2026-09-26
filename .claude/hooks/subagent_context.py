#!/usr/bin/env python3
"""
SubagentStart hook: give each sub-agent what it cannot get elsewhere.

Sub-agents start without the conversation, and the built-in Explore and Plan
agents do not load CLAUDE.md, so this adds a short block to the start of
every sub-agent's context (manual 12.7, 12.8).  It is a backstop; the
generated brief is the main channel.  Test once that it arrives: ask a
sub-agent what it knows about tools/manual.py.  Always exits 0.
"""
import json
import sys

CONTEXT = (
    "This project ports a ZX Spectrum game to JavaScript from its Z80 code. "
    "The method manual docs/PORTING-ZX-TO-JS.txt and the traps docs/TRAPS.md "
    "are read by ID with python tools/manual.py (C9, 6.11, T146; --index lists "
    "IDs; --grep TERM names what mentions a term), never whole. The entries "
    "most relevant to reading Z80 are C8 (one body, two entries), C9 (a loop's "
    "extent comes from its displacement), C10 (flags that nothing reads) and "
    "A8 (backward-decode verdicts are hints). The lead checks every finding by "
    "script, so findings are most useful as typed claims, one JSON object per "
    "line with a \"kind\" field: insn {at, insn, count}, jr_target {at, target}, "
    "falls_into {at, target}, flags_dead {at, flag}, in_loop {at, loop, inside}, "
    "writes {routine, window}, reads {routine, address}. A finding that fits no "
    "kind is labelled HYPOTHESIS. Addresses are written as $-prefixed hex, such "
    "as $9561.")

if __name__ == '__main__':
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'SubagentStart',
        'additionalContext': CONTEXT}}))
    sys.exit(0)
