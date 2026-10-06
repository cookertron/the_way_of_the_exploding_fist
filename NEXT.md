# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     9C6F -- the small timer, then 9ED2/9D29 hit tests, each taken the 97BB/9AD7 way: callio --capture fixture, adis, JS port, gate
Step:     python tools/status.py 9C6F ; find its call site in the $9745 play pass, callio.py --capture (and --derive for unreached exits), then adis and port
Then:     9ED2/9D29 hit tests; 97CB AI and A3FF open 1 last; 95D4 open 1 (ROM bytes as data) needs the user
Blocked:  95D4 port waits on the user: ROM bytes as data (manual 0.5)
Notes:    9AD7+9B9D ported and gated (38 cases, 2 derived); $9B41-$9B66 unreachable, not ported; callio gates now poison unread memory $A5 (T44); web/fist.html still the untracked built page
