# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     97BB -- port fighter_step (move/frame advance, own record + tables $B464-$B47A) to JS, gated by a frozen per-call fixture
Step:     give callio.py a --capture/--check fixture mode (rendfx shape, any call) and capture $9763/$976C; then adis $9920 $9994 $9AA1
Then:     9AD7 the same way; then 9ED2/9D29 hit tests; 9C6F timer is small; 97CB AI and A3FF open 1 last; 95D4 open 1 (ROM bytes as data) needs the user
Blocked:  95D4 port waits on the user: ROM bytes as data (manual 0.5)
Notes:    every play-pass callee interface measured with tools/callio.py and recorded; tools/sample.py samples bytes at a PC (gate half); web/fist.html still the untracked built page
