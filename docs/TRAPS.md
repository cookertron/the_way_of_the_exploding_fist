# Traps — what earlier ports paid to learn

Each entry is a measurement, not an opinion.  The manual
(`docs/PORTING-ZX-TO-JS.txt`) says what to do in each phase; this file is
the list of places a careful engineer still fell in, with the number that
proved it.  Entries 1-25 predate Bubble Bobble; 26-196 come from it.

Do not read it end to end.  `docs/TRAPS-MAP.md` maps every entry to the
mechanism that should make it impossible to fall into again, and whether
that mechanism exists yet.  Read an entry by number when the map, the
session status or a surprising result points at it:
`python tools/manual.py T146`.  A new entry is not recorded until it has
its row in the map, and `python tools/selftest.py` checks that it has.

## Simulation and the oracle

1. **Contended timing changes the game's speed.**  The plain simulator and
   the contended (CMIOSimulator) one disagreed by 7,400 T a main-loop pass
   in the case study: 11.3 Hz uncontended against 10.0 Hz contended, and
   real hardware is the contended figure.  The harness defaults to
   contended; every pass-rate, clock and sound-cadence measurement is wrong
   on the other setting.

2. **Boot the real loader, in order, unpatched.**  Loading blocks "by fiat"
   (copying them into memory and jumping to the entry) skipped a paging
   probe the loader itself ran, left a mode byte at a stale value, and put
   EVERY sound measurement for weeks on the wrong (128K/AY) branch of a
   game that was actually a 48K beeper game on the owner's machine.  The
   fix was a boot that ran the loader's own code between blocks.  If the
   loader does anything but LOAD, let it do it.

3. **An emulation bug can look exactly like a tape fault.**  A corrupt glyph
   was reproduced in a third-party emulator too and blamed on tape
   mastering.  It was the simulator's own interrupt landing while the game
   ran with SP pointed at sprite data; the ISR's pushes scribbled return
   addresses over the tail bytes.  Under contended timing it never
   happened.  Verify every extracted asset against the tape bytes, and
   refuse to ship one that is not genuinely there.

4. **Asset extraction reads the live buffer, not the screen.**  A sprite
   captured off the display is one frame of one draw under one palette;
   the sprite RECORD the game decodes is the asset.  Capture at the instant
   the blitter finishes, or decode the record format outright.

## The audio bridge

5. **Tile buffers on the sample grid — floor BOTH ends, never round a
   length.**  A 50.08 Hz frame is 880.591 samples at 44.1 kHz; rounding
   the length while placing the start exactly made every buffer a fraction
   of a sample too wide or narrow.  Measured: 426 of 1,042 joins collided,
   mixed peak 1.2169 against a largest single sample of 0.9996.  Taking
   both ends onto the grid makes buffers abut by construction for any
   frame count; floor keeps an edge's time inside its own buffer
   non-negative (round put 0.495 of full scale on one sample, −44 dB).

6. **Cut the event log by the WINDOW, not by the frame.**  The buffer ends
   on a sample boundary, up to one sample short of the frame's exact time;
   an edge in that sliver must stay in the log for the next buffer.
   Splicing it with only its level applied cost −54 dB on a two-voice tune
   whose edges are 0.6 of a sample apart.

7. **A backward jump of the simulated clock is a RESTART, not drift.**
   Without a re-origin branch the game played SILENT for as long as the
   menu before it had lasted — 19.3 s after a 930-frame menu.

8. **Count voices against the clock, never in `onended`.**  That callback
   may never fire on a suspended context, and then the cap never releases.

9. **The jitter budget must adapt.**  A fixed 80 ms head start tore the
   schedule on a gaming laptop whose main thread stalls longer than that,
   twice per stall (the gap, then another lead of silence from the
   resync).  Ratchet the lead by the MEASURED deficit on genuine underruns
   only; never on restarts; never decay it.

10. **Ask for the stability buffer.**  `latencyHint: 'playback'`, not the
    default 'interactive' (the smallest hardware buffer the OS will serve).
    A game's sound is quantised to its own frame or pass anyway.

11. **The speaker is a cone, not a voltmeter.**  A bit-exact square wave is
    faithful to the ULA's output pin, not to what anyone heard; the game's
    own chirps reach 7.4 kHz and small laptop drivers buzz on raw edges.
    The 4.2 kHz second-order model stays on by default; the raw voltage is
    one console toggle away for A/B.  (It was NOT the crackle — see 12 —
    but it stays on its merits.)

12. **One continuous stream beats many scheduled buffers.**  A laptop
    crackled on the joins between per-frame buffer sources while a native
    emulator played the same game clean on the same machine — the
    emulator's audio is a pull-model stream.  The worklet FIFO transport is
    that; the crackle lived exactly where joins were densest (the title
    tune, 50 buffers a second) and vanished with it.

13. **Blob worklet modules fail on `file://`.**  Measured in headless
    Chrome: `audioWorklet.addModule(blobUrl)` → `AbortError: Unable to load
    a worklet's module`; a `data:` URL loads, constructs and messages.  A
    double-clicked download IS `file://`.  Try blob, fall back to data.

14. **Never let a fallback engage silently.**  The first worklet build fell
    back to the scheduler without a word, and it took a full remote
    debugging round trip to learn that the fix had never run.  `info()`
    names the transport and the reason it is not the preferred one.

15. **Above-Nyquist content must average, not fold.**  Game data routinely
    holds pitches at 15–21 kHz; a point-sampled square folds them into the
    audible band as a whine that is not in the original.  The beeper's box
    integral and the AY's stepped mean both exist for this (a 100 kHz
    square renders below 0.12 peak, derived bound 0.11).

## The page and the rig

16. **Render with primitives only.**  `fillRect` and `fillStyle`, nothing
    else — so the headless rig can record the draw list and DIFF two
    renders that differ by one flag.  Everything visual then has a test.

17. **A test that cannot fail is not a test.**  Persistence checks passed
    for weeks because the rig had no localStorage and the code guards every
    call in try/catch: save wrote nowhere, load read nothing, nothing
    failed.  The rig now has a real store, and `settingsStore.save` reports
    whether the write landed.

18. **The arrow keys ARE the Spectrum's cursor keys.**  On a 48K, cursor
    left/down/up/right are 5/6/7/8; mapping the arrows onto them is the
    machine, not a convenience.

19. **Keystrokes aimed at a form field are not game keys**, and a button
    left holding focus swallows SPACE.  Guard the first; blur the second.

20. **Losing window focus loses the keyup.**  Release everything on `blur`
    or the player walks into a wall until they press the key again.

## Method

21. **The differential gate is the whole method in one shape.**  One
    sampler at the main-loop top; the same key script through the harness
    and through the built engine; two tables diffed row for row.  The
    first differing row names the bug.  Every other tool exists to feed it.

22. **Freeze the oracle's answer as a fixture.**  When a gate needs the
    tape and the tape is not always available, the real Z80's own output
    lives in `build/*.json` and the headless suite runs against it.

23. **Mutation-test, then trust.**  Break the behaviour on purpose and
    watch the NAMED test fail.  A mutation that nothing catches is either a
    missing test or proof that the line is not load-bearing — both are
    worth knowing, and only the first is a bug.

24. **The added layer is a boundary only if a test says so.**  Run the
    simulation with the enhancement on and off and require the state to be
    byte-identical.  Intent is not a boundary.

25. **On a machine you cannot touch, shipped diagnostics are the
    debugger.**  Every decisive measurement in the audio saga came from the
    player's side: a control experiment (the emulator), one pasted `info()`
    line, and a localisation ("only the title tune").  Build for that.

26. **The static image is POST-BOOT — the front end is not in it.**
    `build/image.bin` is the game after the loader handed over, so the
    control-select / key-redefine front end (`$F5xx-$F9xx`) and the
    one-shot key-table copier `$95F3` (which self-overwrites after its
    `LDIR`) are gone — grepping the image for "the writer of `$B5FD`" finds
    nothing.  Study those in a LIVE title state (`title.pkl`) or by driving
    the menu, not the image.  (M5 bucket-A cost a "no literal writer exists"
    dead-end before this was noticed.)

27. **`Mem.watch(lo,hi)` is HALF-OPEN `[lo,hi)`.**  `watch(a,a)` logs
    nothing; use `watch(a,a+1)` to watch one byte.  An earlier "the boss
    death award never fires" and a "0 writes to enemy `+9`" reading were
    both this off-by-one, not a real absence.  When a write-watch comes
    back empty, first check the range is not degenerate before concluding
    the code path is dead.

28. **The machine detect can be a TIMING PROBE -- and your key script can
    flip it.**  Bubble Bobble decides 48K-vs-128K by counting loop
    iterations across 255 ROM-FRAMES ticks (`$FAC3`) and accepting exactly
    two counts; the count moves with ULA contention and with the ROM ISR's
    keyboard work.  The M2 script held a key through that 5-second credits
    screen, the count came out two blocks low, the game took the 128K branch,
    copied its AY engine over the sprite region, and every harness play
    state for three milestones was on the wrong branch (M3 then read the
    ISR's draw pass as "the music").  Uncontended simulation misdetects too.
    Rules: (a) after the loader, find the branch decision by WATCHING what
    patches the sound hooks, not by reading BANKM; (b) keep contention ON;
    (c) release keys before any long front-end wait and check the decision
    byte (`$8DC4` here) in every saved state; (d) attribute `OUT`s by the
    executing PC (`tools/sfxcensus.py`) -- a static `D3 FE` scan matched
    data bytes.

29. **`run_frames(1)` overshoots, and the overshoot ACCUMULATES.**  Each
    call targets `T + FRAME_T` from wherever the previous call stopped and
    stops up to one instruction late, so over N calls the capture window
    drifts late (~5 T/call measured).  After ~80 calls the NEXT frame's
    early-ISR work leaked into the current window -- here the bubble pool's
    `+4` tick, ~400 T into the frame -- while the frame counters, which the
    same ISR increments LATE, did not: parity looked right and one field was
    one frame early.  Two identical scenarios captured with different call
    granularity then DISAGREED, which is the tell.  Rules: (a) capture long
    fixtures against ABSOLUTE boundaries `t0 + k*FRAME_T`
    (`run_until((), stride=1, predicate=T >= target)`); (b) when a fixture
    and a write-watch differ by exactly one frame, suspect the window, not
    the game -- re-run with a different call granularity before touching
    the engine; (c) long captures are safe for observables written late in
    the frame (main-loop physics); re-check anything the ISR writes early.
    (Kit candidate: give `run_frames` an absolute-target mode.)

30. **A self-modifying PRNG's cycle length is SEED-dependent -- never reuse the map
    as a general stream** (Bubble Bobble, 2026-09-10, docs/RNG.md).  `$FE85` is the
    game's real generator: a 16-bit hash whose state IS its own `LD HL,nn` operand.
    It is a bijection, so every seed lies on a cycle -- but the cycles differ wildly.
    From the tape seed `$002A` the orbit is 54,919 long; from `$BB02` it is 7,503,
    which at the blocked-bubble draw rate repeats inside 3-4 minutes of play, and
    short-orbit seeds score chi2 636-852 on 127 df.  So: transliterate it for its own
    consumers, seed it only the way the machine does, and NEVER borrow it as the
    substitute stream for other sites "because it is already there".

31. **A forced scenario manufactures the statistics you then measure**
    (Bubble Bobble, 2026-09-10).  Chasing a rare RNG path, one census built a
    6-bubble cluster and re-poked it every 40 frames.  That scenario produced chi2
    221.7 on 127 df at a site where NATURAL play measures 123.8 -- an apparently
    damning non-uniformity that was entirely an artefact of the harness driving the
    same code path in lockstep.  Distribution claims must come from natural play;
    forced scenarios are for REACHING a path, not for characterising it.

32. **"No RNG here" from a fixture that logged only ONE site is a false invariant**
    (Bubble Bobble, 2026-09-10, caught by a completeness critic before it shipped).
    Two bubble fixtures record zero random draws, and a proposed gate turned that
    into "this replay consumes no RNG at all".  But the captures logged the bubble
    site alone: on the same idle round-1 scenario the ENEMY hesitation site fires 22
    times in 400 frames.  The assertion was true only because that site was not yet
    wired, and would have gone red the day the enemy work landed correctly.  Scope a
    zero-consumption assertion to the SITE the fixture actually measured, and re-check
    it when a new consumer is wired.  General form: a fixture's silence about X is not
    evidence that X did not happen.

33. **A gate that RE-IMPLEMENTS the logic it tests cannot fail** (Bubble Bobble,
    2026-09-10, caught by my own mutation battery one increment after a critic
    flagged the same class).  The RNG gate checked that a draw is seven bits --
    the single most consequential property, since believing otherwise is the
    1/256 bug the SPEC taught for months.  It built its sample with a local
    helper that did the shift ITSELF rather than calling the engine's.  Every
    frozen constant matched, the gate went green, and mutating the engine's
    extraction to eight bits changed nothing: the test was testing the test.
    Rule: a gate must reach the property through the SAME function the shipped
    path uses -- one source of truth for the computation, exercised by name --
    and where a property is load-bearing, assert it a SECOND way through the
    real call path (here: draw 50,000 values through `rng.draw()` and check the
    maximum), so a mutation that bypasses the shared helper still fails.
    House rule 3 is not satisfied by running the battery; it is satisfied by
    watching each mutation fail a NAMED check, and by treating a mutation that
    does NOT fail as a finding about the gate rather than a pass.

34. **A fixture captured at a fixed T-offset inside a long ISR does not record
    the machine's per-frame state -- it records a CUT THROUGH ONE PASS, and a
    model fitted to it will be confidently wrong** (Bubble Bobble, 2026-09-11;
    the most expensive error on this project so far, shipped and gated for a
    day before a 10-agent measurement workflow caught it).
    The bubble manager was recorded as "split by slot across frame parities":
    pool slot 0 serviced on one parity, slots 1-11 on the other.  That model
    was derived from per-frame PC counts and per-slot write-watches, it was
    written into the SPEC, transliterated into the engine, and three fixture
    scenarios passed against it FRAME FOR FRAME.  It was false.  The machine
    runs ONE unconditional twelve-slot loop, entirely inside one parity's ISR.
    WHAT ACTUALLY HAPPENED: the captures sampled at a fixed `t0 + k*FRAME_T`
    offset, and that offset lands INSIDE the even ISR -- after slot 0's X write
    (+808 T) but before slot 0's `+4` write (+2255 T).  So one manager pass was
    sliced in half: slot 0's pre-sample work appeared on one row, and slot 0's
    tick plus ALL of slots 1-11 appeared on the next.  Two half-passes read
    exactly like two alternating half-schedules.  The reconstruction is
    constructive, not a story: the fixture reproduces with ZERO differing rows
    for sampling phases +1650..+2250 T and for no other phase.
    WHY THE GATES DID NOT CATCH IT: they compared X, and X advances on the same
    row under both models.  The column that separates them is the AGE, because
    it advances in the SAME pass as the move.  The gate was blind BY COLUMN as
    well as by boundary -- so "it passes frame-for-frame" meant only "it agrees
    on the columns I happened to compare, at the phase I happened to capture".
    RULES: (a) sample a fixture at a STRUCTURAL boundary -- run to the ISR
    entry, step in, run to its RET -- never at a fixed `T mod FRAME_T`, because
    the ISR's length is state-dependent (measured 1841 T empty to over 112000 T
    with a full pool, i.e. more than a whole frame); (b) record the sample PC on
    every row, which would have shown these rows landing mid-routine and caught
    it at capture time; (c) assert the boundary as a field in the fixture and
    check it in the gate; (d) when a model says two things happen on different
    frames, gate a column that MUST move with each of them, not one they share;
    (e) a schedule claim needs a scenario that DISCRIMINATES it -- here, a
    bubble in slot 1 with slot 0 deliberately EMPTY, which the two models
    predict as exact mirror images.

35. **Never bracket a routine's cost by watching the STACK POINTER return --
    one such bracket produced TWO wrong conclusions and both shipped**
    (Bubble Bobble, 2026-09-11, docs/TIMING.md).  The IM2 handler's cost was
    measured from its entry until SP rose back above its entry value.  But the
    sprite blitter parks the stack on the sprite and switches it repeatedly
    ($A437 `LD SP,IX`, $A489 `LD SP,HL`, 14 switches per odd interrupt), so the
    bracket stopped at $A48A after 1481 T inside a routine that really costs
    ~27000 T -- a factor of 19.  That alone would have been bad enough.  The
    compounding failure: the first display write happens 139 T AFTER the bracket
    gives up, so all ~288 writes fell OUTSIDE the measured "interrupt" and were
    attributed to the main loop.  The project then recorded, in the SPEC, in a
    fixture and in three comments that ship inside the built artifact, that the
    heavy composite is a main-loop event -- and "corrected" an earlier draft that
    had been right.  RULES: (a) bracket by CONTROL FLOW (entry address to the
    RET), never by a register a stack-blitter will move; (b) a cost measurement
    and a location measurement taken through the same bracket are NOT
    independent evidence -- if the bracket is wrong they fail together and
    corroborate each other; (c) when a new measurement overturns an older one,
    check whether the new METHOD is sound before believing it, because the older
    draft here was correct and was discarded; (d) do NOT validate such a capture
    by checking that the routine's cost plus the remaining time sums to one
    frame -- that is a partition identity, satisfied by ANY cut of the window,
    and the faulty bracket passes it by 0 T.

