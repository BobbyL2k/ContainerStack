# Version Manager + Language Layer Pattern

This document describes how to create image layers for programming language version managers (e.g., `uv`, `nvm`, `fnm`) and the corresponding layers that install a specific language version using that manager.

## Two-Layer Architecture

The pattern uses two distinct layers:

1. **Version Manager Layer** — installs the tool that manages language versions (e.g., `uv`, `nvm`, `asdf`).
2. **Language Version Layer** — uses the version manager to install a specific language version.

This separation allows:
- Reusing the version manager across multiple language versions.
- Changing the language version without rebuilding the manager layer.
- Keeping image tags traceable to their base layers.

## Example: `uv` + Python

### Layer 1: Version Manager (`layer/uv/Dockerfile`)

```dockerfile
ARG BASE_IMAGE=dev_base:latest
FROM ${BASE_IMAGE}

ARG UV_VERSION=0.11.16

RUN curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh
```

Key points:
- Declares `ARG BASE_IMAGE` so the framework can inject the base image.
- Declares `ARG UV_VERSION` with a default, passed via `build_arg_defs`.
- Installs the manager to a known location (e.g., `~/.local/bin`).

### Layer 2: Language Version (`layer/uv-python/Dockerfile`)

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG PYTHON_VERSION=3.14.5

RUN /home/ubuntu/.local/bin/uv python install ${PYTHON_VERSION}
```

Key points:
- Declares `ARG BASE_IMAGE` (no default, injected by framework).
- Declares `ARG PYTHON_VERSION` with a default, passed via `build_arg_defs`.
- Invokes the version manager binary to install the language.

## Python Layer Classes

### Version Manager Class

```python
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
```

- Accepts version components as keyword arguments.
- Constructs the version string and passes it as a build arg.
- Sets `abvr_tag` for traceability in the image tag chain.

### Language Version Class

```python
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
```

Two conventions in this class:

1. **Base validation** — `__call__` checks that the base image chain includes the version manager by matching its `abvr_tag` against a regex. This fails fast if the layer is applied to an incorrect base.

2. **Tag chain cleanup** — after creating the image, the version manager's `abvr_tag` is removed from `prev_abvr_tags`. This keeps the final image tag concise while preserving the intermediate layers in the chain. For example, without cleanup the tag would be `ctn-stack/uv-python:3.14.5-uv0_11-usr-cmn-ubuntu24`, but with cleanup it becomes `ctn-stack/uv-python:3.14.5-usr-cmn-ubuntu24`.

## Creating a New Version Manager + Language Pair

To add support for a new language (e.g., `nvm` + Node.js):

### Step 1: Create the version manager Dockerfile

```
layer/nvm/Dockerfile
```

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG NVM_VERSION=0.40.1

RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v${NVM_VERSION}/install.sh | bash
```

### Step 2: Create the language version Dockerfile

```
layer/nvm-node/Dockerfile
```

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG NODE_VERSION=22.14.0

RUN source ~/.nvm/nvm.sh && nvm install ${NODE_VERSION}
```

### Step 3: Create the Python layer classes

```python
import re
from pathlib import Path

from ctn_stack.container import Image, ImageLayer, LayeredImage


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
```

### Step 4: Wire into the layer chain

```python
nvm_layer = NvmImageLayer(major=0, minor=40, patch=1)
node_layer = NvmNodeLayer(major=22, minor=14, patch=0)

nvm_image = nvm_layer(user_image)
node_image = node_layer(nvm_image)

await node_image.ensure_exists()
```

## Checklist

When creating a new version manager + language pair:

- [ ] Version manager Dockerfile declares `ARG BASE_IMAGE` and `ARG <TOOL>_VERSION`
- [ ] Language Dockerfile declares `ARG BASE_IMAGE` and `ARG <LANG>_VERSION`
- [ ] Version manager class extends `ImageLayer` with versioned `abvr_tag`
- [ ] Language class overrides `__call__` to validate base image has the version manager
- [ ] Language class cleans up the version manager's `abvr_tag` from `prev_abvr_tags`
- [ ] Both classes pass their version as a build arg via `build_arg_defs`
