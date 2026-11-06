import asyncio


async def quick():
    await asyncio.sleep(0.01)
    return 42


async def main():
    print(await asyncio.wait_for(quick(), timeout=1.0))


asyncio.run(main())
