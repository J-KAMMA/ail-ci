"""N-body: the sun and four gas giants advanced by symplectic steps.

The program is the classic nbody kernel: seven floats per body (position,
velocity, mass), pairwise gravitational acceleration, then the energy of the
system printed before and after the requested number of 0.01-day steps.
"""
import sys
import math

PI = 3.141592653589793
DAYS_PER_YEAR = 365.24
SOLAR_MASS = 4 * PI * PI


def advance(bodies, dt):
    n = len(bodies)
    i = 0
    while i < n:
        bi = bodies[i]
        bix = bi[0]
        biy = bi[1]
        biz = bi[2]
        j = i + 1
        while j < n:
            bj = bodies[j]
            dx = bix - bj[0]
            dy = biy - bj[1]
            dz = biz - bj[2]
            d2 = dx * dx + dy * dy + dz * dz
            mag = dt / (d2 * math.sqrt(d2))
            bj[3] = bj[3] + dx * mag * bi[6]
            bj[4] = bj[4] + dy * mag * bi[6]
            bj[5] = bj[5] + dz * mag * bi[6]
            bi[3] = bi[3] - dx * mag * bj[6]
            bi[4] = bi[4] - dy * mag * bj[6]
            bi[5] = bi[5] - dz * mag * bj[6]
            j += 1
        i += 1
    i = 0
    while i < n:
        b = bodies[i]
        b[0] = b[0] + dt * b[3]
        b[1] = b[1] + dt * b[4]
        b[2] = b[2] + dt * b[5]
        i += 1


def energy(bodies):
    e = 0.0
    n = len(bodies)
    i = 0
    while i < n:
        bi = bodies[i]
        vx = bi[3]
        vy = bi[4]
        vz = bi[5]
        e += 0.5 * bi[6] * (vx * vx + vy * vy + vz * vz)
        j = i + 1
        while j < n:
            bj = bodies[j]
            dx = bi[0] - bj[0]
            dy = bi[1] - bj[1]
            dz = bi[2] - bj[2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            e -= bi[6] * bj[6] / d
            j += 1
        i += 1
    return e


def offset_momentum(bodies):
    px = 0.0
    py = 0.0
    pz = 0.0
    i = 0
    while i < len(bodies):
        b = bodies[i]
        px += b[3] * b[6]
        py += b[4] * b[6]
        pz += b[5] * b[6]
        i += 1
    sun = bodies[0]
    sun[3] = -px / SOLAR_MASS
    sun[4] = -py / SOLAR_MASS
    sun[5] = -pz / SOLAR_MASS


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400000
    bodies = [
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, SOLAR_MASS],
        [4.84143144246472090e+00, -1.16032004402742839e+00, -1.03622044471123109e-01,
         1.66007664274403694e-03 * DAYS_PER_YEAR, 7.69901118419740425e-03 * DAYS_PER_YEAR,
         -6.90460016972063023e-05 * DAYS_PER_YEAR, 9.54791938424326609e-04 * SOLAR_MASS],
        [8.34336671824457987e+00, 4.12479856412430479e+00, -4.03523417114321381e-01,
         -2.76742510726862411e-03 * DAYS_PER_YEAR, 4.99852801234917238e-03 * DAYS_PER_YEAR,
         2.30417297573763929e-05 * DAYS_PER_YEAR, 2.85885980666130812e-04 * SOLAR_MASS],
        [1.28943695621391310e+01, -1.51111514016986312e+01, -2.23307578892655734e-01,
         2.96460137564761618e-03 * DAYS_PER_YEAR, 2.37847173959480950e-03 * DAYS_PER_YEAR,
         -2.96589568540237556e-05 * DAYS_PER_YEAR, 4.36624404335156298e-05 * SOLAR_MASS],
        [1.53796971148509165e+01, -2.59193146099879641e+01, 1.79258772950371181e-01,
         2.68067772490389322e-03 * DAYS_PER_YEAR, 1.62824170038242295e-03 * DAYS_PER_YEAR,
         -9.51592254519715870e-05 * DAYS_PER_YEAR, 5.15138902046611451e-05 * SOLAR_MASS],
    ]
    offset_momentum(bodies)
    print("%.9f" % energy(bodies))
    i = 0
    while i < n:
        advance(bodies, 0.01)
        i += 1
    print("%.9f" % energy(bodies))


main()
