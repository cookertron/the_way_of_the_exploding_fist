# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $ABCB the demo's point -- $AF01, Yin_Yang_1UP, $AF36, the pose at 4 ($AE7A/$AE9D), $ABF1 back to $ABC8, so live follows the demo past row 418
Step:     python tools/adis.py 0xABC8 30 ; callio --capture --state p1 --call 0xABCB 0xAE29,0xAC27 (after the lost bout) ; live_p1 rows 419-499
Then:     the RET M quit to $AC27's dispatch and Start_1UP_Game $AC3E / Start_2UP_Game $AD9C; the menu generator (8C54 open 1) retires D7
Blocked:  none
Notes:    AC09 open 1 lists the demo's unported ways out; roundPass(..., demo) returns 'ret' unplayed; demoIn's $9C2B write is redundant (roundIn clears it), no mutant can see it
