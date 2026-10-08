# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     gate helpers, part 2: move the remaining fixture gates (sprdec, 9C6F, 97CB, 976F, 9745, AE26 onward) onto rig.gate.replay, with the corrupt and masked rows
Step:     one block at a time, row names kept (mutants.json kills by name); sprdec fills with 0 today: try the poison, record what breaks
Then:     world builders and the on/off identity gate (map: gate, 38 BUILD); per-verdict stamps and pruning for mutants.py (6.12 steps 4, 6); byte-usage map and roster (12.5, 12.6); brief.py, verify_claims.py (12.7)
Blocked:  the full run of 2026-10-08 left 184 TIMEOUTS at 20 workers -- contention (ledger/topics/battery.toml fact 13); re-running them needs fewer workers than CLAUDE.md's 20, so ask the user
Notes:    rig.gate returns verdicts; blocks keep their own check() rows, since tools/mutants.js finds blocks by the check calls written in them. mutants.py now resolves "rig.js" cases to test/. Full mutation run is due
