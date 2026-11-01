import re

IP = re.compile(r"(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)")
MAC = re.compile(r"[0-9a-f]{2}(?::[0-9a-f]{2}){5}", re.I)


def main() -> int:
    for text in ["192.168.0.1", "255.255.255.255", "256.1.1.1", "", "10.0.0"]:
        print(repr(text), IP.fullmatch(text) is not None)
    print(MAC.fullmatch("AA:bb:cc:dd:ee:ff") is not None)
    print(MAC.fullmatch("aa:bb:cc:dd:ee") is not None)
    print(re.findall(r"\d+", "a1b22c333"))
    print(re.split(r"\.", "192.168.0.1"))
    m = re.search(r"(\d+)\.(\d+)", "version 3.14 here")
    if m:
        print(m.group(1), m.group(2), m.start(2), m.end(2))
    print(re.sub(r"\d+", "#", "a1b22c333"))
    print(re.escape("192.168.0.1"))
    return 0


main()
