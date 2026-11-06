import socket

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.bind(("127.0.0.1", 0))
srv.listen(1)
host, port = srv.getsockname()

cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cli.connect((host, port))
conn, addr = srv.accept()

cli.sendall(b"part one ")
cli.sendall(b"part two")
cli.shutdown(socket.SHUT_WR)

whole = ""
while True:
    chunk = conn.recv(64)
    if not chunk:
        break
    whole += chunk.decode()
print(whole)

conn.sendall(b"bye")
print(cli.recv(8).decode())

cli.close()
conn.close()
srv.close()
