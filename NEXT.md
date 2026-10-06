# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     Q19 stack-imbalance scan over 1P play and demo
Step:     python tools/stackscan.py --state p1 ; python tools/stackscan.py --state s1 ; record each named imbalance against its routine (C1: death, round end)
Then:     phase 9 per-path pass cost of play_pass $9745; bare reference bodies to read first: $9ED2 $A402 $B15A $B2FB $BF13; A3FF open 1 settles when the AI pass is read
Blocked:  none
Notes:    P1 record $AA00 (keys $AA05), P2 $AA40; P1 keys W E D C X Z A Q via $8BFA, P2 $8C0C; states s1 demo, p1/p1b 1P; random = LD A,R at $A3FF, 7-bit, correlated (ledger A3FF); symbols Capitalised = reference
