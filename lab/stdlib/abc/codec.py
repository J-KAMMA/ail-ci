from abc import ABC, abstractmethod, abstractstaticmethod, abstractclassmethod, abstractproperty


class Codec(ABC):
    @abstractstaticmethod
    def normalize(text: str) -> str:
        ...

    @abstractclassmethod
    def default_name(cls) -> str:
        ...

    @abstractproperty
    def name(self) -> str:
        ...

    def encode(self, text: str) -> str:
        return self.name + ":" + self.normalize(text)


class UpperCodec(Codec):
    @staticmethod
    def normalize(text: str) -> str:
        return text.upper()

    @classmethod
    def default_name(cls) -> str:
        return "upper"

    @property
    def name(self) -> str:
        return self.default_name()


class LowerCodec(Codec):
    @staticmethod
    def normalize(text: str) -> str:
        return text.lower()

    @classmethod
    def default_name(cls) -> str:
        return "lower"

    @property
    def name(self) -> str:
        return self.default_name()


print(UpperCodec.default_name(), UpperCodec().encode("Abstract Methods"))
print(LowerCodec.default_name(), LowerCodec().encode("Abstract Methods"))
