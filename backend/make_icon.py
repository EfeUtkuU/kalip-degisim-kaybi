"""icon.icns üretir (yalnızca numpy + macOS 'iconutil'): turuncu zemin üzerinde aralıklı iki blok (kalıp işareti)."""
import os
import struct
import subprocess
import tempfile
import zlib

import numpy as np


def rrect(h, w, x0, y0, x1, y1, r):
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    cx = np.clip(xx, x0 + r, x1 - r)
    cy = np.clip(yy, y0 + r, y1 - r)
    d = np.hypot(xx - cx, yy - cy) - r
    return np.clip(0.5 - d, 0, 1)  # kenar yumuşatma


def make(size):
    s = size
    img = np.zeros((s, s, 4), float)

    def paint(mask, rgb):
        for i in range(3):
            img[..., i] = img[..., i] * (1 - mask) + rgb[i] * mask
        img[..., 3] = np.maximum(img[..., 3], mask)

    m = 0.06 * s
    paint(rrect(s, s, m, m, s - m, s - m, 0.2 * s), (201 / 255, 133 / 255, 60 / 255))
    w, h = 0.5 * s, 0.14 * s
    x0 = (s - w) / 2
    paint(rrect(s, s, x0, 0.30 * s, x0 + w, 0.30 * s + h, 0.03 * s), (26 / 255, 18 / 255, 6 / 255))
    paint(rrect(s, s, x0, 0.56 * s, x0 + w, 0.56 * s + h, 0.03 * s), (26 / 255, 18 / 255, 6 / 255))
    paint(rrect(s, s, 0.44 * s, 0.44 * s, 0.56 * s, 0.56 * s, 0.02 * s), (1.0, 0.85, 0.68))
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def png(arr):
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    with tempfile.TemporaryDirectory() as t:
        iconset = os.path.join(t, "icon.iconset")
        os.makedirs(iconset)
        for base in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                open(os.path.join(iconset, f"icon_{base}x{base}{'@2x' if scale == 2 else ''}.png"), "wb").write(png(make(base * scale)))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", os.path.join(here, "icon.icns")], check=True)
    print("icon.icns hazır")
