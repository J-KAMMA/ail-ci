import asyncio


async def worker():
    print("worker start")
    try:
        await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        print("worker cancelled")
        raise
    finally:
        print("worker finally")


async def main():
    task = asyncio.create_task(worker())
    await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("cancelled at main")
    print("done")


asyncio.run(main())
