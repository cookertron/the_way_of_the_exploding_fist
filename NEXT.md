# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     battery over driven play -- states p1, p1b (1P bout) and s1 (demo)
Step:     python tools/battery.py --state p1 --frames 600 --loop 0x9745 ; compare with s1 facts in ledger/topics/battery.toml
Then:     Q18 random ($A3FF; LD A,R seeds $A645), Q19, then phase 9 per-path pass cost of play_pass $9745; bare reference bodies to read first: $9ED2 $A402 $B15A $B2FB $BF13
Blocked:  none
Notes:    P1 record $AA00, P2 $AA40; P1 keys W E D C X Z A Q (8-way) via $8BFA, P2 $8C0C, Kempston $8C42; menu keys 1, 2, 0; symbols.json names: Capitalised = reference (R1), lower = ours (D2)
