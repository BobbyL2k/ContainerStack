# nvm, Node, pnpm, and ai-agent Layer Notes

This documents the investigation into the `nvm-node`, `pnpm`, and `ai-agent` image failures and the final layer design.

## Context

The image chain is:

```text
ubuntu:24.04
  -> ctn-stack/common
  -> ctn-stack/ubuntu-user
  -> ctn-stack/nvm
  -> ctn-stack/nvm-node
  -> ctn-stack/pnpm
  -> ctn-stack/ai-agent
```

The main images tested during the investigation were:

```text
ctn-stack/pnpm:11.2.2-node26_2-usr-cmn-ubuntu24
ctn-stack/ai-agent:latest
```

## Failure 1: nvm-node build wrote under /bin

Running:

```bash
uv run script/core.py
```

failed while building `layer/nvm-node/Dockerfile`:

```text
mkdir: cannot create directory '/bin/alias': Permission denied
mkdir: cannot create directory '/bin/.cache': Permission denied
creating directory /bin/.cache/bin/node-v26.2.0-linux-x64/files failed
curl: (23) Failure writing output to destination
```

The failing build step was effectively:

```dockerfile
RUN . ~/.nvm/nvm.sh && \
    nvm install $NODE_VERSION
```

### Investigation

The `ubuntu-user` layer switched to `USER ubuntu`, but did not persist `HOME`:

```dockerfile
USER ubuntu
RUN mkdir /home/ubuntu/ws
WORKDIR /home/ubuntu/ws
```

`nvm` depends on `HOME` and `NVM_DIR`. In Docker builds, relying on shell/user inference is fragile after `USER ubuntu`. Sourcing `~/.nvm/nvm.sh` through `/bin/sh` also inferred an incorrect `NVM_DIR` in one check:

```text
HOME=/home/ubuntu NVM_DIR=/home/ubuntu/ws
```

Running the same source through bash produced the expected result:

```text
HOME=/home/ubuntu NVM_DIR=/home/ubuntu/.nvm
```

### Solution

Persist `HOME` in the user layer:

```dockerfile
USER ubuntu
ENV HOME=/home/ubuntu
```

Persist both `HOME` and `NVM_DIR` in the nvm layer:

```dockerfile
ENV HOME=/home/ubuntu
ENV NVM_DIR=/home/ubuntu/.nvm
```

Use bash and the explicit nvm path in the node layer:

```dockerfile
ENV HOME=/home/ubuntu
ENV NVM_DIR=/home/ubuntu/.nvm
ENV PATH=${NVM_DIR}/versions/node/v${NODE_VERSION}/bin:${PATH}

SHELL ["/bin/bash", "-lc"]

RUN . "${NVM_DIR}/nvm.sh" && \
    nvm install "${NODE_VERSION}" && \
    nvm alias default "${NODE_VERSION}"
```

This made `nvm install` write under `/home/ubuntu/.nvm` and exposed Node/npm on `PATH` for downstream layers.

## Failure 2: pnpm existed but was not on PATH

The first pnpm layer used the official installer:

```dockerfile
RUN curl -fsSL https://get.pnpm.io/install.sh | env PNPM_VERSION=${PNPM_VERSION} SHELL=/bin/bash sh -
```

The installer created:

```text
/home/ubuntu/.local/share/pnpm/bin/pnpm
```

but only amended `/home/ubuntu/.bashrc`:

```text
export PNPM_HOME="/home/ubuntu/.local/share/pnpm"
export PATH="$PNPM_HOME/bin:$PATH"
```

Non-interactive container commands do not load `.bashrc`, so `pnpm` was not available from `PATH`.

### Intermediate fix

The first fix persisted `PNPM_HOME` and `PATH` in the image:

```dockerfile
ENV PNPM_HOME=/home/ubuntu/.local/share/pnpm
ENV PATH=${PNPM_HOME}/bin:${PATH}
```

That made `pnpm --version` work in a normal container run.

## Failure 3: bind-mounting the pnpm store broke the pnpm CLI

The compose service mounted the host pnpm store into the same path used by the image:

```yaml
volumes:
  - /home/bobbyl2k/.local/share/pnpm/store:/home/ubuntu/.local/share/pnpm/store
```

