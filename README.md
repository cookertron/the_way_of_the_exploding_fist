# ZX Spectrum → JavaScript Port Kit

Everything game-agnostic from two faithful Spectrum-to-browser ports, in one
starter repository: the field manual (written after the first port, Chuckie
Egg), and the tools, platform runtime and test rig built during the second
(Gauntlet, 1986 — `cookertron/Gauntlet-JS`).  A new port starts here at the
manual's phase five, with a booted image, a disassembler, a Z80 oracle, a
headless test rig and a finished, verified audio/screen/input runtime —
instead of at phase zero.

It does not port a game for you.  Reading the game's own Z80 and proving the
reimplementation against the real machine is the job, and it is most of the
job.  What the kit removes is the platform work and the method discovery.

## Quick start

```
pip install skoolkit               # the Z80 simulator the harness wraps
python tools/selftest.py           # the tools' own gate, no tape needed
python tools/build.py              # port.json -> web/<name>.html
node test/kit.test.js              # the platform suite against the BUILT page
```

Open the built page in a browser: a block moves on QAOP, the cursor keys or a
joystick; SPACE (or fire) beeps through the real beeper path and reddens the
border.  That is the whole runtime exercised end to end, and the thing you
replace with a game.

Starting a port:

1. Copy this repository.  Put the `.tzx` in `tape/` (git-ignored — never
   commit tape-derived material to a public repo) and fill in `port.json`.
2. Read `docs/PORTING-ZX-TO-JS.txt` — the operating procedure, sixteen
   phases — and `docs/TRAPS.md`, the things that cost real effort to learn.
3. Work the phases with the tools (`tools/README.md` maps each tool to its
   phase).  Your extractors write `build/*.json`; `port.json` lists them;
   `tools/build.py` asserts their shape and inlines them.
4. Replace `Demo` in `web/template.html` with the engine.  Keep the shape:
   one video frame per `step()`, sound as an event log on the simulation's
   own frame counter, `fillRect`-only drawing.
5. Keep `test/kit.test.js` green and append the game's checks after it.

## Layout

| Path | What |
|---|---|
| `docs/PORTING-ZX-TO-JS.txt` | The field manual: sixteen phases, what evidence to demand at each |
| `docs/TRAPS.md` | The recorded lessons, each with the measurement that taught it |
| `port.json` | The port's manifest: tape, entry, blocks, contention, assets, includes |
| `tools/` | Tape/loader/boot, the SkoolKit-based Z80 harness, disassembly and discovery, graphics forensics, `build.py` — see `tools/README.md` |
| `web/platform.js` | The platform runtime, inlined into the page by the build |
| `web/template.html` | The page: shell, `#include platform.js`, the demo to replace |
| `test/rig.js` | The headless rig: vm sandbox, recording canvas stub, real localStorage, captured rAF |
| `test/kit.test.js` | The platform suite (115 checks), run against the BUILT file |
| `build/` | Extracted assets (JSON, tracked) and simulator states (`.pkl`/`.bin`, ignored) |

## What the runtime gives you

All plain script-scope globals once inlined; `globalThis.__SPEC__` exports
the same names for the rig.

| Layer | Names |
|---|---|
| Frame clock | `FRAME_HZ` (48K 50.08 / 128K 50.02), settable |
| Display file | `SpecScreen` — the real 6,912-byte buffer with the ULA's address arithmetic (`pixelAddr`, `attrAddr`, `nextRow`, `nextCol`, `plot`, `putGlyph`, `print`); `renderScreen` (BRIGHT, FLASH from the sim's frame count, `fillRect` only); `paintBorder` |
| Input | `KB_HALFROWS`, `Keyboard` (half-rows, `bit(r,b)`, a real `port(hi)`), `buildKeymap` (arrows ARE 5/6/7/8), `attachKeyboard`, Kempston bits, `padBits`/`pollGamepads` |
| Sound | `AyChip`, `BeeperChip` (exact box integral, DC blocker, the ADDED 4.2 kHz speaker model behind `speakerFilter`), `SoundOut` — the bridge from an event log on the simulated clock to Web Audio: AudioWorklet FIFO transport with the scheduled path as fallback, whole-sample tiling, restart re-origin, adaptive lead, `info()` for bug reports |
| Loop | `makeLoop({hz, poll, step, draw})` — fixed simulation timestep under a free-running display |
| Settings | `settingsStore(key)` (guarded localStorage), `installThemeButton` |

What a port still writes: the engine, the front end and its text pages
(the runtime prints through any 8-byte-per-glyph font you extract; the
kit ships none), the game's key dispatch and any options/rebinding screen,
the extractors, and the differential gates.

## The two disciplines the kit assumes

**Faithful first, then a declared added layer.** The chips, the screen
arithmetic and the keyboard are the machine.  The speaker model, the second
Kempston port, the gamepad's sixth bit and the adaptive audio lead are
additions; each says so in its comment and each can be turned off.  Make
your own boundary an assertion, not an intention (manual 0.3).

**Measure, don't assume.** Every number in these comments was read off a
running Z80 or a real browser, and every behaviour in the suite was checked
by breaking it on purpose and watching the test fail.  Keep doing both.

## Provenance

Extracted 2026-08-30 from `cookertron/Gauntlet-JS` (the tools, runtime and
rig) and the Chuckie Egg port (the manual).  The Z80 core is SkoolKit's, a
dependency, not vendored; it also supplies the 48K ROM at run time.  Nothing
here contains any game's tape data.
