# Provenance -- Exploding Fist

Purpose: the provenance record (manual P15) -- routine map, faithful/added boundary,
what the original proved wrong, what is still open.  GENERATED: do not edit.
Read by: a reviewer; whoever ports the next game.  Rewritten with
python tools/provenance.py; --check says whether it is current.

## 1. The routine map

Original address -> what it does -> the function that implements it, joined from
ledger/<ADDR>.toml and the `// @z80 $ADDR -- what it does` tag on each function (manual 7.1).

| address | name | what it does | port (web/template.html) | fixtures | evidence |
|---|---|---|---|---|---|
| $8803 | sprite_decoder | decode one packed sprite into the back buffer, masked at each row end | `spriteDecode` :84 | sprdec | measured ported gated |
| $8C54 | game_configs | the options menu: players, controls (keys, Sinclair, Kempston), sound on/off | `configs` :1428 | control97cb live_menu live_msound | measured ported gated |
| $900E | yin_yang | 2P yin-yang award: draw and add the points scored this pass | `yinYang2P` :982 | yy976f | measured ported gated |
| $95D4 | fighter_motion | step each fighter's motion script: hold, y, x clamped to the arena | `fighterMotion` :1241 | motion95d4 | measured ported gated |
| $9745 | play_pass | one pass of play, the callees in the machine's order, from the CALL at $AE29 | `playPass` :2068 | pass9745 | measured ported gated |
| $97BB | fighter_step | advance each fighter's move by one frame from the move tables | `fighterStep` :482 | step97bb | measured ported gated |
| $97CB | control_pass | read the keys or Kempston for 1P/2P, or drive a fighter by the AI; quit keys | `controlPass` :1378 | control97cb | measured ported gated |
| $9AD7 | fighter_post | settle a finished move and store the move, frame pair back ($9B9D) | `fighterPost` :693 | post9ad7 | measured ported gated |
| $9C2E | game_start | Game_Start: move the scenery code down to $5F00, then into Main_Game_Loop | `gameStart` :2921 | live_boot | measured ported gated |
| $9C6F | bout_timer | the bout clock: one second per 13 passes, frozen while time is up or a fighter reels | `boutTimer` :902 | timer9c6f | measured ported gated |
| $9D29 | p1_hits_p2 | P1's move against P2: copy the x bytes, then the shared hit core | `p1HitsP2` :1221 | hit9d29 | measured ported gated |
| $9ED2 | p2_hits_p1 | P2's move against P1: reach and gap from the move tables, the reel and the points | `p2HitsP1` :1212 | hit9ed2 | measured ported gated |
| $A3FF | Random_Number |  | -- (none: see part 4) | -- | read |
| $ABB9 | demo_ways_on | the demo's ways on: stage and rank up, the next demo stage, or back to the dispatch | `demoOn` :2312 | demo_abb9 live_dtime | measured ported gated |
| $ABCB | demo_point | the demo's point: score, the yin-yang, a pose at count 4, or round_loop again | `demoPoint` :2276 | demo_abcb live | measured ported gated |
| $AC09 | main_game_loop | Main_Game_Loop into Demo_Mode: text rows, rank, scenery, to the first $AE29 | `demoIn` :2785 | demo_ac3c live | measured ported gated |
| $AC27 | main_game_dispatch | the dispatch after Demo_Mode: a new demo, the 1UP game or the 2UP game | `gameDispatch` :2801 | demo_ac27 live | measured ported gated |
| $AC39 | check_highscore | Check_HighScore: compare BCD scores and copy a new high score | `checkHighScore` :2544 | hiscore_ac39 | measured ported gated |
| $AC5F | bout_setup | the next bout's setup: tune, scenery, scores, rank, New_Round, CALL $AD18 | `setupRest` :2754 | setup_ac5f | measured ported gated |
| $ACA6 | bout_next | after a 1UP bout: lost to the high score, won (bouts left, stage, rank up), or the draw | `boutNext` :2487 | next_aca6 | measured ported gated |
| $AD18 | bout_loop_in | the bout's loop top: fighters reset, into round_loop | `roundIn` :2327 | live_p1w live_time | measured ported gated |
| $AD1B | point_path | after a point: yin-yang, score, a bout won at 4, time up, or the next point | `pointPath` :2247 | point_ad1b live live_quit | measured ported gated |
| $AD44 | time_up | time up: both posed, then the decision by count and tally, or the draw | `timeUp` :2460 | end_ae67 time_ad44 draw_ad44 live_time | measured ported gated |
| $AD5F | p1_wins_bonus | P1 wins the bout: the pose, then the time bonus counted down second by second | `bonusPass` :2408 | win_ad5f live_p1w | measured ported gated |
| $AD94 | p2_wins_pose | P2 wins the bout: the victory pose, out of the 1UP game | `winPass` :2366 | win_ad94 live | measured ported gated |
| $AD9C | Start_2UP_Game | Start_2UP_Game: rank, scores, tune, the per-bout stage, into the 2UP round | `stage2` :2840 | start2_ac27 live_2up | measured ported gated |
| $AE17 | Two_Player_Round_On | the 2UP game's ways on: next round, next bout, game end with its pose, quit | `twoOn` :2871 | round_ae17 | measured ported gated |
| $AE26 | round_loop | round_loop: the play pass, then the quit, $C427 from the moves, a point or time up | `roundPass` :2112 | tail_ae2c live | measured ported gated |
| $B15A | sound_effect | play the requested sound effect on the beeper, inline and blocking | `soundEffect` :1016 | sfx | measured ported gated |
| $BF13 | render_fighters | draw both fighters: box union with last frame, overlap test, copy to the screen | `renderFighters` :406 | rendfx | measured ported gated |

