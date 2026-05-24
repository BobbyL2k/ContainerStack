# ctn-stack

Asynchronous Python framework for building layered Docker images. Defines image layers as composable, validated factories that resolve base-image dependencies, inject build args, and orchestrate `docker build` pipelines.

## Key Features

- **Async-first API** - all I/O operations are `async`, built on `asyncio.create_subprocess_exec`.
- **No Docker SDK dependency** - wraps the `docker` CLI directly, avoiding heavy library dependencies.
- **Unified `ensure_exists()` interface** - regardless of whether an image is pulled from a registry or built locally, call `await image.ensure_exists()` to guarantee it is present.
- **Image layering** - describe derived images as Dockerfiles layered on top of a base image, with automatic base-image resolution and `BASE_IMAGE` build-arg injection.
- **Build-arg validation** - declare required and optional build arguments upfront; the framework validates supplied args at construction time.
- **Factory pattern for layers** - `ImageLayer` objects are reusable factories that produce `LayeredImage` instances when applied to any base `Image`.
- **Tag chaining** - images carry an abbreviated tag (`abvr_tag`) and inherit their base chain as `prev_abvr_tags`, producing traceable composite tags like `py3_14-usr-cmn-ubuntu24`.
- **Invalidation tracking** - mark images as invalid with `mark_invalid()` to force rebuilds; `LayeredImage` propagates invalidation from base images.

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
    image = RemoteImage("ubuntu", "24.04", abvr_tag="ubuntu24")
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
    base_image = RemoteImage("ubuntu", "24.04", abvr_tag="ubuntu24")

    # Step 2: Define an image layer (factory) with build-arg declarations
    layer = ImageLayer(
        dockerfile=Path("Dockerfile.worker"),
        name="myapp",
        full_tag="latest",
        abvr_tag="wk",
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
| `Image` | Base class. Provides `exists()`, `get_name_tag()`, `is_invalid()`, `mark_invalid()`, and `ensure_exists()` (raises `NotImplementedError` if not overridden). Tracks `name`, `full_tag`, `abvr_tag`, and `prev_abvr_tags` for traceable tag chaining. |
| `RemoteImage(Image)` | Represents an image pulled from a registry. `ensure_exists()` pulls if missing or invalidated. Requires `name`, `tag`, and `abvr_tag`. |
| `LayeredImage(Image)` | Represents an image built from a Dockerfile on top of a base image. `ensure_exists()` ensures the base exists first, then builds if missing or invalidated. Propagates invalidation from base images. |
| `ImageLayer` | Factory (callable) that produces `LayeredImage` instances. Validates build arguments against declared definitions. Accepts optional `name` and `tag` overrides on `__call__`. |

### Docker CLI Wrappers (`ctn_stack.python_shell.docker`)

| Function | Description |
|---|---|
| `pull(image_name)` | Runs `docker pull <image_name>`. |
| `image_exists(image_name)` | Runs `docker image inspect <image_name>`, returns `True`/`False`. |
| `build(dockerfile_path, context_path, tag=None, build_args=None)` | Runs `docker build` with optional tag and build arguments. |
| `delete_image(image_name, force=False)` | Runs `docker rmi <image_name>`; use `force=True` for `-f`. |

## Image Layering in Detail

### Tag Chaining

Each image has an `abvr_tag` (e.g., `uv0_11`, `py3_14`, `usr`, `cmn`, `ubuntu24`) and inherits its base chain as `prev_abvr_tags`. The final `get_name_tag()` produces composite tags:

```
ctn-stack/uv-python:3.14.5-usr-cmn-ubuntu24
ctn-stack/ai-agent:latest
```

Language version layers can clean up the version manager's `abvr_tag` from the chain, keeping tags concise while preserving traceability.

### Base Validation

Language version layers can validate that their base image includes the required version manager by matching `abvr_tag` against a regex. This fails fast if a layer is applied to an incorrect base:

```python
python_image = language_layer(manager_image)   # OK
python_image = language_layer(user_image)      # ValueError: must include manager
```

### Invalidation

Call `mark_invalid()` on any image to force a rebuild on the next `ensure_exists()`. For `LayeredImage`, invalidation propagates from base images. After a successful build or pull, the image is automatically marked valid so it won't rebuild on subsequent calls.

```python
base_image.mark_invalid()
# derived_image.is_invalid() now returns True
await derived_image.ensure_exists()  # deletes, rebuilds, and marks valid
# derived_image.is_invalid() now returns False
```

## Project Structure

```
src/ctn_stack/
├── __init__.py               # Package init
├── py.typed                  # PEP 561 typed package marker
├── container/
│   └── __init__.py          # Image, RemoteImage, LayeredImage, ImageLayer
└── python_shell/
    ├── __init__.py
    └── docker.py            # Async Docker CLI wrappers

tests/container/
├── __init__.py
├── test_image.py            # Tests for Image base class
├── test_remote_image.py     # Tests for RemoteImage
└── test_image_layer.py      # Tests for ImageLayer and LayeredImage

Makefile                     # Build and check targets
pyproject.toml               # Project metadata and dependencies
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
