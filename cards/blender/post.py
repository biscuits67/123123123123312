"""Film look for the rendered frames, then MP4.

    python post.py            -> renders/post/*.png + ../emerald_blender.mp4

Bloom on the neon and highlights, emerald grade with deep blacks, slight chromatic aberration
towards the edges, vignette and fine film grain. Needs Pillow, numpy and ffmpeg.
"""
import glob
import os
import subprocess

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "renders", "frames")
DST = os.path.join(HERE, "renders", "post")
OUT = os.path.join(os.path.dirname(HERE), "emerald_blender.mp4")
FPS = 24


def bloom(img):
    a = np.asarray(img, dtype=np.float32) / 255
    lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    mask = np.clip((lum - 0.62) / 0.38, 0, 1)[..., None]
    hi = Image.fromarray((a * mask * 255).astype(np.uint8))
    glow = np.zeros_like(a)
    for radius, weight in ((6, 0.55), (22, 0.45), (60, 0.35)):
        glow += np.asarray(hi.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255 * weight
    return a + glow * np.array([0.75, 1.0, 0.85], dtype=np.float32)


def grade(a, i):
    h, w, _ = a.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = (xx / w - 0.5), (yy / h - 0.5)
    r2 = dx * dx + dy * dy
    # chromatic aberration: shift red out, blue in, growing towards the corners
    shift = (r2 * 10).astype(np.float32)
    def sample(ch, k):
        sx = np.clip(xx + dx * shift * k * w * 0.0009, 0, w - 1).astype(np.int32)
        sy = np.clip(yy + dy * shift * k * h * 0.0009, 0, h - 1).astype(np.int32)
        return a[sy, sx, ch]
    a = np.stack([sample(0, 1.0), a[..., 1], sample(2, -1.0)], axis=-1)
    # contrast curve with deep blacks + emerald tint in the shadows
    a = np.clip(a, 0, None)
    a = a / (1 + a * 0.12)
    a = np.clip((a - 0.025) * 1.12, 0, None) ** 1.08
    shadow = np.clip(1 - a.mean(-1, keepdims=True) * 3, 0, 1)
    a = a + shadow * np.array([-0.004, 0.012, 0.006], dtype=np.float32)
    # vignette
    a *= (1 - np.clip((np.sqrt(r2) - 0.32) / 0.5, 0, 1) ** 1.6 * 0.7)[..., None]
    # grain (fresh every frame)
    rng = np.random.default_rng(i)
    a += rng.normal(0, 0.018, a.shape[:2]).astype(np.float32)[..., None]
    return np.clip(a, 0, 1)


def main():
    os.makedirs(DST, exist_ok=True)
    frames = sorted(glob.glob(os.path.join(SRC, "*.png")))
    for i, f in enumerate(frames):
        out = os.path.join(DST, os.path.basename(f))
        img = Image.open(f).convert("RGB")
        Image.fromarray((grade(bloom(img), i) * 255).astype(np.uint8)).save(out)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(DST, "%04d.png"),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT],
                   check=True)
    print(OUT, round(os.path.getsize(OUT) / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
