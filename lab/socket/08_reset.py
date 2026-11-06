import socket

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.bind(("127.0.0.1", 0))
srv.listen(1)
host, port = srv.getsockname()

cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cli.connect((host, port))
conn, addr = srv.accept()

cli.sendall(b"z" * 1000)
conn.close()

try:
    while True:
        data = cli.recv(4096)
        if not data:
            print("eof")
            break
except ConnectionResetError as e:
    print("ConnectionResetError", e.errno)

cli.close()
srv.close()
