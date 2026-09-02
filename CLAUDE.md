# Briefing: porting a ZX Spectrum game with this kit

You are in a repository created from the Spectrum Port Kit.  The job is a
FAITHFUL reproduction of one game, in one self-contained HTML file, verified
against the real machine code running in a Z80 simulator.  The operating
procedure is `docs/PORTING-ZX-TO-JS.txt` — sixteen phases, read it before
anything else — and `docs/TRAPS.md` is what two previous ports paid to learn.

## What is already here (don't rebuild it)

- `tools/` — TZX parsing, loader/boot, the SkoolKit-wrapped Z80 harness
  (contended timing on by default), config-driven disassembler, code
  walker, byte grep, keyboard probe, read-watch, clock histogram, the
  diagnostic battery, screen forensics, `build.py`.  `tools/README.md` maps
  each to its phase.  `python tools/selftest.py` is their gate.
- `web/platform.js` — the platform runtime: display file + renderer,
  keyboard matrix + Kempston + gamepads, AY and beeper chips, the Web Audio
  bridge (worklet transport, scheduled fallback), the loop, settings.
- `test/rig.js` + `test/kit.test.js` — the headless rig and the runtime's
  own 115 checks, run against the BUILT page.  Append the game's checks
  after them; never let the file go red.
- `port.json` — the manifest.  Fill it in before running any tool that
  needs the tape.

## House rules

1. **Measure, don't assume.**  A number in a comment is a measurement with
   its source named, or it is marked PROVISIONAL.  When the JS disagrees
   with the simulator, the simulator is right until proven otherwise.
2. **Differential gates.**  For each behaviour: one sampler at the main-loop
   top, driven by the same key script through the harness and through the
   headless engine, tables diffed row for row.  The first differing row
   names the bug.
3. **Mutation-test every behaviour you add.**  Break it on purpose, watch
   the named test fail, restore, re-run.  A test that cannot fail is not a
   test (see the localStorage lesson in TRAPS).
4. **The built artifact is what is tested.**  `tools/build.py` first, then
   `node test/kit.test.js`.  Never import source modules into a test.
5. **Faithful first, added layer declared.**  Every departure from the
   original is a named flag, off on the faithful path, with the faithful
   behaviour kept in code and tested.  Make the boundary an assertion.
6. **Diagnostics ship.**  `__SPEC__`-style hooks and `sound.info()` exist
   because a machine you cannot touch can only be debugged through what the
   page reports.  Never let a fallback engage silently.
7. **Never commit tape-derived material** to a public repository: no
   `.tzx`, `.pkl`, `build/*.bin`, no extracted binaries.  `build/*.json`
   (decoded data and frozen oracle fixtures) is fine.
8. **Prefer editing the game, not the runtime.**  `web/platform.js` is
   shared with other ports; if you must change it, keep it game-agnostic
   and add the check to `kit.test.js`.

## Commit style

Scoped commits, each with a message that says what was measured and what
the mutation battery covered.  Suite count in the message.
