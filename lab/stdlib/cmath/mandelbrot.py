import cmath


def escape_steps(c: complex, limit: int) -> int:
    z = complex(0.0, 0.0)
    n = 0
    while n < limit and abs(z) <= 2.0:
        z = z * z + c
        n = n + 1
    if not cmath.isfinite(z):
        return limit
    return n


def main() -> None:
    rows = 5
    cols = 16
    limit = 12
    for row in range(rows):
        line = ""
        for col in range(cols):
            x = -2.0 + 2.5 * col / (cols - 1)
            y = 1.0 - 2.0 * row / (rows - 1)
            c = complex(x, y)
            steps = escape_steps(c, limit)
            if steps >= limit:
                line = line + "#"
            elif steps >= limit // 2:
                line = line + "+"
            else:
                line = line + "."
        print(line)
    probes: list[complex] = [complex(0.0, 0.0), complex(-1.0, 0.0), complex(2.0, 2.0)]
    for c in probes:
        steps = escape_steps(c, limit)
        angle = cmath.phase(c)
        print(repr(c), steps, "phase", angle, "finite", cmath.isfinite(c))
    print("inside", cmath.isclose(complex(-1.0, 0.0), complex(-1.0, 0.0)))


main()
