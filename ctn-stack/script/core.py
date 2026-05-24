import asyncio
import logging
import re
from pathlib import Path

from ctn_stack.container import Image, ImageLayer, LayeredImage, RemoteImage


class UvImageLayer(ImageLayer):
    def __init__(self, *, major: int, minor: int, patch: int):
        version = f"{major}.{minor}.{patch}"
        super().__init__(
            dockerfile=Path("layer/uv/Dockerfile"),
            name="ctn-stack/uv",
            full_tag=version,
            abvr_tag=f"uv{major}_{minor}",
            build_arg_defs={"UV_VERSION": version},
        )


class PnpmImageLayer(ImageLayer):
    def __init__(self, *, major: int, minor: int, patch: int):
        version = f"{major}.{minor}.{patch}"
        super().__init__(
            dockerfile=Path("layer/pnpm/Dockerfile"),
            name="ctn-stack/pnpm",
            full_tag=version,
            abvr_tag=f"pnpm{major}_{minor}",
            build_arg_defs={"PNPM_VERSION": version},
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


class NvmImageLayer(ImageLayer):
    def __init__(self, *, major: int, minor: int, patch: int):
        version = f"{major}.{minor}.{patch}"
        super().__init__(
            dockerfile=Path("layer/nvm/Dockerfile"),
            name="ctn-stack/nvm",
            full_tag=version,
            abvr_tag=f"nvm{major}_{minor}",
            build_arg_defs={"NVM_VERSION": version},
        )


class NvmNodeLayer(ImageLayer):
    _NVM_TAG_RE = re.compile(r"^nvm\d+(_\d+)+$")

    def __init__(self, *, major: int, minor: int, patch: int):
        version = f"{major}.{minor}.{patch}"
        super().__init__(
            dockerfile=Path("layer/nvm-node/Dockerfile"),
            name="ctn-stack/nvm-node",
            full_tag=version,
            abvr_tag=f"node{major}_{minor}",
            build_arg_defs={"NODE_VERSION": version},
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
        if not any(self._NVM_TAG_RE.match(t) for t in all_tags):
            raise ValueError(
                "NvmNodeLayer must be built on top of an image that includes NvmImageLayer"
            )

        image = super().__call__(base, name=name, tag=tag, build_args=build_args)
        image.prev_abvr_tags = tuple(
            t for t in image.prev_abvr_tags if not self._NVM_TAG_RE.match(t)
        )
        return image


class AiAgentImageLayer(ImageLayer):
    def __init__(
        self,
        *,
        opencode_version: str,
        codex_version: str,
        pi_version: str,
    ):
        super().__init__(
            dockerfile=Path("layer/ai-agent/Dockerfile"),
            name="ctn-stack/ai-agent",
            full_tag="latest",
            abvr_tag="ai",
            build_arg_defs={
                "OPENCODE_VERSION": opencode_version,
                "CODEX_VERSION": codex_version,
                "PI_VERSION": pi_version,
            },
        )


async def main() -> None:
    base_image = RemoteImage("ubuntu", "24.04", abvr_tag="ubuntu24")

    common_layer = ImageLayer(
        dockerfile=Path("layer/install-common/Dockerfile"),
        name="ctn-stack/common",
        full_tag="latest",
        abvr_tag="cmn",
    )

    user_layer = ImageLayer(
        dockerfile=Path("layer/ubuntu-user/Dockerfile"),
        name="ctn-stack/ubuntu-user",
        full_tag="latest",
        abvr_tag="usr",
    )

    uv_layer = UvImageLayer(major=0, minor=11, patch=16)
    uv_python_layer = UvPythonLayer(major=3, minor=14, patch=5)

    nvm_layer = NvmImageLayer(major=0, minor=40, patch=4)
    node_layer = NvmNodeLayer(major=26, minor=2, patch=0)
    pnpm_layer = PnpmImageLayer(major=11, minor=2, patch=2)
    ai_agent_layer = AiAgentImageLayer(
        opencode_version="1.15.10",
        codex_version="0.133.0",
        pi_version="0.75.5",
    )

    common_image: LayeredImage = common_layer(base_image)
    user_image: LayeredImage = user_layer(common_image)

    # Branch 1: uv -> python
    uv_image = uv_layer(user_image)
    python_image = uv_python_layer(uv_image)

    # Branch 2: nvm -> node -> pnpm -> ai-agent
    nvm_image = nvm_layer(user_image)
    node_image = node_layer(nvm_image)
    pnpm_image = pnpm_layer(node_image)
    ai_agent_image = ai_agent_layer(pnpm_image)
    ai_agent_image.tag = "latest"

    await python_image.ensure_exists()
    await ai_agent_image.ensure_exists()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
