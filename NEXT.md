# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     apply G.worlds to the other guard-bearing gates (demoPoint $ABCB)
Step:     python tools/status.py ABCB; python tools/manual.py --map gate; read build/mutants/summary.txt first -- the full run started before this unit (17:20) is the first with stamped verdicts
Then:     once the stamped full run is in, an --all-rows run then --prune for redundant cases (6.12 step 6); roster still to build: censuses stating population, N and window (T31, T84, T165), and the differ grouping mismatches by roster column
Blocked:  none
Notes:    Roster landed: tools/roster.py, build/roster.json (16 states, all usable); stamps carry the rows of the states read; status warns when stale. No state has sound off, changed controls, 2UP or P2 yin-yang (ledger/topics/roster.toml)
