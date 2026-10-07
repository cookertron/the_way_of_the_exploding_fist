# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $ABB9 the demo's ways on -- demoPoint's p1/p2 (the poses at $AC00/$ABE5, then XOR A RET), time and the round end $AE67 to $ABB9: $AF27 stage up, rank up, $AB97 the next demo stage, or RET to $AC27
Step:     python tools/adis.py 0xABB6 10 ; resample live_p1 with more --passes (and --also 0xAE8E) to reach the demo's first pose or time up ; callio --capture --state p1 --call 0xABB9 0xAE29,0xAC27
Then:     the RET M quit to $AC27's dispatch and Start_1UP_Game $AC3E / Start_2UP_Game $AD9C; the menu generator (8C54 open 1) retires D7
Blocked:  none
Notes:    re-add ABCB's 3 dropped mutants once live reaches a demo exit (DEMO_OUT p1, the !this.demo guard on onward, roundPass's demoPoint choice); callio --derive --up seeds a caller's return
