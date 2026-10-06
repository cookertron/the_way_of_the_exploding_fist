# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     9AD7 -- next play-pass callee, taken the same way as 97BB: callio --capture fixture, adis, JS port, gate
Step:     python tools/status.py 9AD7 ; capture its call site with callio.py --capture (and --derive for unreached exits), then adis and port
Then:     9ED2/9D29 hit tests; 9C6F timer is small; 97CB AI and A3FF open 1 last; 95D4 open 1 (ROM bytes as data) needs the user
Blocked:  95D4 port waits on the user: ROM bytes as data (manual 0.5)
Notes:    97BB ported and gated (170 cases, 11 derived); callio.py now has --capture/--check/--derive; play states s1 and p1b ignore most key scripts (few new cases); web/fist.html still the untracked built page
