# task: Implement a Visitor pattern with an abstract Element base class and two concrete element subclasses that accept a visitor, printing the visitor's results for a fixed structure.
from __future__ import annotations

from abc import ABC, abstractmethod


class Visitor(ABC):
    """Abstract visitor declaring a visit method for each concrete element."""

    @abstractmethod
    def visit_file(self, element: File) -> None:
        ...

    @abstractmethod
    def visit_directory(self, element: Directory) -> None:
        ...


class Element(ABC):
    """Abstract element that can accept a visitor."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def accept(self, visitor: Visitor) -> None:
        ...


class File(Element):
    """Leaf element representing a file with a size in bytes."""

    def __init__(self, name: str, size: int) -> None:
        super().__init__(name)
        self.size = size

    def accept(self, visitor: Visitor) -> None:
        visitor.visit_file(self)


class Directory(Element):
    """Composite element holding an ordered list of child elements."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.children: list[Element] = []

    def add(self, child: Element) -> Directory:
        self.children.append(child)
        return self

    def accept(self, visitor: Visitor) -> None:
        visitor.visit_directory(self)


class SizeVisitor(Visitor):
    """Computes the total size of all files in the visited structure."""

    def __init__(self) -> None:
        self.total: int = 0

    def visit_file(self, element: File) -> None:
        self.total += element.size

    def visit_directory(self, element: Directory) -> None:
        for child in element.children:
            child.accept(self)


class PrintVisitor(Visitor):
    """Prints an indented tree of the visited structure."""

    def __init__(self) -> None:
        self.depth: int = 0
        self.lines: list[str] = []

    def visit_file(self, element: File) -> None:
        self.lines.append(f"{'  ' * self.depth}- {element.name} ({element.size} bytes)")

    def visit_directory(self, element: Directory) -> None:
        self.lines.append(f"{'  ' * self.depth}+ {element.name}/")
        self.depth += 1
        for child in element.children:
            child.accept(self)
        self.depth -= 1


class CountVisitor(Visitor):
    """Counts files and directories in the visited structure."""

    def __init__(self) -> None:
        self.files: int = 0
        self.directories: int = 0

    def visit_file(self, element: File) -> None:
        self.files += 1

    def visit_directory(self, element: Directory) -> None:
        self.directories += 1
        for child in element.children:
            child.accept(self)


def build_structure() -> Directory:
    root = Directory("root")
    docs = Directory("docs")
    docs.add(File("readme.txt", 1200)).add(File("notes.md", 3400))
    src = Directory("src")
    src.add(File("main.py", 5120)).add(File("util.py", 2048))
    empty = Directory("empty")
    root.add(docs).add(src).add(empty).add(File("LICENSE", 800))
    return root


def main() -> None:
    root = build_structure()

    printer = PrintVisitor()
    root.accept(printer)
    print("Structure:")
    for line in printer.lines:
        print(line)

    sizer = SizeVisitor()
    root.accept(sizer)
    print(f"Total size: {sizer.total} bytes")

    counter = CountVisitor()
    root.accept(counter)
    print(f"Files: {counter.files}, Directories: {counter.directories}")


if __name__ == "__main__":
    main()
