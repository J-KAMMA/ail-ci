# C?-job-pre388-10280828-2: attribute-held list of float; int() beyond int64.
class C:
    pass

c = C()
c.a = [1e300]
print(int(c.a[0]))
c.a[0] = 1.5
