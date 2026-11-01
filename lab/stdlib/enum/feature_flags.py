from enum import IntFlag, auto


class Feature(IntFlag):
    NONE = 0
    SEARCH = auto()
    EXPORT = auto()
    IMPORT = auto()
    SYNC = SEARCH | EXPORT


def names(flags):
    return [feature.name for feature in flags]


def main():
    feature = Feature.SEARCH | Feature.EXPORT
    print(feature, repr(feature), feature.value, names(feature))
    print(feature & Feature.SEARCH, feature ^ Feature.SEARCH, feature | Feature.IMPORT)
    print(Feature.SYNC is feature, Feature.SYNC in feature, Feature.IMPORT in feature)
    print(int(feature), feature == 3, feature > 1, feature + 1, 8 - feature)
    print(Feature(7), Feature(0), bool(Feature(0)), bool(feature))
    for value in (0, 1, 2, 3, 4, 7):
        flag = Feature(value)
        print(value, flag, flag.value, names(flag))
    print(Feature.NONE.name, Feature.SYNC.name)


main()
