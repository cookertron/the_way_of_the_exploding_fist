# Traps — what two ports paid to learn

Each entry is a measurement, not an opinion.  The manual (`PORTING-ZX-TO-
JS.txt`) says what to do in each phase; this file is the list of places a
careful engineer still fell in, with the number that proved it.  Read it
once before starting and again whenever something is "nearly right".

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
