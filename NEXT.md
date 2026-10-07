# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AD44 time_up -- time up: the round end $AE67, the decision $AD44 and the draw's pose $ACE8 gated exact (3 fixtures, 7 cases) and live sample for sample to $AC5F
Step:     the 1UP game loop $AC5F-$ACDA: next bout after the draw ($AC5F), rank up after a win ($ACAC-$ACCC, $AF27), the lost bout's RET ($ACD9); bracket from $ACA6 with A = 0/1/$81
Then:     the menu generator (8C54 open 1), which retires D7
Blocked:  none
Notes:    callio ends a bracket only on a return (SP + 2): a JP at the same SP (ACA6 to AC5F) needs the next CALL's return as the end; live gate now takes the way out (lost/won/draw) and stops at the first row reaching $ACA6
