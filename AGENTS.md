# ContainerStack — Agent Instructions

## Repo at a Glance

Two Python packages under a single git repo. `ctn-stack` is a pure async library for building layered Docker images via the `docker` CLI. `ai-dev-ctn` is the build tool that assembles image chains (Ubuntu → common → user → uv → python → nvm → node → pnpm → ai-agent) using the ctn-stack library.

```
ContainerStack/
├── ctn-stack/          # Pure library — Image, RemoteImage, LayeredImage, ImageLayer
│   ├── src/ctn_stack/  # container/, python_shell/docker.py
│   └── tests/          # pytest + pytest-asyncio
├── ai-dev-ctn/         # Build tool — layer classes + Dockerfiles + orchestration
│   ├── src/ai_dev_ctn/build.py   # All layer classes + build_uv_python_image() + build_ai_agent_image()
│   ├── layer/          # 8 Dockerfiles: install-common, ubuntu-user, uv, uv-python, nvm, nvm-node, pnpm, ai-agent
│   └── doc/            # Layer design notes (ai-agent-layer.md, nvm-node-pnpm-layer.md, etc.)
└── plan/               # Executed refactor plans
```

## Container Environment

This container was built by `ai-dev-ctn`'s `ai-agent` layer. Available tools:

| Tool | Version | Source |
|------|---------|--------|
| Python | 3.14 | uv-managed |
| uv | 0.11.16 | version manager |
| Node.js | 26.2.0 | nvm |
| pnpm | 11.2.2 | global via npm |
| ruff | — | formatter + linter |
| ty | — | type checker |
| pytest | 9.0.3 | test runner (with pytest-asyncio) |
| git | 2.43.0 | — |

All CLIs live under `/home/ubuntu/.nvm/versions/node/v26.2.0/bin/`. uv is at `/home/ubuntu/.local/bin/uv`.

## Commands

### ctn-stack (library)

Run from `ctn-stack/`:
- `make sync` — sync dependencies (creates/updates `.venv`)
- `make check` — format check, lint, type-check, tests
- `make check-autofix` — auto-fix format/lint, type-check, tests
- `make check-type` — `ty check` only
- `make test` — `pytest` only

### ai-dev-ctn (build tool)

Run from `ai-dev-ctn/`:
- `make sync` — sync dependencies (editable dep on `../ctn-stack`)
- `make check` — format check, lint, type-check (no tests)
- `make check-autofix` — auto-fix format/lint, type-check
- `make check-type` — `ty check` only
- `make build` — `uv run python -m ai_dev_ctn.build` — builds all Docker images
- `make remove-image` — remove all `ctn-stack/*` Docker images

### Per-file / targeted

```bash
# Single test file
cd ctn-stack && uv run pytest tests/container/test_image_layer.py -v

# Lint only
uv run ruff check src/

# Format check only
uv run ruff format --diff
```

## Architecture Rules

- **Dockerfiles must declare `ARG BASE_IMAGE` before `FROM`.** The framework injects the base image's `name:tag` as a build arg.
- **`ImageLayer` is a factory, not an image.** Call it with a base `Image` to produce a `LayeredImage`.
- **`UvPythonLayer` and `NvmNodeLayer` validate base chains.** They check that the base image's `abvr_tag` chain contains the expected version manager tag (`uv*` or `nvm*`). Applying them to the wrong base raises `ValueError`.
- **Tag chaining:** each image has an `abvr_tag` (e.g., `py3_14`, `usr`, `ubuntu24`) and inherits the base chain as `prev_abvr_tags`. `get_name_tag()` produces composite tags like `ctn-stack/uv-python:3.14.5-usr-cmn-ubuntu24`.
- **Version manager tags are pruned from the chain.** `UvPythonLayer` strips `uv*` from `prev_abvr_tags`; `NvmNodeLayer` strips `nvm*`. This keeps tags concise.
- **Invalidation propagation:** calling `mark_invalid()` on a base image cascades to all derived `LayeredImage` instances. `LayeredImage.is_invalid()` checks both self and base.
- **All I/O is async.** The `docker` module uses `asyncio.create_subprocess_exec`. No Docker SDK dependency — wraps the CLI directly.
- **`build.py` must be run from `ai-dev-ctn/` root.** Dockerfile paths are relative (`Path("layer/...")`).

## Gotchas

- **`ai-dev-ctn` depends on `ctn-stack` as an editable path dep.** `pyproject.toml` has `[tool.uv.sources] ctn-stack = { path = "../ctn-stack", editable = true }`. Changes to `ctn-stack` source are reflected immediately.
- **`common_image.mark_invalid()` is called in both build chains.** This forces a rebuild of the common layer and everything downstream. If you remove it, stale images may be reused.
- **AI agent CLIs are installed via npm, not pnpm.** `opencode-ai` requires postinstall scripts that pnpm skips by default. See `ai-dev-ctn/doc/ai-agent-layer.md` for the full rationale.
- **`pi` (`@earendil-works/pi-coding-agent`) is installed with `--ignore-scripts`.** This is intentional and required for that package.
- **`ctn-stack` has no `remove-image` target.** Image lifecycle management lives in `ai-dev-ctn/Makefile`.
- **Both packages require Python >= 3.14.** Enforced in `pyproject.toml` and `ctn-stack/.python-version`.
- **ruff config:** both packages use `extend-select = ["I"]` (isort rules). No other ruff customization.

## Testing

- `ctn-stack` tests live under `tests/container/`: `test_image.py`, `test_remote_image.py`, `test_image_layer.py`.
- Tests use `pytest-asyncio` — test functions are `async def`.
- `ai-dev-ctn` has no tests. Correctness is verified via `make check` (lint + type-check).
- Tests do NOT require Docker. They test the Python abstractions, not the docker CLI wrappers.

## Git

- Remote: `git@github.com:BobbyL2k/ContainerStack.git`
- `plan/` contains executed refactor plans. `plan/001-refactor-ai-ctn.md` documents the split into two packages.
