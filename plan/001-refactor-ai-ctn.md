# Refactor: Extract AI Container Build to `ai-dev-ctn` Package

> **Status: ✅ EXECUTED** — All 11 steps completed. Both `ai-dev-ctn` and `ctn-stack` pass lint, type-check, and tests with zero errors.

## Goal

Move all AI-related container building logic out of `ctn-stack/script/core.py` into a standalone Python package `ai-dev-ctn`. The new package manages the full build chain for the `ctn-stack/ai-agent` image (nvm → node → pnpm → ai-agent) and depends on `ctn-stack` as an editable install via `uv`. After the refactor, `ctn-stack` is a pure library with no scripts and no Dockerfiles.

## Current State

- `ctn-stack/script/core.py` contains all layer classes and the `main()` orchestration for **both** the Python image (uv → python) and the AI agent image (nvm → node → pnpm → ai-agent).
- Layer Dockerfiles live under `ctn-stack/layer/{install-common, ubuntu-user, nvm, nvm-node, pnpm, ai-agent, uv, uv-python}/`.
- `ctn-stack` is a hatchling-based package with `ctn_stack.container` providing `Image`, `ImageLayer`, `LayeredImage`, `RemoteImage`.
- `ctn-stack/Makefile` provides `sync`, `check`, `check-autofix`, `check-type`, `test`, `remove-image` targets.

## Target State

```
ContainerStack/
├── ctn-stack/                    # pure library — no scripts, no Dockerfiles
│   ├── pyproject.toml
│   ├── Makefile
│   ├── README.md                 # updated: removed core.py, layer/, and doc/ references
│   ├── src/ctn_stack/
│   │   ├── container/            # Image, ImageLayer, LayeredImage, RemoteImage
│   │   └── python_shell/
│   └── tests/
│
├── ai-dev-ctn/                   # NEW package — all build logic and all Dockerfiles
│   ├── pyproject.toml            # uv-managed, editable dep on ctn-stack
│   ├── Makefile                  # borrowed pattern from ctn-stack
│   ├── src/ai_dev_ctn/
│   │   ├── __init__.py
│   │   └── build.py              # everything: layer classes + build orchestration
│   ├── layer/                    # all Dockerfiles moved here from ctn-stack
│   │   ├── install-common/
│   │   ├── ubuntu-user/
│   │   ├── uv/
│   │   ├── uv-python/
│   │   ├── nvm/
│   │   ├── nvm-node/
│   │   ├── pnpm/
│   │   └── ai-agent/
│   └── doc/                      # moved from ctn-stack/doc/
│       ├── add-version-manager-layer.md
│       ├── nvm-node-pnpm-layer.md
│       └── ai-agent-layer.md
│
└── plan/
    └── refactor-ai-ctn.md        # this file
```

**Key principle:** `ctn-stack` becomes a pure library — no scripts, no Dockerfiles, no docs. `ai-dev-ctn` owns everything: build scripts, layer classes, all Dockerfiles, and documentation.

## Steps

### 1. Create `ai-dev-ctn` package skeleton

```bash
mkdir -p ai-dev-ctn/src/ai_dev_ctn
```

