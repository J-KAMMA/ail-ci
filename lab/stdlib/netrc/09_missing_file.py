import netrc

try:
    netrc.netrc("does_not_exist.netrc")
    print("opened")
except FileNotFoundError as e:
    print(type(e).__name__)
    print(e.errno)

print("after")

try:
    netrc.netrc("missing_dir/absent.netrc")
    print("opened")
except FileNotFoundError as e:
    print(type(e).__name__)
    print(e.errno)

print("done")
