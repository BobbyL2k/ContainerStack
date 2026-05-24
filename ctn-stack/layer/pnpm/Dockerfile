ARG BASE_IMAGE=dev_base:latest
FROM ${BASE_IMAGE}

ARG PNPM_VERSION=11.2.2

ENV PNPM_STORE_DIR=/home/ubuntu/.cache/pnpm/store

RUN npm install --global "pnpm@${PNPM_VERSION}" && \
    mkdir -p "${PNPM_STORE_DIR}" /home/ubuntu/.config/pnpm && \
    printf 'storeDir: %s\n' "${PNPM_STORE_DIR}" > /home/ubuntu/.config/pnpm/config.yaml
