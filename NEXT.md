# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     world builders (boundaries, wraps, both instances, every field seeded) in rig.js, with their kit checks
Step:     python tools/manual.py --map gate ; read the BUILD rows, then sketch the builder API against one existing in/out fixture gate
Then:     an engine-step helper that turns a throw into a named FAIL (T197), per-verdict stamps, roster
Blocked:  none
Notes:    full battery 3f4aa12: 623/624 killed, 0 crashes, 1 ambiguous anchor since fixed and killed -- all 624 killed. It took 145.6 min (73.4 before, 7 more cases): unexplained, per-case mean 45 s. Runs --jobs 4 (D8)
