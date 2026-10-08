# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AE17 the 2UP game's ways on -- twoOn, twoNext, twoEnd (AE17 opens 1, 2)
Step:     write them from scratch/PORT-PLAN.md; cp scratch/live_2up_new.json build/live_2up.json (2400 passes, marks + ADE2 ADF3 AC34) and rewrite liveGate's start2 checks; gate build/callio_ae17.json
Then:     the options menu $8C54 (key 0 in the demo: 8C54 open 1); the demo's time up and round end (ABB9 open 1)
Blocked:  none
Notes:    build/live_2up.json is the old 1500-pass sample until the port lands (the new one goes red at row 599 before it); AD9C open 2 settles with the new one; scratch/gen2up.py regenerates; mutation runs use --jobs 20 at most (CLAUDE.md)
