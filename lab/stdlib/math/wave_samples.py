import math

def sample(degrees, offset):
    angle = math.radians(degrees)
    return math.sin(angle) + offset * math.cos(angle)

def peak_angle(offset):
    angle = math.atan(offset)
    return math.degrees(angle)

def main():
    offset = 0.5
    values = []
    for step in range(0, 181, 30):
        values.append(round(sample(step, offset), 6))
    print("samples", values)
    print("peak", round(peak_angle(offset), 6))
    print("tan", round(math.tan(math.radians(45.0)), 6))
    print("identity", math.isclose(math.sin(0.0) ** 2 + math.cos(0.0) ** 2, 1.0))
    print("negative", round(sample(-90.0, offset), 6))
    try:
        print(math.asin(2.0))
    except ValueError as exc:
        print("asin failed:", exc)
    try:
        print(math.acosh(0.5))
    except ValueError as exc:
        print("acosh failed:", exc)

main()
