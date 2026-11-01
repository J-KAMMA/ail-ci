import abc


class Visitor(abc.ABC):
    @abc.abstractmethod
    def visit(self, name: str) -> str:
        ...


class Printer(Visitor):
    def visit(self, name: str) -> str:
        return "visited " + name


before = abc.get_cache_token()
print(type(before).__name__)
for name in ("home", "office"):
    print(Printer().visit(name))
after = abc.get_cache_token()
print(before == after)
try:
    Visitor()
except TypeError as exc:
    print("blocked", str(exc))
