import asyncio


async def calc(name, delay):
    await asyncio.sleep(delay)
    print("finish", name)
    return name


async def main():
    results = await asyncio.gather(
        calc("a", 0.02),
        calc("b", 0.01),
        calc("c", 0.03),
    )
    print("results", results)


asyncio.run(main())
