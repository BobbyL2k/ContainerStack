import asyncio
import logging
import re
from pathlib import Path

from ctn_stack.container import Image, ImageLayer, LayeredImage, RemoteImage

logging.basicConfig(level=logging.INFO)


class UvImageLayer(ImageLayer):
    def __init__(self, *, major: int, minor: int, patch: int):
        version = f"{major}.{minor}.{patch}"
        super().__init__(
            dockerfile=Path("layer/uv/Dockerfile"),
            name="ctn-stack/uv",
            full_tag=version,
            abvr_tag=f"uv{major}_{minor}_{patch}",
            build_arg_defs={"UV_VERSION": version},
        )


class UvPythonLayer(ImageLayer):
    _UV_TAG_RE = re.compile(r"^uv\d+(_\d+)+$")

    def __init__(self, *, major: int, minor: int, patch: int):
        version = f"{major}.{minor}.{patch}"
        super().__init__(
            dockerfile=Path("layer/uv-python/Dockerfile"),
            name="ctn-stack/uv-python",
            full_tag=version,
            abvr_tag=f"py{major}_{minor}",
            build_arg_defs={"PYTHON_VERSION": version},
        )

    def __call__(
        self,
        base: Image,
        *,
        name: str | None = None,
        tag: str | None = None,
        build_args: dict[str, str] | None = None,
    ) -> LayeredImage:
        all_tags = (base.abvr_tag, *base.prev_abvr_tags)
        if not any(self._UV_TAG_RE.match(t) for t in all_tags):
            raise ValueError(
                "UvPythonLayer must be built on top of an image that includes UvImageLayer"
            )

        image = super().__call__(base, name=name, tag=tag, build_args=build_args)
        image.prev_abvr_tags = tuple(
            t for t in image.prev_abvr_tags if not self._UV_TAG_RE.match(t)
        )
        return image


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
    uv_layer = UvImageLayer(major=0, minor=11, patch=16)

    # Installs a specific Python version via uv
    uv_python_layer = UvPythonLayer(major=3, minor=14, patch=5)

    # Apply layers on top
    # common layer is applied before user layer, as package installation requires root access
    common_image: LayeredImage = common_layer(base_image)
    user_image: LayeredImage = user_layer(common_image)
    uv_image = uv_layer(user_image)
    uv_python_image = uv_python_layer(uv_image)

    # Ensure final image exists (builds all layers transitively)
    await uv_python_image.ensure_exists()
    print(f"Image {uv_python_image.get_name_tag()} is ready.")


if __name__ == "__main__":
    asyncio.run(main())
