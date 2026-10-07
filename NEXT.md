# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AD5F p1_wins_bonus -- P1 wins the 1UP bout: pose $AE7A and the time bonus gated exact (2 cases, 23.27M / 16.44M T) and live sample for sample to $ACA6 won
Step:     $AD44 time up: compare counts $AA01/$AA41 then $AA02/$AA42; $AD5C (P1 ahead) and $AD91 (P2) reach the poses; $AD99 the draw returns $81. Derive from point_ad1b's time case (0x9C2B=1) into a bracket $AD44 to $ACA6
Then:     the 1UP game loop $AC5F-$ACDA around $AD18 (rank up, $ACE8), then the menu generator (8C54 open 1), which retires D7
Blocked:  none
Notes:    callio cases now carry 'up' (caller bytes at SP) so --check replays a bracket that RETs through its caller; sample.py --poke builds constructed starts (live_p1w); full --background mutant run started after this commit
