import asyncio


async def ok():
    await asyncio.sleep(0.01)
    print("ok")
    return "ok"


async def bad():
    await asyncio.sleep(0.02)
    print("bad")
    raise ValueError("boom")


async def main():
    try:
        await asyncio.gather(ok(), bad())
    except ValueError as error:
        print("caught", error)
    await asyncio.sleep(0.03)
    print("done")


asyncio.run(main())
