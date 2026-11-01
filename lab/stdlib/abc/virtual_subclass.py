from abc import ABC, abstractmethod


class Stream(ABC):
    @abstractmethod
    def read(self) -> str:
        ...


class Socket:
    def __init__(self, data: str) -> None:
        self.data = data

    def read(self) -> str:
        return self.data


class File:
    def __init__(self, data: str) -> None:
        self.data = data

    def read(self) -> str:
        return self.data


Stream.register(Socket)
print(issubclass(Socket, Stream), isinstance(Socket("hello"), Stream))
print(issubclass(File, Stream), isinstance(File("hello"), Stream))
Stream.register(File)
print(issubclass(File, Stream), isinstance(File("hello"), Stream))
