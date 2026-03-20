#!/usr/bin/env python3
"""
Generate PNG icons from SVG for PWA
Requires: uv pip install cairosvg
"""

from pathlib import Path
import cairosvg

SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
SVG_PATH = Path(__file__).parent / "icon.svg"
ICON_DIR = Path(__file__).parent

def generate_icons():
    for size in SIZES:
        output_path = ICON_DIR / f"icon-{size}x{size}.png"
        cairosvg.svg2png(
            url=str(SVG_PATH),
            write_to=str(output_path),
            output_width=size,
            output_height=size
        )
        print(f"Generated {output_path}")

if __name__ == "__main__":
    print("Generating PWA icons...")
    generate_icons()
    print("Done!")
