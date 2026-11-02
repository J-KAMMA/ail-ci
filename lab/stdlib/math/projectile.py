import math

def flight_time(speed, angle):
    radians = math.radians(angle)
    return 2.0 * speed * math.sin(radians) / 9.81

def range_of(speed, angle):
    radians = math.radians(angle)
    return speed * speed * math.sin(2.0 * radians) / 9.81

def peak_height(speed, angle):
    radians = math.radians(angle)
    return (speed * math.sin(radians)) ** 2 / (2.0 * 9.81)

def launch_angle(distance, speed):
    ratio = distance * 9.81 / (speed * speed)
    return math.degrees(0.5 * math.asin(ratio))

def main():
    speed = 25.0
    for angle in (15.0, 30.0, 45.0, 60.0, 75.0):
        print(angle, round(range_of(speed, angle), 3), round(peak_height(speed, angle), 3))
    print("time", round(flight_time(speed, 45.0), 3))
    print("angle", round(launch_angle(range_of(speed, 45.0), speed), 6))
    print("floor", math.floor(peak_height(speed, 45.0)))
    print("same", math.isclose(range_of(speed, 15.0), range_of(speed, 75.0)))
    try:
        print(math.sqrt(-1.0))
    except ValueError as exc:
        print("sqrt failed:", exc)
    try:
        print(math.asin(2.0))
    except ValueError as exc:
        print("asin failed:", exc)

main()
