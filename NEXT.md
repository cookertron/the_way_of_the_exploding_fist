# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AD9C Start_2UP_Game -- Num_Players 2 at $AC27 (the demo quit by key 2), its own loop to its first $AE29
Step:     python tools/callio.py --capture --state p1 --call 0xAC27 0xAE29 --frames 4000 --keys 2 --per 1 with setup_ac5f's blinds; gameDispatch's n > 1 branch stays at $AC27 until then
Then:     the options menu $8C54 (key 0 in the demo: 8C54 open 1); the demo's time up and round end (ABB9 open 1)
Blocked:  none
Notes:    the page now boots at $8800 into the attract demo (bootPass, live_boot gated 1500 rows; D7 ended); key 2 and key 0 in the demo still stop the engine (.exit) until ported; mutation runs use --jobs 20 at most (CLAUDE.md)
