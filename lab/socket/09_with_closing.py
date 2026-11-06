import socket

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 0))
srv.listen(1)
host, port = srv.getsockname()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cli:
    cli.connect((host, port))
    conn, addr = srv.accept()
    with conn:
        cli.sendall(b"inside")
        print(conn.recv(8).decode())

second = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
second.connect((host, port))
conn2, addr2 = srv.accept()
conn2.sendall(b"again")
print(second.recv(8).decode())
second.close()
conn2.close()
srv.close()
print("closed")
