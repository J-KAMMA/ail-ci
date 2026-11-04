import pkg.a
import pkg.b
m = pkg.a
for i in range(2):
    m = pkg.b if i else pkg.a
m.run()
