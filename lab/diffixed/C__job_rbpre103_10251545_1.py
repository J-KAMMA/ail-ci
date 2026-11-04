# C?-job-rbpre103-10251545-1: NUL byte in a format spec
def show(value, spec):
    try:
        print(repr(format(value, spec)))
    except Exception as exc:
        print(type(exc).__name__, str(exc))

show(1, "\x00")
show("a", "\x00")
show(1, "5\x00")
show("a", ">\x00")
show(1.5, "\x00")
show(1, "\x00.2f")
