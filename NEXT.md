# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AE26 round_loop -- live on the 7.2 accumulator, gated row for row against p1 to the first point (168 passes), 23/23 loop mutants killed
Step:     the point-to-point path back into the loop from $AD18: $AF01, $900E, $AF36, $9CA8 (13-18k T; bracket from the CALL at $AD18 so the RET NZ frame is inside)
Then:     the menu generator (8C54 open 1), which retires D7
Blocked:  none
Notes:    page starts mid-bout (D7) and stops at the first point; live_p1.json rows run to pass 400 with a second point at 336; full --background mutant run started at this milestone
