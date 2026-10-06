# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     BF13 -- read $C1F6 box min/max and the $C34F/$C36E part loop, toward porting render_fighters around spriteDecode
Step:     python tools/adis.py 0xC1F6 40 ; adis 0xC34F 40; record each branch as an insn fact on BF13
Then:     A3FF open 1 when the AI pass is read; battery open 1 (won bout / 2P); $B15A sound blocks inline; apply D4 charges (decoder x1.0317, $C3F0 +4.72 T/byte) when the pass tally lands
Blocked:  none
Notes:    D4 settled 8803 open 1: contention is phase noise under DI free-running, charged as play means. spriteDecode gated (441 cases, 22 mutants). JS has no pass tally yet, so D4 constants are not in the page
