"""Mandelbrot escape counts on a grid; prints a checksum, not the picture."""
import sys

SMALL = "--small" in sys.argv
WIDTH = 90 if SMALL else 600
HEIGHT = 60 if SMALL else 420
MAX_ITER = 30 if SMALL else 160


def escape_count(cx, cy, limit):
    x = 0.0
    y = 0.0
    iteration = 0
    while x * x + y * y <= 4.0 and iteration < limit:
        x, y = x * x - y * y + cx, 2.0 * x * y + cy
        iteration += 1
    return iteration


checksum = 0
inside = 0
peak = 0
for row in range(HEIGHT):
    cy = -1.25 + 2.5 * row / HEIGHT
    for col in range(WIDTH):
        cx = -2.1 + 3.0 * col / WIDTH
        value = escape_count(cx, cy, MAX_ITER)
        checksum += value
        if value == MAX_ITER:
            inside += 1
        if value > peak:
            peak = value

print("width", WIDTH)
print("height", HEIGHT)
print("iterations", MAX_ITER)
print("checksum", checksum)
print("inside", inside)
print("peak", peak)