## 2. The faithful/added boundary

Added layer: `Fist.FLAGS = {}` in web/template.html.  Every departure from the original is a named flag, off on the faithful path (house rule 5); none is declared, so the page is the original throughout.

Enforced by these rows of test/kit.test.js, run against the built page:

- Fist.FLAGS: the page declares exactly the flags the identity gate names
- G.identity: every added-layer flag off (and view flag on) holds the faithful state byte for byte, ${g.passes} passes from the boot through key 1
- G.identity known-wrong: a view flag that writes when on, a play flag that changes nothing, a flag whose off differs -- each named
- G.identity known-wrong: an engine whose two faithful runs differ is named, with no flag declared
- G.identity known-wrong: no frames throws (T110)

Substituted, not added: material the original takes from the ROM, which the port may not ship (manual 0.5).  Timing and counts are kept; the content is ours:

- **D5 ROM font -- an independently drawn lookalike (manual 0.5)** -- User's choice: the $3D00 font read via $923A is replaced by our own 8x8 glyphs in the same layout; no ROM byte is committed or built in (callio keeps ROM reads, --blind outputs, as addresses)
- **D6 ROM-driven sound -- substituted pulse widths, exact timing (manual 0.5, 3.7)** -- User's choice: $B15A fx 1,2,3,5,6 take half-periods from ROM AND mask; the JS reads a fixed substitute per effect with the real count, sum and zero count, so edges and total T match (tools/sfx.py)

## 3. What the original proved wrong

Every question the ledgers closed, oldest first: the "caught by" column is the command or gate that settled it, and the commit that recorded it.

