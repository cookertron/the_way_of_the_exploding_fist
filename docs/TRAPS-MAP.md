# Trap-to-check map for the Spectrum Port Kit

Every trap in `docs/TRAPS.md` (198 entries: 1-25 from the ports before Bubble Bobble, 26-196 from Bubble Bobble, 197 on from this port), mapped to the kit mechanism that should make it impossible to fall into again, and whether that mechanism exists yet. A rule that lives only in `TRAPS.md` protects the next port only if it is read at the right moment, which fails after a compaction and across days. A rule that lives in a tool, a gate helper or a hook protects it every time. Bubble Bobble's own log reached the same conclusion (TRAPS #169): writing a lesson down did not prevent it, and only an assert did.

Rules are one-line paraphrases; `python tools/manual.py T146` prints the full entry with its row here, and `python tools/manual.py --map gate` (or `--map BUILD`) lists the rows for one mechanism or state. States come from what the trap texts and the Bubble Bobble handover say. Where neither says a fix exists, the row is marked BUILD, so check before building.

## Summary

| State | Meaning | All 198 | #61 onward |
|---|---|---|---|
| KIT | the kit already prevents it | 60 | 33 |
| BB | built in the Bubble Bobble repo and generic; move it into the kit | 9 | 9 |
| BUILD | no mechanism yet; build it | 105 | 78 |
| READ | knowledge only; read by ID when relevant | 24 | 18 |

| Mechanism | Traps | Still to build |
|---|---|---|
| `gate`: Gate helpers in test/rig.js | 50 | 37 |
| `measure`: measure(), the single measurement entry point (manual 6.11) | 24 | 24 |
| `battery`: Kit mutation runner, tools/mutants.py (manual 6.12) | 23 | 6 |
| `lint`: Static checks on engine and test source | 14 | 11 |
| `harness`: Harness defaults and API in tools/harness.py | 10 | 8 |
| `roster`: Save-state manifest and census rules (manual 12.6) | 8 | 3 |
| `codemap`: adis, walk, grepbytes and the byte-usage map (phase 4, 12.5) | 8 | 8 |
| `status`: Ledger and status script (manual 12.2-12.4) | 5 | 2 |
| `build`: Build-time checks in tools/build.py | 6 | 3 |
| `platform`: Runtime in web/platform.js | 19 | 3 |
| `rig`: Test runner behaviour in test/rig.js | 4 | 0 |
| `hook`: Claude Code hooks (manual 12.8) | 3 | 0 |
| `manual`: General knowledge, kept as prose | 21 | 0 |
| `game`: Bubble Bobble facts | 3 | 0 |

## What each mechanism must enforce

Each mechanism's trap numbers are its acceptance tests: once it is built, each listed trap should be impossible to fall into, not just documented.

