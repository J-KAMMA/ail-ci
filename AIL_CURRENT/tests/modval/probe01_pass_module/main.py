import pkg.util
import pkg.sub.m

def run(mod, x: int) -> int:
    return mod.double(x) if hasattr(mod, "double") else mod.tri(x)

print(run(pkg.util, 3), run(pkg.sub.m, 3))
