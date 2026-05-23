import asyncio
import logging
from pathlib import Path

from ctn_stack.container import ImageLayer, LayeredImage, RemoteImage

logging.basicConfig(level=logging.INFO)


class UvImageLayer(ImageLayer):
    def __init__(self, version: str):
        super().__init__(
            dockerfile=Path("layer/uv/Dockerfile"),
            name="uv",
            tag=version,
            build_arg_defs={"UV_VERSION": version},
        )


async def main() -> None:
    # Step 1: Define a base image pulled from a remote registry
    base_image = RemoteImage("ubuntu", "24.04")

    # Step 2: Install common tools (curl, etc.) as root
    common_layer = ImageLayer(
        dockerfile=Path("layer/install-common/Dockerfile"),
        name="install-common",
        tag="latest",
    )
    common_image: LayeredImage = common_layer(base_image)
    await common_image.ensure_exists()
    print(f"Image {common_image.get_name_tag()} is ready.")

    # Step 3: Define an image layer that sets the default user as a non-root "ubuntu" user
    user_layer = ImageLayer(
        dockerfile=Path("layer/ubuntu-user/Dockerfile"),
        name="ubuntu-user",
        tag="latest",
    )

    # Step 4: Produce a LayeredImage by applying the user layer
    user_image: LayeredImage = user_layer(common_image)

    # Step 5: Ensure the user image exists locally.
    await user_image.ensure_exists()
    print(f"Image {user_image.get_name_tag()} is ready.")

    # Step 6: Add UV on top of the ubuntu-user image
    uv_layer = UvImageLayer("0.11.16")
    uv_image = uv_layer(user_image)
    await uv_image.ensure_exists()
    print(f"Image {uv_image.get_name_tag()} is ready.")


if __name__ == "__main__":
    asyncio.run(main())