**`gate`: Gate helpers in test/rig.js** (50 traps; KIT 13, BUILD 37). The fixture must exist; the code under test must run on the gate's path; worlds are dirty and position-dependent by default; every comparison, wrap and last slot gets a boundary value; counts and footprints are asserted beside values; every instance is driven (both players); departures are off, and on/off must be byte-identical; a negative control must fail; seeds cover every field the code reads.  Built: `rig.gate` -- replay (a poisoned 64K, the whole of memory compared, the masked-store census), corrupt (the negative control), nonEmpty (an empty measurement throws), ran/missing (coverage from the machine's sig), distinct, sameSource, unnamed, untouched, the world builders (world.at/bounds/both/cross; worlds names each world a fixture lacks as a callio --derive --set; unseeded names stores never seen changing a byte); identity (the on/off identity gate: each declared flag off, each view flag on, beside the faithful run, the whole state every frame, a throwing step a named failure); guard (an engine's step and pass caught: the first throw kept in engine.threw for a row to check, the engine stopped there); each gated in kit.test.js.  Still to build: the seeding derive that empties unseeded.

Traps: #24, #37, #40, #44, #49, #50, #54, #55, #57, #60, #61, #62, #63, #66, #77, #78, #79, #88, #91, #93, #96, #98, #100, #104, #110, #111, #115, #122, #124, #125, #127, #128, #129, #131, #132, #133, #135, #138, #140, #141, #148, #157, #159, #164, #169, #175, #181, #190, #191, #197

**`measure`: measure(), the single measurement entry point (manual 6.11)** (24 traps; BUILD 24). Arms, then snapshots; poisons only the question's extent, around terminators, with a value the routine can't write; excludes only named windows and reports what it dropped; logs every write with its PC; records branch and straddle coverage; brackets by control flow; counts loop tops; takes stop_at; enumerates small input spaces; an empty result fails or says so; every result states its window.

Traps: #27, #34, #35, #46, #59, #64, #71, #87, #89, #90, #94, #102, #143, #144, #146, #147, #152, #153, #154, #160, #172, #182, #189, #193

**`battery`: Kit mutation runner, tools/mutants.py (manual 6.12)** (23 traps; KIT 15, BUILD 6, BB 2). Checks each mutation applied; requires the positive N/N baseline and a selectable copy that runs the same checks; reports dead and ambiguous anchors as red; tells a diagnostic, a broken mutant and a crash apart; gives timeouts their own verdict and keeps their FAIL lines; runs one battery at a time; reads its paths from port.json; records each case's killing row and block; runs only the blocks a case's anchor reaches, killing block first, stopping at the first failure, and confirms survivors against the whole suite; runs the affected cases per increment.  Still to build: anchors checked against live code rather than comments, a reason kept for every withdrawn case, per-verdict stamps, and pruning.

Traps: #23, #33, #70, #73, #106, #107, #118, #119, #126, #130, #137, #145, #158, #162, #166, #167, #177, #185, #186, #194, #195, #196, #198

**`lint`: Static checks on engine and test source** (14 traps; BUILD 11, BB 3). Page+offset addresses built with +, not |; DJNZ as an 8-bit decrement; no bare ram[] stores; an uncalled-method census; duplicate constants; call sites checked when a parameter is added; fallbacks flagged; numbers in labels and comments sourced or PROVISIONAL.

Traps: #45, #75, #81, #95, #99, #103, #113, #114, #117, #123, #134, #163, #173, #174

**`harness`: Harness defaults and API in tools/harness.py** (10 traps; KIT 2, BUILD 8). Contended timing by default; interrupts passed explicitly on every call; SP pinned per call, every call ending on a sentinel, PC and SP restored after; frame stepping to an absolute target; one absolute-address image accessor; registers by name.

Traps: #1, #2, #29, #38, #39, #41, #42, #69, #139, #151

**`roster`: Save-state manifest and census rules (manual 12.6)** (8 traps; KIT 5, BUILD 3). Computed tags per state (machine, detect bytes, PC and stack at capture, usable); every census states its population, N, window and whether play was natural or forced; variables that always co-occur are flagged.  Built: `tools/roster.py` -- every saved state a row of computed columns (hash, PC, SP and the stack top, patched code against the image, usable from the heartbeat and a distinct-PC count, one column per declared world variable) with the census of columns that never vary and pairs set together in every state; stamp.step() records the rows a measurement read and stales one taken on an unusable state; status.py warns when the roster is stale or misses a state.  Still to build: censuses that state their population, N and window (natural play vs forced), and the differ grouping its mismatches by roster column.

Traps: #28, #31, #67, #84, #150, #165, #183, #188

**`codemap`: adis, walk, grepbytes and the byte-usage map (phase 4, 12.5)** (8 traps; BUILD 8). Decode only from known entries; census every reference form; mark fall-through entries, tail jumps and pushed return addresses; list each routine's callers with their tests; list every writer of a patched byte.

Traps: #51, #52, #58, #68, #74, #80, #83, #121

**`status`: Ledger and status script (manual 12.2-12.4)** (5 traps; KIT 3, BUILD 2). Ledger facts carry the command that settles them, and a negative fact its window and n (record.py refuses it otherwise; status.py --check validates every ledger file); every fixture has a reader (warned); counts are derived, never typed; fixtures come only from their tool (stamps, still to build).

Traps: #32, #48, #65, #97, #116

**`build`: Build-time checks in tools/build.py** (6 traps; BUILD 3, BB 3). Ship only assets the engine reads; a page-size budget; every shipped asset traced to exactly one tape source; substitute glyphs that differ from the ROM's.

Traps: #3, #43, #47, #109, #136, #155

**`platform`: Runtime in web/platform.js** (19 traps; KIT 16, BUILD 3). The audio bridge, input handling and shipped diagnostics; plus counted guards and named-throw bounds set above the machine's worst case.

Traps: #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #18, #19, #20, #25, #105, #108, #192

**`rig`: Test runner behaviour in test/rig.js** (4 traps; KIT 3, BB 1). Real browser services; the positive N/N signal and counted merges; short names and terse output; at least one assertion on rendered output.

Traps: #17, #21, #22, #92

**`hook`: Claude Code hooks (manual 12.8)** (3 traps; KIT 3). Code files are written with the Write/Edit tools, never through shell heredocs; the manual and the traps are read by ID; every session starts with the names of the scripts in tools/, and selftest fails on a script without a row in tools/README.md.

Traps: #149, #168, #170

**`manual`: General knowledge, kept as prose** (21 traps; READ 21). Belongs in the manual's catalogue, read by ID when relevant.

Traps: #4, #26, #30, #36, #53, #56, #72, #76, #82, #85, #86, #101, #112, #120, #142, #156, #161, #171, #176, #180, #187

**`game`: Bubble Bobble facts** (3 traps; READ 3). Belong in that game's ledger, not in the kit.

Traps: #178, #179, #184

## The map

| # | Rule | Mechanism | State |
|---|---|---|---|
| 1 | Measure under contended timing; uncontended runs the game measurably fast. | `harness` | KIT |
| 2 | Boot through the tape's own loader, block by block, unpatched. | `harness` | KIT |
| 3 | Verify every extracted asset against the tape bytes; refuse to ship a mismatch. | `build` | BUILD |
| 4 | An asset is the record the game decodes, not a capture of the screen. | `manual` | READ |
| 5 | Put audio buffers on the sample grid: floor both ends, never round a length. | `platform` | KIT |
| 6 | Cut the event log by buffer window, not by frame. | `platform` | KIT |
| 7 | Treat a backward jump of the simulated clock as a restart, not drift. | `platform` | KIT |
| 8 | Count voices against the clock, never in onended. | `platform` | KIT |
| 9 | Adapt the jitter budget to measured underruns only. | `platform` | KIT |
| 10 | Ask the browser for the playback-stability buffer. | `platform` | KIT |
| 11 | Model the speaker cone by default; keep raw voltage as a toggle. | `platform` | KIT |
| 12 | Stream audio continuously rather than scheduling many buffers. | `platform` | KIT |
| 13 | Load worklet modules from data: URLs; blob URLs fail on file://. | `platform` | KIT |
| 14 | Never let a fallback engage silently; diagnostics name it and why. | `platform` | KIT |
| 15 | Average content above Nyquist instead of point-sampling it. | `platform` | KIT |
| 16 | Render with fillRect/fillStyle only, so the rig can diff draw lists. | `platform` | KIT |
| 17 | Give the rig real browser services, so failures can surface. | `rig` | KIT |
| 18 | Map the arrow keys to the Spectrum's cursor keys (5-8). | `platform` | KIT |
| 19 | Ignore keys aimed at form fields; don't let buttons keep focus. | `platform` | KIT |
| 20 | Release every key when the window loses focus. | `platform` | KIT |
| 21 | One key script through harness and engine, diffed row by row. | `rig` | KIT |
| 22 | Freeze the oracle's output as a fixture the suite runs against. | `rig` | KIT |
| 23 | Mutation-test every behaviour; a named check must fail. | `battery` | KIT |
| 24 | Run each enhancement on and off and require byte-identical state. | `gate` | KIT |
| 25 | Ship diagnostics; on a player's machine they are the debugger. | `platform` | KIT |
| 26 | The static image is post-boot; study the front end in a live state. | `manual` | READ |
| 27 | An empty watch result first rules out a degenerate range. | `measure` | BUILD |
| 28 | Record the machine-detect bytes per state; a key script can flip the detect. | `roster` | KIT |
| 29 | Frame stepping overshoots cumulatively; add an absolute-target mode. | `harness` | BUILD |
| 30 | A self-modifying PRNG's cycle depends on its seed; don't reuse it elsewhere. | `manual` | READ |
| 31 | Distribution claims come from natural play; forced scenarios only reach paths. | `roster` | BUILD |
| 32 | Scope a 'nothing reads it' claim to what was watched: its window. | `status` | KIT |
| 33 | A gate that re-implements its subject can't fail; the battery exposes it. | `battery` | KIT |
| 34 | Sample fixtures at structural boundaries (ISR entry, RET), not T offsets. | `measure` | BUILD |
| 35 | Bracket a routine's cost by control flow, never by the stack pointer. | `measure` | BUILD |
| 36 | Get a region's extent first; a known hazard can arrive disguised. | `manual` | READ |
| 37 | Make a routine's two inputs differ, and use synthetic assets with no zeros. | `gate` | BUILD |
| 38 | Remove or flag counters that are dead under the fast simulator. | `harness` | BUILD |
| 39 | Require interrupts to be passed explicitly on every call. | `harness` | BUILD |
| 40 | Ask what the sampled world makes equal, and build worlds that separate them. | `gate` | BUILD |
| 41 | Read memory images through one absolute-address accessor. | `harness` | BUILD |
| 42 | Pin SP per call and assert every call ends on a sentinel. | `harness` | BUILD |
| 43 | Seed tape data from the tape image, never from a live dump. | `build` | BUILD |
| 44 | Seed every field a routine assigns to a different value first. | `gate` | BUILD |
| 45 | Transliterate DJNZ as an 8-bit decrement with its exit test, not a for loop. | `lint` | BUILD |
| 46 | Enumerate a deterministic quantity's inputs rather than sampling it. | `measure` | BUILD |
| 47 | Trace every shipped range to exactly one source in the tape image. | `build` | BUILD |
| 48 | A negative claim carries its window and N; a grep can't prove it. | `status` | KIT |
| 49 | Vary a walk's start position (page edges, alignments), not just contents. | `gate` | BUILD |
| 50 | Seed so a routine's effect is visible, and gate loop counts too. | `gate` | BUILD |
| 51 | For patched code, list every writer, including the one that restores it. | `codemap` | BUILD |
| 52 | No callers doesn't mean dead: check for a fall-through entry. | `codemap` | BUILD |
| 53 | Confirm a mapping through a second, independent encoding. | `manual` | READ |
| 54 | For walks and paints, assert the total write count, not just expected cells. | `gate` | BUILD |
| 55 | Check a gate can see what it is named for; symmetry can hide it. | `gate` | BUILD |
| 56 | A loop's cursor can advance inside a callee; read calls through to RET. | `manual` | READ |
| 57 | Gate idempotent effects by count; prove 'cannot wrap' before withdrawing. | `gate` | BUILD |
| 58 | Census every reference form: conditional calls, JPs, RSTs, bare words. | `codemap` | BUILD |
| 59 | Destructive experiments snapshot and restore everything they can reach. | `measure` | BUILD |
| 60 | Seed every page a walk can reach; build a world that separates each model. | `gate` | BUILD |
| 61 | Gate the computation behind a declared departure directly. | `gate` | BUILD |
| 62 | Transliterate dead work too, and gate it by write count. | `gate` | BUILD |
| 63 | The gate's call path must include the code under test. | `gate` | BUILD |
| 64 | Choose each claim's bracket by when its evidence is destroyed. | `measure` | BUILD |
| 65 | Read the docstring of any tool a plan names before writing a new one. | `status` | BUILD |
| 66 | Check that the oracle's input and the engine method's input are the same. | `gate` | BUILD |
| 67 | Record each state's PC and stack top; a state can resume mid-routine. | `roster` | KIT |
| 68 | Decode from known entries only; one byte into a prefix invents code. | `codemap` | BUILD |
| 69 | Restore PC and SP after call(); sentinels can collide with game bytes. | `harness` | BUILD |
| 70 | Mutate the value that lands; a typed array masks it for you. | `battery` | BUILD |
| 71 | Interval claims name their window; rare states need long windows. | `measure` | BUILD |
| 72 | Wiring is a separate act from gating; missing resets surface there. | `manual` | READ |
| 73 | Report listed, live and killed; a dead anchor is a red result. | `battery` | KIT |
| 74 | Census the address itself, then classify the byte in front of it. | `codemap` | BUILD |
| 75 | Build page+offset addresses with +, not \|; OR hides the carry. | `lint` | BUILD |
| 76 | Enumerate every address an index can produce, not only those play uses. | `manual` | READ |
| 77 | Use position-dependent sources (checkerboards) to test address maths. | `gate` | BUILD |
| 78 | Blit gates compare values too, over every value a pointer's writers store. | `gate` | BUILD |
| 79 | Drive all four corners of a self-modified instruction pair. | `gate` | BUILD |
| 80 | Treat a pushed literal return address as part of the routine. | `codemap` | BUILD |
| 81 | Every store goes through the instrumented path; no bare ram[] writes. | `lint` | BUILD |
| 82 | A CALL can return a datum in a register pair; follow the callee's last write. | `manual` | READ |
| 83 | List a routine's callers and their tests before porting its entry condition. | `codemap` | BUILD |
| 84 | 'What play does' needs a sweep of scripts, reported with its N. | `roster` | BUILD |
| 85 | A reachable set is not a rate; measure rates over counted trials. | `manual` | READ |
| 86 | Key tables hold AND-masks; convert explicitly and add a positive control. | `manual` | READ |
| 87 | End a bracket where both arms converge; two zero readings are the tell. | `measure` | BUILD |
| 88 | Pair touched-position sets with changed-cell counts. | `gate` | BUILD |
| 89 | Profile a routine's address range before claiming it didn't run. | `measure` | BUILD |
| 90 | Sample the driving clock at each consumer and count straddling rows. | `measure` | BUILD |
| 91 | Seed every field the code reads, not only the fields compared. | `gate` | BUILD |
| 92 | Assert something about the rendered output, not only RAM agreement. | `rig` | BB |
| 93 | Gate the seed itself; one step off looks right in every row. | `gate` | BUILD |
| 94 | Arm a routine where the game enters it; a wrong entry invents defects. | `measure` | BUILD |
| 95 | Count call sites, not methods; an uncalled method is untested. | `lint` | BB |
| 96 | Compare values as well as write counts; one-sided misses mean a missing input. | `gate` | BUILD |
| 97 | Never hand-edit a fixture; fixes belong in the tool that writes it. | `status` | BUILD |
| 98 | Also test the generated sequence from reset, not only seeded inputs. | `gate` | BUILD |
| 99 | Every constant names its source; try correcting an unsourced one. | `lint` | BUILD |
| 100 | Feed each gate a known-wrong value and require it to fail. | `gate` | KIT |
| 101 | The ISR can reach code without a HALT; capture both, model one. | `manual` | READ |
| 102 | Measure an extent with a write-watch unioned with the diff. | `measure` | BUILD |
| 103 | Keep an uncalled-method census as a counted, standing check. | `lint` | BB |
| 104 | A gate's two sides must come from different sources. | `gate` | KIT |
| 105 | Guard domains the machine never had, and count every guard hit. | `platform` | BUILD |
| 106 | Bound transliterated loops; judge long jobs by artifacts, not silence. | `battery` | BUILD |
| 107 | Give timeouts their own verdict; never report a hang as a pass. | `battery` | KIT |
| 108 | Bound the quantity that actually grows, with measured headroom. | `platform` | BUILD |
| 109 | Ship only the assets the engine reads; the rig counts test assets it merges. | `build` | BB |
| 110 | Assert that what a check measured is non-empty. | `gate` | KIT |
| 111 | Seed the state a routine reads; narrow declared gaps in the same increment. | `gate` | BUILD |
| 112 | When a faithfulness fix turns gates red, ask if they passed by accident. | `manual` | READ |
| 113 | Flag duplicated constants; a copy can't be mutation-tested. | `lint` | BUILD |
| 114 | Two spellings of one rule drift apart; the census finds the dead copy. | `lint` | BB |
| 115 | Test worlds must be states the machine can actually reach. | `gate` | BUILD |
| 116 | Every artifact a tool writes has a reader, checked by script. | `status` | KIT |
| 117 | Counts in a check's text are derived from the code, never typed. | `lint` | BUILD |
| 118 | Verify each mutation actually applied; NOT-APPLIED is its own verdict. | `battery` | KIT |
| 119 | Runners take paths from config; empty-list checks need a control. | `battery` | KIT |
| 120 | A loop count that disagrees with its table is a measurement, not a typo. | `manual` | READ |
| 121 | A JP into a routine runs the rest of it; map tail jumps as calls. | `codemap` | BUILD |
| 122 | Reject all-zero or uniform tables in a gate unless declared. | `gate` | KIT |
| 123 | Structural claims in comments stay PROVISIONAL until measured. | `lint` | BUILD |
| 124 | Every guard needs a world that trips it. | `gate` | BUILD |
| 125 | Poison first when a routine's job is to make memory match a source. | `gate` | KIT |
| 126 | Withdraw a mutation that changes nothing only with its reason recorded. | `battery` | BUILD |
| 127 | Drive the routine with a world, not its helper with arguments. | `gate` | BUILD |
| 128 | Derive a wrap's test points from where the wrap can occur. | `gate` | BUILD |
| 129 | Two instructions clearing one flag need a world where only one runs. | `gate` | BUILD |
| 130 | Collapsing duplicate code kills anchors on the copy; re-anchor deliberately. | `battery` | KIT |
| 131 | Test a store against a target holding a different value. | `gate` | KIT |
| 132 | Drive both players, or every instance, of a multi-instance routine. | `gate` | BUILD |
| 133 | Assert the footprint (which cells), not only the count. | `gate` | KIT |
| 134 | Build page+offset with +; OR forgives a low-byte bit already set. | `lint` | BUILD |
| 135 | Assert reset values against the tape, behaviour against the fixture. | `gate` | BUILD |
| 136 | Substitute glyphs are asserted to differ from the ROM's cells. | `build` | BB |
| 137 | Record why each withdrawn equivalent is equivalent. | `battery` | BUILD |
| 138 | Length is not coverage: gate every branch the trajectory skips. | `gate` | BUILD |
| 139 | When results degrade with iteration count, suspect the probe. | `harness` | BUILD |
| 140 | Poison, then assert the routine wrote exactly these cells and no others. | `gate` | KIT |
| 141 | Make the last slot and the exact threshold load-bearing. | `gate` | BUILD |
| 142 | Some writes are observed only by the ISR; gate their order in the source. | `manual` | READ |
| 143 | Sweep a comparison where its two sides can straddle. | `measure` | BUILD |
| 144 | A sweep that finds nothing fails or says so out loud. | `measure` | BUILD |
| 145 | Check which row kills a case; it may be a check above the target. | `battery` | KIT |
| 146 | Snapshot after arming, never before. | `measure` | BUILD |
| 147 | Exclude named windows only, and report what was dropped. | `measure` | BUILD |
| 148 | Measure the step the gate names, as a difference of two runs. | `gate` | BUILD |
| 149 | Write code with the Write/Edit tools, never through shell escaping. | `hook` | KIT |
| 150 | Mark hung captures unusable in the roster manifest. | `roster` | KIT |
| 151 | Address registers by name; check a probe aims before sweeping. | `harness` | BUILD |
| 152 | Poison only the question's extent; report contiguous runs. | `measure` | BUILD |
| 153 | Attribute every write to its PC before explaining it. | `measure` | BUILD |
| 154 | Compare censuses only over the same window. | `measure` | BUILD |
| 155 | Substitute glyphs must differ substantially, not by a byte. | `build` | BB |
| 156 | A wider mask downstream can absorb an inner one; check before gating. | `manual` | READ |
| 157 | Drive a wrap from an address on its boundary. | `gate` | BUILD |
| 158 | A case superseded by construction names the row that now holds the claim. | `battery` | BUILD |
| 159 | Don't wipe all memory in a gate; restore what the routine reads. | `gate` | KIT |
| 160 | Prove 'unreachable' by enumerating inputs, not by sampling. | `measure` | BUILD |
| 161 | Wiring a routine can make the stubs around it dishonest; recheck them. | `manual` | READ |
| 162 | Check anchors after every edit; new code can kill one in place. | `battery` | BB |
| 163 | When a method gains a parameter, check every call site. | `lint` | BUILD |
| 164 | Gate a count bound and a terminator bound separately. | `gate` | BUILD |
| 165 | A census counts the machine's population, not your own table. | `roster` | BUILD |
| 166 | Run one battery at a time, and don't edit the tree mid-run. | `battery` | KIT |
| 167 | The baseline must show the positive N/N signal. | `battery` | KIT |
| 168 | Parse generated source before writing it; no heredocs. | `hook` | KIT |
| 169 | Enumerate categories in code and assert none is unnamed. | `gate` | KIT |
| 170 | Every session lists the tools; selftest fails on an unregistered script. | `hook` | KIT |
| 171 | A counter's name states its unit. | `manual` | READ |
| 172 | A diff can't see a write of an unchanged value; poison first. | `measure` | BUILD |
| 173 | A number in a check's label must be read by its predicate. | `lint` | BUILD |
| 174 | Prefer a throw to a fallback lookup. | `lint` | BUILD |
| 175 | Measure coverage against the machine, not the port's own register. | `gate` | KIT |
| 176 | Accidental agreement is still a defect; enumerate its class. | `manual` | READ |
| 177 | A guard added during a fix can be dead on arrival; the battery shows it. | `battery` | KIT |
| 178 | The gate keyed on the delta's sign; the machine uses the phase counter. | `game` | READ |
| 179 | One routine has two bottom wraps, and they differ. | `game` | READ |
| 180 | A mask that looks cosmetic can switch a whole behaviour. | `manual` | READ |
| 181 | When no caller can express a difference, gate the routine at its entry. | `gate` | BUILD |
| 182 | Poison where the routine actually writes, with a telling value. | `measure` | BUILD |
| 183 | Choose census worlds that contain the thing being counted. | `roster` | KIT |
| 184 | The same bits are paint at one time and bubble tags at another. | `game` | READ |
| 185 | Decode suite output as UTF-8 and require the N/N line. | `battery` | KIT |
| 186 | An anchor must match live code, not a comment; keep a count invariant. | `battery` | BB |
| 187 | When a slow check reports a class of error, write the fast one. | `manual` | READ |
| 188 | Flag variables that are set together in every world you built. | `roster` | KIT |
| 189 | Poison around NUL terminators, never over them. | `measure` | BUILD |
| 190 | Drive input-gated routines with input, beside a refusal control. | `gate` | BUILD |
| 191 | Seed data that separates the headline claim from its equivalents. | `gate` | BUILD |
| 192 | Set diagnostic bounds above the machine's worst case, not the best observed. | `platform` | BUILD |
| 193 | Count loop tops for iterations; don't divide write totals. | `measure` | BUILD |
| 194 | Syntax-check each mutant; a hang can be its own malformation. | `battery` | BUILD |
| 195 | Check anchor uniqueness; a repeated idiom matches many lines. | `battery` | KIT |
| 196 | Drain FAIL lines before killing a timed-out run. | `battery` | KIT |
| 197 | Step the engine inside a catch that fails a named row. | `gate` | KIT |
| 198 | Read what a long run ran against when it starts, and stamp each result. | `battery` | KIT |

## Keeping the map honest

- A new trap is recorded with its row here: the rule, the mechanism that now prevents it, and the state. READ is allowed only when no mechanism can catch it, and the entry says why.
- A trap moves from BUILD to KIT when its mechanism lands, and the mechanism's test suite includes a case that would have caught it.
- `python tools/selftest.py` fails if a trap has no row here, or a row names no trap. `python tools/manual.py --map` prints the totals: READ and BUILD should both shrink with every port, and if READ grows, lessons are going back into prose.
- READ rows are the only ones a session should ever need to read, by ID, when the work touches them. `game` rows move to the game's own ledger and leave the kit.

