# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AE17 the 2UP game's ways on -- time up and a point return from $AE26 to $AE17; next round by $AE1F JR Z $AE14, bout won at $ADE2
Step:     python tools/adis.py 0xAE14 20 ; sample.py live_2up past row 816 (machine re-enters $AE14 at rows 816, 1237); capture $AE17 with callio, key 2 in the demo
Then:     the options menu $8C54 (key 0 in the demo: 8C54 open 1); the demo's time up and round end (ABB9 open 1)
Blocked:  none
Notes:    2UP start ported (AD9C): the engine stops at $AE17 (.exit, D7) on the 2UP game's first way out; key 0 in the demo still stops the engine; mutation runs use --jobs 20 at most (CLAUDE.md)
