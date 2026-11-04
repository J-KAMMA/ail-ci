# C?-job-pre70-10241829-1: str.split with a run-time None separator
s = "  a b\tc\n "
sep = None
print(s.split(sep))
print(s.rsplit(sep, 1))
args = [None]
print("a b  c".split(args[0]))
d = {"sep": None}
print("a b  c".split(d["sep"], 1))

def f(x):
    return x.split(None)

print(f(" a b "))
recv = " x y "
print(recv.split(sep))
print("a,b".split(","))
print(" a b ".rsplit(None, 1))
