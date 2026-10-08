# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     the options menu $8C54 (key 0 in the demo: 8C54 open 1)
Step:     python tools/status.py 8C54; read the menu's listing and sample key 0 from the demo
Then:     the demo's time up and round end (ABB9 open 1)
Blocked:  none
Notes:    $AE17 done: the whole 2UP game follows live_2up for 2400 rows; the suite is 55 s alone now, so mutation runs on 20 workers time out at 180 s per case -- re-run TIMEOUTs with --match on 10 workers (CLAUDE.md caps --jobs at 20)