| # | asked (what was assumed or not known) | what the machine said | caught by |
|---|---|---|---|
| 1 | 9745: which timing model for the JS pass -- a T-state tally kept by the JS sprite decoder as it walks the same compressed rows, a per-(frame,mirror,shift) cost table frozen from the harness, or a measured mean pass rate? | timing model chosen (D3) -- the JS sprite decoder tallies T-states as it walks the same rows as $8803; checked per key against callcost.py within 0.65% outside the display copy | grep -n "D3" docs/DECISIONS.md (154a12e) |
| 2 | 8803: how the JS tally charges stack contention (0-7.2% of the call by frame phase) -- a mean factor, or per stack access keyed to the 7.2 clock phase | only stack ops contend in $8803; per-call spread is frame phase, which the JS tally cannot hold (DI, free-running), so charge the play-weighted mean: T x 1.0317 (s1 1.03179, p1 1.03167, p1b 1.03167; D4) | python tools/sprdec.py --capture --state s1 --frames 1500 --out scratch/cap.json (433d7ae) |
| 3 | BF13: is the overlap slack +11 at $C042/$C04F pinned by data -- the fixture's nearest case sits 30 px from the merge/separate boundary, and every box top is in the middle third | box tops ($C41A) never leave $67-$7A, so the copy-out always starts in the middle third: Screen_Calc never returns a top- or bottom-third base in play, and their mutants survive by design | python tools/rendfx.py --capture --state p1 --keys W --per 3 (d105f88) |
| 4 | 95D4: the port needs the ROM bytes $95D4 reads as data; manual 0.5 says ship neither the ROM nor a transcription -- embed them in the local asset bundle, or not? | no ROM bytes needed: $9673 reads $3100-$3312 (FP calculator code) only as the low byte C of (BC) at $9674/$9678, B=$39/$3A; ROM $3900-$3AFF is all $FF, so every byte copied is $FF whatever C is | python tools/adis.py 0x9664 20 (9306ac8) |
| 5 | A3FF: what does the JS substitute for R look like -- one 7-bit draw per AI pass with the measured fixed offsets for the later draws, or an M1-count model per path? | $A646, the $A16D draw mask, is rank table $B432[$A614] (written $A450): 0 only from rank 16; the $A181 draw is the $A16D draw + 13 M1, so $A18A falls through only when $A646 AND $73 = 0; derived and gated / an M1-count model per path: controlPass counts R from io.r plus every M1 it executes, and matches R and every draw on all 670 cases of build/callio_97cb.json, the 128-R sweeps included | python tools/adis.py 0xA402 40; python tools/build.py (a0bdc4b) |
| 6 | 9745: R at the CALL at $9757 (the AI draws) is R at $AE29 plus the M1 of $9C6F $9ED2 $9D29 and $B15A; every callee needs an M1 tally into M1.m1 -- every callee now tallies (gated per callee); left: the composed pass checked... | playPass, composed from the callees, matches the machine on all 130 driven pass cases and the quit: bytes, timer cells, T, A, R, port order; ROM-effect $FE writes in count, value and first T (D6 moves inner edges) | node test/kit.test.js (play_pass block; build/callio_ae29.json, 24 cases after callio --cover) (5c8b60c) |
| 7 | 9745: two composition mutants survive every driven whole-pass case: $9C29 left 0 for P1's step (the $97BB branches that read the opponent, $9920/$9994) and P2's step after the 2P yin-yang award; no pass case reaches them | derived pass case (case 19, $AA03=3, $AA56=1) sends P1's step through $9930, reading P2 via $9C29: kills "$9C29 left 0"; the yinYang2P/P2-step swap is equivalent (disjoint reads, writes; T126), now "P2 stepped after t... | python tools/callio.py --derive --state s1 --fixture build/callio_ae29.json --case 19 --set 0xAA03=3,0xAA56=1 (799d805) |
| 8 | AC09: the demo's ways out of $AE26 -- $ABCB (a point, the pose, rank up by $AF27, the next stage), the RET M quit to the $AC27 dispatch, round end $AE67 -- still stop the engine | the demo's points are played on by demoPoint ($ABCB, ledger ABCB); its other ways out (poses, time, quit, round end) are ABCB open 1 | node test/kit.test.js (demoPoint block (51e1460) |
| 9 | ABCB: the demo's ways on from demoPoint -- the poses at $AC00/$ABE5 then XOR A RET, time up, the round end $AE67 -- to $ABB9: $AF27 stage up, rank up, $AB97 the next demo stage or RET to $AC27 | the demo's poses, time up and the RET M lead to $ABB9; ported as demoOn (ledger ABB9), live through both poses | node test/kit.test.js (demo_abb9 block (09d70a5) |
| 10 | AE17: callio cannot replay a bracket from $AE17: $AE25 RET pops $ADE0 (the quit also $AC34) above the entry SP $5BFB, but up_io keeps 'up' only when the exit SP is above entry; the exit at $AE29 is below | callio records "up" for any POP/RET at or above the entry SP; --up takes WORD,WORD (2UP: $5BFB $ADE0, $5BFD $AC34); callio_ae17: 2 captured + 6 derived (no time up, quit, game end tie/P1/P2/hi), 0 disagree | python tools/callio.py --check --state p1 --fixture build/callio_ae17.json (5681414) |
| 11 | AD9C: the 2UP game's ways on from $AE17: round end, point, next round via $AE1F JR Z $AE14, bout won ($ADE2 on), high score at $ADF3 | answered by $AE17 (ledger/AE17.toml): its ways on ported and gated, callio_ae17 and live_2up to row 2400 / the mutant 'ad9c: Fist: the 2UP game's points played as 1UP' is now killed: live_2up scores P1 a 2UP point (row 599) | node test/kit.test.js; python tools/mutants.py --match "points played as 1UP" (35be24c) |
| 12 | AD9C: mutant 'ad9c: Fist: the 2UP game's points played as 1UP' survives: no gate scores a 2UP point yet (live_2up ends at time up) | answered by $AE17 (ledger/AE17.toml): its ways on ported and gated, callio_ae17 and live_2up to row 2400 / the mutant 'ad9c: Fist: the 2UP game's points played as 1UP' is now killed: live_2up scores P1 a 2UP point (row 599) | node test/kit.test.js; python tools/mutants.py --match "points played as 1UP" (35be24c) |
| 13 | AE17: the port: twoOn $AE17 to $AE29 (roundIn, a point) / $ADE5 (the tune: music '2next', then setupPass twoNext + stage2) / $AC34 (demoIn inline); twoEnd $ADF3 checkHighScore and a pose at sp+2, out by $AE12 winEnd into de... | round_ae17 gated: twoOn and its ways on as the engine runs them, 8 cases exact (bytes, PC, T, R, the tune's writes); recaptured with start2_ac27's text-cell blinds (D5), T and R unchanged / ported; live_2up (2400 passes) followed row for row: point 599, time ups 880 1301 1722, rank-4 end with P1's pose out to $AC34 and the demo at 2143; tune passes within 0.05%, end pass 0.37% under | python tools/build.py; python tools/callio.py --check --state p1 --fixture build/callio_ae17.json (35be24c) |
| 14 | AE17: gate callio_ae17 in kit.test.js: twoOn and twoNext/twoEnd against the 8 cases (point, quit to $AC34, time up, rank 3 game end tie/P1/P2/high score) | round_ae17 gated: twoOn and its ways on as the engine runs them, 8 cases exact (bytes, PC, T, R, the tune's writes); recaptured with start2_ac27's text-cell blinds (D5), T and R unchanged / ported; live_2up (2400 passes) followed row for row: point 599, time ups 880 1301 1722, rank-4 end with P1's pose out to $AC34 and the demo at 2143; tune passes within 0.05%, end pass 0.37% under | python tools/build.py; python tools/callio.py --check --state p1 --fixture build/callio_ae17.json (35be24c) |
| 15 | 8C54: how does the live loop run the menu across frames -- controlPass is synchronous; configs() yields before each IN and after each delay but nothing drives it incrementally yet | key 0 throws MenuSuspend at $9821; Fist.menuPass steps configs() to each IN or delay, T on the clock, keys live; at its RET the pass replays from its start with its recorded reads / menu from the demo (key 0, visit 400) runs inside one pass; RET with A=$80 to $ABCB, $ABB9, $AC27, Num_Players 0, a new demo by gameDispatch -- no new engine path; 118 reads for P1, 4, nine keys | python tools/build.py; python tools/sample.py (port.json live_menu note) --reads-at 0x8C54 --reads ... (19bb7c8) |
| 16 | ABB9: the demo's time up, round end ($AE67 into $ACF0, endPass by demoPoint) and the quit through roundPass -- not yet reached by live play | live_dtime follows the demo's time ups row for row: $AE67, $AD0B x3, demoPoint to $ABB9, on into a new demo (row 66, rank 4) and the next stage (1067); the quit via roundPass is live_1up's row 401 / demo time up charge: $AD0B passes 0.987-0.995 of the machine (live_time's own 0.980-1.018, D4 means), to $ABB9 0.9993 and 0.9996, stage passes 1.0004-1.0012 | node test/kit.test.js (demo time block: ratio of the engine's charge to live_dtime's t); python tools/sample.py (live's arguments) --from 4250 --passes 5420... (e3cbf15) |
| 17 | 8C54: why do the mutants "menu: Get_Key reads the next row" and "menu: sound off tests key 3" crash Node natively (row "11: 00007FF70D8ED4BA") instead of failing a row | menuRead throws 64 reads past the planned keys; the pass's catch fails the row | python tools/mutants.py --match "menu: Get_Key reads the next row\|\|menu: sound off tests key 3" --jobs 2 (517600a) |
| 18 | AD1B: can $9C28 hold a value >= $80, taking the RET M at $AD1C (pointPath 'quit', ported from the listing, ungated)? | $9C28 never holds >= $80: written only at $9CD5 (0) and $9B0A (from $AA03/$AA43: only 0, $16, $1A, $1B); the RET M at $AD1C is taken instead after round_loop's RET M at $AE2D, the 1UP quit / 1UP quit (G+H: A = $80, Num_Players 0): $AE2D, $AD1C RET M, $ACA6 JP M, $ACCF JR NZ, $ACD9 to $AC39 -- the lost way into the demo; onward+boutNext follow live_quit row for row (400 rows, quit at 36), its pass 0.9976 | port.json live_quit (python tools/sample.py --state p1 --script 10:,15:D,10:W,1:G+H,40:); python tools/grepbytes.py "28 9C" (b899af4) |
| 19 | AD44: is (IX) at $AE78 -- the first byte of the frame at word $C428 -- ever >= $80, taking the RET M at $AD1C after time up (pointPath quit)? | (IX) at $AE78 is never >= $80: every frame 0-58 ($44CC + word $C440+2n) starts with 1, 2 or 3; all 8 time ups in the live fixtures end on P1 frame $37 ($F3D4 = 1), and no fixture row holds a frame above 58 | python (image.bin: m[$44CC + word at $C440+2n] for n 0-58) (b899af4) |
| 20 | AD5F: why does the port write $0000-$0007 where the machine drops the write (ROM), in seeded worlds of ad5f, ae17, ae67, ad44, ad44d, aca6 -- all with $C42C-$C433 XOR $FF? | $C42C-$C433 XOR $FF outgrows the back buffer: the fill, decode and LDIRs wrap past $FFFF into ROM, which drops the store; the engine now drops stores below $4000 there, and --seed refuses a derive reading ROM as data... | node test/kit.test.js (the ROM drops a store) (401337b) |
| 21 | AC27: why does no --seed derive seed $9C2C under $AC27 (read, written back unchanged in every case)? | --seed drops $9C2C 1 (the 1UP way): 12.9M T passes its cap and it reads ROM glyphs the demo case never read | python tools/callio.py --derive --state p1 --fixture build/callio_ac27.json --case 0 --set 0x9C2C=0x01 (7257e53) |
| 22 | battery: does a P1 bout WIN (dan progression, bonus stage) or 2P play use a stack-unwinding idiom? | Q19 no stack imbalance: 0 discards, 0 rewrites, 0 fake returns, 0 LD SP cuts, ODD 0 in 1P losses and game over, the demo, a P1 bout win (stage2: pose, $ACA6, rank up $AC5F, next bout) and a real 2P game (key 2 from s1... | python tools/stackscan.py --state p1 --frames 15000 --mark 900E,9057,909E,A647 (3d73cd6) |
| 23 | battery: does the Spectrum tape have a bonus stage at all (D1 scope says any bonus stage)? | no bonus stage: a won bout leaves $ACA6 only by JP $AC5F or RET, stage $AF34 cycles 1-3 ($AF27); the one statically unreached ctl c-block, $B2FB-$B7FF, is data (read from $88EC $8A7C $8A95 $A40B, no PC inside) | python tools/adis.py 0xACA6 45 (74d1386) |

Refuted claims still on record:

| claim | refuted by |
|---|---|
| AE26: fact 3's way out -- the engine no longer stops at the RET NZ at $AE60: pointPath plays the point on (ledger AD1B) | node test/kit.test.js (round_loop live block) |

Lessons this port added to docs/TRAPS.md:

- T197 An engine throw outside a catch is a crash, not a kill
- T198 A long run that reads its revision when it ends credits the wrong commit
- T199 A gate that presses each key for one read never meets a human's scale

## 4. What is still open

Open questions in ledger/: 0.

Routines read but with no port function of their own:

- $A3FF Random_Number -- an M1-count model per path: controlPass counts R from io.r plus every M1 it executes, and matches R and every draw on all 670 cases of build/callio_97cb.json, the 128-R sweeps included

PROVISIONAL numbers in web/template.html: 0.


Our own inventions -- the substitutions of part 2, which are ours and not the original's: D5, D6.
