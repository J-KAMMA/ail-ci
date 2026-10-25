def t(f):
    try:
        print(f())
    except Exception as e:
        print(type(e).__name__, e)
b = 2**70
l = [1]
t(lambda: l[b])
t(lambda: l[-b])
t(lambda: "abc"[b])
t(lambda: (1,2)[b])
t(lambda: "abc"[b:])
t(lambda: "abc"[:b])
t(lambda: "abc"[-b:b])
t(lambda: [1,2,3][::b])
t(lambda: [1,2,3][::-b])
t(lambda: b"abc"[b])
def s():
    l[b] = 3
t(s)
def s2():
    del l[b]
t(s2)
t(lambda: "a"*b)
t(lambda: [1]*b)
t(lambda: "abc".center(b))
d = {b: 1}
t(lambda: d[b])
t(lambda: l.pop(b))
t(lambda: l.insert(b, 3))
