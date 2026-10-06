# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     phase 10 read the render pipeline $BF13 -> $C1A2 -> $C34F -> $C36E -> $C2B5 -> sprite decoder $8803
Step:     read $8803-$8AFF (compressed rows, mirror $C407, shift $C40E) and the $C1F6 box min/max, counting T per row path for the D3 tally; freeze callcost per-key costs as the oracle fixture
Then:     how to charge the $C3F0 display-copy contention (mean T/byte or per row); A3FF open 1 when the AI pass is read; battery open 1 (won bout / 2P); $B15A sound blocks inline
Blocked:  none
Notes:    D3 -- JS sprite decoder tallies T over the same rows as $8803; oracle callcost.py per key $C41B-$C43B, 0.65%. P1 keys W E D C X Z A Q via $8BFA, P2 $8C0C; states s1 demo, p1/p1b 1P
