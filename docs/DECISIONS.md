# Decisions -- project-level choices, numbered

Purpose: the choices that apply to the whole port -- a declared departure, a
timing model, a naming rule -- one short paragraph each (manual 12.11).
Read by: number (D3), when a unit touches the choice.  Written with
python tools/record.py decide; 12 lines per entry at most.

D1. **scope of faithful (manual 0.4)** (2026-10-06).  All of the tape is in scope: title and attract demo, menu and key/Kempston options, 1P and 2P bouts, scoring, dan progression, any bonus stage, beeper sound. The ROM loading phase is not reproduced.

D2. **names in tools/symbols.json -- provenance by case** (2026-10-06).  Reference labels (refcheck.py --symbols) keep their Capitalised_Words and are R1: where to look. Our settled names are lower_snake_case, written first; an import never overwrites one. First: play_pass at $9745.
