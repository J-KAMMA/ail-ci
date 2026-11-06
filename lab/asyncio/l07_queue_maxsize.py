import asyncio


async def producer(queue):
    for item in range(3):
        await queue.put(item)
        print("put", item)


async def consumer(queue):
    for _ in range(3):
        item = await queue.get()
        print("got", item)
        queue.task_done()


async def main():
    queue = asyncio.Queue(maxsize=1)
    await asyncio.gather(producer(queue), consumer(queue))
    await queue.join()
    print("qsize", queue.qsize())


asyncio.run(main())
