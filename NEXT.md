# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     95D4 -- ROM reads only steer which $FF is copied: port it writing $FF, callio fixture, gate
Step:     python tools/status.py 95D4 ; adis, then callio --capture at its call site, port, gate
Then:     97CB AI and A3FF open 1 last
Blocked:  none
Notes:    9D29 and 9ED2 share the JS core hitTest(m, A, V, t); 9D29 gated on 87 cases (56 derived); web/fist.html is a build output, still untracked; a full mutants run is due (hit core refactor)
