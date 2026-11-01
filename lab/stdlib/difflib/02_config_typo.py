from difflib import get_close_matches


KNOWN_KEYS = [
    "timeout", "retries", "backoff", "endpoint", "username", "password",
    "verify_tls", "compression", "buffer_size", "log_level",
]


def resolve(name):
    return get_close_matches(name, KNOWN_KEYS, n=2)


def main():
    supplied = ["timeot", "reties", "endpont", "loglevel", "verify_tls", "unknown"]
    for name in supplied:
        matches = resolve(name)
        if matches:
            print(name, "did you mean", matches[0], "?")
            if len(matches) > 1:
                print("  alternatives:", matches[1:])
        else:
            print(name, "has no close match")
    print("all keys:", len(KNOWN_KEYS))


main()
