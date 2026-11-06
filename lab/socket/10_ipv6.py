import socket

srv = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
srv.bind(("::1", 0))
srv.listen(1)
host, port, flow, scope = srv.getsockname()
print(host)
print(port > 0)
print(flow, scope)

cli = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
cli.connect(("::1", port))
conn, addr = srv.accept()

cli.sendall(b"v6")
print(conn.recv(8).decode())

phost, pport, pflow, pscope = cli.getpeername()
print(phost)
print(pport == port)
print(pflow, pscope)

cli.close()
conn.close()
srv.close()
