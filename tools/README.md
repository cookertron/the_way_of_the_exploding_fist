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
| `boot.py` | boot (from `z80.snapshot` if set, else the tape), `--state NAME` to resume, `--arm-at ADDR` for the interrupt trap (6.3), optionally drive a key script, dump the LIVE image and save a state | `python tools/boot.py --state boot --arm-at 0x8000 --script "60:,60:SPACE" --save menu` | 7-8 boot / drive into live play |
| `simload.py` | the SNAPSHOT ROUTE: run the tape's own loader in SkoolKit's simulated LOAD (tap2sna) -> a .z80/.szx at hand-over; handles protected/custom loaders (bleepload, speedlock, alkatraz, ...) with no loader-specific code | `python tools/simload.py [--machine 48\|128] [--start ADDR] [--no-finish-tape]` | 1-2 tape + loader |
| `snapimport.py` | a .z80/.szx/.sna snapshot -> the harness image (`build/image.bin`) + a saved state (`--save NAME`); prints the loader's postcondition (PC/SP/IM/IFF/I/border) | `python tools/snapimport.py build/boot48.z80 --save boot` | 2 the loader and the memory map |
| `bleepload.py` | decode a Firebird Bleepload tape: block framing (block->dest map, groups), the driver's decryption of group 1 (applied), the later groups' XOR key read from the stage-2 loader, the driver's own copies and hand-over JP read from its code (printed; `--apply-copies`), and a diff against the snapshot with every mismatching page attributed -- to recover R3 (the tape-byte cross-check) the snapshot route loses; verified against thirteen titles on fourteen tapes (1986-89; a 128K side included) | `python tools/bleepload.py [--snapshot build/boot48.z80] [--apply-copies]` | 3/5 cross-check |
| `probeutil.py` | the probes' shared boot layer: `--state NAME` (a saved `.pkl`) or `--snapshot FILE` (any game's `.z80`/`.szx`/`.sna`), `--arm` (IFF=1), `--warm N` (run N frames armed) | imported by the three probes below | 8-10 |
| `stackscan.py` | Q19, the dynamic stack-imbalance scan: a shadow call stack kept BY SLOT -- CALL/RST/interrupt create frames, RET/POP/INC SP/LD SP remove them and are NAMED (the C1 death / level-complete idiom), `LD SP` cuts held pending until buried (a reset) or revived (a blitter's stack switch), fake returns and rewrites reported; validated on Bubble Bobble, Chuckie Egg and Chuckie Egg 2 | `python tools/stackscan.py --state level --script "400:Z"` | 8 drive into live play (Q19) |
| `chaincost.py` | per-routine T-state cost of each `CALL nn` in a linear dispatch chain, with the measured pass period as the self-check; says so and exits 1 when the range is not a running chain | `python tools/chaincost.py --state level --range 0x8D25 0x8D61` | 9 measure time (Q11) |
| `dataread.py` | data reads with instruction fetches filtered out and stack-class reads (POP/RET/EX (SP)) listed apart; `--verify ADDR` for a scalar, `--verify LO HI` for a buffer or map (the physics reads the cells around the player, never a buffer's first byte) | `python tools/dataread.py --state level --keys M --verify 0x61A8 0x6448` | 8/10 find the structures the physics reads |
| `keyprobe.py` | which key does something: press each of the 40 from one state, diff PCs and memory; exports `KEYS` / `keymask` / `KEYMAP` / `press` / `parse_script` / `drive` | `python tools/keyprobe.py --state menu` | 8 drive into live play |
| `readwatch.py` | find buffers that are only ever READ (a level map) by watching memory reads per PC and page | `python tools/readwatch.py --state level --lo 0x5B00 --hi 0x8000` | 8 drive into live play |
| `battery.py` | the post-harness diagnostic battery over driven play: Q2 ports, Q3 self-modification, Q10 clock, Q13 coverage, Q15/Q16 render + colour, Q17 speaker, Q19 stack | `python tools/battery.py --state level --loop 0x8503 --script "60:D,60:Z"` | 8 drive into live play |
| `filmstrip.py` | consecutive frames side by side, keys held -- LOOK at them | `python tools/filmstrip.py strip.png --state level --keys D --every 4` | 8 drive into live play |
| `clock.py` | the clock model by HISTOGRAM of T-states between visits to the loop top (never the mean) | `python tools/clock.py --pc 0x8503 --state level` | 9 measure time |
| `blitprobe.py` | where the draw routine actually WRITES: (writer PC -> region) histogram of every write above $4000, shadow screen labelled if you give it | `python tools/blitprobe.py --state level --keys D --shadow 0xC000` | 10 read the routines, write the behavioural spec |
| `srctrace.py` | ring buffer of PCs (with SP) leading up to a target PC, optionally gated on SP -- "who set this up" | `python tools/srctrace.py --state level --pc 0x9DD2 --sp 0x5F00 0x6F80` | 10 read the routines, write the behavioural spec |
| `build.py` | assembles the shipped single HTML file from the template, the includes and the asset JSON | `python tools/build.py` | 12 write the engine |

Phases 3 (third-party disassembly), 11 (sound), 13-16 (differential tests,
headless tests, provenance, handover) have no generic tool here: theirs are
game-shaped and get written against the engine, as the manual says.  The
example addresses in the invocations above are the case study's.

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

Requirements: Python 3, SkoolKit 9 (its `resources/48.rom` is read locally and
never copied), z80dis, Pillow.  Everything the tools write under `build/` --
block bodies, images, states -- is tape-derived: keep it out of the repository.
