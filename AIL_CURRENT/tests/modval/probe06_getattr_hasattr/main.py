import pkg.util
m = pkg.util
print(getattr(m, "double")(3), hasattr(m, "nope"))
