import asyncio
from pathlib import Path


async def pull(image_name: str) -> None:
    """Pull a Docker image using ``docker pull``.

    Executes the command without a shell and raises ``RuntimeError`` if the
    pull fails (non‑zero exit status).
    """
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "pull",
        image_name,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"docker pull {image_name} failed with exit code {proc.returncode}"
        )


async def image_exists(image_name: str) -> bool:
    """Return ``True`` if the Docker image is present locally.

    Runs ``docker image inspect``; the command succeeds (exit code 0) when the
    image exists.
    """
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "image",
        "inspect",
        image_name,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    return proc.returncode == 0


async def build(
    dockerfile_path: Path,
    context_path: Path,
    build_args: dict[str, str] | None = None,
) -> None:
    """Build a Docker image using ``docker build``.

    Parameters
    ----------
    dockerfile_path:
        Path to the Dockerfile to use for the build.
    context_path:
        Path to the build context directory.
    build_args:
        Optional mapping of build‑time arguments passed as ``--build-arg``.

    The function runs the build command without a shell and raises
    ``RuntimeError`` if the build fails (non‑zero exit status).
    """

    # Base command arguments
    # Convert Path objects to strings for the subprocess command
    cmd = ["docker", "build", "-f", str(dockerfile_path)]

    # Append any build arguments supplied by the caller
    if build_args:
        for key, value in build_args.items():
            cmd.extend(["--build-arg", f"{key}={value}"])

    # Finally, add the context path
    cmd.append(str(context_path))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"docker build failed with exit code {proc.returncode}"
        )
