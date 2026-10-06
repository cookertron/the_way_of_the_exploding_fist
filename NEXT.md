# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     Q18 random -- $A3FF; LD A,R seeds $A645
Step:     python tools/adis.py 0xA3FF 20 ; python tools/readwatch.py on $A645 over p1 ; record who reads the seed and whether R makes play non-deterministic
Then:     Q19 (tools/stackscan.py over p1), then phase 9 per-path pass cost of play_pass $9745; bare reference bodies to read first: $9ED2 $A402 $B15A $B2FB $BF13
Blocked:  none
Notes:    P1 record $AA00 (keys land in $AA05), P2 $AA40; P1 keys W E D C X Z A Q via $8BFA, P2 $8C0C, Kempston $8C42; H runs $982E, 1 runs $8BA4 (unnamed); states s1 demo, p1/p1b 1P; symbols.json Capitalised = reference (R1), lower = ours (D2)
