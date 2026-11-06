import socket

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.bind(("127.0.0.1", 0))
srv.listen(1)
host, port = srv.getsockname()

cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cli.connect((host, port))
conn, addr = srv.accept()

conn.sendall(b"alpha 3\nbeta 4\n")
line = ""
count = 0
lines = 0
while lines < 2:
    chunk = cli.recv(1)
    if not chunk:
        break
    line += chunk.decode()
    if line.endswith("\n"):
        parts = line.split()
        count += int(parts[1])
        print(parts[0])
        line = ""
        lines += 1
print(count)

cli.close()
conn.close()
srv.close()
