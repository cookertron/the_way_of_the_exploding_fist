# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     phase 10 port the sprite decoder $8803 to JS with its T tally (D3), gated against the sprdec fixture
Step:     write the JS decoder from tools/sprdec.py (same rows, same branches, same T constants); a gate block in test/kit.test.js replays every sprdec case from the built page's assets -- bytes written and T exact; mutants for it
Then:     8803 open 1 stack contention (0-7.2%) and the $C3F0 copy contention -- charge both; read $C1F6 box min/max and $C34F/$C36E part loop; A3FF open 1 when the AI pass is read; battery open 1 (won bout / 2P); $B15A sound blocks inline
Blocked:  none
Notes:    sprdec.py model exact on 2604 calls; fixture 441 cases (one per sprite and flag set), 587 KB in the page as asset sprdec. Raw and empty rows never seen in play -- port them but they are ungated. Mirror always paired with recolour
