from abc import ABC, abstractmethod, update_abstractmethods


class Job(ABC):
    @abstractmethod
    def run(self) -> str:
        ...


class Pending(Job):
    pass


def ready(self) -> str:
    return "done"


try:
    Pending()
except TypeError as exc:
    print("blocked", str(exc))

Pending.run = ready
update_abstractmethods(Pending)
job = Pending()
print(job.run())
print(isinstance(job, Job))
