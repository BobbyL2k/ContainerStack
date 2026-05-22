import asyncio
import logging
from pathlib import Path

from ctn_stack.container import ImageLayer, LayeredImage, RemoteImage

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    # Step 1: Define a base image pulled from a remote registry
    base_image = RemoteImage("ubuntu", "24.04")

    # Step 2: Define an image layer that sets the default user as a non-root "ubuntu" user
    layer = ImageLayer(
        dockerfile=Path("layer/ubuntu-user/Dockerfile"),
        name="ubuntu-user",
        tag="latest",
    )

    # Step 3: Produce a LayeredImage by applying the layer to the base
    derived_image: LayeredImage = layer(base_image)

    # Step 4: Ensure the derived image exists locally.
    # This will pull the base image if needed, then build the derived image.
    await derived_image.ensure_exists()
    print(f"Image {derived_image.get_name_tag()} is ready.")


if __name__ == "__main__":
    asyncio.run(main())
