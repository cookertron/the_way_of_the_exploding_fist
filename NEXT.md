# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     8803 open 1 -- charge stack contention (0-7.2% of a call) and the $C3F0 display-copy contention in the D3 tally
Step:     count stack accesses per call in sprdec.py, fit extra T per access against tc in build/sprdec_cases.json; decide mean factor vs per-access by 7.2 clock phase; same question for $C3F0
Then:     read $C1F6 box min/max and $C34F/$C36E part loop; A3FF open 1 when the AI pass is read; battery open 1 (won bout / 2P); $B15A sound blocks inline
Blocked:  none
Notes:    spriteDecode ported and gated (441 cases, bytes + T exact; 22 mutants in test/mutants.json, suite test/kit.test.js via port.json). Raw and empty rows ported but ungated (never seen in play). Mirror always paired with recolour
