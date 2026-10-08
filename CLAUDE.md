# Briefing: porting a ZX Spectrum game with this kit

You are in a repository created from the Spectrum Port Kit.  The job is a
FAITHFUL reproduction of one game, in one self-contained HTML file, verified
against the real machine code running in a Z80 simulator.  The operating
procedure is `docs/PORTING-ZX-TO-JS.txt` — sixteen phases — and
`docs/TRAPS.md` is what earlier ports paid to learn, with
`docs/TRAPS-MAP.md` mapping every trap to the mechanism that should
prevent it.

This file is re-read from disk after every compaction; the conversation is
not.  Keep it short: a rule that a tool or a hook enforces does not belong
here.

## Reading the manual and the traps

Both are read by ID, never end to end.  Together they are well over 100,000
tokens, and a hook refuses whole-file reads:

    python tools/manual.py --index           manual IDs, line numbers, titles
    python tools/manual.py C9 6.11 Q13       manual entries
    python tools/manual.py T146              a trap, with its row in the map
    python tools/manual.py --grep straddle   entries, traps and tools that mention a term
    python tools/manual.py --map gate        the traps a mechanism must prevent
    python tools/manual.py --tools stack     the tool for a job: purpose and usage

Read manual sections 0.7, 0.8 and 12 once at the start of a port, and
section 4 (the failure catalogue) once before phase 5.  After that, read an
entry or a trap when it is cited, when the session status names it, or when
a result surprises you.

## Session routine (manual 0.8)

1. Start from the status block printed at session start and again after
   every compaction or /clear: NEXT.md, the current unit, what to read for
   it, and anything `tools/status.py --check` found.
2. Work in units: one routine taken up one rung of the evidence ladder
   (manual 5.1).  Begin with `python tools/status.py B34C`; end with an
   artifact written by a tool: a fixture, a gate result, a frozen test.
3. Record each judgment the moment it is settled, with
   `python tools/record.py` (fact, refute, open, close, link): it goes to
   the routine's ledger file with the command that settles it.  Link the
   manual entries and traps that govern the routine (manual 12.2).
4. A measurement that surprises you twice means checking the instrument
   (G1, G11), not running it a third time.  Still stuck: record the open
   question and take the next item from NEXT.md.
5. End of unit: roll up anything the check says is over budget, write
   NEXT.md (`record.py next`), draft the commit (`record.py draft`),
   commit, then tell the user the unit is committed and a /clear is safe.
   The same handover applies whenever the context-watch note appears.

## Records: one home each (manual 12.11)

`NEXT.md` where things stand · `ledger/ADDR.toml` current truth about a
routine (`ledger/topics/` for systems) · the commit message what happened ·
`docs/TRAPS.md` new lessons, each with its map row · `docs/DECISIONS.md`
project-level choices · `scratch/` everything else, cleared at unit end.
Write them with `record.py`: fields go on stdin through a quoted heredoc,
one line each, so the shell never touches a `$`:

    python tools/record.py fact B34C <<'EOF'
    kind: insn
    at: $B351
    says: RET Z after AND 7 -- no check at all on cell-aligned x
    by: python tools/adis.py 0xB351 3
    EOF

Any other record file needs "Purpose:" and "Read by:" in its first lines,
or the end-of-response check blocks.  History lives in git, so rolling a
record up loses nothing.

## What is already here (don't rebuild it)

- `tools/` — TZX parsing, loader/boot, the SkoolKit-wrapped Z80 harness
  (contended timing on by default), config-driven disassembler, code
  walker, byte grep, keyboard probe, read-watch, clock histogram, the
  diagnostic battery, screen forensics, `build.py`.  `tools/README.md` maps
  each to its phase.  `python tools/selftest.py` is their gate.  The session
  block lists every script by name; `python tools/manual.py --tools TERM`
  finds the one for a job.  Read its `--help` before extending it or writing
  a new one, and give every new script a row in `tools/README.md`.
- `web/platform.js` — the platform runtime: display file + renderer,
  keyboard matrix + Kempston + gamepads, AY and beeper chips, the Web Audio
  bridge (worklet transport, scheduled fallback), the loop, settings.
- `test/rig.js` + `test/kit.test.js` — the headless rig and the runtime's
  own 115 checks, run against the BUILT page.  Append the game's checks
  after them; never let the file go red.
- `port.json` — the manifest.  Fill it in before running any tool that
  needs the tape.
- `.claude/` and `tools/manual.py` — the session machinery (manual 12.8): a
  status block at every start and after every compaction, a guard that
  refuses whole-file reads of the manual, the traps and `docs/archive/`,
  and source written through shell heredocs, a consistency check at the
  end of every response, a note when the context passes the handover mark,
  and a short block for every sub-agent.
- `tools/mutants.py` — the mutation battery's runner (manual 6.12): each
  case runs only the gate blocks its anchor reaches, killing block first,
  stopping at the first failure; survivors are confirmed against the whole
  suite.
- `tools/record.py` and `tools/status.py` — the records (manual 12.11):
  record.py writes each to its home and checks its links; status.py gives
  the orientation, `status.py ADDR`, `--check` and `--index`.  Evidence is
  reported as present, not yet as fresh.

## Still to build

Never call one of these until it exists: build it, or use the manual
procedure it replaces.  `python tools/manual.py --map` shows how many traps
each must prevent.

| Tool | Replaces |
|---|---|
| stamps for status.py (build first) | trusting evidence that predates a harness fix (manual 12.3) |
| `measure()` in the harness | the measurement checklist (manual 6.11, G11) |
| gate helpers in `test/rig.js` | remembering how gates fail (map: `gate`) |
| per-verdict stamps and pruning, for the runner (manual 6.12 steps 4, 6) | re-running unchanged verdicts at milestones; keeping redundant cases (map: `battery`) |
| the byte-usage map and roster manifest | backward-decode verdicts; guessing how saved states differ (12.5, 12.6) |
| `tools/brief.py`, `tools/verify_claims.py` | re-reading a range to check a sub-agent (12.7) |

When one lands, move it into "What is already here" and delete every rule
on this card that it now enforces.

## The mutation battery (manual 6.9 step 9, 6.12)

- After an increment: `python tools/mutants.py --affected` -- its new
  cases, and older ones whose anchor lines or killing blocks it changed.
- A full run with `python tools/mutants.py --background`: at each milestone,
  after any change to the harness, rig, build or runner (`status.py` warns
  when one is due), and before a release.  It writes a one-line summary to
  `build/mutants/summary.txt`; never wait on it or poll it.
- Every case records its id, file, anchor, replacement, the increment that
  wrote it and the row expected to kill it; the runner records the row and
  block that did.
- Every gate block must pass on its own: a case runs only the blocks its
  anchor reaches, and a block that leans on another's leftovers makes every
  case that needs it slower.
- Say in the commit which kind of run it was.

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
   test (see the localStorage lesson in TRAPS).  How much to run, and how
   to keep it cheap: "The mutation battery", above.
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
9. **Check delegated work by script.**  A sub-agent's finding comes back
   as a typed claim and is verified before it is used (manual 12.7);
   anything else is a HYPOTHESIS.
10. **Every new trap gets its map row** in `docs/TRAPS-MAP.md`: the
    mechanism that now prevents it, or why none can.  `python
    tools/selftest.py` fails if a trap has no row.

## Commit style

Scoped commits, one per unit of work, each with a message that says what
was measured and what the mutation battery covered.  Suite count in the
message.  `python tools/record.py draft` writes the mechanical lines; the
body stays within 15 lines.

## Additional

Use only 20 workers when run mutation battery runs