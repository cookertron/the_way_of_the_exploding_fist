# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $9745 play_pass callees -- the sound effect $B15A (blocking beeper, 10.7 frames in one call) is the last unported one; then compose playPass
Step:     python tools/adis.py 0xB15A 40 and the effect table $B144; read manual on beeper sound (python tools/manual.py --grep beeper) before choosing how the JS plays it
Then:     live loop design must drive the menu generator across frames (ledger/8C54.toml open 1); $ABD2/$AD22 also call $900E with counts 3+ (ledger/900E.toml)
Blocked:  none
Notes:    callio brackets any PC range, not only a CALL (--call 0x976F 0x978D); --poke Num_Players 0x9C2C=2 gives 2P play from s1
