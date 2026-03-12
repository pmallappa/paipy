#!/usr/bin/env python3
"""
PAI Logo - Figlet-style A + I

Classic ASCII art style like figlet/toilet
- A blocky "A" where the P is hidden through color
- P portion (left leg + top + crossbar) = purple
- Right leg of A (below crossbar) = blue
- I next to it in cyan
"""


def rgb(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


R = "\x1b[0m"

# P portion (left leg + top + crossbar of A) - Purple
P = rgb(187, 154, 247)

# Right leg of A (below the P/crossbar) - Blue
A = rgb(122, 162, 247)

# I pillar - Cyan
I = rgb(125, 207, 255)

# The logo: A with P hidden inside + I
logo = [
    f"{P}\u2588\u2588\u2588\u2588\u2588\u2588\u2588{R} {I}\u2588\u2588{R}",
    f"{P}\u2588\u2588{R}   {A}\u2588\u2588{R} {I}\u2588\u2588{R}",
    f"{P}\u2588\u2588\u2588\u2588\u2588\u2588\u2588{R} {I}\u2588\u2588{R}",
    f"{P}\u2588\u2588{R}   {A}\u2588\u2588{R} {I}\u2588\u2588{R}",
    f"{P}\u2588\u2588{R}   {A}\u2588\u2588{R} {I}\u2588\u2588{R}",
]


def print_logo() -> None:
    print()
    for line in logo:
        print(line)
    print()


def get_logo() -> list[str]:
    return logo


if __name__ == "__main__":
    print_logo()
