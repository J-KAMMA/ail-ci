import socket

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.bind(("127.0.0.1", 0))
srv.listen(1)
host, port = srv.getsockname()

cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cli.connect((host, port))
conn, addr = srv.accept()

payload = b"x" * 4096
sent = 0
while sent < 1000000:
    sent += cli.send(payload)

total = 0
while total < 1000000:
    data = conn.recv(65536)
    if not data:
        break
    total += len(data)

print(sent)
print(total)
print(total == 1000000)

cli.close()
conn.close()
srv.close()
