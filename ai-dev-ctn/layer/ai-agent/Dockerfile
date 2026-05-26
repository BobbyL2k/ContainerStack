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

RUN npx playwright install chromium
