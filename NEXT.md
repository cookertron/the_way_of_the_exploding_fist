# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     the boot LDIR mutant crash (last full run: 3 crashes, boot LDIR and two 8C54 menu, the menu two since fixed)
Step:     python tools/mutants.py --match "LDIR" to reproduce; find why the boot case crashes rather than failing a row
Then:     world builders (boundaries, wraps, both instances, every field seeded), per-verdict stamps, roster; a full battery run is due after the gate-helper and fixture changes
Blocked:  none
Notes:    every control set (P1/P2 x default, Sinclair 1/2, Kempston, redefined) is now played in callio_97cb (702 cases). Mutation runs --jobs 4 (D8)
