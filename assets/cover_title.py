"""Replace the 'INDIA DID IT FIRST' title on Cover Image.png with a new title + hook line.
Usage: python3 cover_title.py <cover.png> "<title>" "<hook>" <out.png>
Output is 1080x1920 (upscaled from the 756x1344 source)."""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

src, title, hook, out = sys.argv[1:5]
W, H = 1080, 1920
im = Image.open(src).convert("RGB").resize((W, H), Image.LANCZOS)
a = np.asarray(im).astype(float)

# --- 1. erase the old title (source y≈40–295 → ~57–421 at 1080 scale) ---
TOP, BOT = 0, 505          # band to rebuild (old title + pill)
src_full = Image.open(src).convert('RGB').resize((W, H), Image.LANCZOS)
PILL = src_full.crop((140, 442, 940, 500))  # 'POSITIVE NEWS • WORLD-CHANGING DISCOVERIES'
# take the sky colour from a thin strip just above the old title, per column, blurred
sky = a[8:40].mean(axis=0)                                   # (W,3)
sky = np.array(Image.fromarray(sky[None].astype(np.uint8)).resize((W, 1)).filter(ImageFilter.GaussianBlur(40)))[0].astype(float)
deep = np.array([10, 22, 48], float)                          # navy from the cover
band = np.zeros((BOT - TOP, W, 3))
for i in range(BOT - TOP):
    f = i / (BOT - TOP)
    band[i] = sky * (1 - f) + deep * f * 0.35 + sky * f * 0.65
# keep a few stars: random faint dots, deterministic
rng = np.random.default_rng(3)
for _ in range(120):
    y, x = rng.integers(0, BOT - TOP), rng.integers(0, W)
    band[y, x] = np.minimum(255, band[y, x] + rng.uniform(60, 160))
# feather the bottom 70px back into the original image
FE = 70
BOT2 = BOT + FE
band = np.concatenate([band, np.repeat(band[-1:], FE, 0)])
m = np.ones(BOT2 - TOP); m[-FE - 20:] = np.linspace(1, 0, FE + 20) ** 1.5
a[TOP:BOT2] = band * m[:, None, None] + a[TOP:BOT2] * (1 - m[:, None, None])
im = Image.fromarray(a.clip(0, 255).astype(np.uint8))

# --- 2. text helpers ---
BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
BOLD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
MAXW = W - 140

def wrap(text, font, maxw, draw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur); return lines

def balanced(text, font, maxw, draw, n):
    w = text.split()
    if n == 1 or len(w) < 2: return [text]
    best = None
    for i in range(1, len(w)):
        a_, b_ = " ".join(w[:i]), " ".join(w[i:])
        m_ = max(draw.textlength(a_, font=font), draw.textlength(b_, font=font))
        if best is None or m_ < best[0]: best = (m_, [a_, b_])
    return best[1]

def fit(text, path, start, minsize, maxlines, maxw):
    d = ImageDraw.Draw(im)
    for size in range(start, minsize - 1, -4):
        f = ImageFont.truetype(path, size)
        ls = wrap(text, f, maxw, d)
        if len(ls) == 2: ls = balanced(text, f, maxw, d, 2)
        if len(ls) <= maxlines and all(d.textlength(l, font=f) <= maxw for l in ls): return f, ls
    f = ImageFont.truetype(path, minsize); return f, wrap(text, f, maxw, d)

def gold_text(lines, font, y0, gap):
    """Gold gradient fill, dark bevel outline and drop shadow, centred."""
    global im
    d = ImageDraw.Draw(im)
    asc, desc = font.getmetrics(); lh = asc + desc
    mask = Image.new("L", (W, H), 0); md = ImageDraw.Draw(mask)
    y = y0
    for l in lines:
        x = (W - d.textlength(l, font=font)) / 2
        md.text((x, y), l, font=font, fill=255); y += lh + gap
    y1 = y
    shadow = mask.filter(ImageFilter.GaussianBlur(14))
    im = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, shadow.point(lambda v: int(v * .75)))
    outline = mask.filter(ImageFilter.MaxFilter(9))
    im = Image.composite(Image.new("RGB", (W, H), (92, 48, 8)), im, outline)
    ys = np.arange(H)[:, None]
    t = ((ys - y0) / max(1, (y1 - y0) / len(lines))) % 1.0       # repeat per line
    top, mid, bot = np.array([255, 244, 196]), np.array([247, 196, 72]), np.array([196, 120, 22])
    g = np.where(t < .5, top + (mid - top) * (t / .5), mid + (bot - mid) * ((t - .5) / .5))
    gimg = Image.fromarray(np.ascontiguousarray(np.broadcast_to(g[:, None, :], (H, W, 3))).astype(np.uint8))
    im = Image.composite(gimg, im, mask)
    return y1

# --- 3. title + hook + pill in the cleared band (must end by ~y 560) ---
LIMIT = 560
for tstart in range(150, 70, -8):
    tf, tl = fit(title.upper(), BLACK, tstart, 70, 2, MAXW)
    hf, hl = fit(hook, BOLD, 42, 30, 2, W - 180)
    asc, desc = tf.getmetrics(); ha, hd = hf.getmetrics()
    th = len(tl) * (asc + desc) - 10 * (len(tl) - 1)
    hh = len(hl) * (ha + hd + 6)
    block = th + 20 + hh + 22 + PILL.height
    if block <= LIMIT - 50 and len(hl) <= 2: break
y0 = 50 + max(0, (LIMIT - 50 - block) // 2)
y_end = gold_text(tl, tf, y0, -10)
d = ImageDraw.Draw(im)
y = y_end + 16
for l in hl:
    x = (W - d.textlength(l, font=hf)) / 2
    for dx, dy in [(0, 3), (2, 2), (-2, 2), (0, -1)]:
        d.text((x + dx, y + dy), l, font=hf, fill=(0, 0, 0))
    d.text((x, y), l, font=hf, fill=(255, 255, 255))
    y += ha + hd + 6
py = int(y + 18)
pm = Image.new("L", PILL.size, 0)
ImageDraw.Draw(pm).rounded_rectangle((6, 4, PILL.width - 7, PILL.height - 5), radius=24, fill=255)
im.paste(PILL, (140, py), pm.filter(ImageFilter.GaussianBlur(2)))
im.save(out)
print(out, "title", tl, tf.size, "hook", hl, hf.size, "pill bottom", py + PILL.height)
