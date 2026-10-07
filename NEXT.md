# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $9745 play_pass -- R must be carried through the pass: M1 tallies into M1.m1 for the remaining callees, then compose playPass and gate it
Step:     soundEffect's M1 first (sfx field m1; a delay pass DEC BC/LD A,B/OR C/JR NZ is 4 M1), then $97BB $9AD7 $95D4 $976F (callio rx - r), then $BF13+$8803 (rendfx m1); gate as in the $9C6F block
Then:     whole-pass fixture: callio --capture --call 0xAE29 0xAE2C, --blind each timer row $400B-$470F, states s1, p1, 2P poke; add to port.json; gate playPass bytes, T, ports, outs, rx
Blocked:  none
Notes:    callio logs $FE writes as outs; all callio fixtures carry r/rx (9745 open 1: the R plan); live loop must drive the menu generator (8C54 open 1)
