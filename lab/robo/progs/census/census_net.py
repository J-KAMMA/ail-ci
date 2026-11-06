from ail import tcp_listen

def main() -> None:
    listener = tcp_listen("127.0.0.1", 40123, 4)
    print("ok")

main()
