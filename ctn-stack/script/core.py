import asyncio
import logging
from pathlib import Path

from ctn_stack.container import ImageLayer, LayeredImage, RemoteImage

logging.basicConfig(level=logging.INFO)


class UvImageLayer(ImageLayer):
    def __init__(self, version: str):
        super().__init__(
            dockerfile=Path("layer/uv/Dockerfile"),
            name="ctn-stack/uv",
            full_tag=version,
            abvr_tag=f"uv{version}",
            build_arg_defs={"UV_VERSION": version},
        )


async def main() -> None:
    # Base image from remote registry
    base_image = RemoteImage("ubuntu", "24.04", abvr_tag="ubuntu24")

    # Define layers
    # Installs common packages (curl, ca-certificates) as root
    common_layer = ImageLayer(
        dockerfile=Path("layer/install-common/Dockerfile"),
        name="ctn-stack/common",
        full_tag="latest",
        abvr_tag="cmn",
    )

    # Switches default user from root to non-root "ubuntu"
    user_layer = ImageLayer(
        dockerfile=Path("layer/ubuntu-user/Dockerfile"),
        name="ctn-stack/ubuntu-user",
        full_tag="latest",
        abvr_tag="usr",
    )

    # Installs Astral's UV package manager
    uv_layer = UvImageLayer("0.11.16")

    # Apply layers on top
    # common layer is applied before user layer, as package installation requires root access
    common_image: LayeredImage = common_layer(base_image)
    user_image: LayeredImage = user_layer(common_image)
    uv_image = uv_layer(user_image)

    # Ensure final image exists (builds all layers transitively)
    await uv_image.ensure_exists()
    print(f"Image {uv_image.get_name_tag()} is ready.")


if __name__ == "__main__":
    asyncio.run(main())
