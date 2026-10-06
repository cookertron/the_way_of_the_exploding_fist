# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     9ED2 -- hit test, then 9D29, each the 97BB/9AD7/9C6F way: callio --capture fixture, adis, JS port, gate
Step:     python tools/status.py 9ED2 ; callio.py --capture --call 0x9748 0x974B (+ --derive for unreached exits), then adis and port
Then:     9D29; 97CB AI and A3FF open 1 last; 95D4 open 1 (ROM tables, not a font) still needs the user
Blocked:  95D4 port waits on the user: ROM $3100-$3AFE read as tables (D5 covered only the font)
Notes:    9C6F + printer (9336/9309/92E4/923A) gated, 31 cases; lookalike font has space and 0-9 only, misses counted in fontMiss; callio --blind keeps ROM-copied outputs as addresses; web/fist.html still untracked
