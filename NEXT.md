# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     9ED2 -- hit test, then 9D29, each the 97BB/9AD7/9C6F way: callio --capture fixture, adis, JS port, gate
Step:     python tools/status.py 9ED2 ; callio.py --capture --call 0x9748 0x974B (+ --derive for unreached exits), then adis and port
Then:     9D29; 95D4 now unblocked (ROM reads only steer which $FF is copied: write $FF); 97CB AI and A3FF open 1 last
Blocked:  none
Notes:    9C6F + printer gated, 31 cases; lookalike font has space and 0-9 only, misses counted in fontMiss; callio --blind keeps ROM-copied outputs as addresses; web/fist.html still untracked
