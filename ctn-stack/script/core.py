import asyncio

from ctn_stack.python_shell import docker


async def main() -> None:
    image_name = "ubuntu:24.04"
    if await docker.image_exists(image_name):
        print("Image already exists")
    else:
        await docker.pull(image_name)
        print("Pulled")


if __name__ == "__main__":
    asyncio.run(main())
