import asyncio


async def main():
    loop = asyncio.get_running_loop()
    loop.call_soon(print, "callback-1")
    loop.call_soon(print, "callback-2")
    print("main")
    await asyncio.sleep(0)
    print("after-sleep-0")
    loop.call_soon(print, "callback-3")
    await asyncio.sleep(0)
    print("after-sleep-0-again")


asyncio.run(main())
