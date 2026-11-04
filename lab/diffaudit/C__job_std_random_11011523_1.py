# C?-job-std_random-11011523-1: getrandbits(k) for k > 63 stops at the int64 limit.
import random

random.seed(1)
print(random.getrandbits(64))
