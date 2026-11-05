import os
import os.path

home = os.environ["HOME"]
print(os.path.expandvars("$HOME/x") == home + "/x")
print(os.path.expandvars("${HOME}/y") == home + "/y")
print(os.path.expandvars("$HOME") == home)
print(os.path.expandvars("no/$AIL_VAR_NOT_SET/x") == "no/$AIL_VAR_NOT_SET/x")
print(os.path.expandvars("plain") == "plain")
