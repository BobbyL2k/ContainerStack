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

    The image is identified by a ``name:tag`` string produced by
    :meth:`get_name_tag`. If ``tag`` is explicitly set, that value is
    used directly (acting as an override).

    Otherwise the tag is constructed from ``full_tag``,
    with any ``prev_abvr_tags`` appended as a hyphen-separated suffix
    (e.g. ``full_tag-abvr1-abvr2``). This enable easy tracing for the
    origin of the layered container image.

    Sub-classes can extend functionality (e.g. pulling from a remote
    registry) while re-using the ``get_name_tag`` helper.
    """

    name: str
    full_tag: str
    abvr_tag: str
    prev_abvr_tags: tuple[str, ...]
    tag: str | None = None

    def __init__(
        self,
        name: str,
        full_tag: str,
        abvr_tag: str,
        prev_abvr_tags: tuple[str, ...],
        tag: str | None = None,
    ):
        self.name = name
        self.full_tag = full_tag
        self.abvr_tag = abvr_tag
        self.prev_abvr_tags = prev_abvr_tags
        self.tag = tag
        self._invalidated = False

    def get_name_tag(self) -> str:
        """Return the ``name:tag`` string used by Docker commands."""
        if self.tag is not None:
            tag = self.tag
        else:
            tag = self.full_tag
            if self.prev_abvr_tags:
                tag += "-" + "-".join(self.prev_abvr_tags)
        return f"{self.name}:{tag}"

    async def exists(self) -> bool:
        """Check whether the image exists locally.

        Delegates to :func:`ctn_stack.python_shell.docker.image_exists`.
        """
        return await docker.image_exists(self.get_name_tag())

    def is_invalid(self) -> bool:
        return self._invalidated

    def mark_invalid(self) -> None:
        self._invalidated = True

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

    def __init__(
        self,
        name: str,
        tag: str,
        abvr_tag: str,
    ):
        super().__init__(
            name=name,
            full_tag=tag,
            abvr_tag=abvr_tag,
            prev_abvr_tags=(),
            tag=None,
        )

    async def pull(self) -> None:
        """Pull the image using ``docker pull``.

        Uses :func:`ctn_stack.python_shell.docker.pull`.
        """
        await docker.pull(self.get_name_tag())

    async def ensure_exists(self) -> None:
        """Ensure the image is present locally, pulling if necessary."""
        if not await self.exists() or self.is_invalid():
            await self.pull()
            self._invalidated = False


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
        full_tag: str,
        abvr_tag: str,
        build_args: dict[str, str],
    ) -> None:
        super().__init__(
            name, full_tag, abvr_tag, (base.abvr_tag, *base.prev_abvr_tags), None
        )
        self.base = base
        self.dockerfile = dockerfile
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
        is_invalid = self.is_invalid()
        exists = await self.exists()

        if exists and is_invalid:
            await docker.delete_image(self.get_name_tag(), force=True)

        if not exists or is_invalid:
            await self.base.ensure_exists()
            await self.build()
            self._invalidated = False

    def is_invalid(self):
        return super().is_invalid() or self.base.is_invalid()


class ImageLayer:
    """Factory that produces LayeredImage instances on top of a base Image.

    ``ImageLayer`` is not an ``Image`` itself; it is a callable that, when
    invoked with a base ``Image``, produces a ``LayeredImage`` instance.
    """

    def __init__(
        self,
        dockerfile: Path,
        name: str,
        full_tag: str,
        abvr_tag: str,
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
        self.full_tag = full_tag
        self.abvr_tag = abvr_tag
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

        image = LayeredImage(
            base=base,
            dockerfile=self.dockerfile,
            name=name if name is not None else self.name,
            full_tag=self.full_tag,
            abvr_tag=self.abvr_tag,
            build_args=merged,
        )
        if tag is not None:
            image.tag = tag
        return image
