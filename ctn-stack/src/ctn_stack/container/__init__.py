"""Container module providing image handling abstractions.

The classes here encapsulate basic Docker image operations such as
checking existence and pulling from a remote registry. They delegate the
actual Docker commands to :mod:`ctn_stack.python_shell.docker`.
"""

from __future__ import annotations

from ctn_stack.python_shell import docker


class Image:
    """Represent a Docker image with a name and tag.

    Sub‑classes can extend functionality (e.g. pulling from a remote
    registry) while re‑using the ``get_name_tag`` helper.
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
