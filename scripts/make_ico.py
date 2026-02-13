from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def main() -> int:
    if len(sys.argv) != 3:
        print('Usage: make_ico.py <src_png> <dst_ico>')
        return 2

    src = Path(sys.argv[1]).resolve()
    dst = Path(sys.argv[2]).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)

    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    im = Image.open(src).convert('RGBA')

    # Windows Explorer often prefers a 256x256 icon. Pillow won't upscale to larger
    # sizes when saving ICO, so ensure our base image is at least 256x256.
    max_size = max(w for w, _ in sizes)
    if im.width < max_size or im.height < max_size:
        im = im.resize((max_size, max_size), Image.LANCZOS)

    im.save(dst, format='ICO', sizes=sizes)
    print(f'Wrote {dst}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
