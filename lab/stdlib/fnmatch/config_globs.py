from fnmatch import filter as select
from fnmatch import fnmatchcase as same


def main():
    files = [
        "settings.py",
        "settings.local.py",
        "secrets.env",
        "test_settings.py",
        "tests/test_api.py",
        "tests/test_db.py",
        "docs/conf.py",
        "app.py",
        ".env",
    ]
    includes = ["*.py", "*.env"]
    excludes = ["test_*.py", "tests/*", "settings.local.py"]
    included = []
    for pattern in includes:
        included.extend(select(files, pattern))
    result = []
    for path in included:
        drop = False
        for pattern in excludes:
            if same(path, pattern):
                drop = True
                break
        if not drop:
            result.append(path)
    print("checked", included)
    print("result", result)
    print("tests", select(files, "tests/*"))
    print("local", select(files, "*.local.*"))
    print("hidden", select(files, ".*"))
    print("py", len(select(files, "*.py")))


main()