After starting the container this way, running `pnpm` failed:

```text
/home/ubuntu/.local/share/pnpm/bin/pnpm: 12: exec: /home/ubuntu/.local/share/pnpm/bin/../global/v11/37-19e598b10c8/node_modules/@pnpm/exe/pnpm: not found
```

### Investigation

The installer had placed pnpm's executable shim and global package under `PNPM_HOME`:

```text
/home/ubuntu/.local/share/pnpm/bin/pnpm
/home/ubuntu/.local/share/pnpm/global/v11/.../node_modules/@pnpm/exe/pnpm
/home/ubuntu/.local/share/pnpm/store
```

pnpm's default store path is:

```text
$PNPM_HOME/store, if PNPM_HOME is set
```

So the image had coupled two different concerns under the same parent directory:

```text
/home/ubuntu/.local/share/pnpm/bin      # pnpm executable shims
/home/ubuntu/.local/share/pnpm/global   # pnpm global install metadata
/home/ubuntu/.local/share/pnpm/store    # pnpm package store/cache
```

Mounting the store path made the CLI install layout fragile. The correct design is to keep pnpm's own executable installation separate from the mountable package store.

## Failure 4: ai-agent pnpm global install failed

After adding the `ai-agent` layer, `uv run script/core.py` failed while building:

```dockerfile
RUN pnpm add -g opencode-ai
```

The error was:

```text
[ERROR] The configured global bin directory "/home/ubuntu/.local/share/pnpm/bin" is not in PATH
Run "pnpm setup" to update your shell configuration.
```

### Investigation

The pnpm base image configured the store path, but did not configure pnpm's global binary directory. `pnpm add -g` requires a `globalBinDir` that exists and is on `PATH`.

The base image had:

```text
storeDir: /home/ubuntu/.cache/pnpm/store
```

but `pnpm bin -g` still failed because pnpm defaulted the global bin directory to:

```text
/home/ubuntu/.local/share/pnpm/bin
```

That directory was intentionally no longer on `PATH` after moving away from `PNPM_HOME`, so global installs failed.

Testing in a throwaway container confirmed the needed configuration:

```bash
mkdir -p /home/ubuntu/.local/bin
printf 'storeDir: /home/ubuntu/.cache/pnpm/store\nglobalBinDir: /home/ubuntu/.local/bin\n' \
  > /home/ubuntu/.config/pnpm/config.yaml
export PATH=/home/ubuntu/.local/bin:$PATH
pnpm add -g cowsay
```

With that setup, pnpm installed global command shims into `/home/ubuntu/.local/bin`. However, `opencode-ai` still did not work because its package postinstall script did not run under the pnpm global install.

## Failure 5: opencode postinstall did not run

After configuring `globalBinDir`, the `ai-agent` layer built, but running `opencode` failed at runtime:

```text
Error: opencode-ai's postinstall script was not run.
```

The installed `opencode-ai/bin/opencode.exe` file was only a placeholder shell script. Running the package postinstall manually replaced it with the real native binary:

```bash
cd /path/to/node_modules/opencode-ai
node postinstall.mjs
```

The more robust fix is to install `opencode-ai` with npm instead of pnpm. npm ran the postinstall script during installation and installed the CLI under Node's global prefix, outside the mountable pnpm store.

## Final Solution

Install pnpm via npm into Node's global prefix. Configure pnpm's package store and global binary directory separately:

```dockerfile
ARG BASE_IMAGE=dev_base:latest
FROM ${BASE_IMAGE}

ARG PNPM_VERSION=11.2.2

ENV PNPM_STORE_DIR=/home/ubuntu/.cache/pnpm/store
ENV PNPM_GLOBAL_BIN_DIR=/home/ubuntu/.local/bin
ENV PATH=${PNPM_GLOBAL_BIN_DIR}:${PATH}

RUN npm install --global "pnpm@${PNPM_VERSION}" && \
    mkdir -p "${PNPM_STORE_DIR}" "${PNPM_GLOBAL_BIN_DIR}" /home/ubuntu/.config/pnpm && \
    printf 'storeDir: %s\nglobalBinDir: %s\n' \
        "${PNPM_STORE_DIR}" \
        "${PNPM_GLOBAL_BIN_DIR}" \
        > /home/ubuntu/.config/pnpm/config.yaml
```

