# tools/ -- the game-agnostic analysis kit

Every tool here reads its game-specific facts from ONE manifest, `port.json` at
the repository root, through `tools/portconfig.py`: which tape, where the loader
leaves each block, the entry point, the PC of the game's own CALL into the ROM
loader, and where the 64K image and the saved machine states live.  A tool finds
the manifest by walking up from its own directory (or from
`PORT_JSON=/path/to/port.json`), fills in defaults for anything missing or
`null`, and never fails at import: `--help` works with no manifest at all, and a
tool only stops -- naming the key to fill in -- when it actually needs a value.
Numbers in the manifest may be JSON ints or hex strings (`"0x8400"`, `"$8400"`);
paths are relative to the manifest's directory.  The build script (`build.py`)
reads the same file (`name`, `template`, `out`, `includes`, `assets`); the
analysis tools read `tape` and `z80`.  Run `python tools/selftest.py` first: it
proves the whole kit against a synthetic tape and a ROM-only machine with
nothing filled in, so a missing SkoolKit ROM, z80dis or Pillow shows up before
phase 1, not in phase 8.

## Tools by phase

| tool | purpose | typical invocation | manual phase |
|---|---|---|---|
| `portconfig.py` | the manifest reader every tool uses; run it to print the merged config and which `port.json` was found | `python tools/portconfig.py` | all |
| `manual.py` | the manual and `docs/TRAPS.md` by ID, never end to end: entries (`C9`, `6.11`, `P9`), traps with their map rows (`T146`), `--index`, `--grep TERM` across the manual, the traps and these tables, `--map` for the trap-to-check map, and `--tools TERM` to find the tool for a job from these tables | `python tools/manual.py --tools stack` | all |
| `record.py` | writes every record to its one home (manual 12.11): ledger facts, refuted claims and open questions, links (checked before they are written), NEXT.md, decisions, and a commit draft whose mechanical lines come from git; fields arrive on stdin through a quoted heredoc, so the shell never touches a `$` | `python tools/record.py fact B34C <<'EOF'` | all |
| `status.py` | where the project stands, derived from the records: `--brief` (the session orientation), `ADDR` (everything known about one routine), `--check` (blocks orphans, broken links and malformed ledger files; warns on budgets), `--index` | `python tools/status.py B34C` | all |
| `mutants.py` | the mutation battery's runner (manual 6.12): each case runs only the suite blocks its anchor reaches (coverage), killing block first, stopping at the first FAIL; survivors are confirmed against the whole suite; `--affected`, `--background`, `--profile`, `--sample N`; `mutants.js` (with `vendor/acorn.js`, MIT) makes the selectable copy of the suite and the coverage map | `python tools/mutants.py --affected` | 13 |
| `selftest.py` | self-test with NO tape: synthetic TZX, ROM-only harness, tiny images; exit status non-zero on failure | `python tools/selftest.py [-v]` | 7 the simulator harness (run before anything) |
| `tzx.py` | TZX parser: prints and STOPS on any unhandled block, verifies every ROM-format checksum, decodes headers, checks body length against header, dumps block bodies | `python tools/tzx.py tape/game.tzx --dump build/blocks` | 1 read the tape |
| `basic.py` | BASIC detokeniser; reports each USR target from the 5-byte binary form the ROM actually acts on, not the printed digits | `python tools/basic.py build/blocks/game.b01.body.bin` | 1 read the tape |
| `hexdump.py` | hex + ASCII dump with a base address | `python tools/hexdump.py build/image.bin --offset 0x8000 --len 64` | 2 the loader and the memory map |
| `mkloader.py` | scratch 64K with only the BASIC block at PROG ($5CCB) plus the stub's own relocation, so the stub disassembles at its running address | `python tools/mkloader.py [--copy 0x5CF1 0xFF00 0x100]` | 2 the loader and the memory map |
| `mkimage.py` | the post-loader 64K image, ASSERTED from the loader's postcondition (`tape.blocks`, `tape.copies`); `--upto N` for a transient stage | `python tools/mkimage.py [--upto 1]` | 2 the loader and the memory map |
| `adis.py` | annotated disassembler (z80dis): symbol substitution, region banners, DEFB rows for data regions, raw bytes beside each instruction | `python tools/adis.py 0x8400 40 [--image build/live.bin]`; `--sym NAME=ADDR` | 4 build an annotated disassembler |
| `walk.py` | recursive-descent code walker -- a LOWER BOUND on code -- plus the port / HALT / IM / below-$4000 inventory and the call graph | `python tools/walk.py [--entry ADDR] [--report calls]` | 4 build an annotated disassembler |
| `grepbytes.py` | byte-pattern search with instruction-boundary confirmation; unconfirmed hits are reported, not dropped | `python tools/grepbytes.py "CD 56 05"` | 4 build an annotated disassembler |
| `strings.py` | printable runs, and bit-7-terminated runs | `python tools/strings.py --min 4 [--hi]` | 5 static extraction of data |
| `speckle.py` | rank byte ranges as art vs noise -- the crude sweep before a disassembly says where the graphics are | `python tools/speckle.py build/image.bin --w 2 --h 16` | 5 static extraction of data |
| `contact.py` | contact sheet of a range rendered as sprites BOTH ways (row-major and cell-major); LOOK | `python tools/contact.py build/image.bin out.png --base 0x5F00 --len 0x1000 --w 2 --h 16` | 5 static extraction of data |
| `screen.py` | render the display file, or the 32x24 attribute sheet, out of a memory image | `python tools/screen.py build/live.bin out.png [--attrs]` | 6 ground truth from a real frame |
| `harness.py` | the Z80 simulator harness: real 48K ROM (read locally from SkoolKit), tape deck at a PC breakpoint, keyboard/Kempston ports, memory write watch, step / run_until / run_frames / profile / call / save_state; ULA contention by default | `python tools/harness.py` (profile from the entry point); `from harness import Harness` | 7 the simulator harness (the pivot) |
| `boot.py` | boot (from `z80.snapshot` if set, else the tape), `--state NAME` to resume, `--arm-at ADDR` for the interrupt trap (6.3), optionally drive a key script, dump the LIVE image and save a state | `python tools/boot.py --state boot --arm-at 0xA420 --script "60:,60:SPACE" --save menu` | 7-8 boot / drive into live play |
| `simload.py` | the SNAPSHOT ROUTE: run the tape's own loader in SkoolKit's simulated LOAD (tap2sna) -> a .z80/.szx at hand-over; handles protected/custom loaders (bleepload, speedlock, alkatraz, ...) with no loader-specific code | `python tools/simload.py [--machine 48\|128] [--start ADDR] [--no-finish-tape]` | 1-2 tape + loader |
| `snapimport.py` | a .z80/.szx/.sna snapshot -> the harness image (`build/image.bin`) + a saved state (`--save NAME`); prints the loader's postcondition (PC/SP/IM/IFF/I/border) | `python tools/snapimport.py build/boot48.z80 --save boot` | 2 the loader and the memory map |
| `bleepload.py` | decode a Firebird Bleepload tape: block framing (block->dest map, groups), the driver's decryption of group 1 (applied), the later groups' XOR key read from the stage-2 loader, the driver's own copies and hand-over JP read from its code (printed; `--apply-copies`), and a diff against the snapshot with every mismatching page attributed -- to recover R3 (the tape-byte cross-check) the snapshot route loses; verified against thirteen titles on fourteen tapes (1986-89; a 128K side included) | `python tools/bleepload.py [--snapshot build/boot48.z80] [--apply-copies]` | 3/5 cross-check |
| `probeutil.py` | the probes' shared boot layer: `--state NAME` (a saved `.pkl`) or `--snapshot FILE` (any game's `.z80`/`.szx`/`.sna`), `--arm` (IFF=1), `--warm N` (run N frames armed) | imported by the three probes below | 8-10 |
| `stackscan.py` | Q19, the dynamic stack-imbalance scan: a shadow call stack kept BY SLOT -- CALL/RST/interrupt create frames, RET/POP/INC SP/LD SP remove them and are NAMED (the C1 death / level-complete idiom), `LD SP` cuts held pending until buried (a reset) or revived (a blitter's stack switch), fake returns and rewrites reported, a RET into a frame live before the scan reported apart as INHERITED; validated on Bubble Bobble, Chuckie Egg and Chuckie Egg 2 | `python tools/stackscan.py --state level --script "400:Z"` | 8 drive into live play (Q19) |
| `chaincost.py` | per-routine T-state cost of each `CALL nn` in a linear dispatch chain, with the measured pass period as the self-check; says so and exits 1 when the range is not a running chain | `python tools/chaincost.py --state level --range 0x8D25 0x8D61` | 9 measure time (Q11) |
| `callcost.py` | is one call's cost a function of its inputs: brackets one CALL site and return over driven play, keys each call by a memory range read at the return, reports within-key cost spread; `--sub` takes one instruction (an LDIR into the display) apart so frame-phase contention (3.8) shows separately, with T per byte per call and pooled over all runs (the mean charge, D4) | `python tools/callcost.py --state s1 --call 0x9790 0x9793 --key 0xC41B 0xC43C --sub 0xC3F0 0xC3F2` | 9 measure time (Q11, 3.8) |
| `rendfx.py` | GAME-SPECIFIC: render_fighters $BF13 frozen without a model: `--capture` runs each call in driven play alone in an uncontended logging twin (inputs = bytes read before written, outputs = every write outside the stack, T exact; T in play kept) and keeps one case per distinct path; `--check` replays the fixture in a blank 64K with the code from the target and fails on any differing write, T or unrecorded read | `python tools/rendfx.py --capture --state s1 --per 1` ; `python tools/rendfx.py --check --state s1 --paths` | 10 port (D3, 7.2) |
| `sprdec.py` | GAME-SPECIFIC: the sprite decoder $8803 transliterated with per-instruction T; `--capture` replays every call in driven play against the harness (bytes written, T exact against an uncontended twin, T in play kept; last line the play-weighted contention factor, D4) and freezes one case per sprite and flag set; `--check` replays the fixture in a blank 64K | `python tools/sprdec.py --capture --state s1 --frames 1500` ; `python tools/sprdec.py --check --paths` | 10 port (D3, 7.2) |
| `dataread.py` | data reads with instruction fetches filtered out and stack-class reads (POP/RET/EX (SP)) listed apart; `--verify ADDR` for a scalar, `--verify LO HI` for a buffer or map (the physics reads the cells around the player, never a buffer's first byte) | `python tools/dataread.py --state level --keys M --verify 0x61A8 0x6448` | 8/10 find the structures the physics reads |
| `keyprobe.py` | which key does something: press each of the 40 from one state, diff PCs and memory; exports `KEYS` / `keymask` / `KEYMAP` / `press` / `parse_script` / `drive` | `python tools/keyprobe.py --state menu` | 8 drive into live play |
| `readwatch.py` | find buffers that are only ever READ (a level map) by watching memory reads per PC and page | `python tools/readwatch.py --state level --lo 0x5B00 --hi 0x8000` | 8 drive into live play |
| `drawlog.py` | Q18, characterise a random source: stop at the generator's RET, log A and caller over driven play; per-bit set counts (a stuck bit shows), spread, callers, and same-frame consecutive-draw deltas per caller pair (a constant delta = correlated draws, E1); deltas mod 128 when bit 7 never sets | `python tools/drawlog.py --state level --pc 0xA401 --frames 3000` | 10 read the routines (Q18) |
| `battery.py` | the post-harness diagnostic battery over driven play: Q2 ports, Q3 self-modification, Q10 clock, Q13 coverage, Q15/Q16 render + colour, Q17 speaker, Q19 stack | `python tools/battery.py --state level --loop <loop-top> --script "60:D,60:Z"` | 8 drive into live play |
| `filmstrip.py` | consecutive frames side by side, keys held -- LOOK at them | `python tools/filmstrip.py strip.png --state level --keys D --every 4` | 8 drive into live play |
| `clock.py` | the clock model by HISTOGRAM of T-states between visits to the loop top (never the mean) | `python tools/clock.py --pc <loop-top> --state level` | 9 measure time |
| `blitprobe.py` | where the draw routine actually WRITES: (writer PC -> region) histogram of every write above $4000, shadow screen labelled if you give it | `python tools/blitprobe.py --state level --keys D --shadow 0xC000` | 10 read the routines, write the behavioural spec |
| `blitforensics.py` | measure ONE sprite blit from ground truth: a TWO-BACKGROUND differential (run the call over all-$00 then all-$FF, diff the writes) recovers the sprite's WxH, MASKED/OPAQUE/XOR and the full data+mask bitmap WITHOUT reading the blitter or assuming size/order -- POP/LDI/AND-OR/OR-only/opaque alike, XOR detected+flagged, an empty result declared EMPTY; a THIRD run over the real background checks the model `(bg AND mask) OR data` byte for byte and disowns the grid on a mismatch.  One call is bounded by the return address at `--entry` (a CALL/RST must precede it, else refused; `--ret 0xADDR` or `--ret IX` for a blitter entered by JP that ends `JP (IX)`; a call that never returns exits 3); `--target LO HI` measures a same-layout back-buffer.  Synthetic gold gate in selftest; validated on Bubble Bobble, Chuckie Egg, Chuckie Egg 2 (draw AND erase pass) and Gauntlet (three shadow-screen blitters), model mismatch 0 on all | `python tools/blitforensics.py --state play --entry 0xA600 [--skip N] [--target 0xC000 0xDB00] [--ret IX] [--src HL]` | 5 static extraction / draw routines |
| `srctrace.py` | ring buffer of PCs (with SP) leading up to a target PC, optionally gated on SP -- "who set this up" | `python tools/srctrace.py --state level --pc 0x9DD2 --sp 0x5F00 0x6F80` | 10 read the routines, write the behavioural spec |
| `build.py` | assembles the shipped single HTML file from the template, the includes and the asset JSON | `python tools/build.py` | 12 write the engine |

Phases 3 (third-party disassembly), 11 (sound), 13-16 (differential tests,
headless tests, provenance, handover) have no generic tool here: theirs are
game-shaped and get written against the engine, as the manual says.  The
concrete example addresses (entry, arm point $A420, ...) are the case
study's, from the manual; `<loop-top>` is one you read off the profile (the manual
describes it but gives it no fixed number, and it is game-specific).

## This port's tools

Oracles, extractors and probes written for this game go here, one row each,
in the same four columns.  Every script in `tools/` has a row in this table or
the one above -- `python tools/selftest.py` fails otherwise -- because these
tables are what `python tools/manual.py --tools TERM` searches, and what a
session reaches for after a compaction has taken this file out of its context.
Read a tool's `--help` before extending it or writing a new one (TRAPS #65,
#170).

| tool | purpose | typical invocation | manual phase |
|---|---|---|---|
| `refcheck.py` | phase 3 gate: assemble each line of a third-party SkoolKit disassembly alone at its stated address and compare with our image (start-up relocation applied); prints "bytes compared N / mismatching M / skipped S" with every range and unparsed line named; `--coverage` titled vs default-titled routines and commented lines; `--symbols OUT` imports its @labels without overwriting ours | `python tools/refcheck.py ../ref_wayoftheexplodingfist/sources/wotef.skool [--coverage | --symbols tools/symbols.json]` | 3 find and verify any third-party disassembly |

## The manifest keys the tools read

```
"tape": {
  "path": "tape/game.tzx",   the tape the post-loader image is built from
  "deck": null,              the tape served at runtime loads (default: path)
  "blocks": [],              [] or "auto": follow the ROM headers (a stock tape:
                             BASIC to PROG, CODE to its header address); else
                             one entry per block for a custom loader --
                               {"dest": "0x8600", "len": "0x5210", "flag": "0x80"}
                               {"dest": "0x8400", "len": "0x7777", "block": 6}
  "copies": [],              the loader's own post-load moves, e.g. a stub
                             relocating itself:
                               {"src": "0x5CF1", "dst": "0xFF00", "len": "0x100"}
  "prog": "0x5CCB",          where a BASIC block is LOADed (stock 48K)
  "entry": null,             PC when the loader hands over -- REQUIRED to run
  "sp": "0xFFFF",            SP at that moment (the game usually sets its own)
  "tape_call_pc": null,      PC of the game's own CALL into LD-BYTES, if it
                             loads levels at runtime; this enables the deck
  "tape_ret_pc": null        where that CALL returns (default: call + 3)
},
"z80": {
  "contended": true,         CMIOSimulator (ULA contention) or plain Simulator;
                             PORT_CONTENDED=0/1 in the environment overrides
  "symbols": "tools/symbols.json",   {"0x8400": "main"}                    (adis)
  "regions": "tools/regions.json",   [{"start","end","desc","kind"}]      (adis)
  "states": "build",         directory for saved machine states (NAME.pkl)
  "image": "build/image.bin" the static post-loader image mkimage.py writes
  "snapshot": null,          a .z80/.szx to BOOT from (the snapshot route,
                             manual 6.1); when set, Harness() and the --state
                             tools use it instead of the tape block table
  "snapshot128": null,       the same tape on a 128K (for a 128K layer)
  "varmap": "tools/varmap.json"  {name:{addr,width,note}} a port fills in, so the
                             engine, the differential sampler and the tests all
                             share one variable-name table
}
```

A block matched by `flag` takes the first unused data block with that flag byte,
in tape order; `block` is the TZX block index as `tzx.py` prints it.  `len` is
the loader's own count and a payload of another size is an ERROR -- it means the
block table is wrong.  `tools/symbols.json` and `tools/regions.json` ship empty
(`{}` and `[]`); `adis.py --sym NAME=ADDR` grows the first.

## Typical flow

    python tools/selftest.py                          # prove the environment
    python tools/tzx.py tape/game.tzx --dump build/blocks
    python tools/basic.py build/blocks/game.b01.body.bin       # -> the USR target
    # read the loader; fill tape.blocks / tape.copies / tape.entry in port.json
    python tools/mkimage.py && python tools/walk.py && python tools/adis.py 0x8400 60
    python tools/harness.py                           # profile from the entry point
    python tools/boot.py --steps 400000 --save boot
    python tools/keyprobe.py --state boot             # -> which keys do what
    python tools/boot.py --script "60:,30:SPACE,300:1" --save level
    python tools/clock.py --pc 0x???? --state level   # the loop top from the profile
    python tools/battery.py --state level --loop 0x???? --script "60:D,60:Z"
    python tools/filmstrip.py strip.png --state level --keys D

Requirements: Python 3, SkoolKit 10.0 or later (10.0 and 10.1 tested; its
`resources/48.rom` is read locally and never copied), z80dis, Pillow.
Everything the tools write under `build/` -- block bodies, images, states --
is tape-derived: keep it out of the repository.
