import tomllib

DOC = (
    'title = "TOML Example"\n'
    "literal = 'C:\\\\Users\\\\nodejs\\\\templates'\n"
    'ml_basic = """\nRoses are red\nViolets are blue"""\n'
    "ml_literal = '''literal\nmulti line'''\n"
    'escapes = "tab\\tnewline\\nquote\\" backslash\\\\"\n'
    'line_cont = """The quick brown '
    + "\\" + "\n" +
    'fox jumps"""\n'
    'hex = 0xDEAD_BEEF\n'
    'oct = 0o755\n'
    'bin = 0b1101_0101\n'
    'dec = 1_000_000\n'
    'neg = -42\n'
    'flt = 3.1415\n'
    'exp = 5e+22\n'
    'exp2 = -2E-2\n'
    'big = 1_2.5_0e1_0\n'
    'inf1 = inf\n'
    'inf2 = -inf\n'
    'nan1 = nan\n'
    'ok = true\n'
    'no = false\n'
)


def main():
    data = tomllib.loads(DOC)
    for key in data:
        value = data[key]
        print(key, repr(value))
    print("title", data["title"])
    print("hex", data["hex"], "oct", data["oct"], "bin", data["bin"])
    print("dec", data["dec"], "neg", data["neg"])
    print("ok", data["ok"], "no", data["no"])
    print("nan is nan", data["nan1"] != data["nan1"])
    print("inf", data["inf1"] > 1e308, data["inf2"] < -1e308)


main()
