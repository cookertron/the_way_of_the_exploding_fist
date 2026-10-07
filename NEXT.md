# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AC27 Main_Game_Loop's dispatch -- Num_Players 0 (the demo's RET at rank 4): JR Z to $AC09 and a new demo; demoIn split at $AC09 (mainLoop) so demoNextPass runs on in the same pass
Step:     python tools/callio.py --capture --state p1 --call 0xAC27 0xAE29 --frames 12000 (live reaches $AC27 at frame ~11090, row 2543) ; resample live_p1 with --passes 3000 (port.json live note) so live runs on through the second demo
Then:     the quit with a key held in the demo, RET M to $AC27, Start_1UP_Game $AC3E / Start_2UP_Game $AD9C; the demo's time up and round end (ABB9 open 1); the menu generator (8C54 open 1) retires D7
Blocked:  none
Notes:    3000 passes: demo exits are all poses (rows 801, 1407, 2142, 2543 rank 4 to $AC27/$AC09, 2830) -- no demo bout ends on time; SCEN_K is per stage now (ABB9 fact 4)
