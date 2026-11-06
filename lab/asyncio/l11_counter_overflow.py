import asyncio


async def bump(counter):
    await asyncio.sleep(0)
    counter[0] += 1
    return counter[0]


async def main():
    counter = [9223372036854775806]
    results = await asyncio.gather(bump(counter), bump(counter))
    print(results)
    print(counter[0])


asyncio.run(main())
