# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $9745 play_pass -- R carried through the pass: M1 tallies for $95D4, $976F and $BF13 remain, then compose playPass and gate it
Step:     $95D4 fighterMotion (lumped T: run blockcost.py over $95D4-$9742 first), then $976F yinYang2P with $900E, then $BF13+$8803 (rendfx m1); add the M1 check row to each block as for $97BB
Then:     whole-pass fixture: callio --capture --call 0xAE29 0xAE2C, --blind each timer row $400B-$470F, states s1, p1, 2P poke; add to port.json; gate playPass bytes, T, ports, outs, rx
Blocked:  none
Notes:    a scratchpad script appended M1 counts beside t += sums (lost at /clear); callio logs $FE writes as outs; live loop must drive the menu generator (8C54 open 1)
