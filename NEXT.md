# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AD18 round_loop's way in -- $AD18 CALL $AE26, through CALL $9CA8 to $AE29, so a bout follows a bout live (won and drawn bouts now stop at the CALL $AD18)
Step:     callio.py --capture --call 0xAD18 0xAE29 (or sample $AE26 to $AE29 over live_p1w): what $AE26 does before $AE29 and $9CA8; port it, then let Fist go on from .exit at $AD18 into roundPass, the live gate following the next bout's rows
Then:     the lost bout's way on from $AC39; then the menu generator (8C54 open 1), which retires D7
Blocked:  none
Notes:    live_p1w now ranks up (poke $AA3C=1) so the tune and stage 3 run; text rows above $4800 are D5 font, so the $AD18 row checks the display by the $4800-$5AFF hash; setup charged by SETUP_K means
