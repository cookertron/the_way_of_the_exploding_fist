# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     $8C54 Game_Configs_Main, the last controlPass throw (key 0x23 at $9821)
Step:     python tools/adis.py 0x8C54 120 -- the menu loop polls keys until exit; decide its JS shape (a state machine across passes, or a blocking loop with an io script) before capturing
Then:     a full background mutants run at the next milestone (python tools/mutants.py --background)
Blocked:  none
Notes:    callio --derive now accepts a derived run that stops reading ports early (it keeps its own log); branches.py credits a JR target reached another way as taken -- a mutant found $9233
