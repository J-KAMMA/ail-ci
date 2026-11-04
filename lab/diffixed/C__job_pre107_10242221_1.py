# C?-job-pre107-10242221-1: random.expovariate default rate
import random

a = random.Random(7).expovariate()
b = random.Random(7).expovariate(1.0)
print(a == b, a > 0)
print(random.Random(3).expovariate(2.0) > 0)
print(random.Random(11).gauss(0.0) != 0.0)
