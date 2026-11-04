import tomllib

DEFAULTS_DOC = '''
host = "127.0.0.1"
port = 80
debug = false
retries = 3
paths = ["/usr/share"]

[logging]
level = "warning"
file = "/dev/stderr"
'''

DOC = '''
port = 8443
debug = true
paths = ["/srv/app", "/var/lib/app"]

[logging]
level = "info"
file = "/var/log/app.log"
'''


def merge(base, override):
    result = dict(base)
    for key in override:
        if key in result and isinstance(result[key], dict) and isinstance(override[key], dict):
            result[key] = merge(result[key], override[key])
        else:
            result[key] = override[key]
    return result


def main():
    defaults = tomllib.loads(DEFAULTS_DOC)
    parsed = tomllib.loads(DOC)
    config = merge(defaults, parsed)
    print("config", config)
    print("host", config["host"], "port", config["port"])
    print("debug", config["debug"], "retries", config["retries"])
    print("paths", config["paths"])
    print("logging", config["logging"]["level"], config["logging"]["file"])
    print("defaults unchanged", defaults["port"], defaults["debug"])


main()
