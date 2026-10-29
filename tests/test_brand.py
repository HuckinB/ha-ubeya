"""Check locally bundled Home Assistant brand assets without Pillow."""

from __future__ import annotations

import struct
import unittest
from pathlib import Path


BRAND = Path(__file__).resolve().parents[1] / "custom_components" / "ubeya" / "brand"


def png_metadata(filename: str) -> tuple[int, int, int]:
    with (BRAND / filename).open("rb") as image:
        header = image.read(26)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("Not a PNG image")
    width, height = struct.unpack(">II", header[16:24])
    return width, height, header[25]


class UbeyaBrandTests(unittest.TestCase):
    def test_icons_have_correct_sizes_and_alpha(self):
        self.assertEqual((256, 256, 6), png_metadata("icon.png"))
        self.assertEqual((512, 512, 6), png_metadata("icon@2x.png"))


if __name__ == "__main__":
    unittest.main()
