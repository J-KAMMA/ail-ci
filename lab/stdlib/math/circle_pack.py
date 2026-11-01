import math

def area(radius):
    return math.pi * radius * radius

def ring(outer, inner):
    return area(outer) - area(inner)

def diagonal(width, height):
    return math.hypot(width, height)

def fit_count(width, height, radius):
    across = math.floor(width / (2.0 * radius))
    down = math.floor(height / (2.0 * radius))
    return across * down

def main():
    circles = [1.0, 2.5, 4.0]
    areas = [area(r) for r in circles]
    print("areas", [round(a, 3) for a in areas])
    print("total", round(math.fsum(areas), 3))
    print("ring", round(ring(4.0, 2.5), 3))
    print("diagonal", round(diagonal(3.0, 4.0), 3), "sqrt", round(math.sqrt(25.0), 3))
    print("fits", fit_count(20.0, 12.0, 1.5))
    print("quarter turn", round(math.radians(90.0), 6), round(math.degrees(math.pi / 2.0), 6))
    try:
        print(math.sqrt(-4.0))
    except ValueError as exc:
        print("sqrt failed:", exc)

main()
