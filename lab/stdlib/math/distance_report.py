import math

def length(point):
    return math.hypot(point[0], point[1])

def distance(a, b):
    return math.dist(a, b)

def perimeter(points):
    total = 0.0
    for i in range(len(points)):
        total += distance(points[i], points[(i + 1) % len(points)])
    return total

def main():
    route = [[0.0, 0.0], [3.0, 4.0], [6.0, 4.0], [6.0, 0.0]]
    for i, point in enumerate(route):
        print(i, point, round(length(point), 6))
    print("edge", round(distance(route[0], route[1]), 6))
    print("perimeter", round(perimeter(route), 6))
    print("same", distance(route[0], route[0]))
    lengths = [length(p) for p in route]
    print("flat", round(math.fsum(lengths), 6))
    try:
        print(distance([1.0, 2.0], [3.0]))
    except ValueError as exc:
        print("dist failed:", exc)
    try:
        print(math.sqrt(-9.0))
    except ValueError as exc:
        print("sqrt failed:", exc)

main()
