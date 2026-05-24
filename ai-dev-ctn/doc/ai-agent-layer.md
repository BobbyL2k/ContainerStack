# ai-agent Layer Notes

The `ai-agent` layer installs coding CLI packages on top of the Node/pnpm image: `opencode-ai`, `@openai/codex`, and `@earendil-works/pi-coding-agent`.

## Layer

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG OPENCODE_VERSION=1.15.10
ARG CODEX_VERSION=0.133.0
ARG PI_VERSION=0.75.5

RUN npm install --global \
    "opencode-ai@${OPENCODE_VERSION}" \
    "@openai/codex@${CODEX_VERSION}" && \
    npm install --global --ignore-scripts \
    "@earendil-works/pi-coding-agent@${PI_VERSION}"
```

This intentionally uses `npm`, not `pnpm`. All CLI versions are configurable through Docker build args.

## Why not pnpm

The first implementation used:

```dockerfile
RUN pnpm add -g opencode-ai
```

That failed in two separate ways.

## Failure 1: pnpm global bin directory

`pnpm add -g opencode-ai` initially failed during image build:

```text
[ERROR] The configured global bin directory "/home/ubuntu/.local/share/pnpm/bin" is not in PATH
Run "pnpm setup" to update your shell configuration.
```

This was because pnpm global installs require a configured `globalBinDir` that exists and is on `PATH`.

The pnpm layer now configures this for general pnpm global-install support:

```yaml
storeDir: /home/ubuntu/.cache/pnpm/store
globalBinDir: /home/ubuntu/.local/bin
```

and exports:

```dockerfile
ENV PNPM_GLOBAL_BIN_DIR=/home/ubuntu/.local/bin
ENV PATH=${PNPM_GLOBAL_BIN_DIR}:${PATH}
```

That fixes pnpm global binary placement, but it does not make pnpm the right installer for `opencode-ai`.

## Failure 2: opencode-ai postinstall did not run

After fixing pnpm's global bin directory, the image built, but the CLI failed at runtime:

```text
Error: opencode-ai's postinstall script was not run.

This occurs when using --ignore-scripts during installation, or when using a
package manager like pnpm that does not run postinstall scripts by default.
```

The installed executable was only a placeholder script:

```text
opencode-ai/bin/opencode.exe
```

That placeholder is replaced by the real platform-specific binary only when `opencode-ai`'s postinstall script runs:

```bash
node postinstall.mjs
```

Manually running the postinstall script in a throwaway container replaced the placeholder with the real native binary and made `opencode --version` work.

## Failure 3: pnpm store mounts can hide pnpm-installed package files

This project mounts the pnpm package store into containers for caching:

```yaml
volumes:
  - /home/bobbyl2k/.local/share/pnpm/store:/home/ubuntu/.cache/pnpm/store
```

pnpm global installs are symlink-heavy. Package payloads are stored under the pnpm store, and global project entries point back into that store.

That is acceptable for normal dependency cache use, but it is a poor fit for installing a required system-level CLI in an image. If the runtime bind mount replaces the store, it can hide package files that were installed during image build.

For a base CLI layer, the executable should live outside the cache mount.

## Final approach

Use npm for image-level CLIs:

```dockerfile
ARG OPENCODE_VERSION=1.15.10
ARG CODEX_VERSION=0.133.0
ARG PI_VERSION=0.75.5

RUN npm install --global \
    "opencode-ai@${OPENCODE_VERSION}" \
    "@openai/codex@${CODEX_VERSION}" && \
    npm install --global --ignore-scripts \
    "@earendil-works/pi-coding-agent@${PI_VERSION}"
```

npm runs package postinstall scripts during image build and installs the CLIs under Node's global prefix:

```text
opencode shim:    /home/ubuntu/.nvm/versions/node/v26.2.0/bin/opencode
opencode binary:  /home/ubuntu/.nvm/versions/node/v26.2.0/lib/node_modules/opencode-ai/bin/opencode.exe
codex shim:       /home/ubuntu/.nvm/versions/node/v26.2.0/bin/codex
pi shim:          /home/ubuntu/.nvm/versions/node/v26.2.0/bin/pi
```

This keeps `opencode`, `codex`, and `pi` independent of the pnpm store cache mount.

## Verification

Build through the core script:

```bash
uv run script/core.py
```

Verify the image:

```bash
docker run --rm \
  ctn-stack/ai-agent:latest \
  bash -lc 'command -v opencode; opencode --version; command -v codex; codex --version; command -v pi; pi --version; npm list -g --depth 0'
```

Expected output:

```text
/home/ubuntu/.nvm/versions/node/v26.2.0/bin/opencode
1.15.10
/home/ubuntu/.nvm/versions/node/v26.2.0/bin/codex
codex-cli 0.133.0
/home/ubuntu/.nvm/versions/node/v26.2.0/bin/pi
0.75.5
```

Verify it still works with the pnpm store mounted:

```bash
docker run --rm \
  -v /home/bobbyl2k/.local/share/pnpm/store:/home/ubuntu/.cache/pnpm/store \
  ctn-stack/ai-agent:latest \
  bash -lc 'opencode --version; codex --version; pi --version; pnpm store path'
```

Expected output includes:

```text
1.15.10
codex-cli 0.133.0
0.75.5
/home/ubuntu/.cache/pnpm/store/v11
```

## Rule

Use pnpm for project dependency management and cacheable package installs.

Use npm for image-level global CLIs when the package depends on postinstall behavior or must remain independent of the pnpm store mount. Pin versions with `OPENCODE_VERSION`, `CODEX_VERSION`, and `PI_VERSION` build args. Pi is installed with `--ignore-scripts` because that is the required install mode for `@earendil-works/pi-coding-agent`.
