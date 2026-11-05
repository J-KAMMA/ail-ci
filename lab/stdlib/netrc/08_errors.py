import netrc


def check(name, text):
    with open(name, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        netrc.netrc(name)
        print(name, "no error")
    except netrc.NetrcParseError as e:
        print(name, repr(e.msg))
        print(name, repr(e.filename))
        print(name, repr(e.lineno))
        print(name, str(e))


check("bad_top.netrc", "bogus token\n")
check("missing_name.netrc", "machine\n")
check("unterminated.netrc", "macdef init\ncd /tmp\n")
check("bad_follower.netrc", "machine a.example.com login u nope v\n")
