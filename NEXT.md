# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     the demo's time up and round end (ABB9 open 1)
Step:     python tools/status.py ABB9; read the open question and sample the demo past a time up
Then:     the menu's other ways (sound, P2, joysticks) are gated by callio only; a live fixture if a bug shows there
Blocked:  none
Notes:    $8C54 is live (MenuSuspend, Fist.menuPass, replay of recorded reads; sample.py --reads). Mutation runs on 20 workers time out (suite ~55 s): re-run TIMEOUTs with --match on 10
