# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     roster manifest (manual 12.6; map: roster)
Step:     python tools/manual.py 12.6; python tools/manual.py --map roster; read build/mutants/summary.txt first -- the full run started after this commit is the first with stamped verdicts
Then:     apply G.worlds to the other guard-bearing gates (demoPoint $ABCB); once the stamped full run is in, an --all-rows run then --prune to find redundant cases (6.12 step 6)
Blocked:  none
Notes:    Verdict stamps landed: --affected re-runs only stale stamps and red verdicts (--list shows why). T198: revision read at run start. Full battery restarted on this commit, --jobs 4 (D8)
