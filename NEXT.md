# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     the remaining still-to-build items, in CLAUDE.md's table order: gate helpers in test/rig.js
Step:     python tools/manual.py --map gate; read each trap, design helpers that make each failure unwritable, gate them in kit.test.js
Then:     per-verdict stamps and pruning for mutants.py (6.12 steps 4, 6); the byte-usage map and roster (12.5, 12.6); brief.py, verify_claims.py (12.7)
Blocked:  none
Notes:    measure.py exists, no oracle calls it yet: new oracles use it and pass --lint (10 raw comparisons in older tools, not oracles of measure). Writes below $4000 are invisible to it (SkoolKit drops them). Full mutation run is due (20 workers)
