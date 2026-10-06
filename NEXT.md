# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     phase 10 read the render pipeline $BF13 -> $C1A2 -> $C34F -> $C36E -> $C2B5 -> sprite decoder $8803
Step:     read $8803-$8AFF (compressed rows, mirror $C407, shift $C40E) and the $C1F6 box min/max; then settle 9745 open 1 (timing model) with callcost tables per key
Then:     A3FF open 1 when the AI pass $A0xx-$A5xx is read; battery open 1 (Q19 on a won bout / 2P) when such a state exists; $B15A sound effects block inline (9745 fact 2)
Blocked:  none
Notes:    Q11 settled -- no per-path constants; $BF13 is 95% of the pass and fixed by $C41B-$C43B to 0.65% outside the $C3F0 display LDIR (tools/callcost.py). P1 keys W E D C X Z A Q via $8BFA, P2 $8C0C; states s1 demo, p1/p1b 1P
