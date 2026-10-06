# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     9745 -- the JS play pass: read its callees in order ($9C6F, $9ED2, $9D29, $97CB, $97BB, $95D4, $9AD7, $9B9D) toward an engine step that calls renderFighters and charges rfPlayT
Step:     python tools/chaincost.py per callee for cost shape, then adis $9C6F; record what each reads and writes before porting any
Then:     A3FF open 1 when the AI pass is read; battery open 1 (won bout / 2P -- p1 Q swaps sides, a lead); $B15A sound blocks inline
Blocked:  none
Notes:    $BF13 play T charged and gated (rfPlayT, D4 now three means incl. own code x1.0425); the JS has no engine pass yet -- Demo is still the starter; web/fist.html is the untracked built page
