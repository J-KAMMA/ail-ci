import pkg.util
m = pkg.util
print(m.__name__)
print(m is pkg.util)
print(m.__file__.endswith("pkg/util.py"), m.__package__)
print(repr(m))
