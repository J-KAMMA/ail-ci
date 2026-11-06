import asyncio


async def holder(lock, release):
    await lock.acquire()
    print("holder acquired")
    await release.wait()
    print("holder releasing")
    lock.release()


async def waiter(lock):
    await lock.acquire()
    print("waiter acquired")
    lock.release()


async def main():
    lock = asyncio.Lock()
    release = asyncio.Event()
    held = asyncio.create_task(holder(lock, release))
    await asyncio.sleep(0)
    waiting = asyncio.create_task(waiter(lock))
    await asyncio.sleep(0)
    waiting.cancel()
    try:
        await waiting
    except asyncio.CancelledError:
        print("waiter cancelled")
    release.set()
    await held
    print("locked", lock.locked())


asyncio.run(main())
