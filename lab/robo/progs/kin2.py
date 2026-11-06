"""2-link planar arm forward kinematics over 10000 angles.

Prints one checksum rounded to 6 decimal places. Uses math.sin/cos, the
example of a libm call that differs in the last bits between platforms.
"""

import math

L1 = 0.30
L2 = 0.25


def main() -> None:
    checksum = 0.0
    for k in range(10000):
        t = 0.001 * k
        q1 = math.sin(0.7 * t)
        q2 = 1.3 * math.sin(0.3 * t + 0.5)
        x = L1 * math.cos(q1) + L2 * math.cos(q1 + q2)
        y = L1 * math.sin(q1) + L2 * math.sin(q1 + q2)
        checksum = checksum + x + 0.5 * y
    print(round(checksum, 6))


main()
