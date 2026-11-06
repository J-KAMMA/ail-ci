import socket

probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
probe.bind(("127.0.0.1", 0))
host, port = probe.getsockname()
probe.close()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.connect((host, port))
except ConnectionRefusedError as e:
    print(type(e).__name__)
    print(e.errno)
    print(e.strerror)
    print(str(e))

second = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    second.connect((host, port))
except socket.error as e:
    print(type(e).__name__)

s.close()
second.close()
