import socket

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 0))
srv.listen(3)
host, port = srv.getsockname()

i = 0
while i < 3:
    cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cli.connect((host, port))
    conn, addr = srv.accept()
    word = "row" + str(i)
    cli.sendall(word.encode())
    got = conn.recv(16)
    conn.sendall(got)
    echo = cli.recv(16)
    print(echo.decode())
    cli.close()
    conn.close()
    i += 1

srv.close()
print("served 3")
