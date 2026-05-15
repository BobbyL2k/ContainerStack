import asyncio

from ctn_stack.container import RemoteImage


async def main() -> None:
    image = RemoteImage("ubuntu", "24.04")
    if await image.exists():
        print("Image already exists")
    else:
        await image.pull()
        print("Pulled")


if __name__ == "__main__":
    asyncio.run(main())