The `ai-agent` layer installs `opencode-ai` with npm, not pnpm:

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

RUN npm install --global opencode-ai
```

This results in:

```text
pnpm executable:       /home/ubuntu/.nvm/versions/node/v26.2.0/bin/pnpm
pnpm store:            /home/ubuntu/.cache/pnpm/store/v11
pnpm global bin dir:   /home/ubuntu/.local/bin
ai-agent CLI shim:     /home/ubuntu/.nvm/versions/node/v26.2.0/bin/opencode
ai-agent real binary:  /home/ubuntu/.nvm/versions/node/v26.2.0/lib/node_modules/opencode-ai/bin/opencode.exe
```

The pnpm CLI is no longer inside the mountable store directory. The `opencode` CLI is also independent of the pnpm store, so mounting `/home/ubuntu/.cache/pnpm/store` does not hide its package files.

## Recommended compose mount

Mount the host pnpm store to the configured cache directory, not under `PNPM_HOME`:

```yaml
services:
  ubuntu:
    image: ctn-stack/pnpm:11.2.2-node26_2-usr-cmn-ubuntu24
    container_name: python-pg
    command: tail -f /dev/null
    volumes:
      - /home/bobbyl2k/.cache/uv:/home/ubuntu/.cache/uv
      - /home/bobbyl2k/.local/share/pnpm/store:/home/ubuntu/.cache/pnpm/store
```

After changing mounts or rebuilding the image, recreate the container instead of just restarting it:

```bash
docker compose down
docker compose up -d
```

## Verification commands

Build the final pnpm layer directly:

```bash
docker build \
  -f layer/pnpm/Dockerfile \
  -t ctn-stack/pnpm:11.2.2-node26_2-usr-cmn-ubuntu24 \
  --build-arg BASE_IMAGE=ctn-stack/nvm-node:26.2.0-usr-cmn-ubuntu24 \
  --build-arg PNPM_VERSION=11.2.2 \
  layer/pnpm
```

Run the full image build:

```bash
uv run script/core.py
```

Verify pnpm works without mounts:

```bash
docker run --rm \
  ctn-stack/pnpm:11.2.2-node26_2-usr-cmn-ubuntu24 \
  bash -lc 'command -v pnpm; pnpm --version; pnpm bin -g; pnpm store path'
```

Expected output:

```text
/home/ubuntu/.nvm/versions/node/v26.2.0/bin/pnpm
11.2.2
/home/ubuntu/.local/bin
/home/ubuntu/.cache/pnpm/store/v11
```

Verify pnpm works with the recommended store mount:

```bash
docker run --rm \
  -v /home/bobbyl2k/.local/share/pnpm/store:/home/ubuntu/.cache/pnpm/store \
  ctn-stack/pnpm:11.2.2-node26_2-usr-cmn-ubuntu24 \
  bash -lc 'command -v pnpm; pnpm --version; pnpm bin -g; pnpm store path'
```

Expected output remains:

```text
/home/ubuntu/.nvm/versions/node/v26.2.0/bin/pnpm
11.2.2
/home/ubuntu/.local/bin
/home/ubuntu/.cache/pnpm/store/v11
```

Verify the `ai-agent` image has the CLI on `PATH`:

```bash
docker run --rm \
  ctn-stack/ai-agent:latest \
  bash -lc 'command -v opencode; opencode --version; readlink -f $(command -v opencode)'
```

Expected output includes:

```text
/home/ubuntu/.nvm/versions/node/v26.2.0/bin/opencode
1.15.10
/home/ubuntu/.nvm/versions/node/v26.2.0/lib/node_modules/opencode-ai/bin/opencode.exe
```

## Rule of thumb

Do not mount over directories that contain installed tools, global package metadata, or command shims. Mount only the cache/store directory that the tool is configured to use.

For pnpm in this image:

```text
Safe to mount:     /home/ubuntu/.cache/pnpm/store
Do not depend on:  /home/ubuntu/.local/share/pnpm/store
Do not mount over: /home/ubuntu/.nvm, /home/ubuntu/.local/bin, or /home/ubuntu/.local/share/pnpm
```
