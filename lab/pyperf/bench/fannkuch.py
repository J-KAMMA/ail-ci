"""Fannkuch redux: flip the first k cards of each permutation until the ace is up.

Permutations are generated in place with the Johnson-Trotter rotation of the
first r entries; every sign comes from the permutation number parity.  The
program prints the alternating checksum and the largest flip count.
"""
import sys


def fannkuch(n):
    perm = list(range(n))
    perm1 = list(range(n))
    count = [0] * n
    max_flips = 0
    checksum = 0
    perm_count = 0
    r = n
    while True:
        while r != 1:
            count[r - 1] = r
            r -= 1
        if perm1[0] != 0 or perm1[n - 1] != n - 1:
            i = 0
            while i < n:
                perm[i] = perm1[i]
                i += 1
            flips = 0
            k = perm[0]
            while k != 0:
                i = 0
                while i < (k + 1) >> 1:
                    t = perm[i]
                    perm[i] = perm[k - i]
                    perm[k - i] = t
                    i += 1
                flips += 1
                k = perm[0]
            if flips > max_flips:
                max_flips = flips
            if perm_count % 2 == 0:
                checksum += flips
            else:
                checksum -= flips
            perm_count += 1
        while True:
            if r == n:
                return checksum, max_flips
            t = perm1[0]
            i = 0
            while i < r:
                perm1[i] = perm1[i + 1]
                i += 1
            perm1[r] = t
            count[r] -= 1
            if count[r] > 0:
                break
            r += 1


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    checksum, max_flips = fannkuch(n)
    print("Pfannkuchen(%d) = %d" % (n, checksum))
    print(max_flips)


main()
