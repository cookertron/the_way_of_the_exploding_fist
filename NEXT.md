# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     full background mutants run (python tools/mutants.py --background) -- controlPass now complete; then pick the next unported routine from the main loop $9745
Step:     read build/mutants/summary.txt when it lands; then python tools/status.py --brief to choose the next unit
Then:     live loop design must drive the menu generator across frames (ledger/8C54.toml open 1)
Blocked:  none
Notes:    callio --derive --script FRAMES:KEYS answers ports from a timed key script (for routines that poll inside one call); kit gate throws on a read 64 past the port log so polling mutants fail instead of hanging
