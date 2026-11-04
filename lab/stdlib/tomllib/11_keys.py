import tomllib

DOC = '''
bare = 1
bare-dash = 2
bare_underscore = 3
1234 = "digits"
"quoted key" = "value"
'literal key' = "other"
phys.color = "orange"
phys.shape = "round"
site."google.com" = true
[servers.alpha]
ip = "10.0.0.1"
[servers.beta]
ip = "10.0.0.2"
'''


def main():
    data = tomllib.loads(DOC)
    print("bare", data["bare"], data["bare-dash"], data["bare_underscore"])
    print("digits", data["1234"])
    print("quoted", data["quoted key"], data["literal key"])
    print("phys", data["phys"]["color"], data["phys"]["shape"])
    print("site", data["site"]["google.com"])
    print("servers", sorted(data["servers"].keys()))
    for name in data["servers"]:
        print("server", name, data["servers"][name]["ip"])


main()
