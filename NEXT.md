# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AC27 Start_1UP_Game $AC3E / Start_2UP_Game $AD9C -- Num_Players 1/2 at $AC27 (the demo quit by 1/2/Kempston fire, RET M)
Step:     python tools/callio.py --capture --state p1 --call 0xAC27 ... with a key script that presses 1 in the demo (keyprobe syntax); gameDispatch's nonzero branch stays at $AC27 until then (D7)
Then:     the demo's time up and round end (ABB9 open 1); the menu generator (8C54 open 1) retires D7
Blocked:  none
Notes:    live_p1 is 3000 passes now and runs clean to its last row through the new demo; the machine spreads 0.55% on identical stage passes (ABB9 fact 5), so new-demo stage rows are gated at 0.7%
