#!/usr/bin/env python3
"""
gallery.py -- PNGs of every fighter pose and every background, drawn by the
game's own code in the harness (no decoder of ours in the loop).

  poses        the frame table at $C440 holds 59 offsets from $C4CC and a 60th, $F730, that
               ends the last frame (the back buffer).  For each frame the tool
               puts it in BOTH fighter records (P1 $AA12, P2 $AA52; x, y and
               facing as the state holds them, x pushed apart), zeroes the
               64-row shadow at $8000 and the display file, and CALLs
               render_fighters $BF13 with interrupts off; each fighter is cut
               from the screen by the bounding box of its set pixels.
  backgrounds  CALL $9200 with A = stage 1..3 (as $AB9A does after $AF27),
               the screen rendered with its attributes.

The fighters are pixels only; their colour on screen comes from the scenery's
attributes, so poses are written ink on transparent (--ink names the colour).

Output (tape-derived, never committed -- rule 7): build/gallery/
  pose_NN_p1.png, pose_NN_p2.png, poses_p1.png, poses_p2.png (contact sheets,
  labelled), background_N.png

Usage:
    python tools/gallery.py [--state s1] [--scale 3] [--out build/gallery]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw                                    # noqa: E402

from probeutil import boot_target                                   # noqa: E402
from screen import render, scr_addr                                 # noqa: E402

FRAMES = 59
P1X, P2X = 0x08, 0x48           # x in 2-pixel units: P1 at 16 px, P2 at 144 px
SPLIT = 128                     # screen px between the two fighters


def cut(m, lo, hi):
    """Bounding box of set pixels with x in [lo, hi): (x0, y0, rows of bits)."""
    pts = [(x, y) for y in range(192) for x in range(lo, hi)
           if m[scr_addr(x, y)] & (0x80 >> (x & 7))]
    if not pts:
        return None
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    return x0, y0, x1 - x0 + 1, y1 - y0 + 1, set(pts)


def sprite_png(box, ink, scale):
    x0, y0, w, h, pts = box
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    px = img.load()
    for x, y in pts:
        px[x - x0, y - y0] = ink + (255,)
    return img.resize((w * scale, h * scale), Image.NEAREST)


def sheet(imgs, scale, cols=10):
    cw = max(i.width for i in imgs if i) + 8 * scale
    ch = max(i.height for i in imgs if i) + 14 * scale
    rows = (len(imgs) + cols - 1) // cols
    out = Image.new('RGB', (cw * cols, ch * rows), (24, 24, 24))
    d = ImageDraw.Draw(out)
    for n, i in enumerate(imgs):
        cx, cy = (n % cols) * cw, (n // cols) * ch
        d.text((cx + 4, cy + 2), f'{n:02d}', fill=(160, 160, 160))
        if i:
            out.paste(i, (cx + (cw - i.width) // 2, cy + ch - i.height - 4 * scale), i)
    return out


def main():
    args = sys.argv[1:]
    state, scale, out = 's1', 3, 'build/gallery'
    ink = (255, 255, 255)
    while args:
        a = args.pop(0)
        if a == '--state':
            state = args.pop(0)
        elif a == '--scale':
            scale = int(args.pop(0))
        elif a == '--out':
            out = args.pop(0)
        elif a == '--ink':
            ink = tuple(int(v) for v in args.pop(0).split(','))
        else:
            sys.exit(__doc__)
    os.makedirs(out, exist_ok=True)
    h = boot_target({'state': state, 'snapshot': None, 'arm': False, 'warm': 0}, 'gallery')
    s0 = h.save_state()

    for stage in (1, 2, 3):
        h.load_state(s0)
        code, _, _ = h.call(0x9200, regs={'A': stage})
        if code != 0:
            sys.exit(f'gallery: $9200 stage {stage} did not return')
        img = render(h.mem)
        img.resize((256 * scale, 192 * scale), Image.NEAREST).save(f'{out}/background_{stage}.png')

    sheets = {1: [], 2: []}
    for f in range(FRAMES):
        h.load_state(s0)
        m = h.mem
        for a in range(0x8000, 0x8800):
            m[a] = 0
        for a in range(0x4000, 0x5800):
            m[a] = 0
        m[0xAA12] = m[0xAA52] = f
        m[0xAA19], m[0xAA59] = P1X, P2X
        code, _, _ = h.call(0xBF13)
        if code != 0:
            sys.exit(f'gallery: $BF13 frame {f} did not return')
        for p, (lo, hi) in ((1, (0, SPLIT)), (2, (SPLIT, 256))):
            box = cut(m, lo, hi)
            if box and (box[0] == lo or box[0] + box[2] == hi):
                sys.exit(f'gallery: frame {f} P{p} touches the split at {SPLIT} px')
            img = sprite_png(box, ink, scale) if box else None
            if img:
                img.save(f'{out}/pose_{f:02d}_p{p}.png')
            sheets[p].append(img)
    for p in (1, 2):
        sheet(sheets[p], scale).save(f'{out}/poses_p{p}.png')
    print(f'gallery: {FRAMES} poses x 2 fighters, 3 backgrounds -> {out}/')


if __name__ == '__main__':
    main()
