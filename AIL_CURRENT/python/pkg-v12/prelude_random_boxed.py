# -*- coding: utf-8 -*-
# prelude_random_boxed.py -- prelude_random.py's Random for the general (boxed) path: the same methods, the same draws,
# the Mersenne Twister and the integer arithmetic in C (randrt.py). pyboxed2 puts this class in place of the Python one
# when the program is built on the general path; the typed path keeps prelude_random.py.


class Random:
    def __init__(self, seed):
        self.mt = _ail_rg_new(seed)

    def seed(self, a):
        _ail_rg_seed(self.mt, a)

    def random(self):
        return _ail_rg_random(self.mt)

    def getrandbits(self, k):
        return _ail_rg_bits(self.mt, k)

    def _randbelow(self, n):
        return _ail_rg_below(self.mt, n)

    def randrange(self, start, stop=None, step=1):
        return _ail_rg_range(self.mt, start, stop, step, 0)

    def randrange1(self, start):
        return _ail_rg_range(self.mt, start, None, 1, 0)

    def randrange3(self, start, stop, step):
        return _ail_rg_range(self.mt, start, stop, step, 0)

    def randint(self, a, b):
        return _ail_rg_range(self.mt, a, b, 1, 1)

    def choice(self, seq):
        if not isinstance(seq, list):
            seq = list(seq)
        return _ail_rg_choice(self.mt, seq)

    def shuffle(self, x):
        if isinstance(x, list):
            _ail_rg_shuffle(self.mt, x)
            return
        i = len(x) - 1
        while i >= 1:
            j = _ail_rg_below(self.mt, i + 1)
            t = x[i]
            x[i] = x[j]
            x[j] = t
            i = i - 1

    def sample(self, population, k):
        if not isinstance(population, list):
            population = list(population)
        return _ail_rg_sample(self.mt, population, k)

    def uniform(self, a, b):
        return _ail_rg_uniform(self.mt, a, b)

    def gauss(self, mu=0.0, sigma=1.0):
        return _ail_rg_gauss(self.mt, mu, sigma)

    def expovariate(self, lambd):
        return _ail_rg_expo(self.mt, lambd)

    def triangular(self, low=0.0, high=1.0, mode=None):
        return _ail_rg_tri(self.mt, low, high, mode)

    def choices(self, population, weights=None, k=1):
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
