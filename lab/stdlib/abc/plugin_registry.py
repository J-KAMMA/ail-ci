from abc import ABC, abstractmethod


class Plugin(ABC):
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def run(self, text: str) -> str:
        ...


class Upper(Plugin):
    def name(self) -> str:
        return "upper"

    def run(self, text: str) -> str:
        return text.upper()


class Reverse(Plugin):
    def name(self) -> str:
        return "reverse"

    def run(self, text: str) -> str:
        return text[::-1]


class Replace(Plugin):
    def __init__(self, old: str, new: str) -> None:
        self.old = old
        self.new = new

    def name(self) -> str:
        return "replace"

    def run(self, text: str) -> str:
        return text.replace(self.old, self.new)


plugins = {"upper": Upper(), "reverse": Reverse(), "replace": Replace("a", "A")}
order = ["upper", "reverse", "replace"]
text = "abstract base classes"
for key in order:
    plugin = plugins[key]
    text = plugin.run(text)
    print(plugin.name(), text)
print("plugins", len(plugins))
