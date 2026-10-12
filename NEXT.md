# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     battery open 1 -- does the Spectrum tape have a bonus stage at all (D1 scope)
Step:     python tools/manual.py --grep bonus; then search the reference ctl and the walker's reach for a stage handler outside the bout loop $AC3E/$AB70
Then:     a 2P state worth saving: s1 then key 2 (20:,30:2) is a real 2P game, and (60:D,30:E,30:) repeated makes P1 score -- save it if a 2P gate needs one
Blocked:  none
Notes:    Q19 closed: 0 discards over 1P loss, demo, P1 bout win (stage2) and real 2P play. No code changed this unit, no mutation run due.
