import asyncio


async def waiter(name, event):
    print(name, "waiting")
    await event.wait()
    print(name, "running")


async def main():
    event = asyncio.Event()
    first = asyncio.create_task(waiter("first", event))
    second = asyncio.create_task(waiter("second", event))
    await asyncio.sleep(0.01)
    print("set")
    event.set()
    await asyncio.gather(first, second)


asyncio.run(main())
