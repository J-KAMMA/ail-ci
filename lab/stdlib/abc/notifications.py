from abc import ABC, abstractmethod


class Notifier(ABC):
    def __init__(self, recipient: str) -> None:
        self.recipient = recipient
        self.sent = 0

    @abstractmethod
    def deliver(self, message: str) -> str:
        ...

    def send(self, message: str) -> str:
        self.sent = self.sent + 1
        return self.deliver(message)

    def report(self) -> str:
        return "%s sent=%d to=%s" % (type(self).__name__, self.sent, self.recipient)


class Email(Notifier):
    def deliver(self, message: str) -> str:
        return "email " + self.recipient + ": " + message.upper()


class Sms(Notifier):
    def __init__(self, recipient: str, limit: int) -> None:
        Notifier.__init__(self, recipient)
        self.limit = limit

    def deliver(self, message: str) -> str:
        if len(message) > self.limit:
            return self.deliver(message[:self.limit])
        return "sms " + self.recipient + ": " + message


class Silent(Notifier):
    def deliver(self, message: str) -> str:
        return ""


notifiers = [Email("user@example.com"), Sms("555-0100", 5), Silent("nobody")]
messages = ["hello world", "abstract"]
for notifier in notifiers:
    for message in messages:
        result = notifier.send(message)
        if result == "":
            print("no output")
        else:
            print(result)
    print(notifier.report())
