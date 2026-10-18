# -*- coding: utf-8 -*-
# prelude_random.py -- `random.Random(seed)` as Python source: CPython 3.12's Mersenne Twister and the methods built
# on it, bit for bit. (randlib.py injects it; tests import it and compare with random.Random.)
#
# An int seed only (the key is the absolute value in 32-bit words, as _random.Random.seed does). Not built:
# seeds that are str / bytes / float / None, getstate / setstate, randbytes, and the distributions other than uniform,
# gauss, normalvariate, expovariate and triangular.


class Random:
    def __init__(self, seed: int):
        self.mt = [0] * 624
        self.mti = 624
        self.has_gauss = False
        self.gauss_next = 0.0
        self.seed(seed)

    def seed(self, a: int):
        n = a
        if n < 0:
            n = -n
        key = []
        if n == 0:
            key.append(0)
        while n > 0:
            key.append(n % 4294967296)
            n = n // 4294967296
        mt = self.mt
        mt[0] = 19650218
        i = 1
        while i < 624:
            prev = mt[i - 1]
            mt[i] = (1812433253 * (prev ^ (prev >> 30)) + i) % 4294967296
            i = i + 1
        i = 1
        j = 0
        klen = len(key)
        k = 624
        if klen > k:
            k = klen
        while k > 0:
            prev = mt[i - 1]
            mt[i] = ((mt[i] ^ ((prev ^ (prev >> 30)) * 1664525)) + key[j] + j) % 4294967296
            i = i + 1
            j = j + 1
            if i >= 624:
                mt[0] = mt[623]
                i = 1
            if j >= klen:
                j = 0
            k = k - 1
        k = 623
        while k > 0:
            prev = mt[i - 1]
            mt[i] = ((mt[i] ^ ((prev ^ (prev >> 30)) * 1566083941)) - i) % 4294967296
            i = i + 1
            if i >= 624:
                mt[0] = mt[623]
                i = 1
            k = k - 1
        mt[0] = 2147483648
        self.mti = 624
        self.has_gauss = False

    def _refill(self):
        mt = self.mt
        kk = 0
        while kk < 227:
            y = (mt[kk] & 2147483648) | (mt[kk + 1] & 2147483647)
            v = mt[kk + 397] ^ (y >> 1)
            if y & 1 == 1:
                v = v ^ 2567483615
            mt[kk] = v
            kk = kk + 1
        while kk < 623:
            y = (mt[kk] & 2147483648) | (mt[kk + 1] & 2147483647)
            v = mt[kk - 227] ^ (y >> 1)
            if y & 1 == 1:
                v = v ^ 2567483615
            mt[kk] = v
            kk = kk + 1
        y = (mt[623] & 2147483648) | (mt[0] & 2147483647)
        v = mt[396] ^ (y >> 1)
        if y & 1 == 1:
            v = v ^ 2567483615
        mt[623] = v
        self.mti = 0

    def _genrand(self) -> int:
        if self.mti >= 624:
            self._refill()
        y = self.mt[self.mti]
        self.mti = self.mti + 1
        y = y ^ (y >> 11)
        y = y ^ ((y << 7) & 2636928640)
        y = y ^ ((y << 15) & 4022730752)
        y = y ^ (y >> 18)
        return y

    def random(self) -> float:
        a = self._genrand() >> 5
        b = self._genrand() >> 6
        return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0)

    def getrandbits(self, k: int) -> int:
        if k < 0:
            raise ValueError("number of bits must be non-negative")
        if k == 0:
            return 0
        if k <= 32:
            return self._genrand() >> (32 - k)
        if k > 62:
            raise RuntimeError("getrandbits: more than 62 bits needs integers beyond 64 bits")
        words = (k - 1) // 32 + 1
        r = 0
        shift = 0
        kk = k
        w = 0
        while w < words:
            x = self._genrand()
            if kk < 32:
                x = x >> (32 - kk)
            r = r | (x << shift)
            shift = shift + 32
            kk = kk - 32
            w = w + 1
        return r

    def _randbelow(self, n: int) -> int:
        if n <= 0:
            return 0
        k = 0
        m = n
        while m > 0:
            k = k + 1
            m = m >> 1
        r = self.getrandbits(k)
        while r >= n:
            r = self.getrandbits(k)
        return r

    def randrange(self, start: int, stop=None, step: int = 1) -> int:
        if stop is None:
            if start > 0:
                return self._randbelow(start)
            raise ValueError("empty range for randrange()")
        width = stop - start
        if step == 1:
            if width > 0:
                return start + self._randbelow(width)
            raise ValueError("empty range in randrange(%d, %d)" % (start, stop))
        if step > 0:
            n = (width + step - 1) // step
        elif step < 0:
            n = (width + step + 1) // step
        else:
            raise ValueError("zero step for randrange()")
        if n <= 0:
            raise ValueError("empty range in randrange(%d, %d, %d)" % (start, stop, step))
        return start + step * self._randbelow(n)

    def randint(self, a: int, b: int) -> int:
        return self.randrange(a, b + 1)

    def choice(self, seq):
        if not isinstance(seq, list):
            seq = list(seq)
        n = len(seq)
        if n == 0:
            raise IndexError("Cannot choose from an empty sequence")
        return seq[self._randbelow(n)]

    def shuffle(self, x):
        i = len(x) - 1
        while i >= 1:
            j = self._randbelow(i + 1)
            t = x[i]
            x[i] = x[j]
            x[j] = t
            i = i - 1

    def sample(self, population, k: int):
        if not isinstance(population, list):
            population = list(population)
        n = len(population)
        if k < 0 or k > n:
            raise ValueError("Sample larger than population or is negative")
        result = []
        setsize = 21
        if k > 5:
            m = 0
            p = 1
            while p < k * 3:
                p = p * 4
                m = m + 1
            setsize = setsize + 4 ** m
        if n <= setsize:
            pool = list(population)
            i = 0
            while i < k:
                j = self._randbelow(n - i)
                result.append(pool[j])
                pool[j] = pool[n - i - 1]
                i = i + 1
        else:
            selected = set()
            i = 0
            while i < k:
                j = self._randbelow(n)
                while j in selected:
                    j = self._randbelow(n)
                selected.add(j)
                result.append(population[j])
                i = i + 1
        return result

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.random()

    def gauss(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        if self.has_gauss:
            z = self.gauss_next
            self.has_gauss = False
        else:
            x2pi = self.random() * 6.283185307179586
            g2rad = math.sqrt(-2.0 * math.log(1.0 - self.random()))
            z = math.cos(x2pi) * g2rad
            self.gauss_next = math.sin(x2pi) * g2rad
            self.has_gauss = True
        return mu + z * sigma

    def expovariate(self, lambd: float) -> float:
        return -math.log(1.0 - self.random()) / lambd

    def triangular(self, low: float = 0.0, high: float = 1.0, mode=None) -> float:
        u = self.random()
        c = 0.5
        if mode is not None:
            if high == low:
                return low
            c = (mode - low) / (high - low)
        if high == low:
            return low
        if u > c:
            u = 1.0 - u
            c = 1.0 - c
            t = low
            low = high
            high = t
        return low + (high - low) * math.sqrt(u * c)

    def choices(self, population, weights=None, k: int = 1):
        if not isinstance(population, list):
            population = list(population)
        n = len(population)
        out = []
        if weights is None:
            i = 0
            while i < k:
                out.append(population[int(self.random() * n)])
                i = i + 1
            return out
        if len(weights) != n:
            raise ValueError("The number of weights does not match the population")
        cum = []
        total = 0.0
        for w in weights:
            total = total + w
            cum.append(total)
        if total <= 0.0:
            raise ValueError("Total of weights must be greater than zero")
        hi = n - 1
        i = 0
        while i < k:
            x = self.random() * total
            lo = 0
            h = hi
            while lo < h:
                mid = (lo + h) // 2
                if x < cum[mid]:
                    h = mid
                else:
                    lo = mid + 1
            out.append(population[lo])
            i = i + 1
        return out
