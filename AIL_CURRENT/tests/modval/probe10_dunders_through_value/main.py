import pkg
import pkg.util

def info(mod):
    return (mod.__name__, mod.__file__.endswith("pkg/util.py"), mod.__package__,
            mod.__spec__.name, mod.__spec__.origin.endswith("pkg/util.py"),
            mod.__spec__.parent, mod.__cached__.endswith(".pyc"),
            mod.__loader__.name, mod.__loader__.path.endswith("pkg/util.py"),
            mod.__spec__.loader is mod.__loader__)

print(info(pkg.util))
for m in [pkg.util]:
    print(m.__spec__.name)
    try:
        print(m.__path__)
    except AttributeError:
        print("no path")
table = {"u": pkg.util}
print(table["u"].__spec__.parent)

class Holder:
    pass

h = Holder()
h.mod = pkg.util
print(h.mod.__name__, h.mod.__spec__.name)

def pathof(mod):
    return mod.__path__

def searchof(mod):
    return mod.__spec__.submodule_search_locations

print(pathof(pkg)[0].endswith("pkg"), searchof(pkg)[0].endswith("pkg"))
