# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     seed builder -- callio --derive that sets every byte a case reads then rewrites unchanged to another value, until G.unseeded is [] per fixture
Step:     node scratchpad census (G.unseeded over build/callio_*.json): 598 stores in 20 fixtures never seen changing a byte, worst 97cb 59, ad1b 59, ae17 58, roundIn's reset block shared; start with ad1b
Then:     on/off identity gate, engine-step helper (T197), per-verdict stamps, roster; apply G.worlds to the other guard-bearing gates (demoPoint $ABCB has the same XOR guard)
Blocked:  none
Notes:    full battery started after the worlds commit (rig.js changed): read build/mutants/summary.txt. Affected run at worlds: 24/24 killed, 29.0 min. Runs --jobs 4 (D8)
