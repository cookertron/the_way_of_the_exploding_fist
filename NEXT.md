# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     stamp the 34 unstamped fixtures (python tools/stamp.py lists them), then measure() in the harness (manual 6.11)
Step:     callio/rendfx: --check with each fixture's state (port.json note); live_*: rebuild each sample.py command from its JSON once, capture to a temp, compare rows, keep the stamped copy; sfx/sprdec: recapture, compare
Then:     measure() (manual 6.11, G11), then the rest of CLAUDE.md's still-to-build table in order
Blocked:  none
Notes:    live_dtime needs live's script with --from 4250 --passes 5420. sprdec --check replays the model, so it does not restamp. built.json/gate.json are local (gitignored). Full mutation run started at the end of the stamps unit, 10 workers