36. **A hazard you have already written down will still fool you, if it reaches
    you disguised as a different subsystem** (Bubble Bobble, 2026-09-12; this is
    #28 coming back, and the record is that it worked).  #28 says the 128K
    branch copies its AY engine over the sprite region and that every play state
    made before 2026-09-09 is on it; the project memory even names the range,
    `$C350-$D263`.  Yet when three of those old states (`play1p`, `round1`,
    `crowd`) disagreed with the tape over 336 of the 384 bytes of the bubble
    sprite at `$C780`, that read as evidence about GRAPHICS -- "this sprite must
    be built at runtime" -- and a session went and wrote it into the SPEC.  The
    branch never came to mind because nothing in the question mentioned sound.
    What settled it was measuring the EXTENT before theorising: 3,617 of the
    3,860 bytes inside the `$96B3` LDIR window differ and 0 outside it, which is
    an LDIR's signature and not a builder's.  The real discriminator is `$8DC4`
    (`$F3` = 128K, `$C9` = 48K), NOT `$9AE7`, which reads 0 on both.  RULES:
    (a) when a region disagrees between two states of the same game, get the
    extent first -- an LDIR leaves a window with hard edges, a builder leaves a
    pattern; (b) check the machine branch of every state a claim rests on, and
    say which states those were; (c) a paging-less harness turns a bank write
    into silent corruption, so any claim about memory above the paging boundary
    is suspect until the branch is pinned; (d) note the branch discriminator in
    the fixture metadata, not only in the state's filename.

37. **A resting scene where two of a routine's inputs are EQUAL cannot show you
    which one it reads -- six mutations survived a green byte-exact oracle**
    (Bubble Bobble, 2026-09-12).  The bubble blitter composites the display with
    the SHADOW buffer (the clean platform layer).  The oracle was captured on a
    settled scene, where the platform layer had just been restored -- so at
    every address a draw touches, display == shadow.  With d == s, reading the
    shadow and reading the display give the same answer, and the two edge masks
    are interchangeable: `(d&M)|(s&~M)` == `(d&~M)|(s&M)`.  A second accident
    compounded it: rows 0 and 15 of the real sprite are BLANK, so "row 0's
    sprite bytes are discarded" and "the last row is re-written background-only"
    -- two genuine features of the routine -- were also invisible.  The gate was
    byte-exact over 21 cases and 1,008 bytes and still passed a blitter with the
    wrong background source, the wrong mask polarity, no trailing restore, and
    only 15 rows.  RULES: (a) for any routine with two data inputs, one case
    must make them DIFFER; (b) for any routine driven by asset data, one case
    must use a SYNTHETIC asset with no zero bytes, so every structural position
    is observable -- the machine runs it just the same; (c) gate the addresses a
    routine did NOT write as well as those it did, or a wrong address simply
    goes unexamined; (d) when a mutation survives, the fault is in the SCENARIO
    before it is in the gate -- ask what the scene makes equal.

38. **`rom_writes` is a DEAD COUNTER under the C simulator -- a zero that looks
    like evidence** (Bubble Bobble, 2026-09-12).  The kit's `Mem.__setitem__`
    counts writes below `$4000` so you can tell "the routine attempted a write
    into ROM and it was dropped" from "the routine never went there".  Under
    `CMIOSimulator` -- the default -- it never increments: SkoolKit's C
    simulator enforces the ROM boundary itself and does not call back into
    Python for those writes.  Verified directly: a RAM stub doing
    `LD A,$FF / LD ($0000),A / LD ($8000),A` logs only the `$8000` write, leaves
    `mem[$0000]` untouched, and moves `rom_writes` by 0.  The write LOG is
    complete and correct for `>= $4000`, so oracles built on it are sound; it is
    only the sub-`$4000` counter that silently reads zero.  RULES: (a) never
    take `rom_writes == 0` as evidence a routine avoided ROM -- it cannot
    distinguish that from a dropped write; (b) to tell the two apart, compute
    the address in a model and check the DISPLAY outcome, which is identical
    either way, or single-step; (c) a counter that can only ever read zero is
    worse than no counter, so check a metric can move before reasoning from it.

39. **`run_until` defaults to `interrupts=True`; `Harness.call` defaults to
    `False` -- a hand-rolled call bracket runs the whole ISR inside the routine
    it was meant to isolate** (Bubble Bobble, 2026-09-14).  `harness.py:487`
    signs `run_until(targets, limit, stride, predicate, interrupts=True)`,
    because its usual job is driving frames; `Harness.call` passes
    `interrupts=False` when it brackets a routine between pushed sentinels.  A
    bracket written by hand -- push sentinels, set PC, `run_until(sentinels)` --
    inherits the *free-running* default, so an IM2 interrupt fires mid-routine
    and the whole per-frame ISR executes inside the "isolated" call.  It showed
    up here as 3 divergences in a 618-case walker differential whose fingerprints
    belonged to a DIFFERENT routine: the cached-position bytes `(+2)`/`(+3)`
    written and flag bits 5-6 set, which is the render master `$A447`, not the
    walker.  With `interrupts=False` the same 618 cases diverge 0 times.
    RULES: (a) any hand-rolled `call` bracket passes `interrupts=False`
    explicitly -- do not inherit; (b) when a differential fails, ask FIRST
    whether the changed bytes are the ones the routine under test can even
    write: bytes only another routine touches mean the harness, not the model;
    (c) a "0 divergences" result from a bracket that never re-ran with
    interrupts off has not been shown to test anything.

40. **A model can agree with the machine because the SAMPLED world makes the
    right and wrong answers equal** (Bubble Bobble, 2026-09-15).  `$AED1` above
    the HUD returns the fixed pointer `$712F` rather than a cell, and the floor
    probe dereferences it; the engine modelled that as "no cell -> no floor".
    Those disagree only when `$712E-$7131` or `$710F-$7111` have bit 5 set, and
    in `round1_48` -- the state every capture was taken from -- they are all
    `$00`.  So 618 direct calls agreed perfectly while the model was wrong, and
    every state they are all `$00`.  So 618 direct calls agreed perfectly
    while the model was wrong, and a mutation replacing the pointer with a
    sentinel survived.  What settles it is the byte NEXT DOOR: `$712E` is
    `$F0`, bit 5 SET, so a LEFTWARD look-ahead above the HUD reads a FLOOR
    where the sentinel says nothing -- unreachable only because the foot probe
    falls first.  (Written on the day, this entry cited `$712F` = `$E4` in the
    boot image; that was TRAPS #41's indexing error.  The finding itself was
    proved by POKING the bytes on the machine, so it is unaffected.)  The
    same shape hid the ledge -> hop launch (`$B20F`/`$B25E`): reaching it needs
    an enemy on a platform EDGE with the player at or below its row, and the
    sampled sweep launched 0 hops in 618 cases.  FIX: BUILD the world -- clear
    the colour shadow and the dummy page and poke them cell by cell, with the
    cell the WRONG arithmetic would have read set to the OPPOSITE value so the
    two answers cannot coincide.  128 built cases launch 61 hops and killed all
    five surviving mutations.  RULES: (a) a differential inherits the sampled
    world's coincidences -- ask what the capture state makes EQUAL, and poke it
    apart; (b) when an early-out returns a POINTER rather than a flag, find out
    which callers read the flag and which dereference the pointer, because they
    are not the same test; (c) count the DECISIONS a sweep reaches, not the
    cases it runs -- "0 of 618" hops is the number that matters.

41. **`build/image.bin` is a FULL 64K dump indexed from ZERO -- indexing it as
    `[addr - 0x4000]` silently reads a different address and manufactures
    "runtime-built" and "relocated" conclusions** (Bubble Bobble, 2026-09-15).
    The file is 65,536 bytes and `tools/adis.py` indexes it `mem[addr]`, which
    is why disassembly was always right.  A hand-rolled probe that wrote
    `img[a - 0x4000]` -- reasoning from the fact that RAM starts at `$4000` --
    reads the byte `$4000` BELOW the one it names, and gets plausible-looking
    data rather than an error, because every address in range holds something.
    It produced two confident, wrong facts in one session: that the ballistic
    arc tables at `$B59D` were absent from the image and therefore
    runtime-built, and -- following that thread -- that the whole `$F000-$FFFF`
    page was RELOCATED to `$B000-$BFFF` at init, "confirmed" by finding the
    arcs at `$F59D` (which is `$B59D` read through the same `$4000` shift) and
    by a 4045/4096 match of live `$Bxxx` against `img[a - 0x4000]` for
    `a` in `$F000-$FFFF` (which is live `$Bxxx` against image `$Bxxx` -- a
    tautology dressed as evidence).  Both tables are simply static at
    `$B59D`/`$B5BD`.  RULES: (a) read a memory image through ONE accessor that
    takes an absolute address, defined once, never an inline subtraction;
    (b) a claim that a region is "runtime-built" or "relocated" must be checked
    against the LIVE image at the SAME address before it is written down --
    `img[a] != live[a]` is the whole test; (c) when a probe and an existing tool
    disagree about the same bytes, the tool has been right for longer;
    (d) evidence that a region was copied must compare the two regions IN THE
    SAME image (here boot `$F000` vs boot `$B000`: 95 of 4096, i.e. no copy).

42. **`Harness.call` never restores SP, so a long sweep silently walks the stack
    into ROM and every later row reads "nothing happened"** (Bubble Bobble,
    2026-09-15).  `harness.py:638` pushes the six `SENTINELS` and sets SP; the
    routine RETs to the first, popping one.  Net: **10 bytes lower per call**,
    never restored.  A 2,560-case sweep therefore walks SP down 25,600 bytes.
    MEASURED on round1_48, whose SP rests at `$96D7`: it crosses `$4000` at call
    **2223** -- and call 2223 is exactly where a flyer sweep went dead.  Below
    `$4000` the sentinel writes land in ROM and are dropped, so `run_until`
    never sees one, the call burns its whole instruction limit, and the row is
    captured as before == after.  It does not throw; it produces PLAUSIBLE rows
    that say the routine did nothing.  Worse, before that it writes 12 bytes of
    sentinel into whatever live data SP happens to be passing through.
    RULES: (a) any sweep that calls more than a few hundred times must PIN SP to
    a fixed value per call, not inherit it; (b) assert the call ended on a
    SENTINEL -- `if regs[PC] not in SENTINELS: raise` -- because a limit-exhausted
    call is otherwise indistinguishable from a quiet one; (c) when a capture
    shows a run of identical "nothing changed" rows, check the STACK before the
    routine; (d) earlier fixtures in this project were not corrupted, but only
    because SP happened not to pass through anything they read -- that is luck,
    not correctness, so they were all re-captured with SP pinned.

43. **`build/image.bin` is a LIVE ROUND-80 DUMP, not the tape image, so seeding
    "tape data" from it silently ships bytes the game wrote at runtime**
    (Bubble Bobble, 2026-09-16).  Every disassembly in this project reads
    `build/image.bin`, which is right for reading CODE -- code is not
    self-modified often enough to matter, and where it is, the patch byte IS the
    thing being read.  It is WRONG for extracting a static table into the engine.
    CAUGHT BY a gate, not by inspection: the round build `$8C5E` disagreed with
    the machine on exactly one of 81 rounds.  Round 20's item byte at `$FFA3` is
    `$8F` in `image.bin` and `$95` on the tape, which sends the staged Y byte to
    `$29` instead of `$79`.  Two clusters across the 58 saved states: the early
    ones (including `boot.pkl`, taken at loader hand-over, before a single
    instruction of the game has run) hold `$95`; the boss-round ones hold `$8F`,
    and `image.bin` groups with them.
    **`build/image_tape.bin` -- the R3 rebuild from the actual tape block bytes
    -- is the authority for static data.**  An audit of every table this engine
    carries found exactly two that differ:
      - `$FFA3` above, and
      - `$8A76`, the UMBRELLA LOCK: tape `$2A` (a sentinel no 0..15 draw can
        match), dump `$06`.  `$9707` writes the sentinel at new game and `$8A49`
        writes 6 the instant a draw produces an umbrella -- so the umbrella
        spawns at most ONCE PER GAME, and by round 80 it had already gone.
        Seeding `$06` from the dump would start every new game with the umbrella
        already spent.
    The arcs `$B59D`/`$B5BD`/`$B5DD`, the `$9AC1` reset table, `$8649`, `$861D`,
    `$8839`, `$860F` and `$8A62` are byte-identical in both, so the gates built
    on them stand.  `$B5FD` differs in all 16 bytes and SHOULD: it is P1's key
    table, live state by design (TRAPS #41's companion -- type 4's arc reads one
    byte past its table into it).
    **AMENDED THE SAME DAY, and the amendment matters more than the rule.**
    `image_tape.bin` is authoritative ONLY WHERE THE TAPE ACTUALLY LOADED.  M1
    recorded its coverage as 191 of 192 pages, but that is pages, not bytes: the
    rebuild is **ALL ZEROS from `$5C00` to `$6100`** -- the Spectrum's
    system-variable area and the game's own working RAM, which no tape block
    covers.  Taking "static data" from there returns a block of nothing.
    CAUGHT ON THE FIRST USE OF THE NEW RULE: extracting the item sprite bank at
    `$5D00` from the tape image produced 832 zero bytes, and the only reason it
    did not ship was that the extractor compared against the live dump and
    reported 711 of 832 bytes differing.  A silent extractor would have shipped
    an invisible item.
    So the range was not tape data at all -- it is RUNTIME-BUILT, like `$D380`
    (built by `$BF5B`, deliberately not an asset).  PROVED three ways: the tape
    image is empty there; the bank is byte-identical in 54 of 57 saved states
    and differs only in `boot` and `title`, so it is built during the front end;
    and zeroing it in a live round-1 state produces ZERO writes back over 200
    frames, so nothing rebuilds it in play.
    RULES: (a) extract static tables from `image_tape.bin`, disassemble from
    `image.bin`; (a2) **BEFORE trusting `image_tape.bin` for a range, assert it
    is not all zero there** -- an unloaded page is indistinguishable from real
    data that happens to be zero, and an extractor that does not check will hand
    you silence; (a3) when the tape image is empty and the live states agree,
    the range is RUNTIME-BUILT: find the builder, and carry the bytes as a
    declared asset only until you do; (b) when the two disagree on a byte you
    are about to ship,
    that disagreement is a FINDING -- something writes it, and the engine
    probably has to model the write; (c) `boot.pkl` settles which value is the
    tape's, because nothing has run yet; (d) a one-row-in-81 gate failure is
    worth chasing to the byte -- this one was three layers from where it looked.

44. **A BUILT world is not immune: seeding a field with the value the routine
    WRITES there makes the write a no-op, and no amount of byte-for-byte
    comparison can see it** (Bubble Bobble, 2026-09-16).  The corpse landing
    `$8B83` does `LD (IY+8),0` and the fall `$8B4E` forces the sprite pointer
    back to `$C700` every frame.  The I9 oracle built its worlds from scratch --
    exactly what TRAPS #37 and #40 ask for -- but it built them by zeroing the
    ten-byte slot and then setting the fields it cared about, and it seeded the
    sprite as `$C700` because that is what a corpse holds.  So `(IY+8)` was
    already 0 and the sprite was already `$C700`: deleting either write changed
    nothing on the machine OR in the engine, and both mutations survived a gate
    that compared **all ten slot bytes on every row**.  Widening the comparison
    was the right fix for three other survivors and did nothing for these two.
    The cure is in the SEED, not the comparison: start `(IY+8)` at `$5A` and the
    sprite at the `$D360` FLIGHT frame, and watch the machine put both back.
    RULES: (a) for every field a routine ASSIGNS a constant to, seed that field
    to something else -- ideally the value it would hold one state earlier, so
    the world stays legal; (b) "I built the world" is not the same as "the world
    can distinguish the answers": a zeroed struct is a world in which every
    `:= 0` is invisible; (c) when a survivor names a WRITE rather than a branch,
    look at what the field held BEFORE the call, not at what the gate compares.

    (d) AND THE POISON MUST BE CHOSEN AGAINST THE OPERATION, not merely be a
    value the routine never writes.  $5A is 0101 1010, so it hides an
    `OR $40` (bit 6 already set) and an `AND $80` (bit 7 already clear);
    it hid a `SET 3`/`SET 1` pair in B10 for the same reason.  Pick the
    seed by looking at the INSTRUCTION: for an OR, clear those bits; for
    an AND, set them; for a SET, clear them.  [added by M7.7-R4, after two
    mutations survived on exactly this]

45. **A loop counter you transliterate as a `for` is a loop counter you have
    decided cannot misbehave** (Bubble Bobble, 2026-09-17).  `$C002` walks
    fourteen sparkle slots with `LD B,14` / `DJNZ`, and every instinct says
    `for (s = 0; s < 14; s++)`.  But `$C016`'s `LDI` decrements the SIXTEEN-bit
    BC, and C is a live register the caller sets: entering with C == 0 borrows
    and takes a count off B, so the walk ends one slot short and SLOT 13 IS
    NEVER SERVICED.  That is not a curiosity -- C measured at the call site
    `$8D49` is 3 in `round1`, 1 in `candycane`/`crown`/`hurryup` and ZERO in
    `fruit` and `boss`.  Worse, `$C023 LD C,A` reloads C from the serviced
    slot's X & $F8, so a run of particles at X < 8 zeroes C every time, B passes
    zero, WRAPS, and the walk leaves the table -- measured at 4,563 bytes
    written as far as $5FFE, straight through the $5D00 sprite bank.  A `for`
    loop is green through all of it.  RULES: (a) transliterate `DJNZ` as an
    EIGHT-BIT decrement with the loop's own exit test, and let the wrap emerge;
    (b) any instruction that touches the counter -- `LDI`, `LDD`, `CPIR`, a
    16-bit `DEC` -- is part of the loop control, not a memory move, so find
    every writer of B and C between the `LD B,n` and the `DJNZ`; (c) when a
    register is live INPUT from a caller you have not transliterated, MEASURE it
    across several states before calling it a constant -- one state said 3 and
    would have hidden the whole thing; (d) a runaway walk is a coverage
    instrument: this one read four bytes the engine had never loaded, and that
    is how `$5CFC..$5CFF` was found.

46. **A DETERMINISTIC REGISTER CANNOT BE SAMPLED -- any periodic schedule is a
    comb through its residues** (Bubble Bobble, 2026-09-17).  `$9811` is
    `LD A,R / AND $1F / ADD $1E`, so it should yield all 32 values 30..61.  An
    agent pass sampled it, got eight consecutive EVEN draws, and nearly concluded
    that the milestone values 41 and 61 are unreachable in simulation.  Writing
    the oracle meant to settle that, I stepped `1 + (i % 17)` instructions
    between samples and got 31 of 32 over 420 samples -- the value 38
    (`R AND $1F` == 8) missing entirely, counts running from 1 to 32.  THE
    READING PASS'S PREDICTION WAS RIGHT AND MY MEASUREMENT WAS WRONG.  R advances
    once per opcode fetch, so ANY deterministic step schedule is periodic in R --
    and so is the alternative that looks safest: driving whole frames gave
    exactly TWO distinct values over 200 samples, because `run_frames` is
    deterministic and R phase-locks to the frame parity.
    THE FIX IS NOT A BETTER SAMPLER.  Stop sampling: SET the register to all 256
    values and assert the FUNCTION, which no phase artefact can fake.  That also
    catches what sampling hides -- the answer is `(((R + 2) AND $1F) + $1E)`, not
    `((R AND $1F) + $1E)`, because `LD A,R` is `ED 5F` and reads R after its own
    TWO M1 cycles.  A sampler could never have found the +2; it shows up only
    when you control the input.
    RULES: (a) if a quantity is a pure function of machine state you can write,
    ENUMERATE the input and assert the function -- never sample it; (b) KEEP the
    degenerate sample in the fixture as evidence that the harness cannot answer
    the distribution question, so nobody re-derives a histogram from it later;
    (c) `LD A,R` and `LD A,I` read AFTER their own fetch -- count the M1 cycles
    of the reading instruction itself; (d) this is the third confident wrong
    answer this project has taken from a fixed or periodic phase, after TRAPS
    #34's scheduler and the eight all-even draws.  Where a phase is involved,
    assume the artefact until it is proved otherwise.

47. **THE LOAD IMAGE IS NOT THE RUN IMAGE, and the all-zero guard does not catch
    it** (Bubble Bobble, 2026-09-17).  TRAPS #43 said: before trusting
    `image_tape.bin` for a range, assert it is not all zero, because an unloaded
    page is indistinguishable from real data that happens to be zero.  That rule
    has a HOLE, and $5B00..$61A7 is in it.  1,704 bytes are relocated there from
    $E000 at cold start ($96A5 LDIR), so the tape image's own copy of the range
    is wrong -- by 1,385 of 1,704 bytes -- and its $6180..$61A7 is 36 of 40
    NON-ZERO, so the guard answers YES, THIS RANGE IS SOURCED and hands you
    rubbish.  The rubbish is STACK: $5BB0 does LD SP,$61A7, and 226,384 writes
    land there in 200 front-end frames, every one a ROM push.
    THE GUARD ONLY EVER ANSWERED "IS THIS SOURCED?", NEVER "IS THIS CORRECT?".
    Those are different claims and only the second one matters.
    AND THE BUILDER IS INVISIBLE WHERE YOU WOULD LOOK FOR IT: $8CC4 LD SP,$96DD
    parks the stack over $96A5..$96DC, so disassembling the LIVE dump there gives
    POP HL / RST $38 / NOP, and an analyst concludes the routine does not exist.
    Read it from the TAPE image.  TRAPS #41 was about the right INDEX; this is
    about the right FILE, and the two together mean neither image is authoritative
    on its own.
    RULES: (a) for any range you intend to ship, find its SOURCE, not just its
    bytes -- search the whole 64K tape image for the run image's content and
    require exactly ONE hit, because a match at two addresses proves nothing
    about which was copied; (b) then prove it is a COPY by poking the source and
    watching the destination follow -- a matching range and a shared origin are
    otherwise the same observation; (c) a relocation is CODE, so find it and run
    it on the machine with the destination POISONED, rather than shipping the
    destination; (d) disassemble cold-start code from the tape image and running
    code from the live dump, and expect neither to be readable in the other.

48. **AN "UNREAD" CLAIM MUST CARRY THE FRAME COUNT THAT MADE IT TRUE -- and the
    frame count is not sufficient either** (Bubble Bobble, 2026-09-18).  A
    reading pass grepped for `AND $40` and `AND $80`, found almost nothing, and
    concluded that bits 6 and 7 of the colour shadow were never read.  The grep
    was ACCURATE.  The inference was wrong: the read is `RLCA / RLCA / RLCA /
    AND 6`, a rotate that lifts those two bits into an already-doubled index --
    invisible to any search for a mask.
    A DIFFERENTIAL AGREED WITH THE GREP, AND WAS ALSO WRONG.  Flip bits 6/7
    across the whole map and run 80 frames: the game is IDENTICAL in every state
    tried, which reads as "nothing reads them".  Run 600 and it diverges at
    frame 108 -- the frame the first bubble reaches the drift stage.
    AND LENGTHENING THE RUN IS NOT THE FIX.  `round1_48` still says "unread" at
    600 frames, because no bubble ever reaches that stage there -- while
    `water`, WHICH IS THE SAME ROUND $01, diverges at frame 1.  What decides it
    is whether the WORLD EXERCISES THE PATH, not how long you run and not which
    round you picked.
    RULES: (a) a negative is a measurement and carries its conditions -- "bits
    6/7 are unread" is not a fact, "bits 6/7 are unread over 80 frames of
    round1_48" is; (b) a GREP CANNOT PROVE A NEGATIVE about a value that can be
    rotated, shifted, added or compared into use -- only a differential can, and
    only with a control; (c) ALWAYS RUN THE CONTROL: the same rig mutating bit 5
    diverges at frame 0 or 1 everywhere, which is the only thing that makes the
    bits-6/7 result mean anything; (d) when a differential says "no difference",
    ask what event would have to happen for a difference to appear, and then
    check that the run is long enough AND the world arranged for it to happen.

49. **ONE CELL POSITION IS NOT A TEST OF A CELL WALK -- and the alignment you
    happened to pick decides which register you think it reads** (Bubble Bobble,
    2026-09-18).  `$AE81` probes up to three consecutive colour-shadow cells.
    Six mutations survived a battery over a case list that varied the cell's
    VALUE thoroughly and its POSITION not at all, and between them they covered
    every structural property of the walk: the `INC L` being EIGHT BIT, the
    second and third cells being tested with the caller's mask, the marker's
    mask being `$1F` rather than `$0F`, and -- the one that was an ENGINE
    DEFECT rather than a gate gap -- WHICH REGISTER GATES THE THIRD CELL.
    `$AE86 LD D,E` overwrites D with the incoming X three instructions before
    `$AE92 LD A,D / AND 6`, so the gate is on X.  I transliterated it as Y, and
    it passed everything, because every case I drove had X and Y BOTH 8-ALIGNED
    and `x & 6` and `y & 6` were both zero.
    AND THE WRAP TOOK THREE TRIES.  The end of a ROW is not a page boundary:
    `x=$F8, y=$60` gives base `$F99F`, and an eight-bit and a sixteen-bit INC
    agree there.  `y=$38` gives `$F8FF`, where they differ.  Then the DECOY
    proving it was folded onto the wrap target BY MY OWN SEEDING FORMULA, which
    deliberately addressed cells the way the machine does -- it only works as an
    ABSOLUTE poke, claim at `$F900` with `$F800` empty.
    RULES: (a) for any routine that WALKS, vary the starting POSITION as hard as
    the contents -- page boundaries, both alignments, and each visited cell
    filled alone; (b) when two registers could be the source of a test, find a
    case where they DIFFER before believing either -- coordinate pairs are the
    classic trap because play tends to align both; (c) a helper that seeds a
    world "the way the machine addresses it" CANNOT seed the case that proves
    the addressing -- that one needs an absolute poke; (d) a marker or index
    whose live range is narrower than its field (here 1..12 in five bits) hides
    the mask: drive a value that uses the top bit.

50. **A CALL WHOSE EFFECT IS IDEMPOTENT OVER THE DEFAULT WORLD CANNOT BE SEEN
    TO HAVE RUN -- and a WALK IS NOT PROVED BY ITS TARGETS** (Bubble Bobble,
    M7.7-H1, 2026-09-18).  Two mutations survived a gate that looked complete.
    (a) DELETING a `CALL` survived: the tail's `$98A4 CALL $79AC` maps colour
    cells whose `$38` bits are set to `$20`, and over a fresh world every cell
    was ALREADY `$20`, so "it ran" and "it did not" were the same end state.
    The fix is to seed the input with a value the callee CHANGES (`$57`), which
    costs one line and turns an invisible call into a one-byte assertion.
    (b) Walking TWENTY pointers instead of nineteen survived a gate that
    asserted all NINETEEN NAMED TARGETS end zero -- because the twentieth write
    lands on a byte NOBODY NAMED, and no check over the named set can see it.
    The fix is to COUNT: a recording Proxy over the RAM image makes the write
    count itself the assertion, which is the only thing that bounds a loop from
    above.
    RULES: (a) before asserting that a routine ran, ask what the world would
    look like if it had NOT -- if the answer is "the same", the seed is wrong,
    not the routine; (b) for any loop, gate the COUNT as well as the effects,
    because effect checks are existential and only a count is universal;
    (c) this is the mirror of #44 -- there the SEED made a write invisible, here
    the DEFAULT made a whole call invisible.

51. **A SELF-MODIFICATION'S LIFETIME IS A SEPARATE FACT FROM ITS EFFECT, AND
    NEITHER INCREMENT THAT TOUCHES IT CAN SEE IT** (Bubble Bobble, M7.7-H1,
    2026-09-18).  `$88E0` pins the item generator by zeroing an `INC A` OPCODE
    at `$8BA0`; a later increment measured the generator reading that opcode.
    Both were right and neither could observe that `$9891 LD HL,$3CFF /
    LD ($8B9F),HL` puts the counter AND the opcode back at every round
    transition -- so the pin lasts EXACTLY ONE ROUND.  It took a third
    increment, spanning both, driving the pin in and the transition after it.
    RULE: when a routine writes into code, do not stop at "who reads it".  Ask
    WHO RESTORES IT and WHEN, and gate the expiry as its own negative -- a port
    that never restores looks identical for one round and diverges forever
    after.  Watch for a SIXTEEN-BIT store spanning an operand and the opcode
    next to it: it restores two facts in one instruction and reads as one.

52. **A ROUTINE WITH NO CALLER IS NOT DEAD -- IT IS FALLEN INTO; AND A COUNT
    QUOTED FROM ONE ROUND IS A SAMPLE** (Bubble Bobble, M7.7-H6, 2026-09-18).
    `$7DD6` computes a per-round value that 49 of 81 rounds depend on, and there
    is no `CALL` or `JP` to it anywhere in 64K -- the routine above it simply
    runs off its end.  A caller scan found nothing and the reading pass filed the
    whole subsystem under the previous routine's name for two increments.
    The same increment then caught its own version of the second half: the plan
    carried "70 phantom self-modifications" as a fact, and 70 turned out to be
    the MAXIMUM FOR ONE GROUP.  The real count runs 0 to 106 and is a function of
    where the round sits in its list.
    RULES: (a) when a scan for callers comes back empty, disassemble BACKWARDS
    from the entry before concluding anything -- fall-through is invisible to
    every reference search; (b) a count measured on one round, one slot or one
    frame is a sample until something shows it is constant, so gate the RANGE and
    name the variable it depends on; (c) a subsystem inherits the name of
    whatever routine precedes it, which is exactly how it stays unmodelled.

53. **WHEN TWO UNRELATED TABLES ENCODE THE SAME MAPPING, THAT AGREEMENT IS THE
    PROOF -- AND AN INDEX CAN RUN OFF ITS TABLE ON PURPOSE** (Bubble Bobble,
    M7.7-H6, 2026-09-18).  Eight randomised element classes fold onto six EXTEND
    letters.  Read one way, `$B80E`'s bit masks say classes 11 and 12 alias 5 and
    10.  Read another way -- a sprite-pointer table at `$C068` that nothing
    connects to `$B80E` -- classes 11 and 12 point at the SAME TWO GLYPHS as 5
    and 10.  Either reading alone is an inference; together they are a
    measurement, because a coincidence would have to hold in two encodings at
    once.
    And in the same table: class 0 does `SUB 2 / ADD A,A` and indexes **252 bytes
    past** an eleven-entry table, on 31 of 81 rounds.  A port that "fixes" that by
    clamping the index is not more correct, it is different.
    RULES: (a) look for a SECOND encoding of any mapping before believing the
    first, and prefer a pair of tables that do not know about each other;
    (b) compute what every reachable input does to an index, including the ones
    below the table's base -- an out-of-range index is behaviour until measured
    otherwise; (c) never repair an original's overrun inside a faithful port
    without a declared flag and a test on both sides.

54. **A GATE THAT COMPARES THE CELLS IT EXPECTS TO BE WRITTEN IS EXISTENTIAL --
    ADD THE COUNT** (Bubble Bobble, M7.7-H1/H6/H7, 2026-09-18).  The same gap
    three increments running, in three disguises.  H1: a pointer walk of TWENTY
    instead of nineteen -- every named target still ends correct, and the
    twentieth write lands on a byte nobody named.  H6: a list walk that scans a
    FIFTH list -- every phantom write inside the table still matches, and the
    extra ones fall outside the range the log was FILTERED to.  H7: a map painter
    running 24 rows instead of 22 -- all 616 cells are painted correctly and two
    more rows go past the end of the buffer into a page another subsystem uses.
    Each survived a battery, and each was invisible for the same reason: the
    assertion quantified over the writes I predicted, so it could not see a write
    I had not.
    RULES: (a) for anything that WALKS or PAINTS, count the writes and assert the
    total, not just the values at the addresses you expect; (b) never filter a
    recording log to the region under test -- log everything and make the region
    an ASSERTION on the addresses; (c) the machine-side oracle usually catches
    this for free, because a write-watch has no expectations -- so mirror the
    same count on the ENGINE side, which is where the mutation actually lands.

55. **"CAN THIS GATE SEE THE THING IT IS NAMED AFTER?" IS ITS OWN MEASUREMENT --
    AND SYMMETRY CAN MAKE THE ANSWER NO** (Bubble Bobble, M7.7-H7, 2026-09-18).
    A map record is painted half-width and MIRRORED, and I set out to count the
    rounds on which the mirror is observable.  My first metric counted rounds
    whose finished map is left-right ASYMMETRIC.  It returned 30 -- which is
    exactly "the 30 rounds that are not mirrored at all", because a mirrored
    round is symmetric BY CONSTRUCTION.  The number was real, the question it
    answered was not the one asked, and it would have been quoted as evidence for
    the mirror while being evidence only against the other class.
    The right question was narrower: the mirror's REVERSAL is separable only on a
    mirrored round with a NON-PALINDROMIC row.  That count is 49 of 51 and 3,352
    cells -- and a THIRD competing model turned out to be refused by arithmetic
    rather than by data at all.
    RULES: (a) before quoting a separability count, name the two models it
    separates and check the count is not a tautology about one of them; (b) when
    a transform imposes a symmetry, that symmetry destroys the evidence for the
    transform -- look for the cases that escape it; (c) enumerate every competing
    model explicitly, because one of them may be excluded by a size or a bound
    instead of by a measurement, and that is a stronger result worth stating.

56. **A LOOP'S CURSOR ADVANCE CAN LIVE IN THE CALLEE** (Bubble Bobble, M7.7-H8,
    2026-09-18).  `$833A` is an eleven-iteration loop over a row-address table,
    and its body contains NO `INC IX` anywhere: the advance is `$8375 INC IX /
    INC IX`, sitting inside the subroutine it CALLs, after that subroutine's own
    DJNZ and before its RET.  Read the loop on its own -- which is how anyone
    reads a loop -- and it says the wall is redrawn over the same two char rows
    eleven times.  I had transliterated exactly that before a register trace
    showed IX running `$FD44`, `$FD48`, `$FD4C`: four bytes an iteration, because
    each of the two CALLs moves it twice.
    RULES: (a) when a loop's induction variable never changes in its body, the
    callee is mutating it -- read every CALL to the end of its RET, not to its
    apparent purpose; (b) a subroutine that advances its caller's cursor is a
    second return value with no name, so gate it by TRACING THE REGISTER across
    iterations rather than by reading; (c) this is the dual of #52 -- there a
    routine was entered by fall-through, here it exits having changed state the
    caller owns.  Control flow and data flow both leak across boundaries that
    look closed.

