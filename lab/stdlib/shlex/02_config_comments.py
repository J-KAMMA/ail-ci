import shlex


def main():
    config = """# server settings
listen 127.0.0.1 8080
root '/srv/www files'
timeout 30   # seconds
name "web server"
"""
    for number, raw in enumerate(config.splitlines(), 1):
        line = raw.strip()
        if line == "":
            continue
        if line.startswith("#"):
            print(number, "comment")
            continue
        fields = shlex.split(line, comments=True)
        print(number, len(fields), fields)
        if fields[0] == "timeout":
            print("seconds", int(fields[1]) * 1000)
        if fields[0] == "root":
            print("root", fields[1])
    print("plain", shlex.split("a b # not a comment"))
    print("commented", shlex.split("a b # not a comment", comments=True))


main()
