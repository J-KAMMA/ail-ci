# C?-job-pre68-10241806-1: literal %-format %d with a float value
print("%d" % 3.7)
print("%d" % -3.7)
print("%i" % 3.7)
print("%u" % 3.7)
for value in (float("inf"), float("-inf"), float("nan")):
    try:
        print("%d" % value)
    except Exception as exc:
        print(type(exc).__name__, str(exc))
print("%d%%" % 60.0654)
print("%5.1f %d" % (2.25, 2.9))
