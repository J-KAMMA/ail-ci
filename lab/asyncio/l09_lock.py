import asyncio


async def worker(name, lock):
    await lock.acquire()
    try:
        print(name, "acquired")
        await asyncio.sleep(0.01)
        print(name, "released")
    finally:
        lock.release()


async def main():
    lock = asyncio.Lock()
    await asyncio.gather(
        worker("first", lock),
        worker("second", lock),
        worker("third", lock),
    )


asyncio.run(main())
