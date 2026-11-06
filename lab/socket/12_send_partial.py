import socket

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 0))
srv.listen(1)
host, port = srv.getsockname()

cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cli.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
cli.connect((host, port))
conn, addr = srv.accept()

payload = b"a" * 200000
off = 0
calls = 0
while off < len(payload):
    n = cli.send(payload[off:off + 8192])
    off += n
    calls += 1

total = 0
while total < len(payload):
    data = conn.recv(8192)
    if not data:
        break
    total += len(data)

phost, pport = conn.getpeername()
print(off)
print(total)
print(calls > 0)
print(phost)

cli.close()
conn.close()
srv.close()
