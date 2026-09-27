from __future__ import annotations

import struct
from pathlib import Path


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "assets" / "app.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    sizes = (16, 24, 32, 48, 64, 128, 256)
    images = [_make_dib(size) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries = bytearray()
    for size, dib in zip(sizes, images):
        entries.extend(
            struct.pack(
                "<BBBBHHII",
                0 if size == 256 else size,
                0 if size == 256 else size,
                0,
                0,
                1,
                32,
                len(dib),
                offset,
            )
        )
        offset += len(dib)
    out.write_bytes(header + entries + b"".join(images))


def _make_dib(size: int) -> bytes:
    pixels = []
    cx = cy = size / 2
    radius = size * 0.34
    for y in range(size - 1, -1, -1):
        for x in range(size):
            dx = x + 0.5 - cx
            dy = y + 0.5 - cy
            if (dx * dx + dy * dy) <= radius * radius:
                pixels.append((0xAC, 0xB6, 0x4D, 0xFF))
            else:
                pixels.append((0x20, 0x1B, 0x18, 0xFF))

    xor = bytearray()
    for b, g, r, a in pixels:
        xor.extend((b, g, r, a))
    mask_stride = ((size + 31) // 32) * 4
    and_mask = bytes(mask_stride * size)
    dib = struct.pack(
        "<IIIHHIIIIII",
        40,
        size,
        size * 2,
        1,
        32,
        0,
        len(xor),
        0,
        0,
        0,
        0,
    ) + bytes(xor) + and_mask
    return dib


if __name__ == "__main__":
    main()
