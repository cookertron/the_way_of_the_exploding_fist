# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AC39 the lost bout's way on -- CALL Check_HighScore ($A647), then JR Main_Game_Loop, so the live gate's P2 fixture runs past $AC39
Step:     python tools/adis.py 0xA647 60 and walk.py from $A647: the high-score check and its entry screen; callio.py --capture --call 0xAC39 0xAC3C over live's lost bout (a score above and below the table)
Then:     Main_Game_Loop and the menu generator (8C54 open 1), which retires D7; AD1B open 1 ($9C28 >= $80, RET M) still wants its bracket
Blocked:  none
Notes:    won and drawn bouts now run into the next bout live (setupPass, then enterPass = roundIn to $AE29); $AD18 samples inside a point are mid-pass, so liveGate drops them and carries their T on
