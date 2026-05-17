# Proposal: Image Layer Feature

## 1. Goal

Enable scripts to describe a Docker image as being built from a Dockerfile layered on top of an existing base image, with validated build arguments and a unified `ensure_exists` interface across all image types.

```python
base_image = RemoteImage("ubuntu", "24.04")

layer = ImageLayer(
    dockerfile=Path("Dockerfile.worker"),
    name="myapp",
    tag="latest",
    build_arg_defs={"WORKER_COUNT": "4", "API_KEY": None},  # API_KEY is required
)

derived_image = layer(base_image, build_args={"API_KEY": "secret"})
await derived_image.ensure_exists()  # pulls base if needed, builds derived if needed
```

The framework automatically injects `--build-arg BASE_IMAGE=ubuntu:24.04` into the build command. The Dockerfile must declare and consume this arg (see [Section 2.6](#26-base-image-convention)).

---

## 2. Design Decisions

### 2.1 Class Hierarchy

```
Image (abstract base)
├── RemoteImage  → ensure_exists() pulls if missing
└── LayeredImage → ensure_exists() builds if missing (and ensures base first)
```

`ImageLayer` is **not** an `Image`. It is a factory (callable) that produces `LayeredImage` instances.

### 2.2 Context Path Derivation

The build context is derived automatically from the Dockerfile path: `context_path = dockerfile.parent`. This avoids requiring callers to pass both paths. If needed later, an optional `context` parameter can be added.

### 2.3 Tagging Strategy

The existing `docker.build` does not accept a tag. We will extend it with an optional `tag: str | None = None` parameter that adds `-t <tag>` to the `docker build` command. This is cleaner than a separate `docker tag` step.

### 2.4 Build-Arg Validation

Validation happens at `LayeredImage` creation time (i.e. inside `ImageLayer.__call__`):

- **Missing required args** (those with `None` default and not supplied) → `ValueError`.
- **Extra args** (supplied but not declared in `build_arg_defs`) → `ValueError`.
- Defaults are merged in: final build args = defaults overridden by caller-supplied values.
- `BASE_IMAGE` is **excluded** from this validation - it is injected automatically by the framework.

### 2.5 `ensure_exists` Contract

| Class | `ensure_exists()` behaviour |
|---|---|
| `Image` (base) | Abstract - subclasses must implement |
| `RemoteImage` | If not present locally, `pull()` |
| `LayeredImage` | If not present locally, ensure base exists first (`await base.ensure_exists()`), then `build()` |

### 2.6 Base Image Convention

Every Dockerfile used with `ImageLayer` **must** declare a `BASE_IMAGE` build arg and reference it in the `FROM` line. This is the mechanism by which the framework injects the actual base image at build time.

The framework automatically passes `--build-arg BASE_IMAGE=<name>:<tag>` when building, derived from the `base` image passed to `ImageLayer.__call__`. Callers do not need to supply `BASE_IMAGE` in `build_args` - it is injected automatically and excluded from validation against `build_arg_defs`.

#### Sample Valid Dockerfile

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG WORKER_COUNT=4
ENV WORKER_COUNT=${WORKER_COUNT}

COPY ./app /app
WORKDIR /app
CMD ["python", "-m", "app.worker"]
```

Key rules:
1. `ARG BASE_IMAGE` must appear **before** the `FROM` line (Docker syntax requirement).
2. `FROM ${BASE_IMAGE}` must be the **first** `FROM` in the file (no multi-stage builds).
3. Any additional `ARG` declarations correspond to entries in `build_arg_defs`.

---

## 3. API Specification

### 3.1 `Image` (modified)

```python
class Image:
    name: str
    tag: str

    def get_name_tag(self) -> str: ...

    async def exists(self) -> bool: ...

    async def ensure_exists(self) -> None:
        """Ensure the image is present locally. Subclasses must override."""
        raise NotImplementedError
```

### 3.2 `RemoteImage` (modified)

```python
class RemoteImage(Image):
    def __init__(self, name: str, tag: str): ...
    async def pull(self) -> None: ...

    async def ensure_exists(self) -> None:
        if not await self.exists():
            await self.pull()
```

### 3.3 `ImageLayer` (new)

```python
class ImageLayer:
    """Factory that produces LayeredImage instances on top of a base Image."""

    def __init__(
        self,
        dockerfile: Path,
        name: str,
        tag: str,
        build_arg_defs: dict[str, str | None] | None = None,
    ) -> None:
        """
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

    def __call__(
        self,
        base: Image,
        *,
        name: str | None = None,
        tag: str | None = None,
        build_args: dict[str, str] | None = None,
    ) -> LayeredImage:
        """
        Produce a LayeredImage layered on top of `base`.

        Args:
            base: The base Image to layer on top of.
            name: Override the default image name.
            tag: Override the default image tag.
            build_args: Build-time arguments. Must satisfy build_arg_defs.
                        Do not include BASE_IMAGE; it is injected automatically.

        Raises:
            ValueError: If required build args are missing or extra args are provided.
        """
```

### 3.4 `LayeredImage(Image)` (new)

```python
class LayeredImage(Image):
    """An image built from a Dockerfile on top of a base image."""

    def __init__(
        self,
        base: Image,
        dockerfile: Path,
        name: str,
        tag: str,
        build_args: dict[str, str],
    ) -> None: ...

    async def build(self) -> None:
        """Build the image using `docker build`.

        Automatically injects --build-arg BASE_IMAGE=<base.get_name_tag>().
        """

    async def ensure_exists(self) -> None:
        if not await self.exists():
            await self.base.ensure_exists()
            await self.build()
```

### 3.5 `docker.build` (modified)

```python
async def build(
    dockerfile_path: Path,
    context_path: Path,
    tag: str | None = None,          # NEW
    build_args: dict[str, str] | None = None,
) -> None:
    """Build a Docker image. `tag` adds `-t <tag>` to the command."""
```

---

## 4. Implementation Plan

### Phase 1 - Extend `docker.build` with `tag` support

| File | Change |
|---|---|
| `src/ctn_stack/python_shell/docker.py` | Add `tag: str | None = None` parameter to `build()`. When provided, insert `-t <tag>` into the command before the context path. |

### Phase 2 - Add `ensure_exists` to `Image` and `RemoteImage`

| File | Change |
|---|---|
| `src/ctn_stack/container/__init__.py` | Add `ensure_exists()` to `Image` (raises `NotImplementedError`). Override in `RemoteImage` to pull if missing. |

### Phase 3 - Implement `ImageLayer` and `LayeredImage`

| File | Change |
|---|---|
| `src/ctn_stack/container/__init__.py` | Add `ImageLayer` class (factory with build-arg validation). Add `LayeredImage` class (subclass of `Image` with `build()` and `ensure_exists()`). `build()` automatically injects `BASE_IMAGE` into build args. |

### Phase 4 - Update example script

| File | Change |
|---|---|
| `script/core.py` | Demonstrate the full workflow: create a base `RemoteImage`, define an `ImageLayer`, produce a `LayeredImage`, and call `ensure_exists()`. |

### Phase 5 - Tests

| File | Change |
|---|---|
| `tests/container/test_image.py` | Test `Image.ensure_exists` raises `NotImplementedError`. |
| `tests/container/test_remote_image.py` | Test `RemoteImage.ensure_exists` pulls when missing, does nothing when present. |
| `tests/container/test_image_layer.py` | Test `ImageLayer` build-arg validation (missing required, extra args, defaults). Test `BASE_IMAGE` is excluded from validation. Test `LayeredImage.build` delegates correctly with `BASE_IMAGE` injected. Test `LayeredImage.ensure_exists` ensures base first. |

---

## 5. Risks & Open Questions

| Risk / Question | Mitigation |
|---|---|
| **Dockerfile convention enforcement.** The library cannot parse or validate the Dockerfile to confirm `ARG BASE_IMAGE` / `FROM ${BASE_IMAGE}` is present. | Document the convention clearly. At runtime, a missing `ARG` in the Dockerfile will cause `docker build` to fail with a clear error. |
| **Build context scoping.** Deriving context from `dockerfile.parent` may not always be correct. | Acceptable for v1. An optional `context: Path` parameter can be added to `ImageLayer.__init__` later. |
| **Multi-stage builds.** By convention, Dockerfiles must not use multi-stage builds. | Document as a hard constraint. Multi-stage support can be added later with a different abstraction. |
| **Large build outputs suppressed.** Current `docker.build` discards stdout/stderr. | Consistent with existing behaviour. Can be revisited if debugging support is needed. |

---

## 6. Summary of Files to Create or Modify

| File | Action |
|---|---|
| `src/ctn_stack/python_shell/docker.py` | Modify `build()` to accept `tag` |
| `src/ctn_stack/container/__init__.py` | Add `ensure_exists` to `Image`/`RemoteImage`; add `ImageLayer` and `LayeredImage` |
| `script/core.py` | Update example to demonstrate image layering |
| `tests/container/test_image.py` | New - tests for `Image.ensure_exists` |
| `tests/container/test_remote_image.py` | New - tests for `RemoteImage.ensure_exists` |
| `tests/container/test_image_layer.py` | New - tests for `ImageLayer` and `LayeredImage` |
