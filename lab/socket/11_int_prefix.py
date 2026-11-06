import socket

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.bind(("127.0.0.1", 0))
srv.listen(1)
host, port = srv.getsockname()

cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cli.connect((host, port))
conn, addr = srv.accept()

conn.sendall(b"99999999999999999999\nhello")
head = b""
while not head.endswith(b"\n"):
    piece = cli.recv(1)
    if not piece:
        break
    head += piece

text = head.decode().strip()
n = int(text)
print(n)
print(n > 0)
print(cli.recv(8).decode())

cli.close()
conn.close()
srv.close()
