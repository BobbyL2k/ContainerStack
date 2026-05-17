# Context for Image Layer Feature

This document captures all information about the existing codebase needed to plan the **Image Layer** feature described in `high-level-requirement.md`. It is intended to be read *instead of* reading the source code.

---

## 1. Project Overview

- **Package name:** `ctn-stack` (imported as `ctn_stack`)
- **Purpose:** Asynchronous Python helpers for Docker CLI interactions - pulling images, checking local existence, and building images from a Dockerfile.
- **Python version:** `>= 3.14`
- **Build system:** `hatchling`
- **Test runner:** `pytest` with `pytest-asyncio`
- **Test command:** `make test` → `uv run pytest`
- **Dependencies:** `pytest`, `pytest-asyncio` (no external Docker SDK - all Docker operations go through `asyncio.create_subprocess_exec` wrapping the `docker` CLI).

---

## 2. Source Tree

```
src/ctn_stack/
├── __init__.py              # empty
├── py.typed                 # PEP 561 marker
├── container/
│   └── __init__.py          # Image, RemoteImage
└── python_shell/
    ├── __init__.py          # empty
    └── docker.py            # async Docker CLI wrappers
```

- **`script/core.py`** - example script demonstrating current usage (pull an image if it doesn't exist locally).
- **`tests/`** - currently empty; no tests exist yet.

---

## 3. Existing Classes

### 3.1 `ctn_stack.container.Image`

Base class representing any Docker image.

| Attribute | Type | Description |
|---|---|---|
| `name` | `str` | Image name (e.g. `"ubuntu"`) |
| `tag` | `str` | Image tag (e.g. `"24.04"`) |

| Method | Signature | Description |
|---|---|---|
| `get_name_tag()` | `-> str` | Returns `f"{self.name}:{self.tag}"` |
| `exists()` | `async -> bool` | Delegates to `docker.image_exists(self.get_name_tag())` |

`Image` is **not instantiable on its own** - it is meant to be subclassed. It does not define an `__init__`; subclasses are responsible for setting `self.name` and `self.tag`.

### 3.2 `ctn_stack.container.RemoteImage(Image)`

Subclass for images that can be pulled from a remote registry.

| Constructor | `__init__(self, name: str, tag: str)` |
|---|---|

| Method | Signature | Description |
|---|---|---|
| `pull()` | `async -> None` | Delegates to `docker.pull(self.get_name_tag())` |
| `exists()` | (inherited) | From `Image` |
| `get_name_tag()` | (inherited) | From `Image` |

**Current usage pattern** (from `script/core.py`):
```python
image = RemoteImage("ubuntu", "24.04")
if await image.exists():
    ...
else:
    await image.pull()
```

---

## 4. Existing Docker CLI Wrappers

All live in `ctn_stack.python_shell.docker`. Each function spawns an `asyncio.create_subprocess_exec` with `stdout` and `stderr` set to `DEVNULL`.

### 4.1 `pull(image_name: str) -> None`

- Runs: `docker pull <image_name>`
- Raises `RuntimeError` on non-zero exit.

### 4.2 `image_exists(image_name: str) -> bool`

- Runs: `docker image inspect <image_name>`
- Returns `True` if exit code is `0`, else `False`.

### 4.3 `build(dockerfile_path: Path, context_path: Path, build_args: dict[str, str] | None = None) -> None`

- Runs: `docker build -f <dockerfile_path> [--build-arg K=V ...] <context_path>`
- `build_args`, if provided, are expanded as `--build-arg` pairs.
- Raises `RuntimeError` on non-zero exit.
- **Note:** The current `build` signature does **not** accept a `tag` parameter - the image tag must be specified inside the Dockerfile via `FROM` or a separate `docker tag` step. This is a gap that the new feature may need to address.

---

## 5. What Is Missing (Gap Analysis)

1. **No class for locally-built images.** There is `Image` (abstract base) and `RemoteImage` (pullable), but nothing representing an image that is built from a Dockerfile.

2. **No concept of a "layer" or "derived image."** There is no way to describe an image as being built on top of an existing base image, parameterised by a Dockerfile and build args.

3. **No unified `ensure_exists` method.** The high-level requirement calls for an `ensure_exists` method on `Image` so that callers don't need to know whether an image is remote or local - they just await `image.ensure_exists()` and the image is guaranteed to be present locally. Currently, callers must manually check `exists()` and then call `pull()` or `build()` depending on the image type.

4. **`docker.build` does not take a `tag`.** The existing `build` helper has no mechanism to tag the resulting image. A tag must either be baked into the Dockerfile or applied afterward. The new feature will need to handle tagging the built image (e.g., via `docker tag` or by passing `-t` to `docker build`).

5. **No build-arg validation.** There is no mechanism to declare which build arguments a Dockerfile expects or to validate that the caller supplies the correct set.

---

## 6. Constraints & Design Notes

- **No Docker SDK dependency.** All Docker interactions must go through CLI subprocess calls. Any new functionality (e.g., `docker tag`, `docker build` with `-t`) should follow the same `asyncio.create_subprocess_exec` pattern.
- **Async-first.** All I/O methods are `async`. New classes should follow this convention.
- **`Image` is the common base.** Both `RemoteImage` and any new `LayeredImage` should inherit from `Image` so that `ensure_exists` can be called uniformly.
- **`ImageLayer` is a factory, not an image.** Per the high-level requirement, `ImageLayer` is *not* an `Image` subclass. It is a callable object that, when invoked with a base `Image`, produces a `LayeredImage`.
- **Build args are declared upfront.** `ImageLayer` accepts `build_arg_defs: dict[str, str | None]` - keys are arg names, values are defaults (`None` means required). Validation happens at `LayeredImage` creation or build time.

---

## 7. Files That Will Be Modified or Created

| File | Action |
|---|---|
| `src/ctn_stack/container/__init__.py` | Add `LayeredImage` class; add `ensure_exists` to `Image` and `RemoteImage` |
| `src/ctn_stack/python_shell/docker.py` | Potentially extend `build` to accept a `tag`, or add a `tag` helper |
| `src/ctn_stack/container/` (new file or same file) | Add `ImageLayer` class |
| `tests/` | Add tests for `ImageLayer`, `LayeredImage`, and `ensure_exists` |