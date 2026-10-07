# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AD94 p2_wins_pose -- P2 wins the 1UP bout, the victory pose $AE9D gated exact (14.36M T, 66 passes) and live sample for sample to $ACA6
Step:     P1 wins: $AD5F calls $AE7A (P1's pose, twin of winPass with $AA0D) then the time-bonus count $AD62-$AD8E; bracket $AD5F to $ACA6 (derive from point_ad1b's p1 case), then $AD44 time-up and $AD99 the draw ($81)
Then:     the 1UP game loop $AC5F-$ACDA around $AD18 (rank up, $ACE8), then the menu generator (8C54 open 1), which retires D7
Blocked:  none
Notes:    sample.py --also PC gives inner-loop sub-rows; spriteDecode throws FIST_RUNAWAY on data with no end row (mutants.py diagnostic FIST_); $9C28 writers are $9B0A and $9CD5 (AD1B open 1); full --background mutant run started after this commit
