# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AD9C Start_2UP_Game -- Num_Players 2 at $AC27 (the demo quit by key 2), its own loop to its first $AE29
Step:     python tools/callio.py --capture --state p1 --call 0xAC27 0xAE29 --frames 4000 --keys 2 --per 1 with setup_ac5f's blinds; gameDispatch's n > 1 branch stays at $AC27 until then (D7)
Then:     the demo's time up and round end (ABB9 open 1); the menu generator (8C54 open 1) retires D7
Blocked:  none
Notes:    1UP start ported and gated (callio_ac27_1up, live_1up to row 1000); a quit pass leaves cost.t 0 now (was NaN); roundIn's pass is 1.6% contended after the start, gated at 2%
