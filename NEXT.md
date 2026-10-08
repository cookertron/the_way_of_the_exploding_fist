# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     the menu's other ways (sound, P2, joysticks), gated by callio only
Step:     python tools/status.py 8C54; sample the demo's key 0 with --reads choosing each of the menu's other options; a live fixture if a bug shows
Then:     tools/status.py --check for what else is open; the still-to-build tools (stamps for status.py first)
Blocked:  none
Notes:    sample.py --from N starts a fixture deep in a long play (live_dtime: --from 4250). Fist reads demo/2UP from round_loop's return address on the stack. Mutation runs: 10 workers (20 time out; suite ~60 s)
