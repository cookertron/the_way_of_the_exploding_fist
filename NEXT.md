# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     the full mutation battery run that is due (gate-helper and fixture changes, the boot crash fix)
Step:     python tools/mutants.py --background --jobs 4 ; read build/mutants/summary.txt when it lands -- expect 0 crashes
Then:     world builders (boundaries, wraps, both instances, every field seeded), an engine-step helper that turns a throw into a named FAIL (T197), per-verdict stamps, roster
Blocked:  none
Notes:    last.json still holds pre-00:45 verdicts (25 SURVIVED, 4 TIMEOUT, incl. 'boot: $C425 not cleared') the full run will refresh; check that one if it times out again. Mutation runs --jobs 4 (D8)
