# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $9745 play_pass -- every callee now tallies M1 (R); next compose playPass and gate it whole
Step:     whole-pass fixture: callio --capture --call 0xAE29 0xAE2C, --blind each timer row $400B-$470F, states s1, p1, 2P poke; add to port.json
Then:     write playPass from the callees (boutTimer .. renderFighters), R into controlPass as io.r plus M1.m1; gate bytes, T, ports, outs, rx
Blocked:  none
Notes:    raw rows ($8858) never occur in sprdec cases, so their M1 has no oracle (8803 fact 9); callio logs $FE writes as outs; live loop must drive the menu generator (8C54 open 1)
