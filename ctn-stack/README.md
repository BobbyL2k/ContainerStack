# ctn-stack

Asynchronous Python helpers for Docker CLI interactions, including pulling images, checking local existence, building images from Dockerfiles, and composing layered image pipelines. Designed for scripts and automation that need fine-grained control over Docker image lifecycles.

## Key Features

- **Async-first API** - all I/O operations are `async`, built on `asyncio.create_subprocess_exec`.
- **No Docker SDK dependency** - wraps the `docker` CLI directly, avoiding heavy library dependencies.
- **Unified `ensure_exists()` interface** - regardless of whether an image is pulled from a registry or built locally, call `await image.ensure_exists()` to guarantee it is present.
- **Image layering** - describe derived images as Dockerfiles layered on top of a base image, with automatic base-image resolution and `BASE_IMAGE` build-arg injection.
- **Build-arg validation** - declare required and optional build arguments upfront; the framework validates supplied args at construction time.
- **Factory pattern for layers** - `ImageLayer` objects are reusable factories that produce `LayeredImage` instances when applied to any base `Image`.

## Requirements

- **Python** >= 3.14
- **Docker** CLI available on `$PATH`
- **[uv](https://github.com/astral-sh/uv)** for dependency management

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd ctn-stack

# Sync dependencies (creates .venv and installs all packages)
make sync
```

## Quick Start

### Pull a Remote Image

```python
import asyncio
from ctn_stack.container import RemoteImage

async def main() -> None:
    image = RemoteImage("ubuntu", "24.04")
    await image.ensure_exists()  # pulls if not present locally
    print(f"Image {image.get_name_tag()} is ready.")

asyncio.run(main())
```

### Build a Layered Image on Top of a Base

```python
import asyncio
from pathlib import Path

from ctn_stack.container import ImageLayer, LayeredImage, RemoteImage

async def main() -> None:
    # Step 1: Define a base image pulled from a remote registry
    base_image = RemoteImage("ubuntu", "24.04")

    # Step 2: Define an image layer (factory) with build-arg declarations
    layer = ImageLayer(
        dockerfile=Path("Dockerfile.worker"),
        name="myapp",
        tag="latest",
        build_arg_defs={"WORKER_COUNT": "4", "API_KEY": None},  # API_KEY is required
    )

    # Step 3: Produce a LayeredImage by applying the layer to the base
    derived_image: LayeredImage = layer(base_image, build_args={"API_KEY": "secret"})

    # Step 4: Ensure the derived image exists locally.
    # This pulls the base image if needed, then builds the derived image.
    await derived_image.ensure_exists()
    print(f"Image {derived_image.get_name_tag()} is ready.")

asyncio.run(main())
```

The Dockerfile used with `ImageLayer` must declare `ARG BASE_IMAGE` before the `FROM` line:

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG WORKER_COUNT=4
ENV WORKER_COUNT=${WORKER_COUNT}

COPY ./app /app
WORKDIR /app
CMD ["python", "-m", "app.worker"]
```

## API Overview

### Container Abstractions (`ctn_stack.container`)

| Class | Description |
|---|---|
| `Image` | Base class. Provides `exists()`, `get_name_tag()`, and `ensure_exists()` (raises `NotImplementedError` if not overridden). |
| `RemoteImage(Image)` | Represents an image pulled from a registry. `ensure_exists()` pulls if missing. |
| `LayeredImage(Image)` | Represents an image built from a Dockerfile on top of a base image. `ensure_exists()` ensures the base exists first, then builds if missing. |
| `ImageLayer` | Factory (callable) that produces `LayeredImage` instances. Validates build arguments against declared definitions. |

### Docker CLI Wrappers (`ctn_stack.python_shell.docker`)

| Function | Description |
|---|---|
| `pull(image_name)` | Runs `docker pull <image_name>`. |
| `image_exists(image_name)` | Runs `docker image inspect <image_name>`, returns `True`/`False`. |
| `build(dockerfile_path, context_path, tag=None, build_args=None)` | Runs `docker build` with optional tag and build arguments. |

## Project Structure

```
src/ctn_stack/
├── __init__.py               # Package init
├── py.typed                  # PEP 561 typed package marker
├── container/
│   └── __init__.py          # Image, RemoteImage, LayeredImage, ImageLayer
└── python_shell/
    └── docker.py            # Async Docker CLI wrappers

tests/container/
├── test_image.py            # Tests for Image base class
├── test_remote_image.py     # Tests for RemoteImage
└── test_image_layer.py      # Tests for ImageLayer and LayeredImage

script/
└── core.py                  # Example usage script

layer/
└── <layer-name>/
    └── Dockerfile           # Docker image layer

doc/
├── feature/01-image-layer/  # Design docs for the image layer feature
└── tooling/01-makefile/     # Tooling notes

llk.toml                     # Project configuration
```

## Development

This project uses **[uv](https://github.com/astral-sh/uv)** for dependency management and a **Makefile** for common tasks.

| Command | Description |
|---|---|
| `make sync` | Sync dependencies (creates/updates `.venv`) |
| `make check` | Run all checks (format, lint, type-check, tests) |
| `make check-autofix` | Auto-fix linting and formatting, then run all checks |
| `make check-type` | Run type checking with `ty` |
| `make test` | Run tests with `pytest` |

### Tooling

- **Formatter / Linter:** [ruff](https://github.com/astral-sh/ruff)
- **Type checker:** [ty](https://github.com/astral-sh/ty)
- **Test runner:** [pytest](https://pytest.org) with [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)

## License

Unlicensed, repository copyrighted.
