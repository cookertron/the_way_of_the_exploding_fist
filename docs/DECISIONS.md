# Decisions -- project-level choices, numbered

Purpose: the choices that apply to the whole port -- a declared departure, a
timing model, a naming rule -- one short paragraph each (manual 12.11).
Read by: number (D3), when a unit touches the choice.  Written with
python tools/record.py decide; 12 lines per entry at most.

D1. **scope of faithful (manual 0.4)** (2026-10-06).  All of the tape is in scope: title and attract demo, menu and key/Kempston options, 1P and 2P bouts, scoring, dan progression, any bonus stage, beeper sound. The ROM loading phase is not reproduced.

D2. **names in tools/symbols.json -- provenance by case** (2026-10-06).  Reference labels (refcheck.py --symbols) keep their Capitalised_Words and are R1: where to look. Our settled names are lower_snake_case, written first; an import never overwrites one. First: play_pass at $9745.

D3. **timing model -- T-states tallied by the sprite decoder (7.2, Q11)** (2026-10-06).  The JS sprite decoder counts T-states as it walks the same rows as $8803 (mirror, shift), plus the fixed chain costs, into the 7.2 accumulator. Oracle: callcost.py per key, within 0.65% outside the display copy.

D4. **contention charged as play-weighted means, not by frame phase (3.8, 7.2)** (2026-10-06).  Free-running with DI, so frame phase is lost to the JS tally; charge measured means: $8803 T x 1.0317 (sprdec.py --capture), $C3F0 copy +4.72 T per byte over 21n-5 (callcost.py --sub pooled).
