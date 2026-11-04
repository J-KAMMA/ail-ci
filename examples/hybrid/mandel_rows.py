"""Mandelbrot escape iterations, with the ASCII picture made by Python.

`mandel_checksum` is the hot function: integer width/height in, an integer checksum out, all
float work inside.  The small ASCII image is deliberately produced by plain Python so the
example shows the hybrid split rather than moving every loop into the extension.
"""
import sys


def mandel_checksum(width: int, height: int) -> int:
    total = 0
    y = 0
    while y < height:
        ci = -1.2 + y * 0.0375
        x = 0
        while x < width:
            cr = -2.0 + x * 0.04
            zr = 0.0
            zi = 0.0
            i = 0
            while i < 60:
                zr2 = zr * zr
                zi2 = zi * zi
                if zr2 + zi2 > 4.0:
                    i = 60
                else:
                    zi = 2.0 * zr * zi + ci
                    zr = zr2 - zi2 + cr
                    i += 1
            total += i
            x += 1
        y += 1
    return total


def ascii_image(width, height):
    lines = []
    for py in range(height):
        ci = -1.2 + py * 0.075
        line = ""
        for px in range(width):
            cr = -2.0 + px * 0.09
            zr = 0.0
            zi = 0.0
            i = 0
            while i < 30 and zr * zr + zi * zi <= 4.0:
                zr, zi = zr * zr - zi * zi + cr, 2.0 * zr * zi + ci
                i += 1
            line += "#" if i == 30 else " "
        lines.append(line)
    return lines


def main():
    scale = 3000
    if len(sys.argv) > 1:
        scale = int(sys.argv[1])
    height = scale // 2
    print("mandel checksum %d" % mandel_checksum(scale, height))
    for line in ascii_image(40, 20):
        print(line)


main()
