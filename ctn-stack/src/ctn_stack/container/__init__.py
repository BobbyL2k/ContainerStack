"""Container module providing image handling abstractions.

The classes here encapsulate basic Docker image operations such as
checking existence, pulling from a remote registry, and building
images from a Dockerfile layered on top of a base image. They delegate
the actual Docker commands to :mod:`ctn_stack.python_shell.docker`.
"""

from __future__ import annotations

from pathlib import Path

from ctn_stack.python_shell import docker


class Image:
    """Represent a Docker image with a name and tag.

    Sub-classes can extend functionality (e.g. pulling from a remote
    registry) while re-using the ``get_name_tag`` helper.
    """

    name: str
    tag: str

    def get_name_tag(self) -> str:
        """Return the ``name:tag`` string used by Docker commands."""
        return f"{self.name}:{self.tag}"

    async def exists(self) -> bool:
        """Check whether the image exists locally.

        Delegates to :func:`ctn_stack.python_shell.docker.image_exists`.
        """
        return await docker.image_exists(self.get_name_tag())

    async def ensure_exists(self) -> None:
        """Ensure the image is present locally.

        Subclasses must override this method to provide the actual
        logic (e.g. pulling or building).
        """
        raise NotImplementedError


class RemoteImage(Image):
    """Docker image that can be pulled from a remote registry.

    ``RemoteImage`` is initialised with a ``name`` and ``tag`` and can be
    pulled on demand.
    """

    def __init__(self, name: str, tag: str):
        self.name = name
        self.tag = tag

    async def pull(self) -> None:
        """Pull the image using ``docker pull``.

        Uses :func:`ctn_stack.python_shell.docker.pull`.
        """
        await docker.pull(self.get_name_tag())

    async def ensure_exists(self) -> None:
        """Ensure the image is present locally, pulling if necessary."""
        if not await self.exists():
            await self.pull()


class LayeredImage(Image):
    """An image built from a Dockerfile on top of a base image.

    ``LayeredImage`` stores the metadata required to build the image
    (base image, Dockerfile path, build arguments) and provides a
    ``build`` method to trigger the build.
    """

    def __init__(
        self,
        base: Image,
        dockerfile: Path,
        name: str,
        tag: str,
        build_args: dict[str, str],
    ) -> None:
        self.base = base
        self.dockerfile = dockerfile
        self.name = name
        self.tag = tag
        self.build_args = build_args

    async def build(self) -> None:
        """Build the image using ``docker build``.

        Automatically injects ``--build-arg BASE_IMAGE=<base.get_name_tag()>``
        into the build command.
        """
        context_path = self.dockerfile.parent
        all_build_args = {"BASE_IMAGE": self.base.get_name_tag(), **self.build_args}
        image_tag = self.get_name_tag()
        await docker.build(
            dockerfile_path=self.dockerfile,
            context_path=context_path,
            tag=image_tag,
            build_args=all_build_args,
        )

    async def ensure_exists(self) -> None:
        """Ensure the image is present locally, building if necessary.

        First ensures the base image exists, then builds this image.
        """
        if not await self.exists():
            await self.base.ensure_exists()
            await self.build()


class ImageLayer:
    """Factory that produces LayeredImage instances on top of a base Image.

    ``ImageLayer`` is not an ``Image`` itself; it is a callable that, when
    invoked with a base ``Image``, produces a ``LayeredImage`` instance.
    """

    def __init__(
        self,
        dockerfile: Path,
        name: str,
        tag: str,
        build_arg_defs: dict[str, str | None] | None = None,
    ) -> None:
        """Initialise an ImageLayer.

        Args:
            dockerfile: Path to the Dockerfile (relative or absolute).
            name: Default image name for the produced LayeredImage.
            tag: Default image tag for the produced LayeredImage.
            build_arg_defs: Mapping of build-arg names to their default values.
                            A value of None means the arg is required (no default).
                            If omitted, no build args are accepted.
                            BASE_IMAGE is handled automatically and must not
                            appear here.
        """
        self.dockerfile = dockerfile
        self.name = name
        self.tag = tag
        self.build_arg_defs = build_arg_defs if build_arg_defs is not None else {}

    def __call__(
        self,
        base: Image,
        *,
        name: str | None = None,
        tag: str | None = None,
        build_args: dict[str, str] | None = None,
    ) -> LayeredImage:
        """Produce a LayeredImage layered on top of ``base``.

        Args:
            base: The base Image to layer on top of.
            name: Override the default image name.
            tag: Override the default image tag.
            build_args: Build-time arguments. Must satisfy build_arg_defs.
                        Do not include BASE_IMAGE; it is injected automatically.

        Raises:
            ValueError: If required build args are missing or extra args
                        are provided.
        """
        supplied = build_args if build_args is not None else {}

        # Validate: no extra args
        extra = set(supplied.keys()) - set(self.build_arg_defs.keys())
        if extra:
            raise ValueError(
                f"Unexpected build args: {', '.join(sorted(extra))}. "
                f"Defined args are: {', '.join(sorted(self.build_arg_defs.keys()))}"
            )

        # Validate: all required args provided
        for arg_name, default in self.build_arg_defs.items():
            if default is None and arg_name not in supplied:
                raise ValueError(f"Missing required build arg: '{arg_name}'")

        # Merge defaults with supplied values
        merged: dict[str, str] = {}
        for arg_name, default in self.build_arg_defs.items():
            if default is not None:
                merged[arg_name] = default
        merged.update(supplied)

        return LayeredImage(
            base=base,
            dockerfile=self.dockerfile,
            name=name if name is not None else self.name,
            tag=tag if tag is not None else self.tag,
            build_args=merged,
        )
