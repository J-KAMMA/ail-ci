"""SciMark FFT: an iterative radix-2 Cooley-Tukey transform, repeated.

The input is built from the index (a triangle wave), the bit-reversal and the
butterfly stages run in place, and a checksum of the magnitudes of the result
is printed.  All arithmetic is double precision.
"""
import sys
import math

PI2 = 2.0 * 3.141592653589793


def fft(xr, xi, n):
    j = 0
    i = 1
    while i < n:
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            t = xr[i]
            xr[i] = xr[j]
            xr[j] = t
            t = xi[i]
            xi[i] = xi[j]
            xi[j] = t
        i += 1
    length = 2
    while length <= n:
        half = length >> 1
        ang = -PI2 / length
        wr = math.cos(ang)
        wi = math.sin(ang)
        i = 0
        while i < n:
            cr = 1.0
            ci = 0.0
            k = 0
            while k < half:
                a = i + k
                b = a + half
                vr = xr[b] * cr - xi[b] * ci
                vi = xr[b] * ci + xi[b] * cr
                xr[b] = xr[a] - vr
                xi[b] = xi[a] - vi
                xr[a] = xr[a] + vr
                xi[a] = xi[a] + vi
                nr = cr * wr - ci * wi
                ci = cr * wi + ci * wr
                cr = nr
                k += 1
            i += length
        length = length << 1


def run(n, reps):
    xr = [0.0] * n
    xi = [0.0] * n
    rep = 0
    total = 0.0
    while rep < reps:
        i = 0
        while i < n:
            xr[i] = i * 0.001
            xi[i] = 0.0
            i += 1
        fft(xr, xi, n)
        total += math.fabs(xr[1]) + math.fabs(xi[1])
        rep += 1
    return total


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2048
    reps = 400
    print("%.9f" % run(n, reps))


main()
