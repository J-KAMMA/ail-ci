def t(f):
    try:
        print(f())
    except OverflowError as e:
        print("OE", e)
    except Exception as e:
        print(type(e).__name__, e)
big = 10**400
t(lambda: big/3.0)
t(lambda: big/10**-1)
t(lambda: 3.0/big)
t(lambda: big*3.0)
t(lambda: big**2.0)
t(lambda: big+1.5)
t(lambda: 1.5-big)
t(lambda: big//2.5)
t(lambda: big%2.5)
t(lambda: big/3)
t(lambda: 3/big)
t(lambda: big/big)
t(lambda: big/(big+1))
t(lambda: (2**1030)/(2**1025))
t(lambda: 2.5**big)
t(lambda: divmod(big, 2.5))
t(lambda: float(big))
t(lambda: big < 1.5)
