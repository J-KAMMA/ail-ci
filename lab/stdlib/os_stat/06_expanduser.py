import os
import os.path

home = os.environ["HOME"]
print(os.path.expanduser("~") == home)
print(os.path.expanduser("~/x") == home + "/x")
print(os.path.expanduser("relative/x"))
print(os.path.expanduser("~") == home)
