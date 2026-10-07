# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $ACA6 bout_next -- the 1UP game after a bout: lost to $AC39, won / rank up / top rank / draw to $AC5F gated exact (8 cases, 1 derived) and live on all three ways out
Step:     the next bout's setup $AC5F to the CALL $AD18: new stage ($AF35: Intro_Music $90D1, scenery $9200 with $5F22, contended), score and rank rows, New_Round, Init_Time; bracket --call 0xAC5F 0xAD18
Then:     $AD18 into $AE26 and CALL $9CA8 to $AE29, so a bout follows a bout live; then the menu generator (8C54 open 1), which retires D7
Blocked:  none
Notes:    callio stops at the first RET-list PC reached, any SP: --call 0xACA6 0xAC5F,0xAC39 worked; Fist.exit now carries .at, the PC the engine stopped at