Create `ai-dev-ctn/pyproject.toml`:
```toml
[project]
name = "ai-dev-ctn"
version = "0.1.0"
description = "AI dev container build tool"
requires-python = ">=3.14"
dependencies = [
    "ctn-stack",
]

[tool.uv.sources]
ctn-stack = { path = "../ctn-stack", editable = true }

[tool.ruff.lint]
extend-select = ["I"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Create empty `ai-dev-ctn/src/ai_dev_ctn/__init__.py`.

### 2. Move all Dockerfiles out of `ctn-stack`

Move **every** Dockerfile from `ctn-stack/layer/` into `ai-dev-ctn/layer/`. After this step, `ctn-stack/layer/` no longer exists.

```bash
mkdir -p ai-dev-ctn/layer
mv ctn-stack/layer/* ai-dev-ctn/layer/
rmdir ctn-stack/layer
```

### 3. Create `ai-dev-ctn/src/ai_dev_ctn/build.py`

Move **everything** from `ctn-stack/script/core.py` into a single `build.py`. This includes all layer classes and both build chains (uv/python and nvm/node/pnpm/ai-agent). No separate `layers.py` — one file is sufficient.

```python
# ai-dev-ctn/src/ai_dev_ctn/build.py
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
        opencode_version: tuple[int, int, int],
        codex_version: tuple[int, int, int],
        pi_version: tuple[int, int, int],
    ):
        super().__init__(
            dockerfile=Path("layer/ai-agent/Dockerfile"),
            name="ctn-stack/ai-agent",
            full_tag="latest",
            abvr_tag="ai",
            build_arg_defs={
                "OPENCODE_VERSION": ".".join(str(v) for v in opencode_version),
                "CODEX_VERSION": ".".join(str(v) for v in codex_version),
                "PI_VERSION": ".".join(str(v) for v in pi_version),
            },
        )


async def build_uv_python_image() -> None:
    """Build the uv -> python image chain."""
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

    common_image: LayeredImage = common_layer(base_image)
    user_image: LayeredImage = user_layer(common_image)

    uv_image = uv_layer(user_image)
    python_image = uv_python_layer(uv_image)

    await python_image.ensure_exists()


async def build_ai_agent_image() -> None:
    """Build the nvm -> node -> pnpm -> ai-agent image chain."""
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

    nvm_layer = NvmImageLayer(major=0, minor=40, patch=4)
    node_layer = NvmNodeLayer(major=26, minor=2, patch=0)
    pnpm_layer = PnpmImageLayer(major=11, minor=2, patch=2)
    ai_agent_layer = AiAgentImageLayer(
        opencode_version=(1, 15, 10),
        codex_version=(0, 133, 0),
        pi_version=(0, 75, 5),
    )

    common_image: LayeredImage = common_layer(base_image)
    user_image: LayeredImage = user_layer(common_image)

    nvm_image = nvm_layer(user_image)
    node_image = node_layer(nvm_image)
    pnpm_image = pnpm_layer(node_image)
    ai_agent_image = ai_agent_layer(pnpm_image)
    ai_agent_image.tag = "latest"

    await ai_agent_image.ensure_exists()


async def main() -> None:
    """Build all images."""
    await build_uv_python_image()
    await build_ai_agent_image()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

### 4. Create `ai-dev-ctn/Makefile`

Borrow the pattern from `ctn-stack/Makefile`. The `ai-dev-ctn` package doesn't have its own tests, so `check` runs format, lint, and type-check only. It also needs a `build` target.

```makefile
.venv sync:
	uv sync --all-extras

check: sync
	uv run ruff format --diff
	uv run ruff check
	$(MAKE) check-type

check-autofix: sync
	uv run ruff format
	uv run ruff check --fix
	$(MAKE) check-type

check-type: sync
	uv run ty check

build: sync
	uv run python -m ai_dev_ctn.build

remove-image:
	docker rmi $(shell docker images --format '{{.Repository}}:{{.Tag}}' | grep '^ctn-stack/')

.PHONY: sync check check-autofix check-type build remove-image
```

### 5. Remove `ctn-stack/script/core.py`

Delete the script entirely — all its content has moved to `ai-dev-ctn/src/ai_dev_ctn/build.py`:

```bash
rm -rf ctn-stack/script
```

### 6. Update `ctn-stack/README.md`

Remove all references to `script/core.py`, `layer/`, `doc/`, and the example usage section. Specifically:

- **Remove** the "Project Structure" entries for `script/`, `layer/`, and `doc/`
- **Remove** the "Example Usage" section entirely (it described `core.py` layer classes and image chains)
- **Keep** the API documentation, quick start examples, and image layering detail — those are library-level docs
- **Update** "Development" table: remove `remove-image` target (moved to `ai-dev-ctn`)
- **Remove** the `llk.toml` entry from "Project Structure" (or keep if still relevant)

### 7. Move `ctn-stack/doc/` to `ai-dev-ctn/doc/`

The doc files describe the nvm/node/pnpm/ai-agent layer patterns and troubleshooting. They belong with the build logic, not the library.

```bash
mv ctn-stack/doc ai-dev-ctn/doc
```

### 8. Update `ctn-stack/Makefile`

Remove the `remove-image` target since Docker image management now belongs to `ai-dev-ctn`:

```makefile
.venv sync:
	uv sync --all-extras

check: sync
	uv run ruff format --diff
	uv run ruff check
	$(MAKE) check-type
	$(MAKE) test

check-autofix: sync
	uv run ruff format
	uv run ruff check --fix
	$(MAKE) check-type
	$(MAKE) test

check-type: sync
	uv run ty check

test: sync
	uv run pytest

.PHONY: sync check check-autofix check-type test
```

### 9. Handle `ctn-stack/llk.toml`

The `llk.toml` file references `make` targets. Review whether it needs updating after the `remove-image` target is removed from `ctn-stack/Makefile`. If the file is no longer needed, delete it. If it's used by an external tool, update accordingly.

### 10. Install both packages

```bash
# Install ai-dev-ctn (pulls in ctn-stack as editable dep)
cd ai-dev-ctn
uv sync

# Sync ctn-stack as well
cd ../ctn-stack
uv sync
```

### 11. Verify both packages pass lint and type checks

**DO NOT run `make build`** — the executing environment does not have Docker available. The migration is complete when both packages pass all lint and type checks with zero errors.

```bash
# ai-dev-ctn: autofix + verify
cd ai-dev-ctn
make check-autofix
make check

# ctn-stack: autofix + verify
cd ../ctn-stack
make check-autofix
make check
```

The migration is done when both `make check` invocations exit cleanly.

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| `Path("layer/...")` resolution fails when running `build.py` | Ensure `build.py` is invoked from `ai-dev-ctn/` root (e.g., `uv run python -m ai_dev_ctn.build` run from the project root). Alternatively, use `Path(__file__).resolve().parent.parent / "layer"` for robust resolution. |

## ⚠️ Plan Completeness Notes for Executing Agent

**NO DOCKER AVAILABLE** — do not attempt to run `make build` or any command that invokes Docker. Verify correctness exclusively via `make check` and `make check-autofix`. The migration is complete when both `ctn-stack` and `ai-dev-ctn` pass all lint and type checks with zero errors.

This plan contains the full extracted code for `ai-dev-ctn/src/ai_dev_ctn/build.py` (verified against `ctn-stack/script/core.py`). However, the following items are **not fully specified** in this plan — **read the actual files before executing**:

- **`ctn-stack/README.md`**: The plan describes what to remove/update, but does not contain the full updated README. Read the current `ctn-stack/README.md` and apply the described changes. Pay attention to the `doc/`, `layer/`, `script/`, and `llk.toml` entries in the "Project Structure" section.
- **`ctn-stack/llk.toml`**: The plan doesn't contain the full updated content. Read the current file and decide whether to update or delete based on its usage.
- **`ctn-stack/doc/` files**: The plan moves these to `ai-dev-ctn/doc/` but doesn't extract their content. Verify the move is correct by reading the files.
- **`ai-dev-ctn/pyproject.toml`**: The plan provides the content inline. Verify `ruff` and `ty` are available (they come transitively through `ctn-stack`'s dependencies).

## Future Improvements

- Parameterize tool versions (opencode, codex, pi, node, pnpm, nvm, uv, python) via CLI args or config file instead of hardcoding.
- Consider a shared `base-ctn` package for the common layers (`install-common`, `ubuntu-user`) if more consumers emerge.
