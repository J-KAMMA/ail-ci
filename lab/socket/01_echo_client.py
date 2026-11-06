import socket

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 0))
srv.listen(1)
host, port = srv.getsockname()

cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cli.connect((host, port))
conn, addr = srv.accept()

cli.sendall(b"hello")
data = conn.recv(10)
conn.sendall(data)
reply = cli.recv(10)

print(data.decode())
print(reply.decode())
print(addr[0])

cli.close()
conn.close()
srv.close()
