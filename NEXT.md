# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     gate helpers, part 2: move the remaining fixture gates (sprdec, 9C6F, 97CB, 976F, 9745, AE26 onward) onto rig.gate.replay, with the corrupt and masked rows
Step:     first ledger/8C54.toml open 1: cap the port reads in the menu replay so the two crashing menu mutants FAIL a row; then one block at a time, row names kept (mutants.json kills by name)
Then:     world builders and the on/off identity gate (map: gate, 38 BUILD); per-verdict stamps and pruning for mutants.py (6.12 steps 4, 6); byte-usage map and roster (12.5, 12.6); brief.py, verify_claims.py (12.7)
Blocked:  none
Notes:    mutation runs use --jobs 4 (D8). Last full run 2026-10-08 17:10: 605/608 killed, 0 survivors, 0 timeouts, 3 crashes (boot LDIR; the two 8C54 menu cases). rig.gate returns verdicts; blocks keep their check() rows