57. **AN IDEMPOTENT SIDE EFFECT NEEDS A WRITE COUNT; AND "CANNOT WRAP" IS A
    THEOREM YOU MUST ACTUALLY PROVE** (Bubble Bobble, M7.7-H8, 2026-09-18).  Two
    kinds of survivor from one battery, both about what a state comparison cannot
    express.
    (a) `$82C5` patches three bytes to fixed values.  It fires ONCE, after the
    first row of a 22-row scan.  A mutation making it fire on EVERY row survives
    any check on those three bytes, because the second write puts back what the
    first did -- only counting the writes (6, not 66) separates them.
    (b) Three other survivors were PROVABLE EQUIVALENTS, and proving it took
    enumeration rather than intuition: two eight-bit adds cannot wrap because the
    row-table low bytes top out at `$E0` against a column of 29, and the second
    site reads every OTHER table entry, whose low bytes are `$40/$80/$C0/$00`.
    Worth the enumeration in both directions: a comment in my own code claimed
    the second add "can wrap", and it cannot.
    RULES: (a) for any effect that is idempotent -- a patch to a constant, a
    clear, a flag set -- gate the COUNT, because the end state is the same under
    once, twice and never-again; (b) before withdrawing a mutation as equivalent,
    ENUMERATE the reachable inputs and show the branch is unreachable, then write
    the proof next to the code as TRANSCRIBED-NOT-EXERCISED; (c) enumeration also
    catches the opposite error, a comment asserting a wrap that cannot happen.

58. **AN OPCODE SCAN FOR `CALL` IS NOT A SCAN FOR REACHABILITY** (Bubble Bobble,
    M7.7-H9, 2026-09-18).  A reading pass established that the HUD painter
    `$7FC0` had exactly one reference -- a `CALL z` gated on the round number --
    and concluded the HUD is painted on round 1 and never again.  It scanned for
    `CD` and `CC`.  There is also a `C3`: `$9998 JP $7FC0`, a TAIL CALL, ending
    the player-join routine.  The HUD is repainted on every join, and a port
    built to the original claim shows a stale HUD for the whole of a two-player
    game.
    RULES: (a) scan for the whole family -- `CALL`, every conditional `CALL`, `JP`
    and every conditional `JP`, `RST`, and the bare ADDRESS as a word (for jump
    tables and pushed return addresses); (b) a tail call is invisible to anyone
    looking for a call, and it is the normal way a routine ends when its last act
    is to delegate; (c) this is the third member of a family: #52 (entered by
    fall-through, no reference at all), #56 (leaves having moved its caller's
    cursor), and now this -- reached by a JP that a call scan never sees.

59. **A DESTRUCTIVE EXPERIMENT MUST RESTORE WHAT IT DESTROYS** (Bubble Bobble,
    M7.7-H9, 2026-09-18).  One measurement in this increment exists to prove a
    loop guard is load-bearing: poke the counter and watch the copy run away over
    263 bytes.  It restored the poked operand and not the 263 bytes -- which
    happen to be the very record the NEXT measurements read.  Every controlled
    measurement afterwards was taken in the wreckage, and reported a mask of
    non-zero bytes where the machine has zeros.
    It was caught by an ENGINE DIFFERENTIAL and could not have been caught by a
    census: the write COUNTS matched exactly, 109 against 109, while the values
    from the fourth cell onward were fiction.
    RULES: (a) snapshot and restore any region a destructive experiment can
    reach, and size the snapshot from the WORST case, not the shipped one;
    (b) order matters -- put destructive probes last, or rebuild between them;
    (c) when an oracle and an engine disagree, single-step the real machine
    before assuming the engine is wrong: here the trace showed the engine right
    and the oracle contaminated; (d) a matching write count is not agreement.

60. **A CONTROLLED WORLD IS ONLY CONTROLLED WHERE YOU SEEDED IT -- AND THE
    MODELS YOU WANT TO SEPARATE DECIDE WHICH WORLDS TO BUILD** (Bubble Bobble,
    M7.7-H9, 2026-09-18).  Two lessons from one battery.
    (a) A Spectrum character row is EIGHT PAGES: a row at `$50E0` walks H from
    `$50` to `$57`.  Seeding `$5000..$50FF` controls one row in eight and leaves
    seven reading whatever the previous world left, on both sides of the
    differential.
    (b) Six mutations survived not because the gate was weak but because the
    WORLD was tame.  Lives of 3 cannot separate "clamp at 5" from "clamp at 4"
    from "no clamp" -- all three agree below the threshold.  An attribute whose
    paper is 3 never reaches the branch that fires when paper equals ink.  A
    six-bit mask cannot show that a loop runs six times rather than eight.
    RULES: (a) seed every page a walk can reach, and derive the extent from the
    addressing, not from where you expect writes to land; (b) for each competing
    model, name the input that separates it and BUILD THAT WORLD -- a gate over a
    typical world tests typical behaviour only; (c) a clamp, a threshold and a
    loop bound are all invisible from inside their normal range, so drive them
    from outside it.

61. **A DECLARED DEPARTURE CAN HIDE THE BUG IT SITS ON TOP OF** (Bubble Bobble,
    M7.7-H10, 2026-09-18).  A sprite generator indexes a pointer table with an
    EIGHT-BIT offset, so one input runs 252 bytes past the table and fetches a
    pointer nobody chose.  That overrun is real behaviour on 31 of 81 rounds and
    was gated two increments earlier.  But the pointer lands in the machine ROM,
    which the port does not ship, so the port substitutes nothing there -- and a
    mutation making the index SIXTEEN-BIT survived a battery, because the
    sixteen-bit index lands on a DIFFERENT ROM pointer that the port also
    substitutes nothing for.  Two different wrong answers, one identical output.
    RULES: (a) wherever a departure replaces a computed value with a constant,
    the computation upstream of it becomes unobservable -- gate that computation
    DIRECTLY, by exposing it, rather than through its effect; (b) audit every
    declared departure for what it stops you from being able to see, and write
    that down beside the departure; (c) a test that recomputes the quantity it is
    checking is testing itself -- ask the engine for the value.

62. **DEAD WORK IS STILL BEHAVIOUR, AND ONLY A COUNT CAN SEE IT** (Bubble
    Bobble, M7.7-H10, 2026-09-18).  A routine clears 384 bytes and then
    immediately overwrites all 384 from a table.  The clear cannot be observed in
    the final state by any comparison, at any address, ever.  It is nevertheless
    the machine's behaviour, it costs real time, and it exists for a reason worth
    recording: the clear is 384 rather than the 128 the source asks for, because
    the subroutine it calls twice is a DJNZ loop that exits with B = 0.
    RULES: (a) transliterate dead work and gate it by WRITE COUNT, which is the
    only instrument that can see it; (b) a `LD B,n / CALL / CALL` pair where the
    callee decrements B to zero is a doubling, not a repetition -- this is the
    third TRAPS #45 site in this port and they have all been counted wrong at
    first reading; (c) when a routine's effect is invisible, ask what it costs in
    time before deleting it, because a timing model will notice later.

63. **A GATE WHOSE CALL PATH DOES NOT INCLUDE THE CODE UNDER TEST** (Bubble
    Bobble, M7.7-H11, 2026-09-18).  A driver runs a preparatory step and then a
    four-iteration loop before its main work.  The state after those is
    observable only at that moment, because the main loop scrolls it off the
    screen, so the gate brackets it there -- and to build the expected state it
    calls the preparatory routine and the loop body DIRECTLY.  A mutation to the
    driver's own loop then survives: the routine it corrupts is correct on both
    sides and nothing the gate calls goes through it.
    The remedy is structural, not additional: EXTRACT the loop into a method that
    the driver calls and the gate calls, so there is one path and both ends use
    it.  That also makes the machine's own grouping explicit in the port.
    RULES: (a) after writing a gate, trace the call path from the assertion to
    the mutated line -- if the mutated line is not on it, the gate cannot fail;
    (b) prefer extracting a named step over reassembling it in the test, because
    a reassembly is a second implementation that can agree with the machine while
    the first one does not; (c) this is distinct from every other gap in this
    chain -- not an unobservable effect, not a tame world, not a filtered log,
    but a test that never reaches the code.

64. **"LATER OVERWRITTEN" IS RECURSIVE: CHOOSE THE BRACKET PER CLAIM** (Bubble
    Bobble, M7.7-H11, 2026-09-18).  H2 established that a scroll's finished
    screen is repainted from a shadow immediately afterwards, so the gate must
    compare MID-SCROLL.  Built that way, two mutations still survived -- deleting
    the separator row the scroll begins with, and making its four-step pre-roll
    push rows it should not.  Both are invisible at the END of the scroll for the
    same reason the whole scroll is invisible after the repaint: the band they
    write is scrolled off the top before the animation finishes.
    The bracket had to move inward a second time, to the instant after the
    pre-roll.  There is no "the" mid-point: each claim has its own last moment of
    visibility, and a single sampling point chosen once per increment will be
    wrong for some of them.
    RULES: (a) for every claim, ask when its evidence is destroyed and bracket
    just before THAT, not before some other claim's destruction; (b) a routine
    whose output is consumed by a later stage of the same routine needs its own
    bracket, not its caller's; (c) if two claims have different last-visible
    moments they need two brackets, and saying so costs less than a battery.

65. **WHEN A PLAN NAMES A TOOL TO EXTEND, THAT TOOL'S DOCSTRING IS A LIST OF
    TRAPS ALREADY PAID FOR** (Bubble Bobble, M7.7-H12, 2026-09-18).  The
    increment plan said "extending tools/settle.py".  I wrote a fresh driver
    instead, and paid for two faults that settle.py documents in its own opening
    comment: a direct call leaves PC parked on a SENTINEL, which is game DATA, so
    free-running frames from there executes bytes that are not code until an
    interrupt rescues the machine (every enemy coordinate came back as 2, a
    counter never armed, a player drifted); and an armed window MUST be paired
    with a control that holds the same key with the mechanism disabled, because a
    player never asked to move is frozen either way.
    RULES: (a) before writing a new oracle, read the docstring of any tool the
    plan names -- it is a record of the specific ways this machine has already
    fooled someone; (b) prefer extending to rewriting even when the rewrite looks
    smaller, because the cost of a rewrite is invisible until it reproduces a
    solved bug; (c) an oracle's docstring is a deliverable, not decoration: write
    down what made the obvious world useless, because the next increment will
    face the same world.

66. **AN ORACLE TABLE AND AN ENGINE METHOD CAN BE DIFFERENT FUNCTIONS**
    (Bubble Bobble, M7.7-H12, 2026-09-18).  A machine routine takes ONE
    coordinate and answers "is it in the band?".  The engine method that calls it
    takes an ENTITY and answers "is any of its FOUR coordinates in the band?".
    Comparing the method against the routine's table row for row fails on every
    row where the entity's Y is outside but its Y+16 is inside -- and the failure
    looks exactly like an engine bug.
    RULES: (a) when a gate compares an engine method to a machine measurement,
    state what each one's INPUT is and check they are the same thing; (b) if they
    are not, either restrict the comparison to inputs on which the two agree AND
    say why, or gate the wider behaviour separately -- H12 does both; (c) a
    failing gate is not evidence of an engine fault until the comparison itself
    has been audited.


67. **A SHIPPED STATE CAN RESUME MID-ROUTINE** (Bubble Bobble, M7.7-H13
    constructive pass, 2026-09-19).  `build/bottle.pkl` was captured with
    A = `$0D`, DE = `$9603` and a stack top of `$8A5D`: resuming it COMPLETES a
    bottle spawn that was already half done, with the type the machine had
    before any poke.  Every `$8609` control in that cluster showed a spurious
    frame-0 spawn for exactly this reason, and it looks like the poke causing it.
    RULES: (a) before attributing anything to a poked input, print the saved PC
    and the top of the stack -- a state is a MOMENT, not a scene; (b) a state
    captured inside a CALL owes its caller a return, so the first frames after a
    resume run code the experiment did not choose; (c) if a control and its
    experiment share a captured mid-routine state, they share its tail too, and
    the difference between them is not what the poke did.

68. **A DISASSEMBLY THAT STARTS ONE BYTE LATE INSIDE AN `FD` PREFIX INVENTS A
    PLAUSIBLE INSTRUCTION** (Bubble Bobble, M7.7-H13 constructive pass,
    2026-09-19).  `$9AFD`, `$9DF2` and `$9DFC` were quoted in three separate
    documents as `LD HL,$5B00`.  No such instruction exists: the real ones are
    `$9AFC`/`$9DF1 LD IY,$5B00` and `$9DFB LD IY,$5B0A`, and the phantom is the
    `21 00 5B` that follows the `FD` prefix byte.  The wrong reading is not
    nonsense -- it is a register the routine plausibly uses, which is why it
    survived three readings.
    RULES: (a) disassemble from a known entry, never from an address a grep
    landed on; (b) if a quoted instruction's address is one past an `DD`/`FD`/
    `ED`/`CB` byte, it is the prefix's operand and the instruction is fiction;
    (c) a byte-pair census over 64K finds operands as readily as opcodes -- see
    #58 and the `$8309` miscount in the same pass.

69. **`Harness.call`'s SENTINEL LIST INCLUDES `$FE02`, WHICH IS THE BOSS
    SPRITE'S OWN BYTES** (Bubble Bobble, M7.7-H13 constructive pass,
    2026-09-19).  A sentinel return parks PC on data in this area, so
    single-stepping on from a `call()` return executes pixels.  The same shape
    as #42's SP fault and as `settle.py`'s docstring warning, in a new place.
    RULES: (a) after `call()`, PC is a SENTINEL and nothing may be stepped from
    there -- restore PC (and SP) explicitly before free-running; (b) when a tool
    parks PC on a sentinel inside game memory, say so where the tool is used,
    not only where it is defined.

