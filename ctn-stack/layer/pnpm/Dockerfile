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
