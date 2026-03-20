#!/usr/bin/env python3
"""conformance_compare.py — Bitexact conformance comparison.

Compares RTL decoder/encoder output against golden reference (JM/HM/VTM)
for standards conformance testing (H.264/H.265).

Usage:
    python3 conformance_compare.py \
        --golden golden/decoded.yuv \
        --actual sim/output.yuv \
        [--format yuv420|raw] \
        [--width 1920 --height 1080] \
        [--md5]

Exit code: 0 = PASS (bitexact match), 1 = FAIL
"""

import argparse
import hashlib
import sys


def md5_file(filepath):
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compare_binary(golden_path, actual_path):
    """Byte-by-byte comparison, returns first mismatch position or -1."""
    with open(golden_path, "rb") as fg, open(actual_path, "rb") as fa:
        pos = 0
        while True:
            bg = fg.read(4096)
            ba = fa.read(4096)

            if not bg and not ba:
                return -1  # identical

            if len(bg) != len(ba):
                # Find exact position
                min_len = min(len(bg), len(ba))
                for i in range(min_len):
                    if bg[i] != ba[i]:
                        return pos + i
                return pos + min_len  # length difference

            for i in range(len(bg)):
                if bg[i] != ba[i]:
                    return pos + i

            pos += len(bg)


def compute_frame_location(byte_pos, width, height, fmt="yuv420"):
    """Convert byte position to frame number and pixel location."""
    if fmt == "yuv420":
        frame_size = width * height * 3 // 2
    else:
        frame_size = width * height  # raw

    if frame_size == 0:
        return {"frame": 0, "offset": byte_pos}

    frame_num = byte_pos // frame_size
    frame_offset = byte_pos % frame_size
    return {"frame": frame_num, "offset": frame_offset}


def main():
    parser = argparse.ArgumentParser(description="Conformance bitexact comparison")
    parser.add_argument("--golden", required=True, help="Golden reference output")
    parser.add_argument("--actual", required=True, help="RTL simulation output")
    parser.add_argument("--format", choices=["yuv420", "raw"], default="yuv420")
    parser.add_argument("--width", type=int, default=0, help="Frame width (for location)")
    parser.add_argument("--height", type=int, default=0, help="Frame height (for location)")
    parser.add_argument("--md5", action="store_true", help="Print MD5 hashes")
    args = parser.parse_args()

    print(f"Golden:  {args.golden}")
    print(f"Actual:  {args.actual}")

    if args.md5:
        md5_g = md5_file(args.golden)
        md5_a = md5_file(args.actual)
        print(f"MD5 golden: {md5_g}")
        print(f"MD5 actual: {md5_a}")
        if md5_g == md5_a:
            print("RESULT: PASS (MD5 match)")
            return 0
        else:
            print("RESULT: FAIL (MD5 mismatch)")
            return 1

    mismatch_pos = compare_binary(args.golden, args.actual)

    if mismatch_pos == -1:
        print("RESULT: PASS (bitexact match)")
        return 0

    print(f"RESULT: FAIL")
    print(f"  First mismatch at byte {mismatch_pos}")

    if args.width > 0 and args.height > 0:
        loc = compute_frame_location(mismatch_pos, args.width, args.height, args.format)
        print(f"  Frame: {loc['frame']}, offset in frame: {loc['offset']}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
