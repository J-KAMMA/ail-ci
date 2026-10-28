def t(f):
    try:
        print(f())
    except Exception as e:
        print(type(e).__name__, e)
b = 2**70
z = 0
t(lambda: b % z)
t(lambda: b // z)
t(lambda: divmod(b, z))
t(lambda: 5 % z)
t(lambda: 5 // z)
t(lambda: divmod(5, z))
t(lambda: b % 0.0)
t(lambda: b // 0.0)
t(lambda: pow(b, 2, z))
t(lambda: 5 % (b-b))
t(lambda: b / z)
t(lambda: b / 0.0)
