# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $9745 play_pass -- playPass composed and gated whole (24 cases, 130 replayed); two composition mutants survive
Step:     derive whole-pass cases that kill them: callio --derive on build/callio_ae29.json, --set P1 into a $97BB opponent-reading path (sets from the derived 97bb cases), and a 2P case where P2's step changes $AA43/$AA48
Then:     wire playPass into the live loop with the 7.2 accumulator (rfPlayT for $BF13, effects through the beeper), then the menu generator (8C54 open 1)
Blocked:  none
Notes:    ROM effects: pass gate checks $FE writes in count, value, first T only (D6); gate stops at the first bad case ($A5 poison makes a wrong pass hang); callio --cover is new
