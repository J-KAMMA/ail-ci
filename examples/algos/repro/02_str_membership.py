"""Reproducer: `str in list[str]` is refused, so the small-size switch falls back."""
import sys

if "--small" in sys.argv:
    print("small")
else:
    print("full")
