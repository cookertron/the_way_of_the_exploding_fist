# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     BF13 -- render_fighters fixture: tools/rendfx.py --capture at each $BF13 entry (bytes read before write as inputs, every write outside stack, T), --check by replay
Step:     copy the Logged/runs pattern of tools/sprdec.py capture; case key = both fighters' frame ptrs + positions + $C427; then port renderFighters in JS around spriteDecode and gate it
Then:     A3FF open 1 when the AI pass is read; battery open 1 (won bout / 2P); $B15A sound blocks inline; apply D4 charges (decoder x1.0317, $C3F0 +4.72 T/byte) when the pass tally lands
Blocked:  none
Notes:    BF13 read: 9 insn facts (box union, y-max forced $BE, 8-bit overlap test w/ +11, draw order $C427, part list $C34F/$C36E, dy=$FF floor anchor, flip x). web/fist.html is build output, left untracked
