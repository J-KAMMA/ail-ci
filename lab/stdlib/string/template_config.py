import string

CONFIG = """host=$host
port=${port}
user=$user
"""


def load(text, defaults):
    template = string.Template(text)
    if not template.is_valid():
        raise ValueError("invalid template")
    merged = dict(defaults)
    merged["port"] = 8080
    return template.substitute(merged)


def main():
    print(load(CONFIG, {"host": "example.org", "user": "admin"}), end="")
    values = {"host": "example.com", "port": 80, "user": "root"}
    t = string.Template("$host:${port}/$user")
    print(t.substitute(values))
    print(t.safe_substitute({"host": "example.org"}))
    print(t.substitute(values, user="guest"))
    print(t.get_identifiers())
    for bad in ("$", "${", "${9}", "$9"):
        try:
            string.Template(bad).substitute()
        except ValueError as exc:
            print(repr(bad), exc)
        print(repr(bad), "safe", repr(string.Template(bad).safe_substitute()))
    try:
        string.Template("$x").substitute({})
    except KeyError as exc:
        print("KeyError", exc)


main()
