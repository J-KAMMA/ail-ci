import sys
import pkg.a
import pkg.b
m = pkg.a if len(sys.argv) > 5 else pkg.b
m.run()