70. **A MASK MUTATION ON A TYPED-ARRAY STORE CANNOT FAIL** (Bubble Bobble,
    M7.7-H13-B0, 2026-09-19).  `ram[$FEC8] = (ram[$FEC8] + 1) & 0xFF` into a
    `Uint8Array` -- mutating the `& 0xFF` to `& 0xFFFF` changes NOTHING, because
    the container already truncates.  The battery reported it as a SURVIVOR, and
    a survivor reads as a hole in the gate rather than as a mutation that cannot
    express the bug.  The same is true of every `& 0xFF` on a store into `ram`,
    and this port has hundreds.
    RULES: (a) a mutation must be able to CHANGE THE VALUE THAT LANDS -- on a
    `ram[]` store the mask is enforced by the array, so mutate the SEMANTICS
    instead (B0 replaced it with "the counter is driven by the frame, not by the
    pass", which dies immediately); (b) when a mask mutant survives, check the
    CONTAINER before you go looking for the missing assertion; (c) masks on
    LOCALS and on 16-bit pairs are real and must still be mutated -- it is the
    8-bit store into the byte image that is free.

71. **AN INTERVAL CLAIM MUST NAME THE WINDOW, AND A SHORT WINDOW HIDES THE RARE
    STATE** (Bubble Bobble, M7.7-H13-B0, 2026-09-19).  The plan's headline --
    "the PASS interval is exactly 32 in every interval of both runs" -- is true
    over 300 frames and FALSE over 900: the intervals are 32, 35, 36, 38
    contended and 32, 38, 47 uncontended, because `$A9FC`'s involution LATCHES
    13 and 21 times in 900 frames and a latched pass does not tick the divider.
    What is exactly 32, in both runs, is the interval in TICKS.
    RULES: (a) an interval or period claim carries the window it was measured
    over, and "every interval" means every interval IN THAT WINDOW; (b) if any
    state in the loop is rare, the window must be long enough to contain several
    of them -- count the rare state and say how many the window held; (c) when a
    count and a derived count disagree (passes vs ticks), the ONE that is exact
    names the real unit.

72. **WIRING A ROUTINE IS HOW A MISSING RESET GETS FOUND** (Bubble Bobble,
    M7.7-H13-B0, 2026-09-19).  `$C002` had been transliterated and gated in
    isolation for a whole increment (I10) and was correct.  The moment B0 wired
    it into the main-loop chain it wrote 642 display bytes on a still round --
    because `$5CE0`, its table, is INSIDE the relocated block `$5B00..$61A7`, and
    the port's `reset()` had never run the round build's own `$BF39` clear.  The
    machine has the table ZERO on `round1_48`, `r20_48` and `boss` alike, and
    carries `(IY+3) = 2` in every bubble slot -- which is `$BF4B`, one
    instruction inside the very chain that clears it.
    RULES: (a) a routine gated in isolation is gated over the world the GATE
    built, not over the world the engine has -- wiring is a separate act with its
    own findings; (b) when a newly wired routine misbehaves, compare the engine's
    world against a captured machine world at the same moment BEFORE touching the
    routine; (c) fix it with the machine's own routine, not with a fill: the
    clear belongs to the build, and calling `poolClearChain()` also restored
    `(IY+3) = 2`, which a fill would have missed.

73. **A MUTATION WHOSE ANCHOR DRIFTS IS SILENTLY DEAD, AND THE BATTERY'S HEADLINE
    COUNTS THE LIST RATHER THAN THE LIVE ONES** (Bubble Bobble, M7.7-H13-B1,
    2026-09-19).  I10 gave `itemBlit` a `rec` and an `or_` parameter.  SEVEN I2
    mutations anchored on the old call shape stopped matching that day and were
    reported as `!! ANCHOR 0x` -- and the increments after it went on quoting
    "1038/1038 killed, ZERO survivors", which is the length of the LIST.  Seven
    behaviours had no mutation coverage for eleven increments.
    RULES: (a) report three numbers -- LISTED, LIVE (anchor found), KILLED -- and
    never let LISTED stand in for LIVE; (b) an anchor failure is a RED result,
    not a warning: it means a behaviour that used to be gated no longer is;
    (c) when a routine's SIGNATURE changes, grep the battery for its name in the
    same edit -- the anchors are source text and they rot exactly like a comment.

74. **CENSUSING ONE OPCODE FORM UNDERCOUNTS REFERENCES** (Bubble Bobble,
    M7.7-H13-B1, 2026-09-19).  `web/game.js` said of `$7FC0`: "its sole reference
    in both images is `CC C0 7F` (CALL z), so A PORT THAT NEVER BUILDS ROUND 1
    HAS NO HUD AT ALL".  A census of the ADDRESS -- the two bytes `C0 7F`, with
    the preceding byte classified -- finds `$7F58 CALL z` AND `$9998 JP`, the
    mid-game join's tail jump, so the HUD is repainted whenever a second player
    joins on ANY round.  The same shape one level down: a `32 C9 FE` census of
    `$FEC9`'s writers finds two and there are three, because `$8CFC` loads the
    address into HL and INCs through it.
    RULES: (a) census the ADDRESS and classify the byte in front of it; never
    census opcode-plus-address as one pattern; (b) the forms that hide are the
    conditional calls, the tail JPs and the pointer loads (`LD HL,nn` then an
    indirect write) -- all three are in this game; (c) a sentence of the form
    "its sole reference is X" is a claim about a SEARCH, and the search must be
    stated with it.

75. **AN `OR` AGAINST A PAGE BASE ABSORBS THE CARRY A MASK IS THERE TO CATCH**
    (Bubble Bobble, M7.7-H13-B2, 2026-09-19).  The machine walks an attribute
    row with `INC L`, so the address is `(H << 8) | L` with L EIGHT BIT.
    Transliterated as `ram[page | l]` with `l = (l + 1) & 0xFF`, the mask looks
    load-bearing and is not: every attribute page has bit 8 set, so
    `$5900 | $100` is `$5900` and a sixteen-bit L wraps anyway.  The mutation
    that removed the mask wrote all eleven cells in exactly the right places and
    SURVIVED.  Written as `ram[(page + l) & 0xFFFF]` the same mutation dies at
    once.
    RULES: (a) address arithmetic that models an eight-bit walk must ADD, not
    OR -- the OR silently forgives the carry; (b) this is TRAPS #70 one level
    up: there the CONTAINER masked, here the OPERATOR does, and in both cases
    the surviving mutation is evidence about the TRANSLITERATION, not about the
    gate; (c) when a mask mutation survives, write the same expression two ways
    and see whether they can ever differ before looking for a missing assertion.

76. **A GUARD CAN READ A BYTE THAT BELONGS TO NOBODY** (Bubble Bobble,
    M7.7-H13-B2, 2026-09-19).  `$80FA`'s award computes `HL = 10*A` and adds
    `$FD7D`, so the `BIT 7` guard lands on `$FD87` for player 1 and `$FD91` for
    player 2 -- and on **`$FD7D`** for index 0, three bytes BELOW the entity
    table.  It reads `$A0` on every state on disk, so index 0 always passes a
    guard that is not a player's flag at all.  The port carries zeros there, so
    the award silently did nothing for index 0 and the gate comparing it to the
    machine failed on a byte nobody had ever named.
    RULES: (a) when an index scales a base, ENUMERATE the addresses it produces
    for every index the code accepts, not just the ones play uses; (b) a guard
    outside the structure it appears to guard is a fact about the DATA, not
    about the player -- record the value and where it comes from; (c) an index
    unreachable in play still needs its row, and the world for it is SEEDED from
    the machine rather than invented in the reset.

77. **A UNIFORM SOURCE CANNOT TEST AN ADDRESS COMPUTATION** (Bubble Bobble,
    M7.7-H13-B4, 2026-09-19).  `$9D4C` reads BIT 5 of the colour shadow and
    writes one of two attributes.  Every natural boss row is UNIFORM -- all
    sixteen cells clear on `boss`, `bosskilled` and `bossspawn` -- so a port
    reading that bit from the WRONG ADDRESS (wrong stride, wrong page wrap, the
    display attributes instead of `$F8xx`) produces byte-identical output on all
    of them AND on both uniform controls.  Only one captured state discriminates
    at all, and only in two cells of sixteen.  The H13 falsification pass caught
    this before the oracle existed.
    RULES: (a) when a routine READS a table and the table is uniform, the read's
    ADDRESS is untested no matter how many states are driven -- make the source
    POSITION-DEPENDENT: a checkerboard `bit = (row + col) & 1` for a flag, a
    `(addr * k) & $FF` fill for a byte copy, a distinct value per row for a blit;
    (b) the test to apply to a drafted world is "which cells would differ if the
    address were wrong?" -- if the answer is "none", the world is decoration;
    (c) this is why B4 ships checkerboards and multiplied fills rather than the
    states the game produces.

78. **A POINTER SWEEP FINDS DATA THE PORT NEVER SHIPPED** (Bubble Bobble,
    M7.7-H13-B4, 2026-09-19).  The boss's colours come from a seven-slot array
    of sixteen-byte blocks at `$A890 + 16C`, read by an `LDD` walk through a
    self-modified pointer.  Poking that pointer over every C the routine accepts
    found the engine writing SIXTEEN ZEROS where the machine writes the boss's
    attributes: `$A881..$A8C0` is tape data nobody had extracted, and no gate
    that compared only the write ADDRESSES could ever have noticed.
    RULES: (a) a blit gate must compare VALUES as well as addresses, and the
    source must be non-uniform (see #77); (b) when a routine reads through a
    self-modified pointer, sweep the pointer over every value its writers can
    produce -- and over the TAPE RESIDUE, which here is not of the array's form
    at all and makes the walk read the spawn routine's own source table;
    (c) three of the seven slots are real data, one IS a live array the spawner
    writes, and three point into the draw routine's own opcodes: a sweep says
    which is which, a single captured value says nothing.

79. **A SELF-MODIFIED INSTRUCTION PAIR HAS MORE STATES THAN ITS TWO ENDPOINTS,
    AND THE ONES BETWEEN ARE ARBITRARY OPCODES** (Bubble Bobble, M7.7-H13-B5,
    2026-09-19).  `$A98F/$A990` live inside `$A97D`'s control flow and decay from
    `37 C9` (SCF / RET -- every position is an overlap) to `00 00` (NOP / NOP --
    fall through to the real comparator).  They are decremented ONE AT A TIME by
    `$AAA1 DEC (HL)`, so the pair walks through two hundred-odd intermediate
    OPCODE pairs, and they are not all the same function: `37 00` falls through
    and behaves as the comparator, but **`00 C9` is NOP / RET and returns with
    the caller's carry -- "always miss", a third answer neither endpoint gives**.
    Measured: 5, 2, 2 and 0 hits out of five probes for `37 C9`, `37 00`,
    `00 00` and `00 C9`.
    RULES: (a) drive all four CORNERS of a self-modified pair, not the two the
    images happen to hold -- "non-zero" is not a state; (b) a port that ships no
    Z80 cannot execute the intermediates, so PROVE they are unreachable (here:
    the first byte reaches zero at frame 137 while the second is still near
    `$89`, and the only other consumer needs a round build that cannot happen
    inside the 429 frames the decay takes) and DECLARE the gap in the gate;
    (c) the proof is about the DECAY ORDER and the CONSUMER's reachability, and
    both have to be measured -- neither follows from reading the code.

80. **A PUSHED RETURN ADDRESS IS PART OF THE ROUTINE, AND IT CAN DO A SECOND JOB
    THE BODY DOES NOT HINT AT** (Bubble Bobble, M7.7-H13-B6, 2026-09-19).
    `$93DC` opens by PUSHing `$93F4` and then clears the ISR's even-branch gate
    (`$93E0 XOR A / LD ($FEC5),A`).  `$93F4` is `XOR A / LD ($FFF9),A / INC A /
    LD ($FEC5),A / RET`: it clears the request AND **sets the gate back to 1**.
    Transliterating the body without the pushed return leaves the gate dark
    for ever, the bubble manager never runs again, and the failure surfaces four
    subsystems away -- in this case in M7.5's blow gates, which is how it was
    caught.  MEASURED over 60 frames: `$93E1` writes 0 and `$93F9` writes 1, 523
    times each, and nothing else touches the byte.
    RULES: (a) when a routine PUSHes a literal before doing anything, read that
    address as part of the routine -- it is the epilogue, and no CALL-graph scan
    associates it with the caller; (b) a byte cleared at the top of a routine and
    restored at the bottom is a HAND-OFF, not a reset: transliterate both halves
    or neither; (c) if a new increment breaks a gate in an unrelated subsystem,
    suspect exactly this before suspecting the gate.

81. **AN INSTRUMENT MUST COVER EVERY WRITE PATH OF THE THING IT MEASURES**
    (Bubble Bobble, M7.7-H13-B6, 2026-09-19).  The bolt's draw goes through
    `itemPoke()` and its erase wrote `ram[dst] = ...` directly, so a gate that
    monkey-patched `itemPoke` to count writes measured the draw exactly and
    reported the erase as ZERO WRITES -- a confident, precise, wrong number that
    looked like an engine fault.  The two halves of one blit pair had two write
    paths and the same below-$4000 guard duplicated in both.
    RULES: (a) before trusting an instrumented count, check that EVERY store in
    the routine goes through the instrumented door -- grep the method for a bare
    `ram[` ; (b) unify the paths rather than instrumenting two (the erase now
    calls `itemPoke` too, which also removes the duplicated ROM guard);
    (c) a count of ZERO from an instrument is the most suspicious result it can
    produce: something ran, or nothing did, and only the other half of the pair
    says which.

82. **A CALL IS AN EXPRESSION: ITS RETURN VALUE CAN BE THE DATUM, AND A "VOID"
    TRANSLITERATION SILENTLY SUBSTITUTES THE CALLER'S OWN PRELOADED REGISTER**
    (Bubble Bobble, M7.7-H13-B7, 2026-09-19).  `$B761 LD HL,1 / $B764 CP L /
    $B766 CALL z,$B816 / ... / $B771 LD ($FFED),HL`.  Read as control flow this
    is "if the class is 1, make a corpse, then store the award" -- and the award
    looks like the `LD HL,1` two instructions above.  It is not: `$B816` ends in
    `$8BC2`, which leaves **HL = $0100**, so the CORPSE'S OWN RETURN VALUE is the
    award and a class-1 pop pays ONE HUNDRED.  The engine paid ONE, and the
    difference is invisible in any test that only asks "was a corpse created?".
    RULES: (a) for every `CALL` whose caller stores a register pair afterwards
    WITHOUT reloading it, find what the callee leaves there -- follow the callee
    to its own last write of that pair, through its tail calls; (b) a JS method
    transliterated as a void statement is an ASSERTION that the callee returns
    nothing; write that assertion down or return the value; (c) gate the PAID
    AMOUNT, not the fact of payment -- and seed the destination field, because a
    routine that clears it before adding (here `$80FA` at `$8164`) makes "paid
    ten" and "paid nothing" the same observation.

83. **A BIT TEST IS NOT A GATE UNTIL YOU KNOW WHO CALLS IT**
    (Bubble Bobble, M7.7-H13-B7, 2026-09-19).  `$A437` reads
    `BIT 5,(IY+7) / RET nz / SET 5,(IY+7) / LD HL,$AA5F / DEC (HL)` and is,
    locally, a bit-5 test.  Modelled that way it charges a LIVE enemy twice,
    because the only path that reaches it is `$A447`, the entity master, which
    **diverts to `$A437` when bit 7 is CLEAR** (`$A451 JP p`) or bit 3 is set
    -- otherwise it falls on to the erase/draw and never reaches `$A437` at
    all.  The real rule is bit 7 CLEAR **and** bit 5 clear.  [The mechanism
    sentence here first read "returns early when bit 7 is SET", inverted;
    corrected in B9 from the disassembly.  The rule and the code were right,
    which is exactly why nothing caught it -- see rule (d).]  Worse, `$8BF3` overwrites `(IY+7)` immediately afterwards and clears
    bit 5 again, so THE FLAG CANNOT SAY WHICH ARM RAN -- only the counter can.
    RULES: (a) before transliterating a routine's entry condition, list its
    callers and fold in every test they made on the same byte; (b) when the
    observable is overwritten downstream, gate the SIDE EFFECT (here `($AA5F)`)
    and not the flag; (c) seed that counter to a value the code never writes --
    every shipped capture reads `$00` there, so an unseeded run wraps to `$FF`
    and both arms look like garbage.  (d) WRITE THE MECHANISM DOWN FROM THE
    DISASSEMBLY, NOT FROM THE TABLE.  A measured input/output table pins the
    RULE and says nothing about WHY, so an inverted explanation beside correct
    code passes every gate and every battery -- and the next increment reasons
    from the prose, not the bytes.  This entry shipped that way for three
    increments.

84. **ONE KEY SCRIPT IS NOT A DISTRIBUTION, AND "NEVER IN N" MUST CARRY ITS N**
    (Bubble Bobble, M7.7-H13-B8, 2026-09-19).  Two independent agents measured
    which of the boss's six accepted cells fair play actually produces.  Each
    ran ONE key-script family on the same state; one reported "four of five hits
    were at dx = -3, the visually-absurd cell", the other "every one of six
    decrements landed at (-3,-1); in 22 bolts the overlapping cell (0,-1) NEVER
    fired".  A twelfth script produced (0,-1).  Each had read a property of its
    own script as a property of the game.
    RULES: (a) any claim about "what the game actually does in play" needs a
    SWEEP of scripts and a histogram REPORTED WITH ITS N, never a single run;
    (b) "never observed" is a statement about the sample -- write the sample
    size into the sentence, and into the fixture, so the next reader can see how
    thin it is; (c) when two measurements of the same thing disagree about the
    COMMON CASE while agreeing on the SET, suspect the sampling, not the code.

85. **A CROSS-PRODUCT OF TWO MEASURED SUPPORTS IS NOT A PROBABILITY**
    (Bubble Bobble, M7.7-H13-B8, 2026-09-19).  An enumeration pass measured the
    reachable bubble rows (23 of them) and the reachable boss rows (17), crossed
    them, found 51 of 391 pairs accepted and reported "13.0%" -- then quoted an
    observed 13.6% as corroboration.  Neither axis was uniform (only 7 of the 23
    rows ever reached the allocator) nor independent (the boss's x and y are
    correlated, and only 89 of 425 pairs occur at all), and the pairing was not
    even well defined, because the bolt's row is frozen at allocation while the
    boss's moves through the whole flight.
    RULES: (a) enumerating a SUPPORT is a closure argument -- "these values are
    reachable" -- and says nothing about rates; do not divide it; (b) if a rate
    is wanted, measure the rate, and say over how many trials; (c) a computed
    number that lands near an observed one is a coincidence until the sampling
    model is written down, and quoting it as agreement hides both.

86. **A GAME'S KEY TABLE HOLDS ITS OWN AND-MASK, NOT THE VALUE THE PORT RETURNS**
    (Bubble Bobble, M7.7-H13-B8, 2026-09-19).  `$B5FD` holds four
    (half-row select, BIT MASK) pairs and the game tests `IN A,(sel) / AND mask
    / JR z`, so the mask has the key's bit SET.  `Ports.press` wants the value
    the port RETURNS, where a pressed key is a ZERO.  Handing the table value
    over verbatim pressed the SEVEN OTHER KEYS of that half-row -- and on `$7F`
    one of them is the PAUSE key, so the machine sat in `$8FFB`'s
    `IN A,($FE) / RRA / JR c` loop with interrupts OFF.  The phase ran, produced
    zero bolts, zero hit tests and zero damage, and read exactly like a correct
    negative.
    RULES: (a) convert a game's mask with `0xFF ^ mask` and say so at the
    conversion site; (b) before believing a keyboard-driven negative, assert a
    POSITIVE control from the same script -- here "the player blew at least one
    bubble" -- because a wedged machine and a correct rule give the same zeros;
    (c) if a free-running measurement stops advancing frames, disassemble the PC
    it stopped at before touching anything else: `$8FFF` named the bug in one
    line.

87. **A BRACKET'S END POINT MUST BE AN INSTRUCTION *BOTH* ARMS EXECUTE, AND THE
    TELL IS THAT BOTH ARMS READ ZERO** (Bubble Bobble, M7.7-H13-B9,
    2026-09-22).  To isolate the death tick's out-of-lives branch I armed a
    write watch at `$AB5E` and harvested it at `$ABD4`, "the tick's RET".
    `$ABD4` is P2's RET: P1 leaves at `$ABCB`, four bytes earlier, because
    `$ABBD BIT 0,(IY+$5A) / JR nz` splits the respawn into a P1 arm and a P2
    arm with a `RET` at the end of each.  The harvest point was never reached,
    the log was never read, and the phase reported **0 writes on the last life
    and 0 on the respawn** -- which is exactly the shape a correct negative
    has.  The real numbers were 83 and 1.
    RULES: (a) pick the bracket's end at the instruction where the arms
    CONVERGE -- here `$AB6B`, the target of the `JP p` that skipped the branch
    -- not at "the end of the routine", which may be several addresses;
    (b) ZERO ON BOTH SIDES OF A COMPARISON IS NOT A RESULT, it is a broken
    instrument: a differential whose two halves agree at zero has measured
    nothing, and the control that was supposed to save you agrees with you for
    the wrong reason (the dual of #50 and #81(c));
    (c) count the END POINT's executions alongside the writes -- a bracket that
    closed zero times should fail loudly, not return an empty list.

88. **A COVERAGE COUNT IS AN UPPER-BOUND TEST, NOT AN EQUALITY: "WERE THESE N
    PLACES WRITTEN?" IS SATISFIED BY A ROUTINE THAT WRITES EVERYWHERE**
    (Bubble Bobble, M7.7-H13-B10, 2026-09-22).  The flood arm paints ONE
    32-cell row per step at `$5AE0 - (A & $F8) * 4`, walking up the screen
    through 22 distinct rows.  My gate collected the set of 32-aligned rows
    that had been painted and asserted `size === 22`.  Three different
    mutations passed it: painting the WHOLE 704-cell screen every step (all 22
    rows are in the set), computing the base WITHOUT the `AND $F8` (the set is
    still 22 rows because the gate only sampled 32-byte boundaries), and
    walking the rows DOWN instead of up (a set has no order).
    RULES: (a) a set of touched positions is an EXISTENTIAL -- pair it with the
    changed-cell COUNT per step, which makes over-painting fail immediately;
    (b) assert the ADDRESS against the formula that produced it, not against
    membership of a bucket, or every address inside the bucket passes;
    (c) if the thing walks, assert the ORDER: keep the sequence and check it is
    monotonic, because a set discards exactly the property "walks up".
    And the sibling that showed up four more times in the same run: a THRESHOLD
    probed at a value both models agree on tests nothing -- `AND $1F` and
    `AND $0F` both say "wait" at `$11`, and only `$10` separates them.  That is
    TRAPS #60 re-paid; pick the value ONE STEP from the boundary, on each side.

89. **A CAPTURE CAN SIT INSIDE A WINDOW THAT SWITCHES A WHOLE PASS OFF, AND THE
    COUNTER THAT SAYS SO IS NOT THE EVIDENCE** (Bubble Bobble, M7.7-H13-B11,
    2026-09-22).  `$AA6E LD A,($B54B) / $AA72 JP nz,$B520` abandons the entire
    entity update while the settler byte is non-zero.  `build/boss.pkl` holds
    `$35` and `build/bossspawn.pkl` `$53`, so they sit 107 and ~166 frames
    inside that window -- and four increments measured player-related negatives
    on them.  `build/play1p48.pkl` is inside one too (`$B54B = 14`), which is
    the 28 frames that reconcile two different measurements of the same decay.
    RULES: (a) before recording that a routine did not run, PROFILE IT -- an
    instruction census over its address range (0 against 5928 here) is the
    evidence; a counter reading zero is not; (b) check the gating byte of every
    state you are about to call "the round-N state", and put its value in the
    fixture beside the numbers; (c) a state can be unusable for a SECOND
    reason that the first check passes -- `bosskilled`'s settler is zero and it
    still runs the entity pass once in 120 frames, because a 345-frame freeze
    owns the rest of the run.

90. **A SAMPLER'S ROW IS THE RESULT OF THE PREVIOUS PASS, AND A PASS IS NOT
    ATOMIC WITH RESPECT TO THE CLOCK IT SAMPLES** (Bubble Bobble, M7.7-H13-B11,
    2026-09-22).  Two alignment faults, both of which look exactly like engine
    bugs.  First: a row taken at the loop top holds the frame counter as it was
    at the END of the pass, while the chain that produced the row's other
    fields ran with the PREVIOUS value -- replayed the naive way, the boss's
    tick divider diverged at row 9 against an engine that was self-consistent
    throughout.  Second: the loop runs 8.571 times a frame, so 16 of 600 passes
    STRADDLE an interrupt and the chain members see DIFFERENT counter values --
    the boss tick at `$8D2E` reads one, `$A09A` at `$8D43` reads the next.  One
    replayed value per pass reproduces the boss exactly and is off by one on
    `$A09E`, and the obvious conclusion is that the effect manager is wrong.
    RULES: (a) sample the driving clock AT each consumer, not once per row, and
    record how many rows straddle -- if the number is zero the extra samples
    cost nothing and the claim is now measured; (b) state explicitly which pass
    a row describes; "the row after" and "the pass that produced it" are off by
    one and the difference is invisible while nothing moves; (c) when a replay
    diverges on ONE field while everything around it matches, suspect the
    replay's alignment before the code -- a real defect rarely spares its
    neighbours.

91. **THE SEED LIST IS THE TEST'S WORLD: ANYTHING NOT IN IT IS SUPPLIED,
    SILENTLY, BY THE ENGINE'S OWN DEFAULTS** (Bubble Bobble, M7.7-H13-B11,
    2026-09-22).  The differential seeded 30 fields and compared them.
    `$A98F/$A990` were not among them, so the engine ran on what `reset()` puts
    there -- the tape's `37 C9`, `SCF / RET`, which makes EVERY POSITION AN
    OVERLAP (TRAPS #79) -- while the machine's capture held `00 00`.  The
    engine's boss killed P1 on pass 10 and the first differing row said
    `FDDA 192 vs 196`: a true report of a divergence with an entirely false
    implication.
    RULES: (a) a field that the code under test READS belongs in the seed list
    even when you are not comparing it -- the comparison set and the seed set
    are different lists and only the second one has to be complete;
    (b) when a differential's first divergence is in a field whose INPUTS are
    not seeded, fix the seed before touching the engine; (c) the port's own
    `reset()` defaults are the most dangerous unseeded values there are,
    because they are plausible: a zero would have been obvious.

92. **A SUITE THAT ONLY COMPARES RAM NEVER ASKS WHETHER ANYTHING IS VISIBLE,
    AND IT WILL PASS OVER A BLACK SCREEN** (Bubble Bobble, M7.3c, 2026-09-22).
    The round render asset's attribute third for rows 2-23 was the COLOUR
    SHADOW, byte for byte -- solidity, drift and occupancy bit fields written
    into the attribute file.  433 of the 704 playfield cells had ink equal to
    paper.  The sprites blitted perfectly, byte-exact against the machine, and
    nothing could be seen.  **915 checks passed over it**, and when the fix
    turned the screen from black to the round's colours, NOT ONE of them moved.
    The owner found it by looking at a filmstrip.
    RULES: (a) a differential against a captured world is a test of AGREEMENT,
    not of OUTPUT -- add at least one assertion about the rendered result
    itself, and the cheapest useful one is "no playfield cell has ink equal to
    paper"; (b) every shipped asset needs a PRODUCING TOOL in the repository --
    this one was made ad hoc, had no tool, and so nothing ever re-derived it or
    checked it against the machine; (c) when an asset contains two blocks of
    the same size, check they are not accidentally the same block: `display`'s
    attribute third and `colour` were identical and no gate compared them;
    (d) LOOK AT IT.  The manual says so for a reason, and the one measurement
    that found this was a write-watch run because a human said the screen was
    wrong.

93. **A SEED THAT IS WRONG BY ONE STEP IS NOT VISIBLY WRONG IN ANY SINGLE ROW**
    (Bubble Bobble, M7.8-0a, 2026-09-23).  `roundclass.py`'s chained build
    seeded `($8609) := 0` and called it "the NEW-GAME value $96FB writes".
    `$96FA` is `XOR A / LD ($8609),A / LD ($83EC),A / LD ($82D7),A` -- ALL
    THREE.  The chain inherited round1_48's `($82D7) = ($83EC) = 1`, so every
    build counter in the census, and every palette byte and tile index derived
    from one, came out ONE BUILD AHEAD of a real new game.  Nothing looked
    wrong: each row was internally consistent, the round-keyed findings were
    all correct, and no gate read the counter columns.  It surfaced only when
    the platform shadow was measured and the same round 1 built at the two
    phases differed in 1,661 of 6,144 bytes.  By then TWO independent
    measurement passes had taken 81-round sweeps off it and published tables
    shifted by exactly one round -- an 84-tile reconstruction table missing six
    tiles, and two "sixteen exact rounds" lists each +1.
    (a) When a tool claims to reproduce a machine state, DISASSEMBLE the
    routine it is imitating and seed every byte it writes, not the one you
    remembered.  (b) A comment naming a single address is a claim about a
    whole routine; check it.  (c) Derived columns nobody gates are where this
    hides -- so gate the SEED, not just the output.

94. **THE ENTRY POINT YOU ARM AT IS PART OF THE MEASUREMENT, AND IT CAN INVENT
    A DEFECT THAT IS NOT THERE** (Bubble Bobble, M7.8-A, 2026-09-23).
    `$9858`'s shadow clear is `LD HL,$E000 / LD C,$18 / CALL $AA49 / DEC C /
    JR nz`, and `$AA49` is `XOR A / LD (HL),A / INC HL / DJNZ` -- a fill whose
    length is **B from the caller**.  `$9858` never sets B.  Armed at `$9858`
    from a mid-play save, B held whatever the interrupted main loop left: 88 on
    round1_48 and 10 on r20_48, clearing 5,976 and 5,898 of 6,144 bytes and
    leaving residue in the shadow's bottom sub-rows, predicted to the byte on
    four states.  That looked exactly like a defect in the port's
    `shadowClear()`, which clears all 6,144.  Driven through the REAL advance
    on a correctly seeded chain, **B is 0 on all 81 rounds** -- the whole
    6,144, every time.  The port was right and the harness was lying.
    Before "fixing" a method to match a harness measurement, drive the machine
    the way the GAME drives it and measure again.  An arm point is a poke.

95. **A METHOD WITH NO CALL SITE HAS NEVER HAD ITS PARITY EXERCISED, AND A
    SELF-MODIFIED OPERAND IS EXACTLY WHERE THAT BITES** (Bubble Bobble, M7.8-A,
    2026-09-23).  `$833A` is `LD A,$1E / XOR $1E / LD ($833B),A / LD C,A`: the
    literal IS the state, flipping `$1E -> $00 -> $1E` across the two calls a
    build makes, and C is the COLUMN OFFSET for the wall draw.  `reset()` never
    seeded `$833B`, so it started at `$00`, the parity inverted, and the FIRST
    call drew the RIGHT wall and the second the LEFT.  The method had been
    written, reviewed and gated -- but it had NO CALL SITE, so nothing had ever
    run it twice in sequence, which is the only way the flip is observable.
    Thirteen such methods existed in this engine at once.
    (a) Count call sites, not methods: an uncalled method is untested however
    many rows name it.  (b) For a self-modified operand, gate the RESTING
    VALUE at reset, from the tape image, not just the transition.

96. **THE WRITE COUNT CAN MATCH THE MACHINE EXACTLY WHILE EVERY VALUE IS
    WRONG** (Bubble Bobble, M7.8-A, 2026-09-23).  `$824A`'s inner loop is
    `LD (HL),A` on the even byte and `OR (HL)` on the odd one, and the odd
    bytes come from the platform tile buffer `$856C`.  A build writes only
    offsets +1, +3 and +5 there; +7, +9, +11, +13, +15 and all of +16..+23 are
    **never written by anything** -- pure tape data the port had never shipped.
    With them zero the `OR` contributed nothing, so the engine wrote 2,704
    bytes to the same 2,704 addresses as the machine, in the same order, and
    455 platform bytes went missing.  A gate counting writes, or diffing which
    addresses were touched, passes this perfectly.
    (a) Compare VALUES, not extents.  (b) When a routine merges rather than
    stores, its source buffer is an input -- find the bytes nothing writes and
    ship them.  (c) "Engine-only 0, machine-only 455" is the signature of a
    missing input, not a wrong algorithm; the asymmetry names the bug.

97. **AN ANNOTATION THAT LIVES ONLY IN THE ARTIFACT DIES AT THE NEXT
    RECAPTURE** (Bubble Bobble, M7.8-A, 2026-09-23).  M7.7-R1 recorded why a
    differential row was superseded by editing `build/bossround_fixture.json`
    directly.  Regenerating that fixture for an unrelated reason reverted the
    note to the producing tool's 2026-09-17 text and took a gate red.  This is
    TRAPS #92 rule (b) from the other direction: an asset is its tool's output
    and nothing else, so anything worth keeping belongs in the tool.  If you
    find yourself editing a `build/*.json` by hand, you are editing a build
    product.

98. **A DIFFERENTIAL THAT SEEDS ITS OWN INPUTS TESTS THE ROUTINE AND NEVER THE
    SEQUENCE** (Bubble Bobble, M7.8-A, 2026-09-23).  The round-builder gate
    compared the engine against the machine on 18 covering rows, byte for byte,
    over the whole shadow -- and every row began by seeding `($8609)`,
    `($82D7)` and `($83EC)` from the fixture.  So it proved the builder correct
    *for inputs it supplied itself*.  Meanwhile `reset()` left `($83EC)` one
    build behind `($82D7)`, a pair the machine is never in, and **every round
    the port actually built used the previous round's platform tile** -- about
    1,650 of 6,144 shadow bytes wrong on every advance, with all 18 rows green.
    The fix is a second gate that pokes NOTHING: drive the port's own
    `roundAdvance()` N times from `reset()` and compare against N chained
    `CALL $97F8` from a new game.  A sampled input space and a generated
    sequence are different tests and a suite needs both.

99. **WHEN A CONSTANT HAS NO MEASUREMENT NAMED BESIDE IT, TRY CORRECTING IT AND
    SEE IF THE SUITE GOES RED** (Bubble Bobble, M7.8-A, 2026-09-23).  The
    `($83EC)` defect above was pinned by an assertion -- `pg.ram[V.build_b_at]
    === 0` -- sitting in the same expression as a properly sourced one
    (`=== A.render.build_counter`).  The 0 was `build/image.bin`'s round-80
    residue frozen into a gate with no machine value named for it.  An
    adversarial pass found it not by breaking the code but by **fixing** it and
    watching the suite fail.  The INVERSE MUTATION is the cheap test for a
    constant nobody sourced: if making it right turns the suite red, the suite
    is pinning a bug.  Corollary: in any assertion that ANDs several equalities,
    check that each side has a provenance, because one borrows credibility from
    the others.

100. **AN ASSERTION CAN BE TRUE OF EVERYTHING** (Bubble Bobble, M7.8-A,
    2026-09-23).  A gate meant to bound a declared departure read
    `for (const ad of glyph) if (g.ram[ad] !== undefined) inside++;` and then
    `inside === glyph.size`.  `g.ram` is a `Uint8Array(65536)`, so that is true
    for every in-range index -- including `$0000` and `$FFFF`, addresses the
    glyph never touches.  Directly above it sat `for (let row = 0; row < 22;
    row++){ /* comment */ }`, a loop with an empty body.  The row's prose
    claimed the engine differed from the machine on exactly six bytes and
    asserted nothing of the kind.  Neither survives a moment's reading, and
    both shipped green.  (a) A predicate over a typed array that tests
    `!== undefined` tests nothing.  (b) Mutation-test the GATE, not only the
    code: feed it a value you know is wrong and require it to fail.  (c) An
    empty loop body is a review failure, not a style one.

101. **THE ISR REACHES INTO CODE THAT HAS NO HALT IN IT** (Bubble Bobble,
    M7.8-A, 2026-09-23).  `$7F1B`, the round-start composition, contains no
    `HALT` anywhere, so the 50 Hz interrupt fires *during* the scroll and
    composites entities into the display -- and `$854D` then copies display rows
    2 and 23 back into the SHADOW, so a sprite that lands in row 2 becomes part
    of the built background.  MEASURED by capturing every covering row twice:
    the ISR changes the built shadow on 3 of 23 rows, and on one of them it is
    two bytes that no amount of staring at the builder would explain.  An
    oracle taken with interrupts on, compared against a port that runs no ISR
    inside its own composition, asserts a behaviour the port does not model --
    so capture BOTH, compare against the one the port models, and carry the
    other as the named boundary with its rate.

102. **A BOUNDARY CHECK THAT NAMES RANGES LEAVES EVERYTHING BETWEEN THEM
    UNGUARDED -- AND AN EXTENT MUST BE MEASURED AS WRITES, NOT AS CHANGES**
    (Bubble Bobble, M7.8-A, 2026-09-23).  The builder's "what it must not
    touch" check guarded four named ranges.  A mutation adding
    `ram[0x9000] = 0xFF` to the ceiling routine -- the builder scribbling
    outside its own extent on every build -- survived a battery; the identical
    scribble at `$7000` was caught only because `$7000` happens to fall inside
    the round records.  The fix is to measure the machine's extent as an
    ADDRESS SET over the whole 64K and require the engine's changed set to be a
    subset of it.
    AND THE FIRST ATTEMPT AT THAT WAS WRONG IN AN INSTRUCTIVE WAY: measuring
    the extent by diffing the world before and after gives CHANGED addresses,
    not written ones.  `$860E` is written by `$8400` on every build and changed
    on none of them, so a port writing a different value there looked like it
    had scribbled outside the extent, and three display cells the machine
    rewrites with their own values did too.  A store of the value already there
    is still a store.  Measure the extent with a write-watch, union it with the
    diff, and only then compare.

103. **A ROUTINE REACHED ONLY BY FALL-THROUGH HAS NO CALLERS TO FIND, AND A
    METHOD WRITTEN FOR IT WILL SIT UNCALLED** (Bubble Bobble, M7.8-B,
    2026-09-23).  `$79AC` is `JP $7C43`; `$7C43` masks the colour shadow with
    `$38` and then falls onward through the drift painter, which falls into
    `$7DD6`, the element class.  There is no `CALL` to either tail anywhere in
    64K.  The port had `driftApply()` and `elementClass()` both written, both
    gated in isolation, and both with **zero call sites** -- so every round
    advance wiped the per-round wind (every bubble after round 1 rose straight
    up) and left the element class at 0 (the fire, water and lightning rounds
    never fired).  This is the same shape M7.8-A found three times in one
    increment and it is now five.
    (a) A caller scan proves nothing about a fall-through; walk the code
    FORWARD from the jump target and see where it stops.  (b) Audit for methods
    with no call site as a standing check -- the count is a number the suite can
    assert.  (c) A routine gated in isolation is not wired; "tested" and
    "reached" are different claims.

104. **A GATE WHOSE TWO SIDES ARE THE SAME CAPTURE CANNOT FAIL, AND SHIPPING A
    ROUTINE'S OUTPUT IS HOW YOU GET ONE** (Bubble Bobble, M7.8-C, 2026-09-23).
    The drift field was shipped as an asset -- 81 rounds x 192 bytes of captured
    output -- and the suite's "the drift field matches the machine on all 81
    rounds" row drove the engine, which read `build/drift_field.json`, against
    `build/drift_fixture.json`.  An adversarial pass found those two hold
    **byte-identical base64 for all 81 rounds**: one capture compared with a
    copy of itself, per cell, with a seeded map and a careful commentary about
    permutations -- and no possible failure.
    The cure is not a better comparison, it is a different engine: ship the
    routine's INPUT and compute.  675 bytes of stream and tables replaced 15,552
    bytes of field, and the identical comparison became a test of the algorithm.
    (a) When an asset is a routine's OUTPUT, any gate over it is at risk of
    this; ask what the engine would have to get wrong for the row to go red.
    (b) Two assets derived from one measurement are ONE source -- diff them
    before using one to check the other.  (c) "WHEN THE X LANDS THE ASSET GOES"
    is worth writing into the spec at the moment the asset is created, because
    it is the thing that later makes the gate real.

105. **A TRANSLITERATION CAN INHERIT A DOMAIN IT NEVER HAD** (Bubble Bobble,
    M7.8-C, 2026-09-23).  The port's drift field was a lookup: an unknown round
    found no entry and the routine silently did nothing.  The transliterated
    painter walks a stream through LIVE memory, and off its domain it does not
    do nothing -- at `($8609)` = 0, the byte `$96FB` writes at every new game, it
    writes 141 cells over `$FB02..$FFF0`, and at 255 it writes **10,545** over
    `$FB00..$FFF9`: the player struct at `$FD80`, the bubble pool at `$FED8`, the
    high score at `$FFE1`.  The silent no-op became memory corruption.
    Measuring that the port cannot reach it (`$97F8` increments the round before
    the round start, so the painter only ever sees 1..81) is necessary and not
    sufficient: the guard goes in anyway, and it is COUNTED rather than silent,
    because the next caller will not know.

106. **A TRANSLITERATED LOOP CAN BE UNBOUNDED WHERE THE MACHINE'S WAS BOUNDED
    BY ITS DATA -- AND A MUTATION BATTERY WITH NO PER-CASE TIMEOUT TURNS THAT
    INTO A WEDGED RUN** (Bubble Bobble, M7.8-C, 2026-09-23).  The drift
    painter's alias walk re-enters at `$7C8A` with a new round and nothing in
    the routine limits how often: the Z80 terminates only because the stream
    data terminates.  Transliterated faithfully, that is an unbounded
    `for (;;)` in the browser.  A mutation reading the entry stride from
    `BODY[]` instead of `LEN[]` made the walk under-advance, land on an `$Fx`
    byte and cycle -- and `node test/bb.test.js` then burned a full core for
    **five hours**, while the runner, which had no timeout, sat blocked behind
    it with that mutation STILL APPLIED to `web/game.js`.
    Two defects, one incident, and both needed fixing:
    (a) BOUND the loop and COUNT the overrun.  The bound is a measurement --
    sixteen aliases exist and the deepest real chain is two hops -- not a
    guess, and it is a declared departure because the machine would spin.
    (b) EVERY subprocess in a battery gets a timeout.  *** CORRECTION, and it
    matters because the first version of this entry blamed the wrong tool: the
    PROJECT'S battery `mutate7.py` ALREADY had a 180-second timeout and crash
    detection, with a comment explaining that a hang counts as a kill because
    the suite did not pass.  The runner with no timeout was a HELPER I wrote
    myself that afternoon and then reported results from. ***  Do not write a
    lesson blaming shared tooling until you have read it.
    (c) When a battery is interrupted, VERIFY THE FILE IS RESTORED before
    trusting anything -- checking the first case's anchor is not enough, it was
    the third that was stuck, and a report of "the file is clean" was wrong.
    (d) Silence from a long-running job is not progress.  The output file had
    not grown in five hours; the check that settled it was whether the BUILD
    ARTIFACT's mtime was still moving.

107. **THE FIX FOR A HANG REPORTED THE HANG AS A PASS** (Bubble Bobble, M7.8-C,
    2026-09-23).  After a mutation hung the suite for five hours, a HELPER
    RUNNER I had written -- not the project's `mutate7.py`, which already had
    both guards -- was given a per-case timeout.  It did this:

        except subprocess.TimeoutExpired:
            return ['TIMEOUT'], '...'

    and its caller reads the returned list as the FAILURE LIST:
    `if not fails: SURVIVED else: print('killed by %d' % len(fails))`.  So a
    timeout printed **"killed by 1"** -- indistinguishable from a real kill.
    The next run reported "all 25 mutations killed, zero survivors" and TWO of
    them had hung for 180 seconds each.  That went into a message to the user as
    a clean result.
    It was caught only because a PARALLEL runner, written independently, used a
    distinct TIMEOUT verdict and disagreed -- two implementations of the same
    measurement, which is the only thing that finds this class.
    AND THE SAME DISAGREEMENT THEN CORRECTED THE OPPOSITE ERROR.  The parallel
    runner called a crashing case SURVIVED, which is the same lie inverted: a
    page that will not parse, or an engine that throws, has not been measured
    either.  The project's own battery had this right all along -- it turns an
    empty summary into a named `<crash>` failure -- and the split that survives
    is three-way: an ENGINE DIAGNOSTIC firing (this engine throws on an
    unexpected RNG draw, by design) is a KILL; a SyntaxError is a BROKEN MUTANT
    that tested nothing and must be repaired; only a clean green run is a
    SURVIVOR.
    (a) A timeout is not a kill and not a pass: give it its OWN verdict and
    count it as bad.  An engine that hangs has not been shown to be correct.
    (b) Never encode a new outcome in an existing channel -- a sentinel in the
    failure list is a lie the caller cannot detect.
    (c) When a fix and a report disagree with a second implementation, believe
    the disagreement and go and measure.

108. **A GUARD THAT BOUNDS THE WRONG QUANTITY BOUNDS NOTHING** (Bubble Bobble,
    M7.8-C, 2026-09-23).  The drift painter's fill was given a budget to stop a
    corrupted stream hanging the engine.  The first version counted CALLS and
    capped them at 4,096 -- but one call can ask for 256 rows x 256 cells, so
    the cap permitted 268 million writes and the engine still hung.  Counting
    the CELLS is the only cap that bounds the work.  Measured afterwards: a real
    round asks for at most 1,090 cells, so a 200,000 budget is 183x headroom and
    the 81 real rounds trip it zero times.
    Bound the thing that actually grows, and then measure the real maximum so
    the headroom is a number rather than a hope.

109. **AN ASSET IS SHIPPED BECAUSE NOBODY ASKED WHO READS IT, AND A PAGE GETS TO
    8.8 MB ONE FIXTURE AT A TIME** (Bubble Bobble, M7.9, 2026-09-24).  The built
    page was 8,829,094 bytes.  **97.7% of it was oracle fixtures written for the
    test suite**: 68 of 76 assets, 17.6 MB, one of them -- a per-frame entity
    oracle -- 13.3 MB on its own.  The engine reads EIGHT assets, 207 KB.
    Nothing was wrong with any individual decision; each fixture was inlined
    because the build inlines assets, and nobody asked which of them the engine
    reads.  Holding the test-only ones back and letting the rig load them from
    disk took the page to 621 KB with the suite running every check.
    (a) THE FLAG THAT LOOKS LIKE THE ANSWER IS NOT THE ANSWER: splitting on
    `required` would have BROKEN the page, because two assets the engine reads
    at reset() were marked `required: false`.  Derive the split from the ENGINE
    SOURCE, not from anyone's classification, and gate it that way.
    (b) GATE BOTH DIRECTIONS.  An asset held back by mistake makes the page
    quietly wrong; one shipped by mistake makes it quietly fat -- and only the
    second is how it grew.  Default the flag to SHIP, so an unclassified asset
    costs bytes rather than correctness.
    (c) THE SILENT-SKIP IS THE REAL DANGER.  Every gate block here is guarded by
    `if (A.thing)`, so an unmerged fixture would skip its whole block and the
    suite would go quiet: measured, disabling the rig's merge drops the suite
    from 1,001 checks to 67.  The rig COUNTS what it merged and asserts the
    number, so the collapse is loud.

110. **A PREDICATE BUILT BY STRING CONCATENATION LOSES ITS ESCAPES, AND THE ROW
    PASSES** (Bubble Bobble, M7.9, 2026-09-24).  The gate above was first
    written as `new RegExp('(?:this\.)?A\.' + key + '\b')`, generated through
    a Python heredoc.  The escapes collapsed on the way in, so the JavaScript
    string `'\b'` was a BACKSPACE character rather than a word boundary, the
    pattern matched nothing, and the check reported **"0 referenced"** and
    PASSED -- a guard over an empty set.
    It was caught only because the row printed its own count and the count was
    zero.  (a) Make a check STATE THE SIZE OF WHAT IT MEASURED, so measuring
    nothing is visible.  (b) Assert that size is non-zero as its own row.
    (c) Prefer a literal scan to a dynamically built regex when the pattern
    crosses a code generator; escaping survives one layer, rarely two.

111. **A ROUTINE CAN BE FULLY TRANSLITERATED AND STILL DRAW NOTHING, BECAUSE THE
    STATE IT READS WAS NEVER SEEDED** (Bubble Bobble, M7.10, 2026-09-24).
    `$806C`'s three methods were all written and gated in isolation.  What was
    missing was `reset()`: `($FD87)`, `($FD91)`, `($FDDC)` and `($FDE6)` were
    ZERO, and `$8097` is `RET p` -- a player whose +7 bit 7 is clear draws
    nothing at all.  **Wiring the call without the state would have produced an
    empty row and a green suite**, because the gate that would have caught it
    was masking those very cells as a declared gap.
    (a) Before wiring a routine, take a READ-WATCH over it and diff its input
    set against what `reset()` actually holds.  The code being right is half
    the job.  (b) A declared gap in a gate is a place where wiring something
    badly cannot be seen -- so NARROW THE MASK in the same increment that
    closes the gap, or the next change inherits a blind spot.

112. **SEEDING STATE CORRECTLY CAN BREAK GATES THAT WERE PASSING BY ACCIDENT,
    AND THAT IS THE ENGINE GETTING MORE FAITHFUL** (Bubble Bobble, M7.10,
    2026-09-24).  Setting `($FD87)` for the lives panel also fed `$9840`'s
    `BIT 7,(IX+7)`, the milestone warp's in-play test.  While the byte was 0 the
    port COULD NOT WARP, so eight sequence gates walked rounds 1..23 in order
    and passed; with it seeded the port warps 19 -> 81, correctly, and they went
    red.  The gates were comparing two different journeys and had never said so:
    the oracle's chain suppresses the warp deliberately (F0's recipe) and the
    port had been unable to warp for an unrelated reason.
    When a faithfulness fix turns gates red, check whether they were passing
    because of the very defect you removed -- and then drive BOTH SIDES under
    the oracle's conditions, rather than relaxing the assertion.

113. **A DUPLICATE CONSTANT IS A MUTATION THAT CANNOT FAIL** (Bubble Bobble,
    M7.10, 2026-09-24).  I added a 32-byte `BB_LIVES_ICON` and seeded it at
    `$85A1` -- which `BB_HUDF_ICON` had already seeded, from an earlier HUD
    increment.  The battery then reported the new mutation "the life icon glyph
    is not seeded" as a SURVIVOR, and it was right to: the line it removed was
    dead, the other seed still ran, and nothing changed.  A survivor pointing at
    code that does nothing is the cheapest possible signal that the code should
    not exist.  The real seeding IS tested -- zeroing `$85A1` breaks 23 of 23
    sequence rows -- so the coverage was there all along.
    Grep for the ADDRESS, not the constant name, before adding a seed.

114. **TWO SPELLINGS OF ONE RULE ARE A DUPLICATE WAITING TO DRIFT APART, AND THE
    UNCALLED-METHOD CENSUS IS WHERE THEY SURFACE** (Bubble Bobble, M7.11,
    2026-09-24).  `driftCode()`/`driftDelta()` and the `$B836` bubble move both
    computed the per-round wind -- the helper by name, the move inline -- and
    they were proved equivalent over 3,072 sampled cells.  Equivalent today;
    two things to keep in step for ever.  The helper had no engine caller at
    all, which is why it showed up in the census (TRAPS #103's gate) as a DEAD
    DUPLICATE rather than as a bug.
    The fix is not to delete the helper -- the gates drive it by name -- but to
    make the ENGINE call it, so there is one spelling and the existing coverage
    now covers the live path.  The census then shrinks by two, which is the
    signal that the collapse actually happened.
    A census of unreached methods is not only a list of unfinished work; it is
    a list of places where the same rule may already be written twice.

115. **AN "ISOLATED" TEST WORLD CAN BE A WORLD THE MACHINE IS NEVER IN, AND THE
    ROUTINE YOU WIRE NEXT IS WHAT TELLS YOU** (Bubble Bobble, M7.12,
    2026-09-24).  Six bubble gates zeroed `($FD87)` "to isolate the
    bubble-bubble path", removing the player so it could not touch the bubbles.
    Their fixtures were all captured on round1_48, where the machine has `$E1`
    -- the player is ACTIVE and simply sits somewhere else.  The zeroing was
    belt-and-braces that happened to change nothing.
    Then `$8E2A` was wired, and its test is THE SAME BIT: on this machine "no
    active player" and "game over" are one condition.  Every one of those
    isolated worlds armed the game-over timer, `$8D0D` short-circuited the rest
    of the pass, and six long-standing gates went red at once.
    (a) A test world that DEVIATES from the capture it is compared against is a
    liability even while it passes; prefer to isolate by POSITION or by the
    data under test, not by clearing a flag whose other meanings you have not
    enumerated.  (b) When wiring a routine turns old gates red, check whether
    those gates were relying on the world being impossible before you touch the
    routine.  (c) The fix here made the gates STRICTER, not looser: they now use
    the machine's own world.

116. **A FIXTURE NOBODY READS IS A FIXTURE NOBODY CHECKS -- AND ONE OF THEM WAS
    WRONG** (Bubble Bobble, M7.13, 2026-09-24).  Two structural rows already
    guarded the ship/test asset split: everything the ENGINE source reads must
    be shipped, and nothing it never reads may be.  Neither asked the next
    question.  A third row -- *is every test-only asset read by any check at
    all?* -- found exactly one of sixty-nine that was not:
    `build/livespanel_fixture.json`, captured by M7.10, registered in
    `port.json`, loaded from disk by the rig every single run, and compared
    against nothing.  M7.10 had written its gates from the numbers the tool
    PRINTED, which is not the same as reading the file it wrote.
    AND THE FILE WAS WRONG.  Its read-watch subtracted the colour shadow with
    `not (SHADOW <= a)` and `SHADOW = 0xE000` -- and $E000 is where the game's
    working RAM begins, so the filter swallowed $FD80..$FFFF whole.  The four
    addresses the increment EXISTS for -- ($FD87), ($FD91), ($FDDC), ($FDE6),
    the ones `reset()` had left at zero -- were missing from its own "measured
    input set", and the note in `port.json` advertised that set as complete.
    (a) An exclusion written as a half-open comparison with ONE end is a
    half-open exclusion: the shadow $806C writes is a WINDOW, $E000..$FB00, and
    naming both ends would have been the same amount of typing.  (b) For every
    artefact a tool produces, ask what READS it -- and make that a check, not a
    habit.  (c) The third direction of a structural gate is usually the one
    that finds something; two directions feel complete and are not.

117. **"THE NINE WIRED ROUTINES" WHILE DRIVING EIGHT** (Bubble Bobble, M7.13,
    2026-09-24).  The chain-ORDER gate installs a recorder on each wired method
    and asserts the sequence mainLoop() produces.  Its message said "the NINE
    wired routines record their own entry" and it listed -- and installed --
    eight.  M7.12 wired `gameOverTimer` and never added its recorder, so the
    order check could not have seen `$8E2A` wired at the FRONT of the chain
    instead of the end.  The fix is not the message: it is the tenth recorder.
    A gate whose text counts higher than its body is a gate that is a
    measurement of nothing in the gap, and the gap is exactly where the newest
    increment lives.

118. **THE RUNNER APPLIED NO MUTATION AND CALLED ALL 29 OF THEM SURVIVORS**
    (Bubble Bobble, M7.13, 2026-09-24).  Adding a path resolver to the parallel
    battery -- so that a case naming `bb.test.js` would land in `test/` rather
    than `web/` -- collapsed the two-line write into one and, doing so, moved it
    one indent level in, leaving it INSIDE the dead-anchor branch, after
    `continue`.  Every case then built and tested the PRISTINE tree, passed, and
    was recorded as SURVIVED.
    THE TELL WAS THE SHAPE, not any one row: 29 survivors out of 29.  No real
    increment has ever had a survival rate anywhere near that, and the right
    reading of "everything survived" is *suspect the runner*, not *the suite is
    weak*.  This is the same family as #107 (a hang reported as a kill) and #110
    (a regex that matched nothing reporting "0 referenced" and passing): a run
    that states a verdict for a measurement that did not happen.
    (a) The runner now RE-READS the file after writing and, if the text did not
    change, records NOT-APPLIED -- its own verdict, and one that fails the run.
    (b) It also says so out loud when every case survives.  (c) An edit that
    re-indents a line inside a loop with a `continue` in it deserves the diff
    read back, because Python will not complain.

119. **BOTH BATTERY RUNNERS HARDCODED `web/<fn>` FOR 1,502 CASES** (Bubble
    Bobble, M7.13, 2026-09-24).  The case list has named a FILE since it was
    written -- `('game.js', label, old, new)` -- and both runners resolved it as
    `'web/' + fn`.  Nothing noticed, because all 1,502 cases were `web/game.js`.
    The first case that mutates `test/bb.test.js` crashed with
    FileNotFoundError.
    That is worth more than a path fix: MUTATING THE SUITE IS HOW A GATE IS
    SHOWN TO BE ABLE TO FAIL, and the battery could not do it at all.  The first
    two suite mutations it ran found a row that could be neutered to `a => false`
    and still pass, because its answer is "nothing is wrong" and an empty list
    is a pass.  Such a row needs a CONTROL -- the same predicate run over a list
    with a phantom entry, which must come back naming exactly the phantom.

120. **`DJNZ` WITH B = 7 OVER AN EIGHT-ENTRY TABLE, AND THE EIGHTH ENTRY IS
    WRITTEN BY THE SAME ROUTINE** (Bubble Bobble, M7.14, 2026-09-24).  $900B's
    second gate ORs the enemy wake-up delays and fires the reveal when they are
    all zero.  The table is eight bytes, $A891..$A898, and its own first gate
    writes all EIGHT of them.  The OR loop reads SEVEN: `LD B,7` at $9026, so
    $A898 is never in it.
    Transcribing "all the delays" would have been wrong in exactly one world --
    seven zero and the eighth not -- and that world is REACHABLE, because the
    heart arm three instructions earlier is what puts a non-zero value in the
    eighth.  The proof is not the listing: one byte poked non-zero at a time
    across all eight, and only index 7 still lets the reveal fire.
    A loop counter that does not match the table it walks is a MEASUREMENT, not
    a typo, until the machine says otherwise -- and the cheap way to ask is to
    sweep the table one entry at a time rather than to read the DJNZ twice.

121. **A `JP` INTO A ROUTINE IS A CALL OF THE WHOLE ROUTINE, AND A STUB NAMED
    AFTER HALF OF IT HIDES THAT** (Bubble Bobble, M7.14, 2026-09-24).  $8C28 is
    `CALL $8216` then an attribute derive then `CALL $957E` then `CALL $806C`.
    The port had the derive, under the name `attrRestore()`, and the flood
    effect's `$A0BE JP z,$8C28` called it -- so a jump to a four-part routine
    ran one part, and the name made that look deliberate.  The comment even
    said "the $8216 half is still a stub", which is true and was read for three
    increments as "this is finished".
    The call ORDER, incidentally, is not readable either: $8216 does not RET, it
    ends `JP $7F80`, so a PC watch over the real routine reports FOUR callees
    where the source of $8C28 shows three.

122. **A TABLE OF ZEROS IS A TABLE THAT WORKS** (Bubble Bobble, M7.15,
    2026-09-24).  $8FA5's pitch is `|($B57D + phase) - $10| + 1`, and the port
    had thirty-two zeros at $B57D -- so every jump phase gave |0 - $10| + 1 =
    17, one flat note, and the routine ran, returned and produced a perfectly
    plausible square wave.  Nothing was undefined, nothing threw, and a gate
    that compared "the engine makes four edges" would have passed.
    The tell was not the sound: it was that EVERY animation byte gave the SAME
    answer.  A lookup whose output does not vary with its index is not a
    lookup, and the cheap check is to sweep the index and count the distinct
    results BEFORE comparing any of them to the machine.
    The table also agrees with its neighbour $B59D in 30 of 32 bytes, so a gate
    that seeded the wrong one and compared casually would also have passed; the
    two differing indices are named in the gate.

123. **"24 AND AN 8-BYTE SPILL" WAS A GUESS THAT HAD BEEN IN A COMMENT FOR
    THREE INCREMENTS** (Bubble Bobble, M7.15, 2026-09-24).  The arc-table
    comment described $B57D as "(24) and its spill $B595 (8)".  Driving the
    machine says otherwise: the jump phase runs 1..32, `$AD6E CP $21` is what
    turns 33 into $FF, and phase 32 reads $B59D -- the first byte of the NEXT
    table.  There is no spill; there is a 32-byte table whose last index is one
    off the end and lands on a byte that happens to be in range.
    A structural claim in a comment ("this table is 24 long") is a measurement
    like any other and wants the same treatment: drive the index to its extreme
    and see where it reads.

124. **A CLAMP THAT NEVER TRIPS IS NOT A TESTED CLAMP** (Bubble Bobble, M7.15,
    2026-09-24).  The sound log must stay sorted, so `beepEdge` pins a
    backwards push to the previous time and counts it.  The gate drove it with
    a NEGATIVE frame offset -- which clamps every edge to 0, so they all land on
    the same time and the ORDER guard never fires.  The battery found it: the
    guard could be deleted and the suite stayed green.
    Two different guards on the same line need two different worlds.  The one
    that exercises the order guard is an edge already in the log LATE in the
    frame and a tone emitted EARLY in it.

125. **AN ERASE THAT RESTORES FROM A SHADOW WRITES NOTHING IN A CLEAN WORLD**
    (Bubble Bobble, M7.16, 2026-09-24).  The giant's erase copies the backing
    store back over the display.  In a freshly reset port the display ALREADY
    equals the shadow, so a before/after diff of the screen finds zero changed
    cells -- and a gate that compares "the addresses the erase touched" gets an
    empty list, which compares equal to nothing and passes.
    POISON FIRST.  The same shape as TRAPS #100 (a tautological assertion) and
    #44 (a diff that cannot see an idempotent write): when a routine's job is to
    make memory match something, the test world has to start NOT matching.

126. **A MUTATION THAT REORDERS TWO LINES MAY REORDER NOTHING** (Bubble Bobble,
    M7.16, 2026-09-24).  A case meant to move the presence test AFTER the frame
    store moved it only past the `const clock = ...` line above the store, which
    changes nothing -- and the battery duly reported it as a survivor, which
    read as "the gate is weak" rather than "the case is wrong".
    A survivor is a claim about a PAIR (mutation, suite).  Before strengthening
    the suite, read the mutation and ask what it actually does; two of the six
    survivors in this increment were the case's fault, and one of those two was
    a genuine PROVABLE EQUIVALENT -- an idempotent store, visible in the
    machine's write log and not in the port's memory, which is withdrawn with
    its reason rather than chased.

127. **A GATE THAT DRIVES THE HELPER INSTEAD OF THE ROUTINE TESTS THE TEST'S
    ARITHMETIC** (Bubble Bobble, M7.17, 2026-09-24).  $925A's box test was
    gated by computing B, C, D and E in the test and calling the engine's
    `boxAxis` with them.  It matched the machine's 65,536-position sweep
    exactly -- and FIVE mutations survived it: the `+2`, the `+14`, their eight
    bits, which axis is asked first, and the sixteen-bit form.  None of those
    live in `boxAxis`; they live in the CALLER, and the gate had replaced the
    caller with itself.
    Fourteen of forty-one M7.17 cases survived the first pass for this one
    reason.  When a routine computes its own inputs, the gate must place the
    WORLD and let the routine compute them -- the helper's signature is exactly
    the boundary a test must not step over.

128. **THREE ANCHORS WERE NOT ENOUGH FOR AN EIGHT-BIT WRAP** (Bubble Bobble,
    M7.17, 2026-09-24).  TRAPS #49 says sweep at more than one anchor.  Three
    were swept -- (100,100), (200,150), (250,250) -- and a mutation replacing
    `(v + 15) & 0xFF` with `v + 15` still survived.  `ADD A,15` can only wrap
    for an entity at 241 or above, and the `CP B` above it only lets such an
    entity through when `player + 14` is bigger still: the two arithmetics
    agree everywhere except a player in [228, 241], and none of the three
    anchors was in it.
    An anchor set for a wrap is not "a few spread out": it is derived from
    WHERE THE WRAP CAN HAPPEN.  The fourth anchor, (235,100), accepts 513 and
    is cut off at x = 240 exactly where the wrap bites.

129. **A FLAG CLEAR ON THE COMMON PATH IS INVISIBLE UNTIL THE UNCOMMON PATH IS
    DRIVEN** (Bubble Bobble, M7.17, 2026-09-24).  $925A opens with `XOR A`,
    which clears the carry before the first scan.  Deleting the port's
    equivalent survived, because with the player ALIVE the scan runs on to
    $9308's own `OR A` and clears the flag anyway.  Only a DYING player -- whose
    scan RETs at $92BB without touching the carry -- lets a stale flag reach
    $9269's `CALL c,$927D`.
    Two instructions that clear the same flag need two worlds: one where only
    the first runs.  The same shape as #124's clamp-versus-order guard, one
    increment later.

130. **COLLAPSING TWO SPELLINGS INTO ONE KILLS THE MUTATIONS THAT ANCHORED ON
    THE COPY** (Bubble Bobble, M7.17, 2026-09-24).  $927D had THREE spellings in
    the port -- an uncalled `playerHit`, a second half inside `bossKillPlayer`,
    and the `$9298` arm that was in neither.  Collapsing them (the right move,
    and what M7.11 did for the wind read) left six of B5's mutation cases with
    dead anchors, because every one of them had anchored on the copy.
    Their BEHAVIOUR is unchanged, so they are RE-ANCHORED on the single body,
    not withdrawn -- except one, which became the same (old, new) pair as an
    M7.17 case on the same line and is MERGED with a note saying so.  A dead
    anchor after a deliberate collapse is bookkeeping; a withdrawn case is a
    lost measurement.
    And one of the re-anchored six then SURVIVED: swapping the order of two
    refusals that both write nothing is invisible unless BOTH their bits are
    set, and no row drove that.  The machine cannot tell them apart either --
    nothing in RAM records which RET was taken -- so the port's own label
    carries the claim, and a row with both bits set is what pins it.

131. **A STORE OF THE VALUE ALREADY THERE IS A STORE YOU CAN DELETE** (Bubble
    Bobble, M7.18, 2026-09-24).  `$931E XOR A / LD ($93C4),A` puts a NOP in the
    routine's own code so the enemy sweep corpses what it finds.  Deleting the
    port's equivalent SURVIVED -- because `reset()` already leaves $00 at
    $93C4, so the write was setting the byte to what it held.  The same shape
    as M7.16's idempotent-store equivalent, except this one is NOT an
    equivalent: the byte is live state that the routine's own second write
    ($C9) changes, so between passes it really does need putting back.
    A gate for a store must POISON THE TARGET first, and the poison has to be a
    value the routine can actually meet -- here the $C9 the same routine writes
    forty instructions later.  Three of this increment's five survivors were
    this: $93C4's NOP, and the direction byte the water carry zeroes (already
    zero in the test world).

132. **THE SECOND PLAYER IS HALF THE ROUTINE AND NONE OF THE GATE** (Bubble
    Bobble, M7.18, 2026-09-24).  $931A probes P1, and if P1 is swept up the
    routine RETURNS; otherwise it probes P2 at ITS OWN +7.  Three mutations
    survived the first gate pass -- "P2 is never probed", "P2 is probed at P1's
    +7", and "P1 falls through to P2 after being carried" -- because every
    world the gates built had P2 out of play.
    The same hole M7.17 had one increment earlier (TRAPS #127's P2 half), which
    means naming it once was not enough.  A routine that names two structs
    needs a world with both of them live, and a routine whose two halves are
    mutually exclusive needs the PAIR driven: both players in the same hazard,
    two passes, and the second pass is where the exclusivity shows.

133. **A COUNT IS NOT A FOOTPRINT** (Bubble Bobble, M7.19, 2026-09-24).  The
    banner's erase was gated by COUNTING its calls -- 22 erases, 220 attribute
    restores, 24 attribute runs -- and every count matched the machine.  SEVEN
    mutations survived it: seven rows instead of eight, the display read instead
    of the shadow, the `+11` on the low byte dropped, the erase aimed at the
    position the banner is moving TO rather than the one it is leaving, and the
    recolour's ink changed.  None of those changes a count.
    The fix is three measurements, not one: the ADDRESSES (an ordered list and a
    span), the VALUES (by count per value, because the SET of values is the same
    whichever way round the recolour and the flash are), and a POISONED source
    (the display filled with $5A so "copied from the shadow" is distinguishable
    from "copied from itself").  This is TRAPS #127 one increment on, in its
    other form: there the gate replaced the routine's arithmetic, here it
    replaced the routine's output with a tally of it.

134. **`|` FORGIVES A SIXTEEN-BIT LOW BYTE WHEN THE PAGE ALREADY HAS THAT BIT**
    (Bubble Bobble, M7.19, 2026-09-24).  TRAPS #75 said this about the boss
    erase's attribute walk and it happened again: `ram[(hl & 0xFF00) | l]` with
    `l` allowed past 255 lands on the SAME cell, because every attribute page
    ($58, $59, $5A) already has bit 8 set.  A mutation making `INC L` sixteen
    bits survived a whole battery.
    Written as `+` the mask becomes load-bearing and the mutation dies.  The
    rule: when an address is assembled from a page and an offset, use `+` and
    let the mask carry the eight-bit claim -- an OR hides exactly the bug the
    mask exists to prevent.

135. **A FIXTURE AND AN ENGINE CAN DESCRIBE DIFFERENT MACHINES AND BOTH BE
    RIGHT** (Bubble Bobble, M7.19, 2026-09-24).  $9077 is the operand of the
    flash's `LD A,6` and it ALTERNATES, so it is live state with no
    initialiser: the tape holds 6 and round1_48 holds 3.  reset() seeds the tape
    value, which is what a cold machine has; the oracle captured the other.  The
    flash therefore comes out 3/6/3 in the port and 6/3/6 in the fixture, and a
    gate comparing them directly is comparing two different moments.
    Three of the five censused states differ from the tape in this byte, and a
    fourth (hurryup) has the temper latch already set.  The gate now asserts
    reset()'s value against the TAPE and the behaviour against the FIXTURE'S
    OWN operand -- and the same rule caught ($745C), the threshold, which reads
    1000 on the tape and 1500 in play.

136. **THE FIRST DRAFT OF A SUBSTITUTE GLYPH WAS THE ROM'S** (Bubble Bobble,
    M7.20, 2026-09-24).  `tools/make_hurry.py` draws ten cells to replace the
    Spectrum ROM character set the HURRY UP banner reads, and asserts every one
    that carries ink differs from the cell it replaces.  The '!' I drew --
    `00 10 10 10 10 00 10 00` -- was byte for byte the ROM's, because there is
    only one obvious way to draw an exclamation mark on an 8x8 grid.
    The assert is what said so, which is the whole reason `make_letters.py`
    established it.  A substitute font needs the guard in BOTH directions,
    too: a blank in the ROM must stay blank here, or the assert can be
    satisfied by drawing something visible in a gap.  Two of the ten ARE
    spaces, eight zero bytes in any font, and that is named in the tool rather
    than special-cased around.

137. **TWO IDENTICAL-LOOKING MUTATIONS, ONE LOAD-BEARING AND ONE NOT** (Bubble
    Bobble, M7.20, 2026-09-24).  `ram[(hl & 0xFF00) | l]` in $995A hid a
    sixteen-bit L, because every attribute page already carries bit 8 (TRAPS
    #134).  `ram[((h << 8) | l) & 0xFFFF]` in $802E's blit does NOT, because
    both operands are masked one line earlier and the address is finished with
    `& 0xFFFF` -- which keeps exactly the bits an inner mask would have kept.
    The same is true of `INC H`'s own mask there.
    Both are written the honest way and both mutations are WITHDRAWN as provable
    equivalents WITH THEIR REASONS, because the next reader will see two lines
    that look the same and need to know why only one has a live case behind it.

138. **A 1,100-TICK TRAJECTORY IS A LONG TEST AND STILL A NARROW ONE** (Bubble
    Bobble, M7.21, 2026-09-24).  $917C is a state machine in seven operands, so
    the fixture is its PATH -- 1,100 ticks, every operand, Boris's ten bytes.
    The engine walked it exactly, and NINE mutations survived.
    The path sees two move starts, both on the Y axis, both ARRIVING rather than
    running out of steps, with the step length only ever 2 or 4 and the target
    exactly level with Boris.  So: the X arm's sprite write, the counter-ending
    move, the `NEG` that makes the arrival test a distance, the carry reset on
    the step length, the sixteen-bit wrap in the wait, and reset()'s own seeding
    all had no world at all.
    LENGTH IS NOT COVERAGE.  A trajectory proves the port walks the same path;
    it says nothing about the branches the path did not take, and each of those
    needs a world built for it.

139. **A PROBE THAT LEAKS TEN BYTES OF STACK A CALL LOOKS LIKE A GAME BUG**
    (Bubble Bobble, M7.21, 2026-09-24).  The tick bracket pushes six sentinels
    and the routine pops one, so a hundred and twenty ticks walked SP down
    through whatever was under it and the PC came out at $FE88, inside the RNG,
    which $917C never calls.  Before that, two other probe artefacts wore the
    same disguise: with interrupts on, the real ISR reached the round advance
    and left the bracket at $9781, and $A447 -- erasing at a cached position
    that is garbage on a poked world -- wrote over $9250 ITSELF, so Boris's
    record came back `FE 02 FE 04 ...` after 128 ticks.
    Three "the game does something strange after N calls" reports, all three the
    probe's.  When a driven measurement degrades WITH ITERATION COUNT rather than
    with the input, suspect the scaffold: the machine has no idea how many times
    you have called it.

140. **A RESET WORLD ALREADY HELD THE VALUE THE ROUTINE WRITES** (Bubble Bobble,
    M7.22, 2026-09-24).  $7F00 sets (IY+3) := 2 on the slot it fills, and the
    port's bubble pool already reads 2 there after `reset()` -- so deleting the
    write changed nothing and the mutation survived a row that compared all ten
    bytes of the record.
    Poison the whole record first, and then assert BOTH halves: the five bytes
    the routine writes must match the machine, and the five it does not must
    still be the poison.  That second half is what turns "it wrote the right
    values" into "it wrote exactly these and nothing else".  Third time this
    session (TRAPS #131, #125): a store is only tested against a target that
    did not already agree.

141. **A TIDY WORLD HIDES THE LAST SLOT AND THE EXACT THRESHOLD** (Bubble
    Bobble, M7.22, 2026-09-24).  $7EA7 counts twelve pool slots whose +9 is TWO
    OR MORE.  The gate drove the count 0..6 by filling slots from the FRONT with
    the value 3 -- so slot 11 was never the one that mattered and `>= 1` was
    never distinguishable from `>= 2`.  Both mutations lived.
    A loop bound wants its LAST iteration to be the load-bearing one, and a
    comparison wants a value ON the boundary.  One live element in slot 11, and
    one slot holding exactly 1, killed both.

142. **SOME WRITES ARE UNOBSERVABLE FROM INSIDE THE PORT BECAUSE THE OBSERVER IS
    THE INTERRUPT** (Bubble Bobble, M7.22, 2026-09-24).  $7EC7 clears the even
    ISR gate and $7F05 puts it back, bracketing the slot write so a mid-write
    interrupt cannot see a half-built element.  In the port nothing runs between
    those two lines -- the ISR is called at frame boundaries -- so deleting the
    clear changes no byte any check can read, and the mutation survived.
    The claim is real and the port keeps it, so the row is made about the
    SOURCE: both writes present, in order, inside the routine.  That is the
    honest shape for a guard whose only observer is a thing the port models
    elsewhere -- neither a survivor to shrug at nor a behaviour to invent.

143. **A GATE THAT CAN NEVER BITE AT THE VALUE YOU DRIVE IT AT** (Bubble Bobble,
    M7.23, 2026-09-24).  $9B31 is `LD A,($AA57) / SUB 3 / CP C / RET c`, the
    spawner's check that the drawn enemy index exists.  The oracle drove it at
    index 0 with counts 12 and 3 and both passed, so the phase was written down
    as "($AA57) is too small for the index -> still spawns" and proved nothing.
    At index 0 the comparison is (count - 3) against 0, and `SUB 3` is EIGHT-BIT:
    a count of 2 wraps to $FF and passes harder than 12 does.  The gate can only
    refuse high in the roster.  Re-driven at index 6 -- the largest a draw of 7
    can make -- it refuses 6, 7, 8 and 3, and passes 9, 10, 12, 2 and 0.  The
    wrap is a real 1987 behaviour and the port now reproduces it.
    Before sweeping a comparison, work out the input at which its two sides can
    actually straddle.  A sweep taken where every value lands on the same side
    of the branch is a table of one answer.

144. **A SWEEP THAT FINDS NOTHING MUST SAY SO OUT LOUD** (Bubble Bobble, M7.23,
    2026-09-24).  $5B0A is reached by FALL-THROUGH from $5B00's handler, and to
    see it filled at all the first PRNG draw must spawn nothing and the second
    must spawn something -- because a successful first draw MARKS the enemy and
    the second draw then finds nobody.  The phase swept 4,096 seeds for the pair
    (0, 1), found none, and silently wrote a fixture whose "second slot" rows
    never once filled the second slot.  Two of the three arms passed on a port
    with one slot.
    The fix was both halves: print the census of what WAS reachable (`(g0) 4096
    seeds swept ... second draws reachable: 2 3 6 7`), take any of them instead
    of insisting on one, and `assert` in the tool that at least one arm really
    filled $5B0A.  A sweep with no hit is not a null result; it is a sweep that
    has not run.

145. **THE MUTATION THAT RE-TESTS A CHECK THREE LINES ABOVE IT** (Bubble Bobble,
    M7.23, 2026-09-24).  One M7.23 case meant to stop the generator advancing on
    a refused draw.  What it actually inserted was a copy of $9B1E's
    `BIT 7,(IX+7)` -- a test that had already passed on every path that reaches
    the draw.  It changed no behaviour, survived, and sat in the survivor list
    looking like a hole in the gates.
    A survivor is a claim about the SUITE; a mutation that mutates nothing is a
    claim about nothing.  Read every survivor's diff before writing the gate it
    seems to ask for, or you will write a check for a bug that cannot exist.
    (The real case -- snapshot $FE86/$FE87 and restore them when the draw is
    refused -- dies on the row that says the generator advances twice.)

146. **A SNAPSHOT TAKEN BEFORE THE PROBE ARMS REPORTS THE PROBE'S OWN STACK**
    (Bubble Bobble, M7.24, 2026-09-24).  `tools/extenddone.py`'s first run said
    `$948F` writes 128 bytes.  It writes 112.  The sixteen extra were the
    harness's own sentinel return addresses, pushed by `arm()` AFTER the "before"
    snapshot was taken -- and they were obvious in hindsight, because the diff
    read `FE 02 FE 04 FE 06 FE 08`, which is the sentinel list counting up.
    Snapshot AFTER arming, and drop only a named window below the armed SP for
    the routine's own CALL/RET traffic.  A probe's scaffolding is not a finding.

147. **A FILTER WIDE ENOUGH TO HIDE THE MEASUREMENT IS WORSE THAN THE ARTEFACT**
    (Bubble Bobble, M7.24, 2026-09-24).  The fix for #146 was `if (ad < floor):
    continue`, with `floor` the armed SP.  The stack on this state sits at
    `$96CB` -- so that one line silently dropped the entire display file, every
    game variable below `$96CB`, and `$7E0E`, which is the ONE byte `$7E04`
    writes and the whole point of that branch.  The count went down and looked
    tidier.
    Exclude a NAMED WINDOW, never a half-line.  And report what was dropped
    beside what was kept, so the next reader can see the size of the hole.

148. **A GATE THAT MEASURES THE STEP BEFORE THE ONE IT NAMES** (Bubble Bobble,
    M7.24, 2026-09-24).  The round-start row poisoned the twelve EXTEND letter
    cells with `$5A`, ran `roundStart()`, and asserted they were no longer
    poison -- claiming that `$986F`'s `CALL $957E` had drawn them.  But
    `roundBuild()` repaints the whole playfield earlier in the same sequence, so
    "no longer `$5A`" was true whether or not `$957E` ran at all.  The battery
    made `$986F` a no-op and the row lived.
    When a routine runs late in a long sequence, poisoning at the top measures
    whatever runs FIRST.  The fix is a DIFFERENCE: the same sequence with the
    masks at `$00` against the same sequence with them at `$3F`, and the twelve
    cells must disagree.

149. **SIX THINGS LOST TO ESCAPE HANDLING** (Bubble Bobble, M7.24, 2026-09-24).
    The running tally: four heredocs that ate `\n` and produced
    `SyntaxError: unterminated string literal`; a check row whose regex was
    built by concatenation and lost its `\b`; and now a row whose regex was
    written `/this\\.elemRedraw\\(\\)/` -- matching a literal backslash,
    matching nothing, and failing a check EVERY OTHER PART OF WHICH PASSED.
    The same run left `\u2019` sitting raw in sixty-two labels.
    The standing rule, now earned six times: build source with the Write/Edit
    tools or `repr()`, never a shell heredoc; and prefer a plain-string
    `split(...).length - 1` to a regex when all you are doing is counting
    occurrences.

150. **TWO STATES IN THE ROSTER ARE HUNG 128K CAPTURES** (Bubble Bobble, M7.24,
    2026-09-24).  Reconnaissance over all 57 `build/*.pkl` found `play1p.pkl`
    (PC `$8E07`) and `play2p.pkl` (PC `$8E08`) sitting INSIDE `$8E05`'s delay
    loop with its operand `$8E06` at `$00` -- 300,000 steps from each visits
    only `{$8E05, $8E07, $8E08}`.  They are 48K images captured before `$9690`
    patched the branch, and they never leave.  `iball.pkl` is not a state of
    this build at all: 4,036 bytes differ from `image_tape.bin` in `$8000-$8FFF`
    alone, against 55 for `round1_48.pkl`.
    Any sweep that says "measured on all states" must say WHICH, and the 48K
    branch check (`$8DC4 == $C9`, TRAPS #28/#36) is what separates them.  Note
    the three patch bytes are INTERLOCKED: `$9690` writes `$C9` to `$8DC4`,
    `$8E05` and `$8E0A` together, and patching `$8DC4` while leaving `$8E05`
    alive hangs the machine, because `$8E05`'s `JR nz` returns to its own
    `LD C,n` and only `$8DC4`'s tail refreshes the operand.

151. **A PROBE THAT CANNOT AIM IS NOT A MEASUREMENT** (Bubble Bobble, M7.25,
    2026-09-24).  `tools/extcomp.py`'s first run reported that PLAYER TWO CANNOT
    COMPLETE EXTEND -- 256 values swept, none accepted.  The routine was fine.
    The tool set IX by writing registers 13 and 14, and in this simulator IXh
    and IXl are 8 and 9; 13 and 14 are SP-adjacent and I.  IX never moved off
    whatever the state happened to hold, which was P1's address, so every P2
    sweep was a P1 sweep with P2's letters poked.
    A sweep that finds a whole arm dead is reporting on the probe until proved
    otherwise.  Read the harness's own register table rather than guessing a
    conventional layout.

152. **A POISON WIDER THAN THE ROUTINE MEASURES ITS NEIGHBOURS** (Bubble Bobble,
    M7.25, 2026-09-24).  The wipe phase filled `$DF00..$FFFF` with `$5A` and
    then reported `$94EA`'s LDIR as "6,915 bytes, `$E000..$FEC5`, 963 gaps
    inside".  The LDIR does exactly 6,912 contiguous bytes; the extra three were
    `($FEC4)` and `($FEC5)`, which `$94CD`/`$94D0` zero TWENTY-NINE BYTES EARLIER
    in the same routine, and the 963 "gaps" were simply the poison between the
    two regions.
    Poison as wide as the question and no wider, and report a CONTIGUOUS RUN
    rather than a set -- a set cannot tell "it cleared this range" from "it
    cleared this range and something else cleared two more bytes".

153. **ATTRIBUTE THE WRITES BY PC BEFORE EXPLAINING THEM** (Bubble Bobble,
    M7.25, 2026-09-24).  The item-shower phase counted 283 changes from a loop
    that makes 320 writes, and the obvious story was a second writer -- `$8689`
    ageing the records it had just been handed.  Splitting the changes by the PC
    that made them killed that story in one line: `$951C` 123 and `$9527` 160,
    both inside the loop, and `$8689` writes NONE of these bytes.  The 37
    "missing" are stores whose value already agreed, because byte0 carries a
    two-bit PRNG draw that repeats over ten passes.
    The attribution costs one variable and it is the difference between a
    measurement and a plausible story.

154. **A CENSUS IS ONLY COMPARABLE TO ONE TAKEN OVER THE SAME WINDOW** (Bubble
    Bobble, M7.25, 2026-09-24).  The oracle's call census stops at `$9553`,
    because everything past it is two multi-million-T delays.  The gate compared
    the PORT's whole run against it and failed on `$806C`: two on the machine,
    three in the port.  Both are right.  `$955B` is past the abort line.
    A window is part of a measurement.  Either compare like with like, or
    capture the full-run figure as well and say which is which -- and when a
    count disagrees by exactly the number of calls past the boundary, suspect
    the boundary before the port.

155. **"NOT IDENTICAL" IS NOT "A DIFFERENT FACE"** (Bubble Bobble, M7.26,
    2026-09-25).  Every substitute font in this port is policed by an assert that
    the glyph is not byte-for-byte the ROM's cell.  The first drafts of the new
    T and F passed it while differing in ONE and TWO bytes of eight -- a T whose
    only change was a narrower crossbar, and an F whose only change was a
    narrower top bar.  They are the ROM's letters with a haircut.
    The assert is a MINIMUM now: an inked glyph must differ in at least three of
    its eight bytes, and the per-glyph count is printed as evidence.  A rule that
    a lazy draft can satisfy is a rule that will be satisfied lazily.

156. **THE OUTER MASK CAN ABSORB THE INNER ONE** (Bubble Bobble, M7.26,
    2026-09-25).  Two mutations made `INC H` sixteen-bit instead of eight in the
    banner blits, and both survived.  They are provable equivalents: the address
    is built as `((h << 8) + l) & $FFFF`, h rises by at most seven inside one
    glyph, so it can never reach $200 and the outer truncation does the inner
    mask's job.  Verified rather than argued -- the two spellings were run side
    by side over all 256 start pages times four columns, and not one world
    differs.  The same reasoning retires `(h << 8) | l` versus `+ l` HERE while
    leaving TRAPS #134 intact THERE, because #134 is about a left operand whose
    low byte is not zero.
    When a mutation to an arithmetic width survives, look for a wider mask
    downstream before writing a gate for it -- and check by running both, not by
    reasoning about both.

157. **A GATE NAMED FOR A WRAP THAT DRIVES NO WRAP** (Bubble Bobble, M7.26,
    2026-09-25).  The row for $803F's eight-bit `INC L` started a string at
    column 30 and reported "columns 30, 31, 0, 1 -- WRAPPED inside the third".
    From $487E the low byte runs $7E $7F $80 $81 and never carries; the "column
    0" is the ROW field of the display address changing, which every walk does.
    Three separate mutations to the three adds lived behind that sentence.
    Each of $803F's `INC L`, $8054's `INC H` and $805D's `ADD HL,BC` is now
    driven from an address where THAT add is on its boundary -- $48FE, $FC40 and
    $48FE respectively.  A wrap has an address; find it before claiming it.  This
    is TRAPS #143's rule for comparisons applied to arithmetic.

158. **A MUTATION CAN BE SUPERSEDED BY CONSTRUCTION, AND THAT IS THE POINT**
    (Bubble Bobble, M7.27, 2026-09-25).  Folding the two substitute fonts into
    one code-indexed table killed three mutation cases outright -- "the two R
    glyphs are different shapes", "the two SPACES are drawn with ink", and a
    duplicate `INC L` -- not because the gates got weaker but because the bugs
    stopped being expressible.  There is ONE R now and the string reaches it
    twice; there is no second space to make differ; there is one walk, so there
    is one place to break it.
    A withdrawal like this is evidence that a refactor removed a CLASS of bug,
    and it is only honest if it says which row carries the claim afterwards --
    here the pixel-neutrality row, which asserts that positions 2 and 3, 1 and 6,
    and 5 and 8 resolve to the same cell.  "Superseded by construction" is a
    reason; "it stopped applying" is not.

159. **A GATE THAT WIPES ALL 64K REMOVES THE THING UNDER TEST** (Bubble Bobble,
    M7.27, 2026-09-25).  M7.20's `INC H` row zeroes the whole world image and
    then prints the HURRY banner at $FCFB to watch the rows wrap $FF -> $00.
    That worked while the glyphs came from a JS constant and the string was
    implicit.  M7.27 moved the string into the byte image at $9A1C, where the
    machine keeps it -- so the wipe deleted the string, the printer hit a NUL
    immediately, and the row failed.
    The row was right and the wipe was too wide.  When DATA migrates into the
    world image -- which is the direction this port keeps moving -- every
    wholesale `for (a = 0; a < 0x10000) ram[a] = 0` in the suite becomes
    destructive, and the fix is to put back what the routine reads and say why.

160. **"UNREACHABLE" IS A CLAIM AND IT NEEDS ENUMERATING, NOT SAMPLING** (Bubble
    Bobble, M7.28, 2026-09-25).  A mutation removing the `AND 3` from $9904's
    attribute-page derive survived.  I drove it at $7AFA, saw the masked and
    unmasked answers agree, and was one keystroke from withdrawing it as
    unreachable.  They agree there because `OR $58` already has bits 3 and 4
    set, so the mask only changes an answer when the shifted page has BIT 2 set
    -- and enumerating all 256 start pages gives $19..$38, $59..$78, $99..$B8
    and $D9..$F8, of which $60 is ordinary RAM.  The world existed; my sample
    was in the wrong place.
    The sibling case in the same routine -- the eight-bit `INC D` -- really is
    unreachable, and the way that was established is the same enumeration, not
    the same hunch.  When withdrawing anything as "cannot happen", enumerate the
    input space; a single disagreeing sample is not evidence of a rule.

161. **A STUB THAT MODELS THE OUTCOME STOPS BEING HONEST WHEN ITS NEIGHBOUR IS
    WIRED** (Bubble Bobble, M7.28, 2026-09-25).  $9904 was a NAMED COUNTED STUB
    that RESTORED the twenty attribute cells to whatever they held before the
    round banner ran.  That was a fair model of the OUTCOME while the banner's
    glyphs were not being drawn -- the end state really was byte-identical, and
    the port reached it by a different route.  Wiring the glyphs made it wrong
    at once: a restore cannot put back eighty display bytes it never saved, and
    the real routine does not remember anything, it rebuilds from the SHADOW and
    re-derives the attributes from bit 5 of the COLOUR shadow.
    Outcome-modelling stubs are fine and should say so -- this one did -- but
    they are coupled to what is stubbed AROUND them.  When wiring X, check every
    stub whose correctness rested on X staying stubbed, and expect them to come
    as a pair.

162. **NEW CODE CAN KILL AN OLD ANCHOR WITHOUT MOVING IT** (Bubble Bobble,
    M7.28, 2026-09-25).  The battery's DEAD ANCHOR verdict has always meant "the
    increment moved the code this case pointed at".  This one meant something
    else: H11's mutation anchored on a one-line copy loop, and $9904's LDIR is
    spelled identically, so the anchor started matching TWICE and the runner
    could not place it.  Nothing H11 cares about changed at all.
    Both failures look the same in the report, and the fix is different: a moved
    anchor is RE-ANCHORED to where the code went, an ambiguous one is given the
    CONTEXT that distinguishes the two sites -- here the enclosing method.  When
    a dead anchor points at code that is still exactly where it was, count the
    matches before rewriting anything.

163. **ADDING A PARAMETER DEGRADES EVERY EXISTING CALLER SILENTLY** (Bubble
    Bobble, M7.29, 2026-09-25).  `bossBanner` gained a fourth argument -- the
    string to print -- and the two older rows that drive it kept passing three.
    JavaScript gave them `undefined`, `undefined & 0xFFFF` is 0, `ram[0]` is the
    zero the ROM window holds, and the printer stopped at once.  Both rows WENT
    ON PASSING while the thing they now covered drew nothing at all.  The suite
    was green and one of its newest paths was dead.
    The fix is a DIAGNOSTIC, not a default: `bannerPrint` throws on a
    non-integer address, the way `prngNext` throws on an unlisted site.  House
    rule 6 is usually read as being about runtime fallbacks; it applies just as
    hard to an argument that silently arrives as `undefined`.  When a method
    gains a parameter, grep every call site -- the compiler will not.

164. **A COUNT AND A TERMINATOR ARE TWO DIFFERENT BOUNDS IN ONE CALL** (Bubble
    Bobble, M7.29, 2026-09-25).  `$8E83` loads B with ELEVEN and `$8E7A` points
    IX at "WELL DONE!", which is TEN characters.  `$995A` is bounded by B and
    `$802E` is bounded by the NUL, so the attribute run is one cell WIDER than
    the text it colours -- and the eleventh cell is coloured while the eleventh
    character cell is never drawn.
    That asymmetry is invisible while the glyphs are COUNTED rather than DRAWN:
    a stub that added `n` to a glyph tally agrees with the machine on every
    number except the one that matters.  Gate the two bounds separately, and in
    one world -- `ram[$5955] === $C5 && ram[$4855] === $5A` says it in a line.

165. **I COUNTED MY OWN TABLE AND CALLED IT A CENSUS** (Bubble Bobble, M7.29,
    2026-09-25).  "$8EA7 was the last $802E call site" went into a check label,
    the SPEC, the progress log and very nearly a commit message.  It is false:
    the image holds NINE references to $802E and four are still counted rather
    than drawn -- the HUD's two rows at $7FE9/$7FEF, "GAME OVER" at $8CEE and
    "CREDIT n" at $9758.  What I had actually counted was the six strings in
    BB_BANNER_STR, which is the port's own list of what it already does.
    `python tools/grepbytes.py "2E 80"` takes ten seconds and would have said so
    at any point.  A claim about COVERAGE has to be measured against the IMAGE,
    never against the port's own table of what it has done -- that table cannot
    know what is missing from it.  The row is a census now and asserts both
    halves: the six that draw, and the four that do not.
    The same sweep found a comment on treasurePerfect that had said "$801D and
    $994F, neither of which is transliterated yet" for three increments after
    M7.26 transliterated both.

166. **TWO BATTERIES AT ONCE PRODUCE NOISE, AND THE NOISE LOOKS LIKE FINDINGS**
    (Bubble Bobble, M7.29, 2026-09-25).  I started a second full run while the
    first was still going.  `scratchpad/battery/parallel.py` gives each worker a
    FIXED directory -- `workers/w0..wN` -- so the two runs handed each other
    half-mutated trees.  The report came back with SIXTEEN survivors scattered
    across ARC, PATCH, M7.16, M7.20, M7.21 and the walker: milestones untouched
    in weeks, every one of them plausible enough to spend an hour on.  The same
    tree, run alone, gives ZERO.
    The tell was one line I nearly scrolled past: `WORKER 2 FATAL: baseline RED`.
    A worker whose baseline is red is not testing anything, and the runner
    already knows to shout when EVERY case survives (TRAPS #118) -- it did not
    know to shout when its own tree was being edited underneath it.
    The runner takes a LOCK now and refuses a second run by name and pid.  The
    working tree was never touched, which is the one promise that held.  Related:
    do not edit `web/game.js` or `test/bb.test.js` mid-run either -- I did that
    in the same session and threw away a seventeen-minute result.

167. **THE BASELINE ASKED WHETHER ANYTHING FAILED, NOT WHETHER THE SUITE PASSED**
    (Bubble Bobble, M7.30, 2026-09-25).  A heredoc turned an escaped newline into
    a real line break inside a JS string, so `test/bb.test.js` stopped parsing.
    `baseline()` collected lines beginning with `FAIL`, found none -- a crash
    produces none -- and declared the worker healthy.  Every case then died on
    the same crash.
    The per-case logic already knew better: no summary plus `SyntaxError` is
    BROKEN-MUTANT, not a kill (TRAPS #107's rule).  The BASELINE had no business
    being laxer than the cases it guards.  It now requires the POSITIVE signal --
    the `N/N checks passed` line -- and a plausible check count, so a suite that
    parses but exits after two checks is not a baseline either.  Verified by
    breaking the suite on purpose: the workers report `baseline DID NOT RUN` and
    the run lists ZERO cases instead of claiming kills.
    The general rule: a health check must look for the evidence of health, never
    for the absence of evidence of illness.

168. **NINE THINGS NOW LOST TO SHELL HEREDOCS** (Bubble Bobble, M7.30,
    2026-09-25).  The tally: four Python files whose `\n` collapsed, one regex
    built by concatenation that lost its `\b`, one written with doubled
    backslashes that matched a literal one, sixty-two labels left carrying a raw
    `\u2019`, a lock block in the battery runner, and now a check row whose
    `src.indexOf('\n  }')` became a line break -- which took the whole suite
    down and hid it behind a green battery (TRAPS #167).
    Twice now the script has WRITTEN the broken file and compiled it afterwards,
    so the repo carried a syntax error for as long as it took to notice.  The
    rule is not just "use the Write tool": it is **round-trip through a temp file
    and parse it BEFORE writing the real one**.  Both repair scripts in this
    increment do that (`node --check` for JS, `py_compile` for Python), and that
    is the pattern to copy.

169. **I GENERALISED FROM THE MEMBERS I HAD MEASURED -- FOUR TIMES, GETTING A
    DIFFERENT ANSWER EACH TIME** (Bubble Bobble, M7.31, 2026-09-25).  One
    property, four claims:

    | claim | source | verdict |
    |---|---|---|
    | "the off-by-one BELONGS to the hand-coded sites" | M7.30, from 2 of 3 | wrong |
    | "1 of 3 exact" | M7.31 first pass, from a list I typed | wrong |
    | "4 of 6 exact" | a verification pass, from a wider read | wrong |
    | **"5 of 7 exact"** | the phase's own ENUMERATION + assert | right |

    `$8E83` loads 11 attribute cells for a ten-character string and `$9760` loads
    9 for eight, while the `$9A85` table gets it right four times out of four.
    From those two I wrote, in SPEC.md and in a check label and in the progress
    log, that the off-by-one BELONGED to the hand-coded sites.  M7.31 measured a
    third, `$8CF6`, found it exact, and wrote "1 of 3" -- **inside the same
    increment as this entry warning against exactly that move.**  A verification
    pass then found `$98CA`, `$98DA` and `$9948`, all exact.  And the assert I
    finally added -- *every `$995A` site with an immediate `B` must be named* --
    found `$9074` on its first run: a SEVENTH site, which colours the same ten
    cells as `$9948` and flashes them from `$9068`'s border loop, with the colour
    living in the operand at `$9077`.
    Every wrong number came from a list I typed.  The right one came from a scan.
    And note what the scan had to cover: `CALL` **and** `JP`, because `$A04B` and
    `$A08D` reach `$995A` by jump and a `CD 5A 99` census cannot see them -- the
    same shape as `phase_writers` finding two of `$FEC9`'s three.
    **And no story survived the count either.**  "Ten-character strings are exact,
    odd lengths carry a spare" is the obvious pattern and `$8E83` kills it: eleven
    cells for the ten characters of "WELL DONE!".  Five of seven are exact and
    nothing about the strings separates the two that are not.  The finding is a
    bare count, and it is written as one on purpose.
    The rule: **a claim about a CATEGORY is not earned by the members you have
    measured -- enumerate the category IN CODE, and make the enumeration assert
    that nothing is unnamed.**  TRAPS #160 is the same shape from the other end
    (do not call a mutation unreachable without enumerating the 256 cases) and
    #165 is it again (do not count coverage from your own table).  What this one
    adds: writing the lesson down does not protect you from it.  Only the assert
    does.  *When a sentence says "always", "belongs to" or "never", the next
    commit contains a loop.*

170. **THE ORACLE ALREADY EXISTED AND I NEARLY WROTE OVER IT** (Bubble Bobble,
    M7.31, 2026-09-25).  I composed a new `tools/gameover.py` -- eighteen
    hundred bytes of phases for the GAME OVER screen -- and a shell heredoc
    failed on a quote before it could be written.  `ls` then showed
    `tools/gameover.py` already present at 18,744 bytes: the H13-B1 increment's
    oracle for the SAME routine, which already measured the 256-frame countdown
    (`phase_countdown`), the three writers of `$FEC9` including the one that INCs
    through HL (`phase_writers`), the `$96DF` reset and the screen's changed
    cells.  A broken heredoc is what saved it.
    Worse, I had spent three subagents' time on questions that file answers, and
    had to send one of them a correction mid-flight.
    The rule: **before writing `tools/X.py`, list `tools/`.**  This repo has
    ninety-odd tools and an eight-month memory; "is there already one for this?"
    costs one command and the alternative is silent destruction of measured work.
    The same applies to a phase name inside an existing tool -- `phase_glyphs`
    went in beside `phase_screen` rather than replacing it, because the old
    measurement was right for the gate it served.

171. **ONE COUNTER, TWO MEANINGS, AND NOTHING SAID SO** (Bubble Bobble, M7.31,
    2026-09-25).  `bannerGlyphs` counts GLYPHS DRAWN at `$8EA7` and at `$98C4`
    -- `+10` each, the NUL deliberately not counted.  At `$8CF6` it counted
    FRAMES OWED, `+1` per redraw, because the glyphs were a declared departure
    and there was nothing else to count.  Same name, two units, and a gate
    asserting `bannerGlyphs === 2` after two calls looked exactly like the gates
    asserting `+10` after one.
    A declared departure needs a counter, and the cheap move is to reuse the
    counter the real behaviour uses.  That is precisely when the name must
    change: the departure counter and the behaviour counter are not the same
    quantity, and once the departure closes the two silently merge into a number
    that means neither.  Drawing the nine made it uniform (`+9`, the NUL still
    not counted) and the row that says so is the only record that it ever was
    not.
    The rule: **a counter's name states its unit; a declared departure counts in
    its own name.**

172. **A DIFF CANNOT SEE A WRITE THAT CHANGES NOTHING, AND MY FIRST EXPLANATION
    OF WHY WAS ALSO WRONG** (Bubble Bobble, M7.31, 2026-09-25).  `phase_screen`
    measures the game-over banner by snapshotting `$4000..$5B00`, running the loop,
    and diffing.  It reports **51** changed bitmap cells.  The banner writes
    **72**.
    I wrote that the snapshot must be taken after the loop had already drawn once.
    **It is not**: `frames()` evaluates `watch(p, f)` on the PC about to execute,
    so it stops AT `$8CDC` with `$484C` = `$7F` -- play-field bytes, nothing drawn.
    The real reason is better and it is measured: of the 72 writes, **24 are `$00`**
    (the blank top and bottom row of every glyph, plus the space character) and
    **21 of those land on a byte that already holds `$00`**.  72 - 21 = 51, exactly.
    **There is no CLS**: the banner draws straight onto the live play field, so 51
    is a fact about `round1_48`'s wallpaper and not about the banner.
    That was SOUND for the gate it served, which asserted `> 0` against an engine
    drawing none: the number did not matter and the row only had to prove the
    machine drew something there.  It stops being sound the moment a DRAWING engine
    is compared against it, and 51 is exactly the kind of plausible wrong target
    that gets adopted without question.
    The rule: **to count what a routine WRITES, watch the write; to count what it
    CHANGES, diff.**  Those differ by however much of the output already happened
    to be there, which is a property of the WORLD and not of the routine.
    `phase_glyphs` watches `$8052` and gets 72; both numbers are in the fixture and
    a row asserts the inequality, so neither can be mistaken for the other again.
    And the smaller lesson: when a measurement disagrees with the code, find the
    mechanism before naming it.  I had a plausible story (stale snapshot) and it
    cost nothing to check -- `stopped at PC = $8CDC` and one dump of the row.

173. **"NO ROM BYTE IS RECORDED" QUIETLY BECAME "NO VALUE IS CHECKED", AND A
    ROUTINE WROTE ZEROS FOR WEEKS** (Bubble Bobble, M7.32, 2026-09-25).
    `digitGlyph`, the `$7FAF` transliteration, fetched its glyph byte like this:

        ram[((d << 8) | l) & 0xFFFF] = BB_DIGITS[digit * 8 + i + 1];

    `BB_DIGITS` is TEN EIGHT-ELEMENT ARRAYS.  A flat index yields an inner **Array**
    for 0..9 and **undefined** above, and a `Uint8Array` element store coerces both
    to **0** without throwing -- `Number([..])` is `NaN`, and `NaN` truncates to
    zero.  So every round-number digit drew seven zero bytes, while `roundDigits`
    reported a faithful call count, faithful `$9A0E`/`$9A0F` ASCII and faithful
    `$F840`/`$F841` colour writes.  The other consumer of the same font,
    `scoreGlyph`, indexes it correctly -- **one font, two consumers, two beliefs
    about its dimensions.**
    **WHY NOTHING CAUGHT IT IS THE LESSON.**  This project ships no Spectrum ROM and
    its fixtures deliberately record destinations and source ADDRESSES and no ROM
    bytes.  That is right.  What it became is "no value is ever compared", including
    the bytes of the port's OWN substitute fonts -- which are the port's data, are
    in the built page, and could have been compared from the first day.  The nearest
    row diffs the engine WITH digits drawn against the same engine WITHOUT and
    requires the changed set to be a non-empty SUBSET of the machine's glyph
    addresses.  **All-zeros is a valid subset.**  Its label even states "the engine
    differs from the machine on SIX bytes" -- a number its predicate never reads.
    The rule: **a declared departure still has bytes, and they are YOUR bytes.**
    Refusing to record the original's data in a fixture does not excuse never
    checking the substitute's.  Concretely: for every glyph a port draws from a
    substitute table, one row must compute the expected byte FROM THAT TABLE and
    compare it at an address the oracle measured.  A destination-only row cannot
    tell drawing from erasing.
    And the smaller tell, worth grepping for on its own: **a number stated in a
    check's LABEL that the predicate never reads.**  That is a claim with no test
    behind it, sitting inside something that looks tested.

174. **A LOOKUP THAT IS WRONG FOR EVERY INPUT CANNOT SHOW YOU THAT ITS DOMAIN IS
    WRONG TOO** (Bubble Bobble, M7.32, 2026-09-25).  Fixing #173 I added a
    diagnostic throw beside it -- house rule 6, never let a fallback engage
    silently, since falling back on zero and reporting success is exactly what the
    bug did.  **It fired on the first run**: `no cell for digit 12`.
    A SECOND, independent fault had been sitting underneath.  The port's signature
    took a DECIMAL DIGIT; the machine takes a code.  `$8042` does `ADD A,$30` and
    `$8044` builds `$3C00 + 8*code`, so it draws whatever cell that lands on -- and
    `$7F86`'s divide-by-ten leaves `tens` as high as 25 for a byte round counter, so
    round 128 draws `'<'` and round 255 draws `'I'`.  `$9877`'s settle-window oracle
    sweeps twelve round values and one of them is in that range, so the suite had
    been *driving* the broken domain all along.
    It was invisible because the value fetch was wrong for EVERY input: a lookup
    that always returns the same wrong thing is equally wrong at 8 and at 12, so the
    domain error had no signature of its own.  Two faults stacked in six lines, and
    the first one masked the second.
    The rule: **after fixing a fault that affected every input, re-ask the questions
    the fault could have hidden** -- the domain, the range, the arity.  And prefer a
    THROW to a `|| FALLBACK[0]`: `scoreGlyph` has exactly that fallback and so
    cannot answer whether it is ever asked for a cell it does not have.  A fallback
    is an answer to a question you have then stopped asking.

175. **A GUARD OVER THE REGISTER CANNOT FIND WHAT IS ABSENT FROM THE REGISTER**
    (Bubble Bobble, M7.32, 2026-09-25).  The suite has a row built for exactly this
    job -- *every test-only asset is READ by a check* -- and it had been green for
    weeks while `build/digits.json` sat unread since 16 September.  It iterates
    `port.json`'s asset list.  A fixture that was never REGISTERED is invisible to
    it by construction.
    That mattered: `digits.json` records `BB_DIGITS`, the font whose consumer was
    writing seven zeros per digit (TRAPS #173).  The fixture is byte-identical to
    the engine's table, so a row comparing them would have existed all along -- and
    the tool that writes it already asserts a difference from the ROM, so the whole
    apparatus was there and simply unplugged.
    The fix is to enumerate **the directory**, subtract the register, and require the
    remainder to equal a PINNED list.  A new unregistered fixture then fails, and has
    to be either registered or named with a reason.  The pinned list here came out at
    eight extraction intermediates (each with a producing tool or a suite reference)
    and **fourteen orphans that no tool writes and no check reads** -- itself a
    finding, recorded rather than tidied away, and derived by scanning `tools/` for
    each filename rather than by my judging which looked disposable.
    And the guard is shown to WORK, not merely to be quiet: the same set-difference
    re-run over the listing PLUS a phantom must come back naming exactly the phantom.
    Verified with a real file on disk as well -- it fired and named it.
    The general rule: **a completeness check must enumerate the territory, not the
    map.**  TRAPS #165 is the same lesson about coverage (never count call sites from
    the port's own table) and #169 about categories (enumerate in code, and assert
    nothing is unnamed).  Three shapes of one mistake: asking the record what the
    record contains.

176. **THE PORT AND THE MACHINE CAN AGREE BY ACCIDENT, AND THAT IS NOT A REASON TO
    LEAVE IT** (Bubble Bobble, M7.32, 2026-09-25).  A coercion hunt over the whole
    engine found **213 store sites in 70 methods** that index `ram[var + n]` with no
    `& 0xFFFF`.  All are unreachable from the real slot bases.  Where a fuzz did reach
    one -- `corpseBirth` with the hit pointer at 0, giving `$FFF9` -- the wrapped
    addresses are `$0000..$0002`: ROM, which the machine also ignores.  **So the port
    and the machine produce the same visible result for opposite reasons** -- the
    machine because a store to ROM does nothing, the port because a JS index past the
    end of a typed array is dropped.
    Not reported as a defect, and deliberately not fixed en masse: 213 edits with no
    behavioural difference is churn, and the analysis that says "unreachable" is worth
    more written down than acted on.  But the agreement is a coincidence of two
    different mechanisms, and if either base ever moves into RAM the port stops
    tracking the machine with nothing to say so.
    The rule: **when a port and the original agree, know WHICH mechanism is producing
    the agreement.**  "The output matches" is not the same as "the model is right",
    and the difference only shows up later, when an input moves.
    The same hunt's useful negatives, worth keeping because a clean negative with its
    method stated is a result: all 64 `BB_*` tables deep-proxied for fractional,
    negative, past-end and absent reads; every `Uint8Array` proxied for non-number
    stores; 1,500 frames, rounds 1..81 through the build routines, `roundDigits` over
    all 256 values of `($8609)`, eight banner strings by five destinations,
    `extendPass` over 256 masks, `elementBank` over 256 classes, and all 311 prototype
    methods over ~100 tuples -- 22,557 calls.  No reachable instance of the `$7FAF`
    class survives.  Three latent ones and one wart remain, each guarded by exactly one
    caller and each named in M7-PROGRESS rather than left to be rediscovered.

177. **THE GUARD I ADDED WHILE FIXING SOMETHING WAS DEAD ON ARRIVAL, AND ONLY THE
    BATTERY SAID SO** (Bubble Bobble, M7.32, 2026-09-25).  Fixing `digitGlyph` I wrote

        const g = code >= 0x30 && code <= 0x39 ? BB_DIGITS[code - 0x30] : undefined;

    and the battery's one survivor was the mutation that dropped the guard:

        const g = BB_DIGITS[code - 0x30];

    It survived because it is the same function.  `BB_DIGITS[code - 0x30]` is a cell
    IFF `code - 0x30` is 0..9, which is exactly `0x30 <= code <= 0x39` -- enumerated
    over every digit 0..255, the two forms never differ.  The guard tested a condition
    the array lookup had already decided, and the `g === undefined` branch below was
    carrying the whole domain by itself.
    So the code went, not the mutation.  A survivor pointing at code that does nothing
    means the code should not exist; the domain it was documenting now lives in a
    comment, which is the honest place for a statement that is not a test.
    **The specific trap is that this was code added IN THE ACT OF FIXING A BUG**, when
    the instinct to be careful is strongest and the scrutiny is lowest -- the fix gets
    tested, the belt-and-braces around it does not.  The diagnostic throw added at the
    same moment earned its place immediately (it found a second fault, TRAPS #174); the
    range guard beside it was decoration.  Both felt equally prudent when written.
    The rule: **mutate the defensive code you add during a fix, not just the fix.**
    And note what made this cheap to settle: the mutation already existed because I
    write a case for every line I touch, so the battery answered a question I had not
    thought to ask.
    **SECOND INSTANCE, two increments later** (M7.34): fixing `extendGlyph`'s silent
    fallback I wrote
    `Number.isInteger(k) && k >= 0 && k < BB_LETTERS.length ? BB_LETTERS[k] : undefined`,
    and the mutation deleting it survived -- because `BB_LETTERS[k]` is ALREADY
    `undefined` for `6.2`, `-1`, `6`, `7` and `2.5`, enumerated.  Same shape, same
    circumstance: a guard added in the act of fixing something else, testing a condition
    the lookup had already decided.  Twice is a habit, so the habit is what to watch:
    **when a fix adds a guard, ask what the operation returns WITHOUT it before writing
    it.**

178. **THE GATE WAS ON THE SIGN OF THE DELTA AND THE MACHINE'S IS ON THE PHASE
    COUNTER** (Bubble Bobble, M7.33, 2026-09-25).  `playerJumpFall` decided whether to
    probe the floor with `if (dy > 0)`.  The machine decides with `$AD7D CP $10 /
    JR nc`, and A at that point is the NEW phase -- `$AD6D INC A` has already run and
    `$AD74` has already STORED it -- so the machine probes from OLD PHASE >= 15.
    `dy > 0` first holds at phase 19.  The four phases in between, 15..18, are exactly
    the arc table's ZERO-DELTA entries, so the port skipped the probe on four phases the
    machine takes it on.  **REACHABLE**: any short hop whose apex has floor 16 px below.
    Both rules agree on 13 of the 17 phases either could see, which is why it survived.
    **What made it invisible is that the divergence needs TWO conditions at once** -- a
    phase in 15..18 AND floor on the probe row -- and no shipped world and no existing
    gate happened to place both.  The suite was green because untested, not because
    right, exactly as in TRAPS #173.
    The rule: **a predicate derived from a value is not the predicate the machine
    evaluates, even when it agrees.**  `dy > 0` and `newphase >= 16` are both true
    statements about a descending jump; only one of them is the instruction.  When a
    port's condition is a paraphrase rather than a transliteration, write down the
    instruction it replaces and check the paraphrase over the WHOLE domain -- here, the
    two rules differ on precisely the phases where the delta is zero, which is the one
    place "descending" is ambiguous.
    And the corroboration was sitting in the image: `($ADA1) = $B58B` is the
    self-modified arc pointer left by the last descent probe the real machine ran, index
    14, **phase 15** -- one of the four.

179. **ONE ROUTINE, TWO BOTTOM WRAPS, AND THEY ARE NOT THE SAME WRAP** (Bubble Bobble,
    M7.33, 2026-09-25).  The jump arc has two exits and each clamps Y differently:

        $AD88  CP $C0 / RET c / LD (IY+6),0      the PLAIN arc step  -> Y := 0
        $AD5D  CP $BF / RET c / LD (IY+6),2      the FREE-FALL tail  -> Y := 2

    Different thresholds AND different landing values, one instruction apart in intent
    and 63 bytes apart in the image.  The port modelled neither, using `(y + dy) & 0xFF`
    for both -- and a single mask cannot express two wraps, so no amount of tuning one
    number would have covered it.  `playerFloorTick` shares the second tail and its own
    comment had flagged it as unmodelled since it was written.
    The rule: **when a routine has more than one exit, ask each exit what it clamps.**
    A wrap discovered on one path is not the routine's wrap, it is that path's wrap, and
    the giveaway is a comment saying "the bottom wrap" in the singular.
    Measured: the plain step first wraps from Y `$BE` (result `$C0`) and the free-fall
    tail from Y `$BD` (result `$BF`), so there is a one-pixel band where the two rules
    disagree about whether to wrap at all, on top of disagreeing where to land.

180. **A MASK THAT LOOKS COSMETIC WAS THE SWITCH ON A WHOLE BEHAVIOUR** (Bubble
    Bobble, M7.33, 2026-09-25).  The floor probe has two entry points one instruction
    apart -- `$AE7F LD C,$3F` and `$AE81`, which the floor tick enters with `C := $20`
    already loaded.  I had a port helper with `$20` hard-coded and a note that the
    difference was "measured as 0 differing cells over shipped data", i.e. cosmetic.
    It is not.  After the probe decides a cell is solid it runs `$AE9C AND $20`:

        AE9A  LD E,1
        AE9C  AND $20              <- PATCHED TO $C9 (RET) around the FEET probe
        AE9E  JR z,$AEA1
        AEA0  RET                     solid under $20 -- an ordinary floor
        AEA1  BIT 1,(IY+8) / JR z,$AEAD
        AEA7  LD (IY+9),1 / POP HL / RET    *** sets the JUMP PHASE and UNWINDS ***

    With `C = $20` the `AND` is always non-zero and `$AEA0` returns.  With `C = $3F` a
    cell solid only in bits 0..4 -- the walker's claim and release bits -- falls through,
    and with `(IY+8)` bit 1 set the probe **sets the jump phase to 1 and POPs the
    caller's return address**: a bounce that returns past its caller.  The mask is the
    switch.  And that is why the floor tick patches `$AE9C` to `RET` for its feet probe
    and restores it for the row below: to choose which probe may bounce.
    **The equivalence measurement was true and the conclusion drawn from it was wrong.**
    Zero shipped cells have a low bit set -- I re-measured it, ten shadows, zero -- so
    the two masks select the same cells today.  That makes the mutations unkillable, and
    it says nothing about whether the masks mean the same thing.
    The rule: **"observationally equivalent on the data I have" is not "the same
    operation."**  When a constant differs between two call sites of one routine, find
    what reads it downstream before concluding the difference does not matter; the
    distinguishing input may be one the shipped captures never contain because it is
    written at RUNTIME.
    Consequence recorded rather than papered over: the three mask mutations are
    WITHDRAWN, with the note that the world distinguishing them is exactly the world
    that reaches the unmodelled bounce -- so they cannot be gated until it is modelled,
    and gating them against a half-modelled world would assert something false.
    **RESOLVED (M7.34): the bounce is REACHABLE and the masks are genuinely different.**
    A measurement pass counted **21 hits at `$AEA7` over 67,540 measured video frames
    from key scripts alone, nothing poked** -- it is the BUBBLE-JUMP.  The low five bits
    of a colour-shadow cell are a BUBBLE INDEX, claimed by `$B8C0` (`AND $E0 / OR tag`)
    and released by `$B6D6` (`AND $E0`), the tag for slot *j* being `12 - j`.  So the
    suspicion in this entry was right, the withdrawal was the right call, and the three
    mutations come back when M7.35 models the tail.

181. **WHEN NO CALLER CAN EXPRESS A DIFFERENCE, GATE THE ROUTINE AT ITS OWN ENTRY**
    (Bubble Bobble, M7.33, 2026-09-25).  A mutation turning the floor probe's
    `$AE92 AND 6` into `AND 7` survived a full battery.  The two differ only at X = 1
    mod 8, and no mover produces an odd X: driving `$ADAA` over all 256 X by four
    direction bytes -- 1,024 runs -- **X parity is preserved**, 512 even-to-even and
    zero even-to-odd, and the player starts at 24.  So every gate that reaches the probe
    through `playerJumpFall` or `playerFloorTick` is structurally unable to kill it.
    The reflex here is to withdraw it as a provable equivalent, and that would have been
    wrong.  `$AE7F` is a ROUTINE, not a helper: it has its own entry, its own register
    contract (D = pixel row, E = X) and a second entry one byte later at `$AE81` that
    differs only in which mask C holds.  Driven directly over all 256 X with floor in
    the THIRD CELL ONLY, it is solid for 192 of them and follows `AND 6` at every one --
    so the case is gated, not withdrawn.
    This does not contradict *drive the routine, never the helper*.  That rule is about
    not substituting a convenient inner function for the behaviour under test.  Here the
    inner function IS a routine of the original with its own address, and the claim being
    gated is its arithmetic.  **The test is whether the thing you are driving has a
    contract in the MACHINE, not whether it is at the bottom of the call stack.**
    The order that got there: withdraw only after establishing that no entry point can
    express the difference -- and check the routine's own entry before concluding that.

182. **A POISON-AND-SWEEP ROW MUST SWEEP WHERE THE ROUTINE WRITES, AND A COMPUTED
    ADDRESS IS NOT A FIXED REGION** (Bubble Bobble, M7.34, 2026-09-25).  A new row
    proved that `extendGlyph`'s declared gap writes NOTHING -- not zeros, which is what
    the old silent fallback wrote.  It poisoned `$4000..$5800` and `$E000..$F800` with
    `$5A`, drove an off-grid index, and asserted nothing moved.  It passed, and a
    mutation that wrote ZEROS passed with it.
    The off-grid index I chose reads table bytes `00 00`, so `hl` is **0** and the eight
    writes would land at `$0000..$0700` -- outside both poisoned regions.  The sweep was
    looking somewhere the routine never wrote.
    Fixed by COMPUTING the sixteen addresses from the same table bytes the routine reads
    and asserting those.  **And it still passed**, because `$0000..$0700` is the ROM
    window, which the byte image leaves ZERO -- so writing zeros changed nothing and the
    before/after comparison was satisfied.  That is *zero writes is a measurement of the
    world, not of the routine*, a rule already in this file, applied to my own gate:
    the sixteen computed targets are now POISONED before the call.
    Two lessons, and the second is the sharper one:
    **(a)** when a routine's destination is computed from data, a fixed-region sweep can
    miss it entirely -- derive the addresses the way the routine does.
    **(b)** "nothing was written" needs the target to hold something that is NOT what a
    faulty write would put there.  Against a zeroed region, "wrote zeros" and "wrote
    nothing" are the same observation, and the gate proving the difference was the one
    thing that had to tell them apart.

183. **A CENSUS RETURNED ZERO BECAUSE I SAMPLED THE CAPTURES WITHOUT THE THING**
    (Bubble Bobble, M7.34, 2026-09-25).  I measured whether any colour-shadow cell can
    hold a low bit with bit 5 clear -- the state that makes the floor probe's wider mask
    behave differently -- and got **zero**, over ten shipped 48K captures, twice,
    independently.  I wrote it into TRAPS #180 and into a mutation withdrawal.
    The ten captures had **no live bubbles**.  The low five bits ARE a bubble index, and
    the count of low-bit cells equals the number of live bubbles, every time: `elwater`
    five bubbles five cells, `sweet` three and three, `water` three and three,
    `round1_48` zero and zero.  Driven for 300 frames, **46 of 48 in-play captures
    produce one** -- and the three that start with none produce one the frame after BLOW
    works.
    So the measurement was correct and the population was wrong.  I had asked "does this
    ever happen?" of a sample selected for not containing it, and nothing in the
    arithmetic of the answer could tell me that.
    The rule: **when a census returns zero, state what the sample was selected FOR
    before concluding the thing cannot happen.**  Concretely: name the property, then
    check whether any member of the sample exhibits its PRECONDITION -- here, a live
    bubble.  A zero over a sample that cannot contain the event is not evidence, and it
    reads exactly like evidence.
    Related but distinct: TRAPS #144 says a sweep that finds nothing must print the
    census of what WAS reachable.  This one is worse, because the census of what was
    reachable would also have been zero -- the missing step is upstream of the sweep, in
    choosing the worlds.  And #180 is the consequence: a correct measurement supporting
    a wrong conclusion about what an operation MEANS.

184. **THE SAME BITS MEAN TWO THINGS AT TWO TIMES, AND ONE OF THEM IS PAINT** (Bubble
    Bobble, M7.34, 2026-09-25).  Chasing the bubble index above, seven captures reported
    **704 low-bit cells at once** -- every cell of the 22x32 playfield, which twelve
    bubbles cannot do.  Attributed: `$8306` is the round painter's `LDIR` fill, and
    `$82F7 AND $47` keeps flash, bright and **ink**, so during a repaint every playfield
    cell carries low bits that are colour, not a bubble tag.
    In the steady state the map uses only the top three bits -- `round1_48` shows eight
    distinct values, `$00 $20 $40 $A0 $C0 $E0` and two more -- so bits 0..4 are reserved
    for the tag while a round RUNS, and only the painter puts anything else there.
    The rule: **a field can be reserved without being exclusive.**  Before reading a bit
    range as one thing, find every writer and ask when each one runs; a port that models
    the reader and runs it against a half-painted map will decode paint as data.  The
    tell here was a count that was physically impossible for the meaning I had assumed --
    704 cells for a twelve-slot pool -- which is worth watching for on its own.

185. **THE BATTERY DECODED THE SUITE WITH THE CONSOLE'S CODEPAGE, AND HAD BEEN DOING
    SO ALL ALONG** (Bubble Bobble, M7.35, 2026-09-25).  `subprocess.run(..., text=True)`
    with no `encoding` decodes with the LOCALE DEFAULT -- cp1252 on this machine -- while
    `test/bb.test.js` prints UTF-8.  The project's non-ASCII had survived by luck:
    `U+2019` is `E2 80 99` and cp1252 happens to have a character at `0x99`.  A check
    label I added contained `U+201D`, which is `E2 80 9D`, and **`0x9D` is undefined in
    cp1252** -- so every worker died in its subprocess reader thread and **"finished" in
    0.2 minutes having run nothing.**
    **The tell was the CLOCK, not the traceback.**  2,170 cases cannot be decided in
    twelve seconds.  The traceback only said where; what said *something is wrong* was a
    run that could not possibly have done the work.  And the baseline's positive-signal
    check (TRAPS #167) never got a chance, because the failure was in READING the output
    rather than in the output -- a health check can only inspect what it can decode.
    Fixed twice over: `encoding='utf-8', errors='replace'` at both call sites, so a
    stray byte degrades one character instead of killing a worker; and a WALL-CLOCK
    FLOOR on the run, which says outright that a thousand-case run finishing in seconds
    did not run.
    The general rule: **a test harness must pin its own encodings**, because the default
    is a property of the machine and not of the project -- and *fast* is a failure
    signal in anything whose job takes minutes.
    Two of my own scratch mutation harnesses had the identical bug, with the identical
    consequence: nine cases reported as SURVIVORS when the harness could not read the
    output. They now require `N/N checks passed` and raise if it is absent.

186. **A FIND-BY-LABEL EDIT MUST CONFIRM ITS MATCH IS LIVE CODE, NOT A COMMENT**
    (Bubble Bobble, M7.35, 2026-09-25).  My re-anchor helpers locate a mutation case by
    `m.find(label)` and replace the span `rindex('    (', 0, i)` .. `index('),\n', i)`.
    For a WITHDRAWN case -- commented out with `#  (` -- the label is still found, but
    `rindex('    (')` walks BACK PAST the comment into the preceding LIVE case, so the
    replacement swallows it.  **Two cases were deleted this way and the anchor checker
    could not see it: a deleted case has no anchor to be dead.**
    Caught by arithmetic: 2,149 at the previous battery, +3 restored, -2 eaten = 2,150,
    and the +1 did not match the +3 I had made.  Both were restored and identified by
    name (`M7.33: probe ONE uses $3F` and `M7.33: the probe row is not masked to a
    character row`).
    Two rules: **an edit located by text must verify the match is in the construct it
    means to edit** -- here, that the span actually starts at a live tuple; and **a
    completeness check needs a COUNT INVARIANT as well as a validity check**, because
    every per-item check in the world passes over an item that is gone.  The checker
    prints the live-case count, the distinct-label count and a per-milestone census now.

187. **THE CHEAP CHECK EXISTED ALL ALONG AND I HAD NEVER WRITTEN IT** (Bubble Bobble,
    M7.35, 2026-09-25).  The mutation battery reports dead anchors after eighteen
    minutes.  Walking the case list with `ast` and counting each anchor's occurrences in
    the engine takes **under a second**, and it reports AMBIGUOUS anchors too -- which
    the battery cannot, since it applies the first match and never knows there was a
    second.
    Written in M7.35 after the fourth increment in a row that produced dead anchors, it
    found ten candidates on its first run.  Four were its own blind spot: it did not know
    `bb.test.js` is a legitimate mutation target (cases that break the SUITE to prove a
    row can fail), and it called them dead.  **A checker that does not know its own
    domain reports its blind spot as a defect**, so it now lists the targets it knows and
    names an unrecognised one instead of failing it.
    The rule: **when a slow process reports a class of error, ask what the fast version
    of that check would cost.**  Eighteen minutes against one second, for four
    increments, is the price of not asking.

188. **TWO BITS THAT ARE SET TOGETHER IN EVERY WORLD I BUILT** (Bubble Bobble, M7.35,
    2026-09-25).  `$AEA1 BIT 1,(IY+8)` tests the jump key HELD THIS FRAME.  My gate used
    `$22` for "jump" and `$44` for "no jump", taken straight from a measured capture --
    and `$22` carries bit 1 AND bit 5.  So a mutation testing **bit 5** instead passed
    every row, and the battery found it.
    Bit 5 is the same key LAST frame.  That is why `$AD00 BIT 1 / $AD04 BIT 5` is an
    EDGE detector for starting a ground jump while `$AEA1` is a plain HELD test -- and
    the two bits only part company on the FIRST frame of a press (`$02`) and the frame
    after release (`$20`), neither of which a steady-state capture contains.
    The rule: **when two inputs are correlated in the worlds you sampled, the gate tests
    their conjunction and not either one.**  Before trusting a bit test, construct the
    world where that bit disagrees with its neighbours -- and note that a captured value
    is exactly the wrong place to look for one, because a capture is a steady state and
    the interesting frames are transitions.
    Same family as #183 (a census over a population selected for not containing the
    event) and #180 (observationally equivalent on the data I have).  Three shapes of
    one thing: the sample decided the answer and did not say so.

189. **A POISON-AND-SWEEP OVER A NUL-TERMINATED REGION CANNOT INCLUDE THE NUL** (Bubble
    Bobble, M7.36, 2026-09-25).  I added a diagnostic bound to `$802E`'s walk -- it reads
    until a NUL, so a mutation deleting the terminator test used to hang a battery worker
    for 120 seconds.  The bound sits above the measurement (32 against the longest
    string's 29) and cannot fire on the faithful path.  It fired immediately, **on the
    faithful path, in a gate of my own**: row (b) of the same increment poisons
    `$85C1..$85FB` with `$5A` to prove nothing but the RRD conversion writes inside the
    template, and two of those 59 bytes are the terminators at `$85DD` and `$85FB`.
    The rule: **a sweep that overwrites a terminator is not testing the region, it is
    constructing the failure the bound exists to name.**  Hold the terminators back and
    assert they came back zero; the claim ("nothing writes here") is about the content
    bytes, so nothing is lost.  And the general form: a new invariant can invalidate an
    OLD gate's method, not just an old behaviour -- so after adding a bound, look at
    every gate that deliberately builds illegal states.

190. **A KEYBOARD-GATED ROUTINE DRIVEN WITH NO KEYBOARD RETURNS BEFORE THE THING YOU ARE
    MEASURING** (Bubble Bobble, M7.36, 2026-09-25).  Row (c) had to show that `$7FC0`
    falls into `$7FFC` at BOTH of its call sites, and the second site is the mid-game
    join's tail jump.  The clause seeded the credit count and called `joinCheck()` -- and
    measured nothing, because `$9967` reads half-row `$F7` and **the Spectrum's keys are
    ACTIVE LOW**.  With no Keyboard attached `port($F7)` is `$FF`, so the routine returns
    at `$996F RET c`, long before `joinCommit` where `$9998 JP $7FC0` actually lives.
    The gate failed rather than passing vacuously, which is the only reason it was found.
    The rule: **for a routine gated on input, the absence of input is not a neutral
    default -- it is one specific branch, usually the early return.**  Drive it, and put
    a refusal control beside it so the positive case cannot pass for the wrong reason.

191. **AN EQUIVALENT MUTANT BY CONSTRUCTION MAKES THE HEADLINE CLAIM UNTESTABLE, AND
    MOVING ONE BYTE OF DATA FIXES IT** (Bubble Bobble, M7.36, 2026-09-25).  The
    increment's second row is titled "the second row's pointer is NOT LOADED": `$7FEC`
    sets `HL` alone and `$802E`'s own `INC IX` has carried `IX` past the NUL at `$85DD`.
    Every clause in that row -- `next === $85DE`, the template's bytes, the poison sweep
    -- passes identically whether the port writes `bannerPrint(next, $4020)` or
    `bannerPrint($85DE, $4020)`, **because `next` IS `$85DE` on the faithful path.**  The
    obvious mutation was therefore an equivalent mutant, and the row's own headline was
    the one thing it did not test.
    The fix is not a cleverer assertion, it is a different WORLD: move the terminator to
    `$85CB` and row 0 is ten characters, so `IX` lands on the `'H'` of HIGH.  A chained
    printer draws HIGH SCORE at `$4020`; one that names `$85DE` draws the score row
    whatever the template says.  Hand-mutated both ways to confirm: one named kill.
    The rule: **when two implementations agree on every world you have, the gate is
    testing their agreement, not your claim.**  Ask what data would separate them and
    seed it -- a NUL, a length, a count.  This is TRAPS #44's shape (a world that already
    holds the answer cannot show the write) applied to control flow instead of data.

192. **A BOUND TAKEN FROM THE REACHABLE MEASUREMENT WOULD HAVE FIRED ON A REAL HAZARD**
    (Bubble Bobble, M7.36, 2026-09-25).  `$C002`'s burst-sparkle walk takes **14**
    iterations on every reachable state -- 48 captures, 12 consecutive passes each, HL
    never leaving `$5CE0..$5CFA`.  A ceiling of 32, or even 256, looks generous against
    14 and is wrong, because `$C016`'s `LDI` is a **second decrementer of the same B**: a
    serviced slot with X bits `$00` makes the DJNZ wrap and the total becomes
    `(wraps+1) x <=256`, decided by whatever RAM holds above `$5CFC`.  Over 1500
    randomised tables the count came out in three regimes -- 8..13, 216..269, and
    452/502/709 -- the largest walking HL to `$6268`.  **The machine really does that.**
    A ceiling of 256 would have named a faithful hazard as a bug.
    The rule: **a diagnostic ceiling is bounded below by the worst the MACHINE can do,
    not by the best you have observed.**  The reachable number tells you the bound cannot
    fire in play; the unreachable-but-real number tells you where to put it.

193. **THE RUNAWAY WAS IN THE SHIPPED FIXTURE ALL ALONG, AS A PIXEL COUNT NOBODY DIVIDED**
    (Bubble Bobble, M7.36, 2026-09-25).  `build/sparkle_fixture.json`'s `bc` row 3 has
    reported `pix = 4256` since M7.7, against row 1's `448`, and `ptr = $603C` against
    row 1's `$5CFA`.  448 over 14 slots is 32 pixel writes a draw, so 4256 is **133 draws
    from fourteen seeded slots**, and the pointer ended 320 bytes past the end of the
    table.  Two numbers, both present, both correct, and the fact they encode -- a
    431-iteration runaway -- went unread for twenty-eight increments.
    The rule: **a fixture that records a CONSEQUENCE instead of the QUANTITY hides the
    quantity in plain sight.**  If a claim is about how many times something ran, count
    the loop top; do not infer it from a write total that needs dividing.  `tools/
    sparkle.py` now records `iters` and `ptr_out` per row, and the harness, an
    independent agent and the engine all three say 431.

194. **A MALFORMED MUTATION'S TIMEOUT WAS THE MALFORMATION** (Bubble Bobble, M7.36,
    2026-09-25).  One of the five long-standing battery TIMEOUTs was R2's "the loop runs
    255 times".  It replaced the `do {` line of `$98E2`'s banner loop with
    `while (b !== 1) {` and **left the `} while (b !== 0);` behind** -- so the mutant
    carried an ORPHANED, EMPTY-BODIED `while` that spun on `1 !== 0` for ever.  A worker
    died at 120 seconds for a parsing accident, and the behaviour the case named (255
    iterations) is exactly what the first loop already did.
    `$98E2` needs no bound at all: `B` is an eight-bit sole counter bracketed by
    `$98BC PUSH BC` / `$98E1 POP BC`, so from zero it is 256 and can be nothing else --
    confirmed on four independent captures, and 0 on round `$51`.
    The rule: **before bounding the engine, check that the mutation is well-formed.** A
    hang can be the case's own syntax.  Prefer a single-line replacement with no
    dangling tail, and prefer one whose effect is visible through a counter the gate
    already reads.

195. **A MUTATION ANCHOR THAT MATCHES NINE LINES APPLIES TO WHICHEVER ONE THE REPLACER
    FINDS FIRST** (Bubble Bobble, M7.36, 2026-09-25).  Rewriting R2 well-formed, I
    anchored on `} while (b !== 0);` and `b = (b - 1) & 0xFF;` -- which match **five** and
    **nine** do/while tails in `game.js` respectively, one of them `$C002`'s.  The cases
    would have applied, gone red, and reported a kill for a routine they never touched.
    `scratchpad/m735_anchors.py` said so in under a second.
    The rule: **"it applied" is not "it applied where I meant".**  Anchor uniqueness is a
    property to be checked, not assumed, and a one-line anchor in a file with a house
    idiom (`do {` ... `} while (b !== 0);` appears once per transliterated DJNZ) is
    almost never unique.  Carry the line above it.

196. **A TIMEOUT DISCARDS THE FAIL LINES ALREADY ON THE PIPE** (Bubble Bobble, M7.36,
    2026-09-25).  The drift painter's stride mutation prints **five FAILs** -- one of them
    the drift-field row itself -- and only then hangs, in `scrollIn`, thousands of calls
    later.  `subprocess.TimeoutExpired` carries whatever was captured before the kill and
    `parallel.py` threw it away, recording `TIMEOUT, n=0`.  So a mutation the suite HAD
    named was filed as an unnamed hang, for three increments.
    The rule: **a hang is not an absence of evidence; it is evidence plus an interruption.**
    Read the partial output.  FAILs before the hang make it a named kill
    (`TIMEOUT-KILLED`); none, and it stays a TIMEOUT, because then nothing was shown and
    saying otherwise is the crash-as-pass lie in another costume (TRAPS #107).
    A separate lesson from the same work: a diagnostic counter named `scrollSteps`
    **clobbered** the existing `$840A` execution counter of the same name, which the
    composition-trace gate caught on the first build.  New observability can collide with
    old observability; grep the name before adding it.

<!-- budget: entries below this line are 20 lines at most, each with its row in
docs/TRAPS-MAP.md (tools/status.py --check, tools/selftest.py). -->

197. **AN ENGINE THROW OUTSIDE A CATCH IS A CRASH, NOT A KILL** (Exploding Fist,
    boot, 2026-10-09).  The mutant `boot: LDIR the wrong way` left the scenery tables
    shifted, and the engine threw its own diagnostic (`Change_Background: stage 2 jumps
    to $0`) from inside the page's rAF frame, which the kit's loop block drives with no
    catch -- and again from liveGate's boot `g.pass`, the one pass there without the
    catch the others have.  Node died, no FAIL line was printed, and the runner (rightly,
    TRAPS #107) filed a CRASH: a mutation the gates could have named, unnamed through a
    full run.  The two 8C54 menu crashes before it were the same hole.
    The rule: **every call that steps the engine inside a check goes through a catch
    that fails a named row with the error's message**, so a throw is a kill the runner
    can attribute.  A gate helper should own this, not each gate.
