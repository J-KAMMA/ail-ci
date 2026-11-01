"""A version type ordered with functools.total_ordering."""
from functools import total_ordering


@total_ordering
class Version:
    def __init__(self, major, minor):
        self.major = major
        self.minor = minor

    def __eq__(self, other):
        return (self.major, self.minor) == (other.major, other.minor)

    def __lt__(self, other):
        return (self.major, self.minor) < (other.major, other.minor)

    def __repr__(self):
        return f"Version({self.major}, {self.minor})"


def main() -> None:
    versions = [Version(1, 2), Version(2, 0), Version(1, 10), Version(1, 2)]
    print(sorted(versions))
    print(versions[0] == versions[3], versions[0] != versions[1])
    print(versions[0] < versions[1], versions[0] <= versions[3])
    print(versions[1] > versions[0], versions[1] >= versions[2])
    print(max(versions), min(versions))
    print(Version(3, 1) > Version(3, 0), Version(0, 9) <= Version(1, 0))


main()
