# AGENTS-global.md — Container Environment

You are running inside an AI development container. The following tools are available system-wide.

## Runtime

| Tool | Version | Path |
|------|---------|------|
| Python | 3.14 | uv-managed |
| uv | 0.11.16 | `/home/ubuntu/.local/bin/uv` |
| Node.js | 26.2.0 | `/home/ubuntu/.nvm/versions/node/v26.2.0/bin/node` |
| npm | — | `/home/ubuntu/.nvm/versions/node/v26.2.0/bin/npm` |
| npx | — | `/home/ubuntu/.nvm/versions/node/v26.2.0/bin/npx` |
| pnpm | 11.2.2 | `/home/ubuntu/.nvm/versions/node/v26.2.0/bin/pnpm` |
| git | 2.43.0 | `/usr/bin/git` |
| make | — | `/usr/bin/make` |

All Node-based CLIs live under `/home/ubuntu/.nvm/versions/node/v26.2.0/bin/`.

## Notes

- **uv** manages Python and dependencies. Use `uv sync` and `uv run` inside project directories.
- **pnpm store** may be bind-mounted at runtime.
