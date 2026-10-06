# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     9D29 -- the P1-hits-P2 counterpart of 9ED2, the same way: callio --capture fixture, adis, JS port, gate
Step:     python tools/status.py 9D29 ; callio.py --capture --call 0x974B 0x974E over s1, p1, p1b x key scripts (6000 frames), then --derive for unreached branches
Then:     95D4 (ROM reads only steer which $FF is copied: write $FF); 97CB AI and A3FF open 1 last
Blocked:  none
Notes:    9ED2 gated, 60 cases (18 derived; play never had $AA17 set at a hit); 9D29 likely mirrors 9ED2 with $AA03/$AA43 swapped -- diff the adis before porting; web/fist.html still untracked
