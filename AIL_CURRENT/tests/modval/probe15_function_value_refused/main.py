import pkg.util

def f(mod):
    return (mod is pkg.util, mod.double is pkg.util.double)

print(f(pkg.util))
