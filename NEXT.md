# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $9745 play_pass -- every callee is now ported and gated ($B15A last); compose playPass from them and gate it against a callio fixture of the whole pass
Step:     python tools/callio.py --help, then bracket the CALL $9745 at $AE29 (--call 0xAE29 0xAE2C); playPass must hand soundEffect's edges to the bridge stamped in simulated T (manual 11.10)
Then:     live loop design must drive the menu generator across frames (ledger/8C54.toml open 1); $ABD2/$AD22 also call $900E with counts 3+ (ledger/900E.toml); Intro_Music $90D1 is a separate tune player, not yet read
Blocked:  none
Notes:    sfx.py --measure is the D6 gate (real ROM T = substitute T); fx1 has no writer in play; $B150 holds the request and soundEffect clears it
