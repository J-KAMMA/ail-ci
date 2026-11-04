# C?-job-pre26-10240859-1: repr of numeric exception arguments
try:
    raise ValueError(3.0)
except Exception as e:
    print(repr(e.args[0]), "%r" % (e.args[0],), "{!r}".format(e.args[0]), e)
try:
    raise ValueError(True)
except Exception as e:
    print(repr(e.args[0]), "%r" % (e.args[0],), "{!r}".format(e.args[0]), e)
try:
    raise ValueError(None)
except Exception as e:
    print(repr(e.args[0]), "%r" % (e.args[0],), "{!r}".format(e.args[0]), e)
try:
    raise ValueError(3, "x")
except Exception as e:
    print(repr(e.args[0]), "%r" % (e.args[0],), "{!r}".format(e.args[0]), e)
