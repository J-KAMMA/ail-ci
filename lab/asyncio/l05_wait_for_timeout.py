import asyncio


async def slow():
    try:
        await asyncio.sleep(1.0)
        return "late"
    except asyncio.CancelledError:
        print("slow cancelled")
        raise


async def main():
    try:
        await asyncio.wait_for(slow(), timeout=0.01)
    except asyncio.TimeoutError:
        print("timeout")
    print("done")


asyncio.run(main())
