import asyncio
from pathlib import Path

from ctn_stack.container import ImageLayer, LayeredImage, RemoteImage


async def main() -> None:
    # Step 1: Define a base image pulled from a remote registry
    base_image = RemoteImage("ubuntu", "24.04")

    # Step 2: Define an image layer (factory) that describes how to build
    # on top of a base image
    layer = ImageLayer(
        dockerfile=Path("Dockerfile.worker"),
        name="myapp",
        tag="latest",
        build_arg_defs={"WORKER_COUNT": "4", "API_KEY": None},  # API_KEY is required
    )

    # Step 3: Produce a LayeredImage by applying the layer to the base
    derived_image: LayeredImage = layer(base_image, build_args={"API_KEY": "secret"})

    # Step 4: Ensure the derived image exists locally.
    # This will pull the base image if needed, then build the derived image.
    await derived_image.ensure_exists()
    print(f"Image {derived_image.get_name_tag()} is ready.")


if __name__ == "__main__":
    asyncio.run(main())
