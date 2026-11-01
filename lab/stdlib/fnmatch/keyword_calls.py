import fnmatch as fn


def main():
    names = ["report.csv", "summary.txt", "data.csv", "readme.md"]
    print("filter", fn.filter(names=names, pat="*.csv"))
    print("filter2", fn.filter(pat="*.txt", names=names))
    print("match", fn.fnmatch(name="report.csv", pat="*.csv"))
    print("case", fn.fnmatchcase(name="Report.CSV", pat="*.csv"))
    print("case2", fn.fnmatchcase(pat="*.md", name="readme.md"))
    print("translate", fn.translate(pat="*.csv"))
    alias = fn.fnmatch
    case = fn.fnmatchcase
    print("alias", alias("a.csv", "*.csv"), case("a.csv", "*.csv"))
    print("count", len(fn.filter(names, "*.*")))
    print("star", fn.fnmatch("x", "*"), fn.fnmatch("", "*"))


main()
