import asyncio


async def worker(name, delay):
    await asyncio.sleep(delay)
    print(name)


async def main():
    tasks = [
        asyncio.create_task(worker("a", 0.02)),
        asyncio.create_task(worker("b", 0.01)),
        asyncio.create_task(worker("c", 0.02)),
        asyncio.create_task(worker("d", 0.01)),
    ]
    await asyncio.gather(*tasks)


asyncio.run(main())
