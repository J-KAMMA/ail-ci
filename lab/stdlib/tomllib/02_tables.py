import tomllib

DOC = '''
[server]
host = "localhost"
port = 8080

[server.limits]
max_connections = 100
timeout = 2.5

[database]
enabled = true

[database.primary]
name = "main"
user = "admin"

[owner]
name = "Tom"
dob = 1979-05-27T07:32:00Z
site.scheme = "https"
site.host = "example.com"
'''


def main():
    data = tomllib.loads(DOC)
    print("top", sorted(data.keys()))
    print("server", data["server"]["host"], data["server"]["port"])
    print("limits", data["server"]["limits"]["max_connections"],
          data["server"]["limits"]["timeout"])
    print("primary", data["database"]["primary"]["name"],
          data["database"]["primary"]["user"])
    print("enabled", data["database"]["enabled"])
    print("owner", data["owner"]["name"])
    print("site", data["owner"]["site"]["scheme"], data["owner"]["site"]["host"])


main()
