import base64
import io


def main() -> None:
    out = io.BytesIO()
    base64.encode(io.BytesIO(b"hello world"), out)
    print(out.getvalue())
    inp = io.BytesIO(out.getvalue())
    result = io.BytesIO()
    base64.decode(inp, result)
    print(result.getvalue())
    print(base64.encode(io.BytesIO(b"x"), io.BytesIO()))
    print(base64.decode(io.BytesIO(b"eA==\n"), io.BytesIO()))
    print(base64.encode(io.BytesIO(bytes(range(100))), io.BytesIO()))
    print(base64.decode(io.BytesIO(b"aGVs\nbG8=\n"), io.BytesIO()))


main()
