# NEXT -- where things stand
<!-- Overwritten at every unit end by python tools/record.py next; 20 lines at most (manual 12.11). -->

Unit:     BF13 -- settle open 1: a rendfx capture near the overlap boundary (fighters within 11 px), then restore the +10 slack mutant
Step:     try p1/p1b with keys that close the distance (keyprobe), --append to build/rendfx_cases.json; rendfx --check; rebuild and run the suite
Then:     wire renderFighters into the engine pass with the D4 charges (decoder x1.0317, $C3F0 +4.72 T/byte); A3FF open 1 when the AI pass is read; battery open 1 (won bout / 2P); $B15A sound blocks inline
Blocked:  none
Notes:    renderFighters ported and gated (41 cases, writes + T exact); no-overflow branch at $C23C dead in play; full mutation run launched in background, see build/mutants/summary.txt
