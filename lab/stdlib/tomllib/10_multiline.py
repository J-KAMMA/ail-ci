import tomllib

DOC = (
    'basic = """\n'
    'The quick brown '
    + "\\" + "\n" +
    'fox jumps over '
    + "\\" + "\n" +
    'the lazy dog"""\n'
    "literal = '''\nLine one\nLine two'''\n"
    'quoted = """She said "hello" loudly."""\n'
    "apostrophe = 'It is what it is.'\n"
    'four = """ends with quote""""\n'
    'five = """ends with two quotes"""""\n'
    'unicode = "caf\\u00e9 \\U0001F600"\n'
)


def main():
    data = tomllib.loads(DOC)
    print("basic", repr(data["basic"]))
    print("literal", repr(data["literal"]))
    print("quoted", repr(data["quoted"]))
    print("apostrophe", repr(data["apostrophe"]))
    print("four", repr(data["four"]))
    print("five", repr(data["five"]))
    print("unicode", repr(data["unicode"]), len(data["unicode"]))


main()
