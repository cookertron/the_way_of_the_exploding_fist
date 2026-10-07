# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AC09 Main_Game_Loop -- the text rows, Demo_Mode $AB70 and the player-count dispatch, so the lost bout (live, out at $AC3C) and boot can reach the menu
Step:     python tools/adis.py 0xAB70 80 and walk.py from $AC09; live_p1.json rows after 336 are the machine's demo (round_loop again at $AE29): the next fixture to follow
Then:     the menu generator (8C54 open 1), which retires D7; AD1B open 1 ($9C28 >= $80, RET M) still wants its bracket
Blocked:  none
Notes:    Check_HighScore's 2UP path (also CALLed at $ADF3) is gated by derived cases only; the 1UP compare quirk (first lower byte decides) is faithful, ledger AC39 fact 1
