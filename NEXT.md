# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $AC5F bout_setup -- the next bout's setup to the CALL $AD18 gated exact on 7 cases (3 derived): the tune's $FE writes, the scenery, the text rows; not yet live
Step:     run the setup live: from .exit at $AC5F through setupMusic (charged once, edges to the sound log) then setupRest, stop at $AD18; measure the setup's contended T ($5F22 is contended RAM)
Then:     $AD18 into $AE26 and CALL $9CA8 to $AE29, so a bout follows a bout live; then the menu generator (8C54 open 1), which retires D7
Blocked:  none
Notes:    text cells blinded by explicit ranges (port.json setup_ac5f); Show_Rank's suffix choice is gated by T and R only (D5)
