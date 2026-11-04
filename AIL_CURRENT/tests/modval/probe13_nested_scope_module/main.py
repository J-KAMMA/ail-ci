import pkg.a
import pkg.b
m = pkg.a

def outer():
    def inner():
        m = pkg.b
        return m.run()
    print(m.run())
    print(inner())

outer()
