import socket

def main() -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    host, port = srv.getsockname()

    cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(cli.gettimeout())

    cli.settimeout(0.15)
    print(cli.gettimeout())

    cli.connect((host, port))
    conn, addr = srv.accept()
    cli.sendall(b"")

    try:
        cli.recv(16)
    except TimeoutError as e:
        print("TimeoutError", str(e))

    try:
        cli.recv(16)
    except socket.timeout as e:
        print("socket.timeout", str(e))

    cli.settimeout(None)
    print(cli.gettimeout())

    cli.close()
    conn.close()
    srv.close()

main()
